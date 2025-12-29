package calendar_app.v1.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import calendar_app.v1.data.network.EventsApiClient
import calendar_app.v1.data.network.MdnsEndpoint
import calendar_app.v1.data.network.MdnsResolver
import calendar_app.v1.data.preferences.PreferenceStorage
import calendar_app.v1.model.DEFAULT_HISTORY_LIMIT
import calendar_app.v1.model.FrequencyUnit
import calendar_app.v1.model.RecurringEvent
import calendar_app.v1.model.TimelineHorizon
import calendar_app.v1.model.TimelineHorizons
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import java.time.LocalDate

data class SettingsUiState(
    val token: String = "",
    val manualHost: String = "",
    val manualPort: String = "8000"
)

data class EventEditorState(
    val id: Int? = null,
    val name: String = "",
    val dueDate: String = LocalDate.now().toString(),
    val frequencyValue: String = "30",
    val frequencyUnit: FrequencyUnit = FrequencyUnit.DAYS
)

data class EventsScreenState(
    val events: List<RecurringEvent> = emptyList(),
    val horizonIndex: Int = 0,
    val timelineOffsetDays: Int = 0,
    val isSyncing: Boolean = false,
    val statusMessage: String? = null,
    val errorMessage: String? = null,
    val endpointDescription: String? = null,
    val settings: SettingsUiState = SettingsUiState(),
    val showSettings: Boolean = false,
    val editorState: EventEditorState? = null
) {
    val horizon: TimelineHorizon
        get() = TimelineHorizons.getOrElse(horizonIndex.coerceIn(TimelineHorizons.indices)) { TimelineHorizons.first() }

    val visibleEvents: List<RecurringEvent>
        get() = events
}

class EventsViewModel(application: Application) : AndroidViewModel(application) {

    private val prefs = PreferenceStorage(application)
    private val apiClient = EventsApiClient(
        resolver = MdnsResolver(application),
        httpClient = OkHttpClient()
    )

    private val _uiState = MutableStateFlow(
        EventsScreenState(
            settings = SettingsUiState(
                token = prefs.token,
                manualHost = prefs.manualHost,
                manualPort = prefs.manualPort.toString()
            )
        )
    )
    val uiState: StateFlow<EventsScreenState> = _uiState.asStateFlow()

    fun updateTimelineOffset(value: Int) {
        val range = uiState.value.horizon.sliderRange
        val clamped = value.coerceIn(range.first, range.last)
        _uiState.update { it.copy(timelineOffsetDays = clamped) }
    }

    fun selectHorizon(index: Int) {
        _uiState.update {
            val bounded = index.coerceIn(TimelineHorizons.indices)
            it.copy(
                horizonIndex = bounded,
                timelineOffsetDays = 0
            )
        }
    }

    fun toggleSettings(show: Boolean) {
        _uiState.update { it.copy(showSettings = show, statusMessage = null, errorMessage = null) }
    }

    fun updateToken(value: String) {
        prefs.token = value
        _uiState.update {
            it.copy(settings = it.settings.copy(token = value))
        }
    }

    fun updateManualHost(value: String) {
        prefs.manualHost = value
        _uiState.update {
            it.copy(settings = it.settings.copy(manualHost = value))
        }
    }

    fun updateManualPort(value: String) {
        _uiState.update {
            it.copy(settings = it.settings.copy(manualPort = value))
        }
    }

    fun openEditor(existing: RecurringEvent? = null) {
        val editor = if (existing == null) {
            EventEditorState()
        } else {
            EventEditorState(
                id = existing.id,
                name = existing.name,
                dueDate = existing.dueDate.toString(),
                frequencyValue = existing.frequencyValue.toString(),
                frequencyUnit = existing.frequencyUnit
            )
        }
        _uiState.update { it.copy(editorState = editor, statusMessage = null, errorMessage = null) }
    }

    fun updateEditor(name: String? = null, dueDate: String? = null, frequencyValue: String? = null, unit: FrequencyUnit? = null) {
        _uiState.update { state ->
            val editor = state.editorState ?: return
            state.copy(
                editorState = editor.copy(
                    name = name ?: editor.name,
                    dueDate = dueDate ?: editor.dueDate,
                    frequencyValue = frequencyValue ?: editor.frequencyValue,
                    frequencyUnit = unit ?: editor.frequencyUnit
                )
            )
        }
    }

    fun updateEditorName(value: String) = updateEditor(name = value)

    fun updateEditorDueDate(value: String) = updateEditor(dueDate = value)

    fun updateEditorFrequencyValue(value: String) = updateEditor(frequencyValue = value)

    fun updateEditorUnit(value: FrequencyUnit) = updateEditor(unit = value)

    fun closeEditor() {
        _uiState.update { it.copy(editorState = null) }
    }

