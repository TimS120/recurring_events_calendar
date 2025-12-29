# Recurring Events Calendar

Prototype for a shared integer value that is synchronized between a PC FastAPI server+UI and an Android client over the same WLAN.

## PC application (FastAPI + Tkinter)

### Requirements

- Python 3.11+
- `pip install -r pc/requirements.txt`

### Running the server

```bash
cd pc
python server.py
```

On the first launch the server:

- Creates `shared_state.db` and seeds the shared record.
- Generates `token.txt` with a random bearer token (printed to the console).
- Generates `server_id.txt` (for mDNS/health responses).
- Starts FastAPI on `0.0.0.0:8000`.
- Advertises an mDNS service `_sharednum._tcp.local` so other devices discover it without hardcoded IPs.

Allow inbound TCP 8000 on your computer's private-network firewall profile so Android devices on the same WLAN can reach the API.

### Running the PC UI

In a second terminal:

```bash
cd pc
python py_ui.py
```

The Tkinter window shows the current number (read from `shared_state.db`), lets you enter a new integer, and has:

- **Apply locally** - updates the SQLite record with the current machine timestamp and `source_id="pc-ui"`. FastAPI immediately exposes that value via `/api/state`.
- **Refresh** - re-reads the database so you can see changes pushed by Android.

### Manual test workflow

1. Start the server and note the printed token.
2. Launch the PC UI, apply a local value (e.g., 10) and confirm it shows up.
3. Configure the Android client with the mDNS-discovered host and token.
4. From Android, sync to pull 10, change to (e.g.) 42 locally, then sync; observe that the PC UI refresh shows 42 after Android pushes.
5. For negative tests, try an incorrect token (FastAPI returns HTTP 401) or turn the PC server off to see Android report discovery/fetch errors.

## Android app

The `android/` module is a complete Android Studio project using Jetpack Compose + Room + OkHttp. The UI exposes:

- Token field (persisted) and device `source_id`.
- Optional manual host/port fields to bypass mDNS (leave blank to auto-discover `_sharednum._tcp` services).
- Local Room-backed value with **Apply locally** and **Sync now** buttons.
- Connection status (resolved host:port/path), last sync time, last authoritative `source_id`, and surfaced errors.

Sync uses `NsdManager` to discover `_sharednum._tcp`, then GETs/POSTs `/api/state` with the bearer token and Last-Write-Wins logic. When manual host/port is supplied, the app skips discovery and targets that endpoint directly.

See `android/README.md` for build/run instructions, permission requirements (INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE, CHANGE_WIFI_MULTICAST_STATE, NEARBY_WIFI_DEVICES), and the acceptance walkthrough.
