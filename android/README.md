## Android Client

Shared integer client implemented with Jetpack Compose, Room, OkHttp, and `NsdManager` for zeroconf discovery.

### Build & Run

1. Start the PC server (`python pc/server.py`) and note the printed bearer token. If mDNS is blocked in your environment, enter the PC's LAN IP/hostname (e.g., `192.168.178.22`) and port (default `8000`) in the app's fields; otherwise leave them blank for auto-discovery.
2. Open the `android/` directory in Android Studio (or run `./gradlew :app:assembleDebug` with a configured JDK/SDK).
3. Connect an Android device (API 24+) via USB debugging or launch an emulator on the same WLAN as the PC.
4. Run the `app` configuration. On first launch, grant the Nearby Wi-Fi permission on Android 13+ when prompted.
5. In the app, paste the bearer token, optionally set the manual host/port override, use **Apply locally** to change the Room row, and tap **Sync now** to push/pull with the FastAPI server.

### Permissions

- `INTERNET`, `ACCESS_NETWORK_STATE`, `ACCESS_WIFI_STATE`, `CHANGE_WIFI_MULTICAST_STATE`
- `NEARBY_WIFI_DEVICES` (Android 13+, requested at runtime)

### Manual Test Flow

1. PC UI sets value to 10 and shows 10.
2. Android enters the token, optionally the manual host/port, taps **Sync now** → sees 10.
3. Android edits to 42 locally, hits **Apply locally**, then **Sync now** → pushes 42 to the server.
4. PC UI refresh shows 42.
5. Try an incorrect token or stop the PC server to verify error handling. Use the manual host/port fields if discovery fails.
