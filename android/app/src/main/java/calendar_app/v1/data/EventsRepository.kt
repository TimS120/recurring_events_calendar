package calendar_app.v1.data

import calendar_app.v1.data.local.EventDao
import calendar_app.v1.data.local.EventEntity
import calendar_app.v1.data.local.EventHistoryEntity
import calendar_app.v1.data.local.EventWithHistoryEntity
import calendar_app.v1.data.local.PendingChangeDao
import calendar_app.v1.data.local.PendingChangeEntity
import calendar_app.v1.data.local.PendingChangeType
import calendar_app.v1.data.local.PendingChangeType.CREATE
import calendar_app.v1.data.local.PendingChangeType.DELETE
import calendar_app.v1.data.local.PendingChangeType.MARK_DONE
import calendar_app.v1.data.local.PendingChangeType.UPDATE
import calendar_app.v1.data.local.RecurringEventsDatabase
import calendar_app.v1.data.local.toModel
import calendar_app.v1.data.network.EventsApiClient
import calendar_app.v1.data.network.EventsApiClient.ApiException
import calendar_app.v1.data.network.MdnsEndpoint
import calendar_app.v1.model.FrequencyUnit
import calendar_app.v1.model.RecurringEvent
import calendar_app.v1.model.addFrequency
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.time.LocalDate

