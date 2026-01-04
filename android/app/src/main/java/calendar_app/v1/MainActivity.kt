package calendar_app.v1

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.getValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import calendar_app.v1.ui.EventsScreen
import calendar_app.v1.ui.EventsViewModel
import calendar_app.v1.ui.theme.Calendar_app_v1Theme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val nearbyPermissionLauncher =
            registerForActivityResult(ActivityResultContracts.RequestPermission()) { }
        maybeRequestNearbyPermission(nearbyPermissionLauncher)

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
                    onDeleteEvent = viewModel::deleteEvent,
                    onToggleSettings = viewModel::toggleSettings,
                    onTokenChange = viewModel::updateToken,
                    onManualHostChange = viewModel::updateManualHost,
                    onManualPortChange = viewModel::updateManualPort,
                    onApplySettings = viewModel::useSettingsDefaults,
                    onEditorNameChange = viewModel::updateEditorName,
                    onEditorTagChange = viewModel::updateEditorTag,
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

    private fun maybeRequestNearbyPermission(launcher: ActivityResultLauncher<String>) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val permission = Manifest.permission.NEARBY_WIFI_DEVICES
        val granted = ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED
        if (!granted) {
            launcher.launch(permission)
        }
    }
}
