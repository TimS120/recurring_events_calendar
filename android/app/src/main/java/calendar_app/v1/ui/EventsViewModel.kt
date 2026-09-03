package calendar_app.v1.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import calendar_app.v1.data.EventsRepository
import calendar_app.v1.data.local.RecurringEventsDatabase
import calendar_app.v1.data.network.EventsApiClient
import calendar_app.v1.data.network.MdnsResolver
import calendar_app.v1.data.preferences.PreferenceStorage
import calendar_app.v1.data.firebase.FirebaseAuthManager
import calendar_app.v1.data.firebase.FirestoreCalendarStore
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

data class SettingsUiState(
    val email: String = "",
    val isSignedIn: Boolean = false
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
    private val firebaseAuth = FirebaseAuthManager()
    private val firestoreStore = FirestoreCalendarStore(firebaseAuth)

    private val _uiState = MutableStateFlow(
        EventsScreenState(
            settings = SettingsUiState(
                email = prefs.firebaseEmail,
                isSignedIn = firebaseAuth.isSignedIn
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

    fun updateEmail(value: String) {
        prefs.firebaseEmail = value
        _uiState.update {
            it.copy(settings = it.settings.copy(email = value))
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
        if (!firebaseAuth.isSignedIn) {
            _uiState.update { it.copy(errorMessage = "Sign in to Firebase before syncing.", statusMessage = null) }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isSyncing = true, errorMessage = null, statusMessage = "Synchronizing...") }
            when (val result = repository.syncFirebase(firestoreStore)) {
                is EventsRepository.SyncResult.FirebaseSuccess -> {
                    val message = "Synced ${result.remoteCount} event(s). Pushed ${result.pushedChanges} change(s)."
                    _uiState.update {
                        it.copy(
                            isSyncing = false,
                            endpointDescription = "Firebase",
                            statusMessage = message,
                            errorMessage = null
                        )
                    }
                }

                is EventsRepository.SyncResult.Success -> {
                    _uiState.update {
                        it.copy(
                            isSyncing = false,
                            endpointDescription = result.endpoint.host,
                            statusMessage = "Synced ${result.remoteCount} event(s).",
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

    fun signIn(email: String, password: String, create: Boolean) {
        viewModelScope.launch {
            _uiState.update { it.copy(isSyncing = true, errorMessage = null, statusMessage = "Signing in...") }
            try {
                if (create) firebaseAuth.createAccount(email, password) else firebaseAuth.signIn(email, password)
                prefs.firebaseEmail = email
                _uiState.update { it.copy(isSyncing = false, settings = it.settings.copy(email = email, isSignedIn = true), statusMessage = "Signed in. Syncing...") }
                syncNow()
            } catch (ex: Exception) {
                _uiState.update { it.copy(isSyncing = false, errorMessage = ex.localizedMessage ?: "Firebase sign-in failed.") }
            }
        }
    }

    /** Intentionally destructive reset for a fresh shared calendar. */
    fun resetFirebaseCalendar() {
        if (!firebaseAuth.isSignedIn) {
            _uiState.update { it.copy(errorMessage = "Sign in to Firebase before clearing the calendar.", statusMessage = null) }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isSyncing = true, errorMessage = null, statusMessage = "Clearing calendar data...") }
            try {
                repository.resetFirebaseCalendar(firestoreStore)
                _uiState.update {
                    it.copy(isSyncing = false, statusMessage = "All local and Firebase calendar data was cleared.", errorMessage = null)
                }
            } catch (ex: Exception) {
                _uiState.update {
                    it.copy(isSyncing = false, errorMessage = ex.humanMessage("Could not clear calendar data."), statusMessage = null)
                }
            }
        }
        // Firebase Auth restores its saved session during app startup.  Only
        // trusted, already-signed-in devices synchronize automatically.
        if (firebaseAuth.isSignedIn) {
            syncNow()
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
        markDone(eventId, LocalDate.now())
    }

    fun markDonePast(eventId: Int, doneDate: LocalDate) {
        if (doneDate.isAfter(LocalDate.now())) {
            _uiState.update {
                it.copy(
                    errorMessage = "Done past date must be today or earlier.",
                    statusMessage = null
                )
            }
            return
        }
        markDone(eventId, doneDate)
    }

    private fun markDone(eventId: Int, doneDate: LocalDate) {
        viewModelScope.launch {
            repository.markDoneLocally(eventId, doneDate)
            val status = if (doneDate == LocalDate.now()) {
                "Marked as done locally. Run sync to push updates."
            } else {
                "Marked as done for ${formatDisplayDate(doneDate)} locally. Run sync to push updates."
            }
            _uiState.update {
                it.copy(
                    statusMessage = status,
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

    private fun Throwable.humanMessage(fallback: String): String {
        val direct = localizedMessage?.takeIf { it.isNotBlank() }
            ?: message?.takeIf { it.isNotBlank() }
            ?: toString()
        return direct.ifBlank { fallback }
    }
}
