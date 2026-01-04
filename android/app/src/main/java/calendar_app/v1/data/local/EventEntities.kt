package calendar_app.v1.data.local

import androidx.room.Embedded
import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.Relation
import calendar_app.v1.model.EventHistory
import calendar_app.v1.model.FrequencyUnit
import calendar_app.v1.model.RecurringEvent
import java.time.LocalDate
import kotlin.math.absoluteValue

@Entity(tableName = "events")
data class EventEntity(
    @PrimaryKey
    val id: Int,
    val name: String,
    val tag: String?,
    val details: String? = null,
    val frequencyValue: Int,
    val frequencyUnit: String,
    val dueDate: LocalDate,
    val lastDone: LocalDate?,
    val isOverdue: Boolean,
    val createdAtMillis: Long = System.currentTimeMillis(),
    val updatedAtMillis: Long = System.currentTimeMillis(),
    val dirty: Boolean = false,
    val deleted: Boolean = false
)

@Entity(tableName = "event_history")
data class EventHistoryEntity(
    @PrimaryKey(autoGenerate = true)
    val localId: Long = 0,
    val remoteId: Int? = null,
    val eventId: Int,
    val action: String,
    val actionDate: LocalDate,
    val note: String? = null
)

data class EventWithHistoryEntity(
    @Embedded val event: EventEntity,
    @Relation(parentColumn = "id", entityColumn = "eventId")
    val history: List<EventHistoryEntity>
)

fun EventWithHistoryEntity.toModel(): RecurringEvent =
    RecurringEvent(
        id = event.id,
        name = event.name,
        tag = event.tag,
        details = event.details,
        frequencyValue = event.frequencyValue,
        frequencyUnit = FrequencyUnit.fromApi(event.frequencyUnit),
        dueDate = event.dueDate,
        lastDone = event.lastDone,
        isOverdue = event.isOverdue,
        history = history.map {
            EventHistory(
                id = it.remoteId ?: -it.localId.absoluteValue.toInt(),
                actionDate = it.actionDate,
                action = it.action,
                note = it.note
            )
        }
    )
