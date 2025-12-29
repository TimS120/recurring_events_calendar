package calendar_app.v1.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import calendar_app.v1.data.local.SharedStateDatabase
import calendar_app.v1.data.local.SharedStateRepository
import calendar_app.v1.data.network.MdnsEndpoint
import calendar_app.v1.data.network.MdnsResolver
import calendar_app.v1.data.network.SyncClient
import calendar_app.v1.data.preferences.PreferenceStorage
import calendar_app.v1.model.SharedState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient

data class SharedNumberUiState(
    val currentValue: Int = 0,
    val updatedAt: Long = 0L,
    val sourceId: String = "",
    val token: String = "",
    val numberInput: String = "",
    val manualHost: String = "",
    val manualPort: String = "8000",
    val isSyncing: Boolean = false,
    val endpointDescription: String? = null,
    val lastSyncTime: Long? = null,
    val lastSyncedSource: String? = null,
    val statusMessage: String? = null,
    val errorMessage: String? = null
)

class SharedNumberViewModel(application: Application) : AndroidViewModel(application) {

    private val preferenceStorage = PreferenceStorage(application)
    private val repository = SharedStateRepository(
        SharedStateDatabase.getInstance(application).sharedStateDao()
    )
    private val syncClient = SyncClient(
        resolver = MdnsResolver(application),
        httpClient = OkHttpClient()
    )

    private val _uiState = MutableStateFlow(
        SharedNumberUiState(
            sourceId = preferenceStorage.sourceId,
            token = preferenceStorage.token,
            numberInput = "",
            manualHost = preferenceStorage.manualHost,
            manualPort = preferenceStorage.manualPort.toString()
        )
    )
    val uiState: StateFlow<SharedNumberUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.ensureSeed(preferenceStorage.sourceId)
            repository.stateFlow.collect { state ->
                _uiState.update {
                    it.copy(
                        currentValue = state.value,
                        updatedAt = state.updatedAt,
                        numberInput = state.value.toString()
                    )
                }
            }
        }
    }

    fun updateNumberInput(value: String) {
        _uiState.update { it.copy(numberInput = value) }
    }

    fun updateToken(value: String) {
        preferenceStorage.token = value
        _uiState.update { it.copy(token = value) }
    }

    fun updateManualHost(value: String) {
        preferenceStorage.manualHost = value
        _uiState.update { it.copy(manualHost = value) }
    }

    fun updateManualPort(value: String) {
        _uiState.update { it.copy(manualPort = value) }
    }

    fun applyLocalUpdate() {
        val input = uiState.value.numberInput.trim()
        val parsed = input.toIntOrNull()
        if (input.isEmpty() || parsed == null) {
            _uiState.update {
                it.copy(errorMessage = "Enter a valid integer before applying.", statusMessage = null)
            }
            return
        }
        viewModelScope.launch {
            try {
                repository.applyLocal(parsed, preferenceStorage.sourceId)
                _uiState.update {
                    it.copy(
                        statusMessage = "Local value updated.",
                        errorMessage = null
                    )
                }
            } catch (ex: Exception) {
                _uiState.update {
                    it.copy(
                        errorMessage = ex.message ?: "Local update failed.",
                        statusMessage = null
                    )
                }
            }
        }
    }

    fun syncNow() {
        val token = uiState.value.token.trim()
        if (token.isEmpty()) {
            _uiState.update {
                it.copy(
                    errorMessage = "Token required before syncing.",
                    statusMessage = null
                )
            }
            return
        }

        val manualEndpoint = run {
            val host = uiState.value.manualHost.trim()
            if (host.isEmpty()) {
                preferenceStorage.manualHost = ""
                null
            } else {
                val portValue = uiState.value.manualPort.trim().ifEmpty { "8000" }.toIntOrNull()
                if (portValue == null) {
                    _uiState.update {
                        it.copy(
                            errorMessage = "Invalid port number.",
                            statusMessage = null,
                            isSyncing = false
                        )
                    }
                    return
                }
                preferenceStorage.manualHost = host
                preferenceStorage.manualPort = portValue
                MdnsEndpoint(host = host, port = portValue, path = "/api")
            }
        }

        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isSyncing = true,
                    statusMessage = "Preparing sync...",
                    errorMessage = null
                )
            }

            try {
                val localState = repository.getState() ?: SharedState(
                    value = 0,
                    updatedAt = System.currentTimeMillis(),
                    sourceId = preferenceStorage.sourceId
                )
                val result = syncClient.sync(
                    token = token,
                    localState = localState,
                    manualEndpoint = manualEndpoint
                )
                repository.save(result.state)
                val endpointLabel = "${result.endpoint.host}:${result.endpoint.port}${result.endpoint.path}"
                _uiState.update {
                    it.copy(
                        isSyncing = false,
                        endpointDescription = endpointLabel,
                        lastSyncTime = System.currentTimeMillis(),
                        lastSyncedSource = result.state.sourceId,
                        statusMessage = "Synced successfully.",
                        errorMessage = null
                    )
                }
            } catch (ex: Exception) {
                _uiState.update {
                    it.copy(
                        isSyncing = false,
                        errorMessage = ex.message ?: "Sync failed.",
                        statusMessage = null
                    )
                }
            }
        }
    }

}
