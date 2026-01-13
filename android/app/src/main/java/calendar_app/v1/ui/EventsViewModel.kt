package calendar_app.v1.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import calendar_app.v1.data.EventsRepository
import calendar_app.v1.data.local.RecurringEventsDatabase
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
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import java.time.LocalDate
import java.net.URI

data class SettingsUiState(
    val token: String = "",
    val serverUrl: String = "",
    val manualHost: String = "",
    val manualPort: String = "8000"
)

data class EventEditorState(
    val id: Int? = null,
    val name: String = "",
    val tag: String = "",
    val details: String = "",
    val dueDate: String = formatDisplayDate(LocalDate.now()),
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
    val editorState: EventEditorState? = null,
    val darkModeOverride: Boolean? = null,
    val availableTags: List<String> = emptyList(),
    val prioritizedTag: String? = null
) {
    val horizon: TimelineHorizon
        get() = TimelineHorizons.getOrElse(horizonIndex.coerceIn(TimelineHorizons.indices)) { TimelineHorizons.first() }

    val visibleEvents: List<RecurringEvent>
        get() {
            val prioritized = prioritizedTag?.takeIf { it.isNotBlank() } ?: return events
            val prioritizedLower = prioritized.lowercase()
            val withTag = mutableListOf<RecurringEvent>()
            val withoutTag = mutableListOf<RecurringEvent>()
            events.forEach { event ->
                val tagValue = event.tag?.trim()
                if (!tagValue.isNullOrEmpty() && tagValue.lowercase() == prioritizedLower) {
                    withTag += event
                } else {
                    withoutTag += event
                }
            }
            return withTag + withoutTag
        }
}

class EventsViewModel(application: Application) : AndroidViewModel(application) {

    private val prefs = PreferenceStorage(application)
    private val apiClient = EventsApiClient(
        resolver = MdnsResolver(application),
        httpClient = OkHttpClient()
    )
    private val database = RecurringEventsDatabase.getInstance(application)
    private val repository = EventsRepository(database, apiClient)

