## Android Client

Jetpack Compose client that mirrors the PC timeline UI but keeps the PC FastAPI database as the only source of truth. The phone discovers the server via mDNS (_recurringevents._tcp), fetches the event list, and pushes changes back through the HTTP endpoints.

### Build & Run

1. Start python pc/server.py on the PC and note the printed bearer token.
2. Put the phone/emulator on the same WLAN. If multicast is blocked, note the PC's LAN IP (e.g. 192.168.0.42) for manual entry.
3. Open ndroid/ in Android Studio and run the pp configuration (API 24+).
4. On Android 13+, grant the Nearby Wi-Fi permission when prompted so mDNS works.
5. Tap the gear icon to open the connection sheet, paste the token, and optionally enter a manual host/port override. Hit **Apply** to save/close, then tap **Sync now** to pull events.
6. All edits (new event, edit, delete, mark done) hit the FastAPI endpoints immediately and then trigger another sync so the phone stays aligned with the PC database.

### UI overview

- **Top row**: New button, Day/Month/Year horizon picker, Sync now, and a gear icon that opens the hidden settings sheet.
- **Horizontal slider**: moves the visible time window; Today jumps back to an offset of zero.
- **Timeline rows**: cards on the left mirror the PC layout (name, cadence, due label, Delete + "Done today"). The canvas on the right shows the shared axis, completion dots, and upcoming due markers for the visible slice.
- **Vertical slider**: controls which set of rows (up to five at once) is visible.
- **Dialogs/sheets**: the event editor captures name/due date/frequency, while the connection sheet stores bearer token + optional host/port without cluttering the main timeline.

### Networking notes

- Discovery uses NsdManager to look for _recurringevents._tcp. When a manual host is supplied the resolver skips discovery and hits http://host:port/api/... directly.
- Every request attaches the bearer token; failures are surfaced as dismissible banners.
- The app does not cache data locally?after every change it re-runs GET /api/events?history_limit=12, so the PC remains the canonical store.

### Manual test flow

1. Populate a few events on the PC UI.
2. On Android, open the gear sheet, paste the token (and host if needed), apply, then tap **Sync now**. The list/timeline should mirror the PC ordering.
3. Create a new event on Android, save it, and wait for the automatic sync; confirm it appears on the PC.
4. Tap "Done today" on a mobile card; the due marker jumps ahead on both devices after sync.
5. Delete an event on Android and verify it disappears on the PC after the follow-up sync.
6. Test failure cases (wrong token, server offline) to ensure the error banner appears and no stale data is written.
