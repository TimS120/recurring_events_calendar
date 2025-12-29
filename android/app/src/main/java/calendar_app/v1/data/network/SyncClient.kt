package calendar_app.v1.data.network

import calendar_app.v1.model.SharedState
import calendar_app.v1.model.shouldReplace
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class SyncClient(
    private val resolver: MdnsResolver,
    private val httpClient: OkHttpClient
) {

    suspend fun sync(
        token: String,
        localState: SharedState,
        manualEndpoint: MdnsEndpoint? = null,
        discoveryTimeout: Long = 5000L
    ): SyncResult = withContext(Dispatchers.IO) {
        val endpoint = manualEndpoint ?: resolver.discover(discoveryTimeout)
        val serverState = fetchState(endpoint, token)
        val authoritative = if (shouldReplace(localState, serverState)) {
            pushState(endpoint, token, localState)
        } else {
            serverState
        }
        SyncResult(authoritative, endpoint)
    }

    private fun fetchState(
        endpoint: MdnsEndpoint,
        token: String
    ): SharedState {
        val request = Request.Builder()
            .url(endpoint.buildUrl("/state"))
            .addToken(token)
            .get()
            .build()

        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw IllegalStateException("GET /state failed: ${response.code}")
            }
            val body = response.body?.string().orEmpty()
            return body.toSharedState()
        }
    }

    private fun pushState(
        endpoint: MdnsEndpoint,
        token: String,
        payload: SharedState
    ): SharedState {
        val jsonBody = JSONObject().apply {
            put("value", payload.value)
            put("updated_at", payload.updatedAt)
            put("source_id", payload.sourceId)
        }
        val request = Request.Builder()
            .url(endpoint.buildUrl("/state"))
            .addToken(token)
            .post(
                jsonBody.toString()
                    .toRequestBody("application/json; charset=utf-8".toMediaType())
            )
            .build()

        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw IllegalStateException("POST /state failed: ${response.code}")
            }
            val body = response.body?.string().orEmpty()
            return body.toSharedState()
        }
    }
}

data class SyncResult(
    val state: SharedState,
    val endpoint: MdnsEndpoint
)

private fun Request.Builder.addToken(token: String) = apply {
    header("Authorization", "Bearer $token")
}

private fun String.toSharedState(): SharedState {
    val json = JSONObject(this)
    return SharedState(
        value = json.getInt("value"),
        updatedAt = json.getLong("updated_at"),
        sourceId = json.getString("source_id")
    )
}

private fun MdnsEndpoint.buildUrl(relative: String): String {
    val normalizedBase = path.trimEnd('/')
    val normalizedRelative = if (relative.startsWith("/")) relative else "/$relative"
    val finalPath = if (normalizedBase.isBlank()) normalizedRelative else "$normalizedBase$normalizedRelative"
    return "http://$host:$port$finalPath"
}
