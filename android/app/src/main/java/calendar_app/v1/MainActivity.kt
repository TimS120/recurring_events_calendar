package calendar_app.v1

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import calendar_app.v1.ui.EventsScreen
import calendar_app.v1.ui.EventsViewModel
import calendar_app.v1.ui.theme.Calendar_app_v1Theme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        setContent {
            val viewModel: EventsViewModel = viewModel()
            val state by viewModel.uiState.collectAsStateWithLifecycle()
            val systemDark = isSystemInDarkTheme()
            Calendar_app_v1Theme(darkTheme = state.darkModeOverride ?: systemDark) {
                EventsScreen(
                    state = state,
                    isDarkTheme = state.darkModeOverride ?: systemDark,
                    isUsingSystemTheme = state.darkModeOverride == null,
                    onTimelineOffsetChange = viewModel::updateTimelineOffset,
                    onHorizonSelected = viewModel::selectHorizon,
                    onSync = viewModel::syncNow,
                    onOpenEditor = viewModel::openEditor,
                    onMarkDone = viewModel::markDone,
                    onMarkDonePast = viewModel::markDonePast,
                    onMarkDueToday = viewModel::markDueToday,
                    onDeleteEvent = viewModel::deleteEvent,
                    onToggleSettings = viewModel::toggleSettings,
                    onFirebaseSignIn = viewModel::signIn,
                    onResetFirebaseCalendar = viewModel::resetFirebaseCalendar,
                    onEditorNameChange = viewModel::updateEditorName,
                    onEditorTagChange = viewModel::updateEditorTag,
                    onEditorDetailsChange = viewModel::updateEditorDetails,
                    onEditorDueDateChange = viewModel::updateEditorDueDate,
                    onEditorFrequencyValueChange = viewModel::updateEditorFrequencyValue,
                    onEditorUnitChange = viewModel::updateEditorUnit,
                    onSubmitEditor = viewModel::submitEditor,
                    onCloseEditor = viewModel::closeEditor,
                    onClearMessage = viewModel::clearMessages,
                    onToggleDarkMode = { viewModel.toggleDarkMode(systemDark) },
                    onTagPrioritySelected = viewModel::prioritizeTag
                )
            }
        }
    }

}
