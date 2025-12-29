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
import androidx.compose.runtime.getValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import calendar_app.v1.ui.SharedNumberScreen
import calendar_app.v1.ui.SharedNumberViewModel
import calendar_app.v1.ui.theme.Calendar_app_v1Theme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val nearbyPermissionLauncher =
            registerForActivityResult(ActivityResultContracts.RequestPermission()) { }
        maybeRequestNearbyPermission(nearbyPermissionLauncher)

        setContent {
            Calendar_app_v1Theme {
                val viewModel: SharedNumberViewModel = viewModel()
                val uiState by viewModel.uiState.collectAsStateWithLifecycle()
                SharedNumberScreen(
                    state = uiState,
                    onNumberChange = viewModel::updateNumberInput,
                    onTokenChange = viewModel::updateToken,
                    onManualHostChange = viewModel::updateManualHost,
                    onManualPortChange = viewModel::updateManualPort,
                    onApplyLocal = viewModel::applyLocalUpdate,
                    onSync = viewModel::syncNow
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
