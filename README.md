# Recurring Events Calendar

Cross-platform playground for planning recurring chores and reminders. The PC side now provides a FastAPI backend plus a Tkinter dashboard that visualizes events on a configurable timeline. The Android client will be updated next to use the new API, but you can already explore the full PC experience.

## PC application (FastAPI + Tkinter)

### Requirements

- Python 3.11+
- `pip install -r pc/requirements.txt`


On first launch the server:

- Creates `events.db` with `events` + `event_history` tables.
- Generates `token.txt` with a random bearer token (printed to the console).
- Generates `server_id.txt` (used by health/mDNS).

### Running the UI
  1. Start the PC app (pc/py_ui.py)
  2. In another terminal run:
  - cloudflared tunnel --url http://localhost:8000
  3. Copy the https://...trycloudflare.com URL
  4. In the Android app Settings:
  - Set “Server URL” to that URL (e.g. https://random.trycloudflare.com)
  - Keep the bearer token the same as the PC prints
  - Tap Apply
  5. Sync on both devices


Features:

- **New** dialog to define an event name, first due date, and frequency (days/weeks/months/years).
- Horizon selector (Day/Month/Year) that changes the overall span of the shared timeline.
- Horizontal slider to move the visible time window while keeping the axis on top of the event rows.
- Global axis row plus a per-event timeline that shows past completions (green dots) and upcoming due dates (blue/red markers for future/overdue occurrences).
- Left-hand event cards (click to edit) showing the name, cadence, and current status, plus a “Mark done today” shortcut that resets the timer starting from the completion date.
- Vertical slider to choose which rows are visible when you have more than six events.

Events are sorted by the residual time to the next due date. Overdue rows remain highlighted until you mark them as complete, at which point the due date jumps forward according to the defined frequency.

### Manual walkthrough

1. Start `server.py` and note the printed bearer token.
2. Launch `py_ui.py`.
3. Use **New Event** to add a few chores with different cadences.
4. Drag the horizontal slider to inspect near-term vs long-term plans.
5. Use the event cards to edit cadence or click **Mark done today** to advance a task, then watch the due marker jump ahead on the timeline.

## HTTP API overview

Authenticated with the printed bearer token (Authorization: `Bearer <token>`):

- `GET /api/events?history_limit=5` — list events sorted by next due date (includes a limited history array for timeline markers).
- `POST /api/events` — create a new event.
- `GET /api/events/{id}` — fetch a single event plus optional history.
- `PUT /api/events/{id}` — update name, due date, or frequency.
- `DELETE /api/events/{id}` — remove an event (history deleted via cascade).
- `POST /api/events/{id}/complete` — mark an event done (optional payload `{ "done_date": "YYYY-MM-DD" }`).
- `GET /api/events/{id}/history?limit=50` — fetch the completion ledger.

All timestamps are stored in UTC inside `events.db`, and the FastAPI service still exposes `/api/health` for readiness checks.

## Android app

`android/` now ships a Compose client that mirrors the PC layout:

- **Settings gear** reveals the bearer token + optional host/port sheet so it never clutters the main timeline. Leave host blank to auto-discover `_recurringevents._tcp`.
- **New / Sync / Horizon** controls mirror Tkinter. Horizontal and vertical sliders control the visible time window and event rows, keeping the shared axis at the top.
- The cards/timeline rows stay aligned: tap a card to edit, use “Done today” to advance, or delete it. The right-hand canvas shows completions (green dots) and due markers (blue/red) just like the desktop build.
- Every change immediately hits the FastAPI endpoints and then triggers a fresh `/api/events` sync, so the PC database stays authoritative.

See `android/README.md` for build instructions, permissions, and the full walkthrough.
