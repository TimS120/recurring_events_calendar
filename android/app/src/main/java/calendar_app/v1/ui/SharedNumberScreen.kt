package calendar_app.v1.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import java.text.DateFormat
import java.util.Date

@Composable
fun SharedNumberScreen(
    state: SharedNumberUiState,
    onNumberChange: (String) -> Unit,
    onTokenChange: (String) -> Unit,
    onManualHostChange: (String) -> Unit,
    onManualPortChange: (String) -> Unit,
    onApplyLocal: () -> Unit,
    onSync: () -> Unit,
    modifier: Modifier = Modifier
) {
    val scrollState = rememberScrollState()
    Surface(
        modifier = modifier.fillMaxSize()
    ) {
        Column(
            modifier = Modifier
                .padding(16.dp)
                .verticalScroll(scrollState),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text(
                text = "Current number: ${state.currentValue}",
                style = MaterialTheme.typography.headlineSmall
            )
            Text(
                text = "Last updated: ${state.updatedAt.formatTimestamp()} from ${state.sourceId}",
                style = MaterialTheme.typography.bodyMedium
            )

            OutlinedTextField(
                value = state.numberInput,
                onValueChange = onNumberChange,
                label = { Text("New number") },
                placeholder = { Text("Enter integer") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth()
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Button(
                    onClick = onApplyLocal,
                    modifier = Modifier.weight(1f)
                ) {
                    Text("Apply locally")
                }
                Button(
                    onClick = onSync,
                    enabled = !state.isSyncing,
                    modifier = Modifier.weight(1f)
                ) {
                    Text("Sync now")
                }
                if (state.isSyncing) {
                    CircularProgressIndicator(
                        modifier = Modifier.height(24.dp),
                        strokeWidth = 2.dp
                    )
                }
            }

            OutlinedTextField(
                value = state.token,
                onValueChange = onTokenChange,
                label = { Text("Token (Bearer)") },
                placeholder = { Text("Paste token printed by PC app") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )

            OutlinedTextField(
                value = state.manualHost,
                onValueChange = onManualHostChange,
                label = { Text("Server IP / hostname (optional)") },
                placeholder = { Text("e.g., 192.168.178.22") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )

            OutlinedTextField(
                value = state.manualPort,
                onValueChange = onManualPortChange,
                label = { Text("Server port") },
                placeholder = { Text("8000") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth()
            )

            Text(
                text = "Device source ID: ${state.sourceId}",
                style = MaterialTheme.typography.bodySmall
            )

            Text(
                text = "Connection: ${state.endpointDescription ?: "Not discovered"}",
                style = MaterialTheme.typography.bodySmall
            )

            Text(
                text = "Last sync: ${state.lastSyncTime.formatTimestamp()}",
                style = MaterialTheme.typography.bodySmall
            )

            Text(
                text = "Last authoritative source: ${state.lastSyncedSource ?: "-"}",
                style = MaterialTheme.typography.bodySmall
            )

            state.statusMessage?.let { status ->
                Text(
                    text = status,
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.bodyMedium
                )
            }

            state.errorMessage?.let { error ->
                Text(
                    text = error,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium
                )
            }

            Spacer(modifier = Modifier.height(32.dp))

            Text(
                text = "Need the token? Start the PC FastAPI server and copy the printed token. Both devices must share the same Wi-Fi network.",
                style = MaterialTheme.typography.bodySmall
            )
        }
    }
}

private fun Long?.formatTimestamp(): String {
    if (this == null || this <= 0L) return "Never"
    val formatter = DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.MEDIUM)
    return formatter.format(Date(this))
}
