package calendar_app.v1.data.network

import calendar_app.v1.model.EventHistory
import calendar_app.v1.model.FrequencyUnit
import calendar_app.v1.model.RecurringEvent
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate

class EventsApiClient(
    private val resolver: MdnsResolver,
    private val httpClient: OkHttpClient
) {
    private var lastEndpoint: MdnsEndpoint? = null

    suspend fun fetchEvents(
        token: String,
        manualEndpoint: MdnsEndpoint?,
        historyLimit: Int
    ): SyncBundle = withContext(Dispatchers.IO) {
        val endpoint = resolveEndpoint(manualEndpoint)
        val request = Request.Builder()
            .url(endpoint.buildUrl("/events?history_limit=$historyLimit"))
            .addToken(token)
            .get()
            .build()

        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw ApiException(response.code, "GET /events failed")
            }
            val payload = response.body?.string().orEmpty()
            val events = JSONArray(payload).toRecurringEvents()
            lastEndpoint = endpoint
            return@withContext SyncBundle(events, endpoint)
        }
    }

    suspend fun createEvent(
        token: String,
        manualEndpoint: MdnsEndpoint?,
        name: String,
        dueDate: LocalDate,
        frequencyValue: Int,
        frequencyUnit: FrequencyUnit
    ): RecurringEvent = withContext(Dispatchers.IO) {
        val endpoint = resolveEndpoint(manualEndpoint)
        val body = JSONObject().apply {
            put("name", name)
            put("due_date", dueDate.toString())
            put("frequency_value", frequencyValue)
            put("frequency_unit", frequencyUnit.apiValue)
        }
        val request = Request.Builder()
            .url(endpoint.buildUrl("/events"))
            .addToken(token)
            .post(body.asJson())
            .build()

        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw ApiException(response.code, "POST /events failed")
            }
            lastEndpoint = endpoint
            return@withContext response.body?.string().orEmpty().toRecurringEvent()
        }
    }

    suspend fun updateEvent(
        token: String,
        manualEndpoint: MdnsEndpoint?,
        eventId: Int,
        name: String,
        dueDate: LocalDate,
        frequencyValue: Int,
        frequencyUnit: FrequencyUnit
    ): RecurringEvent = withContext(Dispatchers.IO) {
        val endpoint = resolveEndpoint(manualEndpoint)
        val body = JSONObject().apply {
            put("name", name)
            put("due_date", dueDate.toString())
            put("frequency_value", frequencyValue)
            put("frequency_unit", frequencyUnit.apiValue)
        }
        val request = Request.Builder()
            .url(endpoint.buildUrl("/events/$eventId"))
            .addToken(token)
            .put(body.asJson())
            .build()

        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw ApiException(response.code, "PUT /events/$eventId failed")
            }
            lastEndpoint = endpoint
            return@withContext response.body?.string().orEmpty().toRecurringEvent()
        }
    }

    suspend fun deleteEvent(
        token: String,
        manualEndpoint: MdnsEndpoint?,
        eventId: Int
    ) = withContext(Dispatchers.IO) {
        val endpoint = resolveEndpoint(manualEndpoint)
        val request = Request.Builder()
            .url(endpoint.buildUrl("/events/$eventId"))
            .addToken(token)
            .delete()
            .build()

        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw ApiException(response.code, "DELETE /events/$eventId failed")
            }
            lastEndpoint = endpoint
        }
    }

    suspend fun markDone(
        token: String,
        manualEndpoint: MdnsEndpoint?,
        eventId: Int
    ): RecurringEvent = withContext(Dispatchers.IO) {
        val endpoint = resolveEndpoint(manualEndpoint)
        val request = Request.Builder()
            .url(endpoint.buildUrl("/events/$eventId/complete"))
            .addToken(token)
            .post("{}".toRequestBody(JSON))
            .build()

        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw ApiException(response.code, "POST /events/$eventId/complete failed")
            }
            lastEndpoint = endpoint
            return@withContext response.body?.string().orEmpty().toRecurringEvent()
        }
    }

    private suspend fun resolveEndpoint(manual: MdnsEndpoint?): MdnsEndpoint {
        manual?.let { return it }
        lastEndpoint?.let { return it }
        return resolver.discover().also { lastEndpoint = it }
    }

    private fun JSONArray.toRecurringEvents(): List<RecurringEvent> =
        buildList {
            for (index in 0 until length()) {
                val obj = getJSONObject(index)
                add(obj.toRecurringEvent())
            }
        }

    private fun String.toRecurringEvent(): RecurringEvent =
        JSONObject(this).toRecurringEvent()

    private fun JSONObject.toRecurringEvent(): RecurringEvent {
        val historyArray = optJSONArray("history") ?: JSONArray()
        return RecurringEvent(
            id = getInt("id"),
            name = getString("name"),
            frequencyValue = getInt("frequency_value"),
            frequencyUnit = FrequencyUnit.fromApi(getString("frequency_unit")),
            dueDate = LocalDate.parse(getString("due_date")),
            lastDone = optStringOrNull("last_done")?.let(LocalDate::parse),
            isOverdue = optBoolean("is_overdue", false),
            history = historyArray.mapHistory()
        )
    }

    private fun JSONArray.mapHistory(): List<EventHistory> =
        buildList {
            for (index in 0 until length()) {
                val obj = getJSONObject(index)
                add(
                    EventHistory(
                        id = obj.getInt("id"),
                        actionDate = LocalDate.parse(obj.getString("action_date")),
                        action = obj.getString("action"),
                        note = obj.optStringOrNull("note")
                    )
                )
            }
        }

    private fun JSONObject.optStringOrNull(key: String): String? =
        if (has(key) && !isNull(key)) getString(key) else null

    data class SyncBundle(
        val events: List<RecurringEvent>,
        val endpoint: MdnsEndpoint
    )

    class ApiException(val code: Int, message: String) : Exception(message)

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
    }
}

private fun Request.Builder.addToken(token: String) = apply {
    header("Authorization", "Bearer $token")
}

private fun MdnsEndpoint.buildUrl(relative: String): String {
    val normalizedBase = path.trimEnd('/')
    val normalizedRelative = if (relative.startsWith("/")) relative else "/$relative"
    val finalPath = if (normalizedBase.isBlank()) normalizedRelative else "$normalizedBase$normalizedRelative"
    return "http://$host:$port$finalPath"
}

private fun JSONObject.asJson() = toString().toRequestBody("application/json; charset=utf-8".toMediaType())
