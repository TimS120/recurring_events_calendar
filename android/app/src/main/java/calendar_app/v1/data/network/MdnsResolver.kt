package calendar_app.v1.data.network

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.net.InetAddress
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

data class MdnsEndpoint(
    val host: String,
    val port: Int,
    val path: String
)

class MdnsResolver(context: Context) {

    private val nsdManager = context.getSystemService(Context.NSD_SERVICE) as NsdManager

    suspend fun discover(timeoutMillis: Long = 5000L): MdnsEndpoint = withContext(Dispatchers.IO) {
        withTimeout(timeoutMillis) {
            suspendCancellableCoroutine { continuation ->
                lateinit var discoveryListener: NsdManager.DiscoveryListener
                discoveryListener = object : NsdManager.DiscoveryListener {
                    override fun onDiscoveryStarted(regType: String?) {}

                    override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                        if (!serviceInfo.serviceType.contains(SERVICE_TYPE_ROOT)) {
                            return
                        }
                        val resolveListener = object : NsdManager.ResolveListener {
                            override fun onResolveFailed(
                                serviceInfo: NsdServiceInfo,
                                errorCode: Int
                            ) {
                                stopDiscoverySafe(discoveryListener)
                                if (continuation.isActive) {
                                    continuation.resumeWithException(
                                        IllegalStateException("Resolve failed: $errorCode")
                                    )
                                }
                            }

                            override fun onServiceResolved(resolvedServiceInfo: NsdServiceInfo) {
                                stopDiscoverySafe(discoveryListener)
                                if (continuation.isActive) {
                                    continuation.resume(resolvedServiceInfo.toEndpoint())
                                }
                            }
                        }
                        nsdManager.resolveService(serviceInfo, resolveListener)
                    }

                    override fun onServiceLost(serviceInfo: NsdServiceInfo?) {}

                    override fun onStartDiscoveryFailed(serviceType: String?, errorCode: Int) {
                        stopDiscoverySafe(this)
                        if (continuation.isActive) {
                            continuation.resumeWithException(
                                IllegalStateException("Discovery start failed: $errorCode")
                            )
                        }
                    }

                    override fun onStopDiscoveryFailed(serviceType: String?, errorCode: Int) {
                        stopDiscoverySafe(this)
                        if (continuation.isActive) {
                            continuation.resumeWithException(
                                IllegalStateException("Discovery stop failed: $errorCode")
                            )
                        }
                    }

                    override fun onDiscoveryStopped(serviceType: String?) {
                        if (continuation.isActive) {
                            continuation.resumeWithException(
                                IllegalStateException("Discovery stopped before resolving service.")
                            )
                        }
                    }
                }

                continuation.invokeOnCancellation {
                    stopDiscoverySafe(discoveryListener)
                }

                nsdManager.discoverServices(
                    SERVICE_TYPE,
                    NsdManager.PROTOCOL_DNS_SD,
                    discoveryListener
                )
            }
        }
    }

    private fun stopDiscoverySafe(listener: NsdManager.DiscoveryListener) {
        runCatching { nsdManager.stopServiceDiscovery(listener) }
    }

    companion object {
        private const val SERVICE_TYPE = "_sharednum._tcp."
        private const val SERVICE_TYPE_ROOT = "_sharednum._tcp"
    }
}

private fun NsdServiceInfo.toEndpoint(): MdnsEndpoint {
    val hostAddress = host?.toV4Address() ?: throw IllegalStateException("Missing host address")
    val txtRecords = attributes?.mapValues { entry ->
        entry.value?.decodeToString().orEmpty()
    } ?: emptyMap()
    val path = txtRecords["path"].orEmpty().ifBlank { "/api" }
    return MdnsEndpoint(
        host = hostAddress,
        port = port,
        path = path
    )
}

private fun InetAddress.toV4Address(): String = hostAddress