    fun syncNow() {
        val token = uiState.value.settings.token.trim()
        if (token.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "Enter the bearer token before syncing.", statusMessage = null) }
            return
        }
        val manualEndpoint = manualEndpointOrNull()
        viewModelScope.launch {
            _uiState.update { it.copy(isSyncing = true, errorMessage = null, statusMessage = "Looking for server...") }
            try {
                val bundle = apiClient.fetchEvents(token, manualEndpoint, historyLimit = DEFAULT_HISTORY_LIMIT)
                val sorted = bundle.events.sortedBy { it.dueDate }
                _uiState.update {
                    it.copy(
                        isSyncing = false,
                        events = sorted,
                        endpointDescription = "${bundle.endpoint.host}:${bundle.endpoint.port}",
                        statusMessage = "Synchronized ${sorted.size} event(s).",
                        errorMessage = null
                    )
                }
            } catch (ex: Exception) {
                _uiState.update {
                    it.copy(isSyncing = false, errorMessage = ex.humanMessage("Sync failed."), statusMessage = null)
                }
            }
        }
    }

    fun deleteEvent(eventId: Int) {
        val token = uiState.value.settings.token.trim()
        if (token.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "Token required to delete events.") }
            return
        }
        val manualEndpoint = manualEndpointOrNull()
        viewModelScope.launch {
            _uiState.update { it.copy(isSyncing = true, errorMessage = null, statusMessage = "Deleting event...") }
            try {
                apiClient.deleteEvent(token, manualEndpoint, eventId)
                syncNow()
            } catch (ex: Exception) {
                _uiState.update {
                    it.copy(isSyncing = false, errorMessage = ex.humanMessage("Delete failed."), statusMessage = null)
                }
            }
        }
    }

    fun markDone(eventId: Int) {
        val token = uiState.value.settings.token.trim()
        if (token.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "Token required to mark events.") }
            return
        }
        val manualEndpoint = manualEndpointOrNull()
        viewModelScope.launch {
            _uiState.update { it.copy(isSyncing = true, statusMessage = "Marking event...", errorMessage = null) }
            try {
                apiClient.markDone(token, manualEndpoint, eventId)
                syncNow()
            } catch (ex: Exception) {
                _uiState.update {
                    it.copy(isSyncing = false, errorMessage = ex.humanMessage("Action failed."), statusMessage = null)
                }
            }
        }
    }

    fun submitEditor() {
        val editor = uiState.value.editorState ?: return
        val token = uiState.value.settings.token.trim()
        if (token.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "Token required to save events.") }
            return
        }
        val name = editor.name.trim()
        if (name.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "Event name required.") }
            return
        }
        val dueDate = runCatching { LocalDate.parse(editor.dueDate.trim()) }.getOrElse {
            _uiState.update { it.copy(errorMessage = "Due date must be YYYY-MM-DD.") }
            return
        }
        val freqValue = editor.frequencyValue.trim().toIntOrNull()?.takeIf { it > 0 } ?: run {
            _uiState.update { it.copy(errorMessage = "Frequency must be a positive number.") }
            return
        }
        val manualEndpoint = manualEndpointOrNull()
        viewModelScope.launch {
            _uiState.update { it.copy(isSyncing = true, errorMessage = null, statusMessage = "Saving event...") }
            try {
                if (editor.id == null) {
                    apiClient.createEvent(token, manualEndpoint, name, dueDate, freqValue, editor.frequencyUnit)
                } else {
                    apiClient.updateEvent(token, manualEndpoint, editor.id, name, dueDate, freqValue, editor.frequencyUnit)
                }
                _uiState.update { it.copy(editorState = null) }
                syncNow()
            } catch (ex: Exception) {
                _uiState.update {
                    it.copy(isSyncing = false, errorMessage = ex.humanMessage("Save failed."), statusMessage = null)
                }
            }
        }
    }

    fun useSettingsDefaults() {
        val port = uiState.value.settings.manualPort.trim().ifEmpty { "8000" }.toIntOrNull() ?: run {
            _uiState.update { it.copy(errorMessage = "Manual port must be numeric.") }
            return
        }
        prefs.manualPort = port
        _uiState.update {
            it.copy(
                settings = it.settings.copy(manualPort = port.toString()),
                showSettings = false,
                statusMessage = "Settings updated."
            )
        }
    }

    fun clearMessages() {
        _uiState.update { it.copy(statusMessage = null, errorMessage = null) }
    }

    private fun manualEndpointOrNull(): MdnsEndpoint? {
        val host = uiState.value.settings.manualHost.trim()
        if (host.isEmpty()) return null
        val port = uiState.value.settings.manualPort.trim().ifEmpty { "8000" }.toIntOrNull() ?: return null
        return MdnsEndpoint(host = host, port = port, path = "/api")
    }

    private fun Throwable.humanMessage(fallback: String): String {
        val direct = localizedMessage?.takeIf { it.isNotBlank() }
            ?: message?.takeIf { it.isNotBlank() }
            ?: toString()
        return direct.ifBlank { fallback }
    }
}
