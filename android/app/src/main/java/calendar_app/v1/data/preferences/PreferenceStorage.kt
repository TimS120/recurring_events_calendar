package calendar_app.v1.data.preferences

import android.content.Context
import java.util.UUID

class PreferenceStorage(context: Context) {

    private val prefs = context.getSharedPreferences("shared_number_prefs", Context.MODE_PRIVATE)

    var token: String
        get() = prefs.getString(KEY_TOKEN, "") ?: ""
        set(value) {
            prefs.edit().putString(KEY_TOKEN, value.trim()).apply()
        }

    val sourceId: String
        get() {
            val existing = prefs.getString(KEY_SOURCE_ID, null)
            if (existing.isNullOrEmpty()) {
                val generated = UUID.randomUUID().toString()
                prefs.edit().putString(KEY_SOURCE_ID, generated).apply()
                return generated
            }
            return existing
        }

    var manualHost: String
        get() = prefs.getString(KEY_MANUAL_HOST, "") ?: ""
        set(value) {
            prefs.edit().putString(KEY_MANUAL_HOST, value.trim()).apply()
        }

    var serverUrl: String
        get() = prefs.getString(KEY_SERVER_URL, "") ?: ""
        set(value) {
            prefs.edit().putString(KEY_SERVER_URL, value.trim()).apply()
        }

    var manualPort: Int
        get() = prefs.getInt(KEY_MANUAL_PORT, 8000)
        set(value) {
            prefs.edit().putInt(KEY_MANUAL_PORT, value).apply()
        }

    fun nextLocalEventId(): Int {
        val current = prefs.getInt(KEY_NEXT_LOCAL_EVENT_ID, -1)
        val next = if (current >= 0) -1 else current
        val assigned = next
        val updated = assigned - 1
        prefs.edit().putInt(KEY_NEXT_LOCAL_EVENT_ID, updated).apply()
        return assigned
    }

    companion object {
        private const val KEY_TOKEN = "token"
        private const val KEY_SOURCE_ID = "source_id"
        private const val KEY_MANUAL_HOST = "manual_host"
        private const val KEY_SERVER_URL = "server_url"
        private const val KEY_MANUAL_PORT = "manual_port"
        private const val KEY_NEXT_LOCAL_EVENT_ID = "next_local_event_id"
    }
}