    private val _uiState = MutableStateFlow(
        EventsScreenState(
            settings = SettingsUiState(
                token = prefs.token,
                serverUrl = prefs.serverUrl,
                manualHost = prefs.manualHost,
                manualPort = prefs.manualPort.toString()
            )
        )
    )
    val uiState: StateFlow<EventsScreenState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.eventsFlow.collectLatest { events ->
                _uiState.update { state ->
                    val sorted = events.sortedBy { it.dueDate }
                    val tags = sorted
                        .mapNotNull { it.tag?.trim()?.takeIf(String::isNotEmpty) }
                        .associateBy { it.lowercase() }
                        .values
                        .sortedWith(java.lang.String.CASE_INSENSITIVE_ORDER)
                    val resolvedSelection = state.prioritizedTag?.let { selection ->
                        tags.firstOrNull { it.equals(selection, ignoreCase = true) }
                    }
                    state.copy(
                        events = sorted,
                        availableTags = tags,
                        prioritizedTag = resolvedSelection
                    )
                }
            }
        }
    }

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

    fun updateServerUrl(value: String) {
        prefs.serverUrl = value
        _uiState.update {
            it.copy(settings = it.settings.copy(serverUrl = value))
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
                tag = existing.tag.orEmpty(),
                details = existing.details.orEmpty(),
                dueDate = formatDisplayDate(existing.dueDate),
                frequencyValue = existing.frequencyValue.toString(),
                frequencyUnit = existing.frequencyUnit
            )
        }
        _uiState.update { it.copy(editorState = editor, statusMessage = null, errorMessage = null) }
    }

    fun updateEditor(
        name: String? = null,
        tag: String? = null,
        details: String? = null,
        dueDate: String? = null,
        frequencyValue: String? = null,
        unit: FrequencyUnit? = null
    ) {
        _uiState.update { state ->
            val editor = state.editorState ?: return
            state.copy(
                editorState = editor.copy(
                    name = name ?: editor.name,
                    tag = tag ?: editor.tag,
                    details = details ?: editor.details,
                    dueDate = dueDate ?: editor.dueDate,
                    frequencyValue = frequencyValue ?: editor.frequencyValue,
                    frequencyUnit = unit ?: editor.frequencyUnit
                )
            )
        }
    }

    fun updateEditorName(value: String) = updateEditor(name = value)

    fun updateEditorTag(value: String) = updateEditor(tag = value)

    fun updateEditorDetails(value: String) = updateEditor(details = value)

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
            _uiState.update { it.copy(isSyncing = true, errorMessage = null, statusMessage = "Synchronizing...") }
            when (val result = repository.sync(token, manualEndpoint, DEFAULT_HISTORY_LIMIT)) {
                is EventsRepository.SyncResult.Success -> {
                    val endpointDescription = "${result.endpoint.host}:${result.endpoint.port}"
                    val message = "Synced ${result.remoteCount} event(s). Pushed ${result.pushedChanges} change(s)."
                    _uiState.update {
                        it.copy(
                            isSyncing = false,
                            endpointDescription = endpointDescription,
                            statusMessage = message,
                            errorMessage = null
                        )
                    }
                }

                is EventsRepository.SyncResult.Failure -> {
                    _uiState.update {
                        it.copy(isSyncing = false, errorMessage = result.error.humanMessage("Sync failed."), statusMessage = null)
                    }
                }
            }
        }
    }

    fun deleteEvent(eventId: Int) {
        viewModelScope.launch {
            repository.deleteEventLocally(eventId)
            _uiState.update {
                it.copy(
                    statusMessage = "Event deleted locally. Sync to propagate changes.",
                    errorMessage = null
                )
            }
        }
    }

    fun markDone(eventId: Int) {
        viewModelScope.launch {
            repository.markDoneLocally(eventId)
            _uiState.update {
                it.copy(
                    statusMessage = "Marked as done locally. Run sync to push updates.",
                    errorMessage = null
                )
            }
        }
    }

    fun markDueToday(eventId: Int) {
        val event = uiState.value.events.firstOrNull { it.id == eventId } ?: run {
            _uiState.update { it.copy(errorMessage = "Event not found.") }
            return
        }
        viewModelScope.launch {
            repository.saveEventLocally(
                inputId = event.id,
                name = event.name,
                tag = event.tag,
                details = event.details,
                dueDate = LocalDate.now(),
                frequencyValue = event.frequencyValue,
                frequencyUnit = event.frequencyUnit,
                generateLocalId = { prefs.nextLocalEventId() }
            )
            _uiState.update {
                it.copy(
                    statusMessage = "Due date set to today locally. Sync to push updates.",
                    errorMessage = null
                )
            }
        }
    }

    fun submitEditor() {
        val editor = uiState.value.editorState ?: return
        val name = editor.name.trim()
        if (name.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "Event name required.") }
            return
        }
        val dueDate = parseDisplayDateOrNull(editor.dueDate) ?: run {
            _uiState.update { it.copy(errorMessage = "Due date must be DD.MM.YYYY.") }
            return
        }
        val freqValue = editor.frequencyValue.trim().toIntOrNull()?.takeIf { it > 0 } ?: run {
            _uiState.update { it.copy(errorMessage = "Frequency must be a positive number.") }
            return
        }
        viewModelScope.launch {
            repository.saveEventLocally(
                inputId = editor.id,
                name = name,
                tag = editor.tag.trim().takeIf { it.isNotEmpty() },
                details = editor.details,
                dueDate = dueDate,
                frequencyValue = freqValue,
                frequencyUnit = editor.frequencyUnit,
                generateLocalId = { prefs.nextLocalEventId() }
            )
            val status = if (editor.id == null) {
                "Event saved locally. Sync to upload it."
            } else {
                "Event updated locally. Sync to push changes."
            }
            _uiState.update { it.copy(editorState = null, statusMessage = status, errorMessage = null) }
        }
    }

    fun useSettingsDefaults() {
        val serverUrl = uiState.value.settings.serverUrl.trim()
        val resolvedPort: Int
        if (serverUrl.isNotEmpty()) {
            val endpoint = parseServerUrl(serverUrl) ?: run {
                _uiState.update { it.copy(errorMessage = "Server URL must be a valid http(s) URL.") }
                return
            }
            prefs.serverUrl = serverUrl
            prefs.manualPort = endpoint.port
            resolvedPort = endpoint.port
        } else {
            val port = uiState.value.settings.manualPort.trim().ifEmpty { "8000" }.toIntOrNull() ?: run {
                _uiState.update { it.copy(errorMessage = "Manual port must be numeric.") }
                return
            }
            prefs.serverUrl = ""
            prefs.manualPort = port
            resolvedPort = port
        }
        _uiState.update {
            it.copy(
                settings = it.settings.copy(manualPort = resolvedPort.toString(), serverUrl = serverUrl),
                showSettings = false,
                statusMessage = "Settings updated."
            )
        }
    }

    fun clearMessages() {
        _uiState.update { it.copy(statusMessage = null, errorMessage = null) }
    }

    fun toggleDarkMode(systemDark: Boolean) {
        _uiState.update { state ->
            val baseline = state.darkModeOverride ?: systemDark
            val target = !baseline
            val newOverride = if (target == systemDark) null else target
            state.copy(darkModeOverride = newOverride)
        }
    }

    fun prioritizeTag(tag: String?) {
        _uiState.update { state ->
            val cleaned = tag?.takeIf { it.isNotBlank() }
            val allowed = cleaned?.let { candidate ->
                state.availableTags.firstOrNull { it.equals(candidate, ignoreCase = true) }
            }
            state.copy(prioritizedTag = allowed)
        }
    }

    private fun manualEndpointOrNull(): MdnsEndpoint? {
        val urlEndpoint = serverUrlEndpointOrNull()
        if (urlEndpoint != null) return urlEndpoint
        val host = uiState.value.settings.manualHost.trim()
        if (host.isEmpty()) return null
        val port = uiState.value.settings.manualPort.trim().ifEmpty { "8000" }.toIntOrNull() ?: return null
        return MdnsEndpoint(scheme = "http", host = host, port = port, path = "/api")
    }

    private fun serverUrlEndpointOrNull(): MdnsEndpoint? {
        val raw = uiState.value.settings.serverUrl.trim()
        if (raw.isEmpty()) return null
        return parseServerUrl(raw)
    }

    private fun parseServerUrl(raw: String): MdnsEndpoint? {
        val uri = runCatching { URI(raw) }.getOrNull() ?: return null
        val scheme = uri.scheme?.lowercase() ?: return null
        if (scheme != "http" && scheme != "https") return null
        val host = uri.host ?: return null
        val port = if (uri.port != -1) uri.port else if (scheme == "https") 443 else 80
        val path = uri.path?.takeIf { it.isNotBlank() && it != "/" } ?: "/api"
        return MdnsEndpoint(scheme = scheme, host = host, port = port, path = path)
    }

    private fun Throwable.humanMessage(fallback: String): String {
        val direct = localizedMessage?.takeIf { it.isNotBlank() }
            ?: message?.takeIf { it.isNotBlank() }
            ?: toString()
        return direct.ifBlank { fallback }
    }
}