class EventsRepository(
    database: RecurringEventsDatabase,
    private val apiClient: EventsApiClient
) {

    private val eventDao: EventDao = database.eventDao()
    private val pendingDao: PendingChangeDao = database.pendingChangeDao()

    val eventsFlow: Flow<List<RecurringEvent>> =
        eventDao.observeEvents().map { items -> items.map(EventWithHistoryEntity::toModel) }

    suspend fun saveEventLocally(
        inputId: Int?,
        name: String,
        tag: String?,
        details: String?,
        dueDate: LocalDate,
        frequencyValue: Int,
        frequencyUnit: FrequencyUnit,
        generateLocalId: () -> Int
    ) = withContext(Dispatchers.IO) {
        val eventId = inputId ?: generateLocalId()
        val now = System.currentTimeMillis()
        val normalizedTag = tag?.trim()?.takeIf { it.isNotEmpty() }
        val normalizedDetails = details?.trim()?.takeIf { it.isNotEmpty() }
        val entity = eventDao.getEventById(eventId)?.copy(
            name = name,
            tag = normalizedTag,
            details = normalizedDetails,
            dueDate = dueDate,
            frequencyValue = frequencyValue,
            frequencyUnit = frequencyUnit.apiValue,
            isOverdue = dueDate.isBefore(LocalDate.now()) || dueDate == LocalDate.now(),
            updatedAtMillis = now,
            dirty = true,
            deleted = false
        ) ?: EventEntity(
            id = eventId,
            name = name,
            tag = normalizedTag,
            details = normalizedDetails,
            frequencyValue = frequencyValue,
            frequencyUnit = frequencyUnit.apiValue,
            dueDate = dueDate,
            lastDone = null,
            isOverdue = dueDate.isBefore(LocalDate.now()) || dueDate == LocalDate.now(),
            createdAtMillis = now,
            updatedAtMillis = now,
            dirty = true,
            deleted = false
        )
        eventDao.upsertEvent(entity)
        val payload = JSONObject().apply {
            put("name", name)
            if (normalizedTag == null) {
                put("tag", JSONObject.NULL)
            } else {
                put("tag", normalizedTag)
            }
            if (normalizedDetails == null) {
                put("details", JSONObject.NULL)
            } else {
                put("details", normalizedDetails)
            }
            put("due_date", dueDate.toString())
            put("frequency_value", frequencyValue)
            put("frequency_unit", frequencyUnit.apiValue)
        }
        val changeType = if (inputId == null || eventId < 0) CREATE else UPDATE
        pendingDao.deleteByEventAndType(eventId, changeType)
        pendingDao.insert(
            PendingChangeEntity(
                eventId = eventId,
                changeType = changeType,
                payload = payload.toString()
            )
        )
        Unit
    }

    suspend fun deleteEventLocally(eventId: Int) = withContext(Dispatchers.IO) {
        val entity = eventDao.getEventById(eventId)
        if (entity != null) {
            eventDao.upsertEvent(entity.copy(deleted = true, dirty = true, updatedAtMillis = System.currentTimeMillis()))
        }
        pendingDao.deleteByEventAndType(eventId, DELETE)
        pendingDao.insert(PendingChangeEntity(eventId = eventId, changeType = DELETE, payload = null))
    }

    suspend fun markDoneLocally(eventId: Int, doneDate: LocalDate = LocalDate.now()) = withContext(Dispatchers.IO) {
        val entity = eventDao.getEventById(eventId) ?: return@withContext
        val unit = FrequencyUnit.fromApi(entity.frequencyUnit)
        val newDue = addFrequency(doneDate, entity.frequencyValue, unit)
        val updated = entity.copy(
            lastDone = doneDate,
            dueDate = newDue,
            isOverdue = newDue.isBefore(LocalDate.now()) || newDue == LocalDate.now(),
            updatedAtMillis = System.currentTimeMillis(),
            dirty = true
        )
        eventDao.upsertEvent(updated)
        eventDao.upsertHistories(
            listOf(
                EventHistoryEntity(
                    eventId = eventId,
                    action = "done",
                    actionDate = doneDate,
                    note = null
                )
            )
        )
        val payload = JSONObject().apply { put("done_date", doneDate.toString()) }
        pendingDao.deleteByEventAndType(eventId, MARK_DONE)
        pendingDao.insert(PendingChangeEntity(eventId = eventId, changeType = MARK_DONE, payload = payload.toString()))
    }

    suspend fun sync(
        token: String,
        manualEndpoint: MdnsEndpoint?,
        historyLimit: Int
    ): SyncResult = withContext(Dispatchers.IO) {
        val pending = pendingDao.getPendingChanges()
        val appliedIds = mutableListOf<Long>()
        val idRemap = mutableMapOf<Int, Int>()
        pending.forEach { change ->
            val currentEventId = idRemap[change.eventId] ?: change.eventId
            try {
                val result = applyPendingChange(change, currentEventId, token, manualEndpoint)
                if (result?.newRemoteId != null && result.newRemoteId != currentEventId) {
                    idRemap[change.eventId] = result.newRemoteId
                    pendingDao.retargetEvent(change.eventId, result.newRemoteId)
                }
                appliedIds += change.id
            } catch (ex: Exception) {
                // stop on first failure to preserve ordering
                return@withContext SyncResult.Failure(ex)
            }
        }
        if (appliedIds.isNotEmpty()) {
            pendingDao.deleteByIds(appliedIds)
        }
        return@withContext try {
            val bundle = apiClient.fetchEvents(token, manualEndpoint, historyLimit)
            storeSnapshot(bundle.events)
            SyncResult.Success(
                endpoint = bundle.endpoint,
                remoteCount = bundle.events.size,
                pushedChanges = appliedIds.size
            )
        } catch (ex: Exception) {
            SyncResult.Failure(ex)
        }
    }

    private suspend fun applyPendingChange(
        originalChange: PendingChangeEntity,
        currentEventId: Int,
        token: String,
        manualEndpoint: MdnsEndpoint?
    ): PendingApplyResult? {
        return when (originalChange.changeType) {
            CREATE -> {
                val payload = originalChange.payload?.let(::JSONObject) ?: return null
                val name = payload.getString("name")
                val tag = payload.optStringOrNullCompat("tag")
                val details = payload.optStringOrNullCompat("details")
                val dueDate = LocalDate.parse(payload.getString("due_date"))
                val freqValue = payload.getInt("frequency_value")
                val unit = FrequencyUnit.fromApi(payload.getString("frequency_unit"))
                val created = apiClient.createEvent(token, manualEndpoint, name, tag, details, dueDate, freqValue, unit)
                if (currentEventId != created.id) {
                    eventDao.replaceEventId(currentEventId, created.id)
                    eventDao.replaceHistoryEventId(currentEventId, created.id)
                }
                persistRemoteEvent(created)
                PendingApplyResult(newRemoteId = created.id)
            }

            UPDATE -> {
                val payload = originalChange.payload?.let(::JSONObject) ?: return null
                val name = payload.getString("name")
                val tag = payload.optStringOrNullCompat("tag")
                val details = payload.optStringOrNullCompat("details")
                val dueDate = LocalDate.parse(payload.getString("due_date"))
                val freqValue = payload.getInt("frequency_value")
                val unit = FrequencyUnit.fromApi(payload.getString("frequency_unit"))
                return try {
                    val updated =
                        apiClient.updateEvent(
                            token,
                            manualEndpoint,
                            currentEventId,
                            name,
                            tag,
                            details,
                            dueDate,
                            freqValue,
                            unit,
                        )
                    persistRemoteEvent(updated)
                    null
                } catch (ex: ApiException) {
                    if (ex.code == 404) {
                        markDeletedLocally(currentEventId)
                        null
                    } else {
                        throw ex
                    }
                }
            }

            DELETE -> {
                return try {
                    apiClient.deleteEvent(token, manualEndpoint, currentEventId)
                    markDeletedLocally(currentEventId)
                    null
                } catch (ex: ApiException) {
                    if (ex.code == 404) {
                        markDeletedLocally(currentEventId)
                        null
                    } else {
                        throw ex
                    }
                }
            }

            MARK_DONE -> {
                val payload = originalChange.payload?.let(::JSONObject)
                val doneDate = payload?.optString("done_date")?.takeIf { it.isNotBlank() }?.let(LocalDate::parse)
                return try {
                    val updated = apiClient.markDone(token, manualEndpoint, currentEventId)
                    persistRemoteEvent(updated)
                    null
                } catch (ex: ApiException) {
                    if (ex.code == 404) {
                        markDeletedLocally(currentEventId)
                        null
                    } else {
                        throw ex
                    }
                }
            }
        }
    }

    suspend fun storeSnapshot(events: List<RecurringEvent>) = withContext(Dispatchers.IO) {
        val pairs = events.map { event ->
            event.toEntity() to event.toHistoryEntities()
        }
        eventDao.replaceAll(pairs)
    }

    private suspend fun persistRemoteEvent(event: RecurringEvent) {
        eventDao.upsertEvent(event.toEntity())
        eventDao.deleteHistoryForEvent(event.id)
        eventDao.upsertHistories(event.toHistoryEntities())
    }

    private fun RecurringEvent.toEntity(): EventEntity =
        EventEntity(
            id = id,
            name = name,
            tag = tag,
            details = details,
            frequencyValue = frequencyValue,
            frequencyUnit = frequencyUnit.apiValue,
            dueDate = dueDate,
            lastDone = lastDone,
            isOverdue = isOverdue,
            createdAtMillis = System.currentTimeMillis(),
            updatedAtMillis = System.currentTimeMillis(),
            dirty = false,
            deleted = false
        )

    private fun RecurringEvent.toHistoryEntities(): List<EventHistoryEntity> =
        history.map {
            EventHistoryEntity(
                remoteId = it.id,
                eventId = id,
                action = it.action,
                actionDate = it.actionDate,
                note = it.note
            )
        }

    private suspend fun markDeletedLocally(eventId: Int) {
        eventDao.getEventById(eventId)?.let {
            eventDao.upsertEvent(it.copy(deleted = true, dirty = false))
        }
        eventDao.deleteHistoryForEvent(eventId)
    }

    sealed interface SyncResult {
        data class Success(
            val endpoint: MdnsEndpoint,
            val remoteCount: Int,
            val pushedChanges: Int
        ) : SyncResult

        data class Failure(val error: Throwable) : SyncResult
    }

    data class PendingApplyResult(val newRemoteId: Int?)
}

private fun JSONObject.optStringOrNullCompat(key: String): String? =
    if (has(key) && !isNull(key)) getString(key) else null
