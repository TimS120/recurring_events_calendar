"""Conversion and first-sync support between the desktop SQLite cache and Firestore."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from data import list_events_with_history
from data.store import DEFAULT_DB_PATH, _connect, _db_lock


def export_local_calendar() -> dict[str, Any]:
    events = []
    for event, history in list_events_with_history(history_limit=365):
        events.append({
            "id": event.id, "name": event.name, "tag": event.tag, "details": event.details,
            "frequencyValue": event.frequency_value, "frequencyUnit": event.frequency_unit,
            "dueDate": event.due_date.isoformat(), "lastDone": event.last_done.isoformat() if event.last_done else None,
            "updatedAt": event.updated_at.isoformat(),
            "history": [{"id": item.id, "action": item.action, "actionDate": item.action_date.isoformat(),
                         "note": item.note, "scheduledDueDate": item.scheduled_due_date.isoformat() if item.scheduled_due_date else None}
                        for item in history],
        })
    return {"schemaVersion": 1, "updatedAt": datetime.utcnow().isoformat(), "events": events}


def merge_calendars(remote: dict[str, Any], local: dict[str, Any]) -> dict[str, Any]:
    """Merge two snapshots by event ID, keeping the most recently modified copy."""
    deleted_ids = {int(value) for value in remote.get("deletedIds", [])}
    deleted_ids.update(int(value) for value in local.get("deletedIds", []))
    merged = {int(event["id"]): event for event in remote.get("events", [])}
    for event in local.get("events", []):
        event_id = int(event["id"])
        if event_id in deleted_ids:
            continue
        existing = merged.get(event_id)
        if existing is None or _updated_timestamp(event) >= _updated_timestamp(existing):
            merged[event_id] = event
    for event_id in deleted_ids:
        merged.pop(event_id, None)
    return {
        "schemaVersion": 1,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "events": [merged[key] for key in sorted(merged)],
        "deletedIds": sorted(deleted_ids),
    }


def _updated_timestamp(event: dict[str, Any]) -> float:
    value = event.get("updatedAt")
    if isinstance(value, str):
        return datetime.fromisoformat(value).timestamp()
    raise ValueError("Calendar event is missing a canonical ISO updatedAt timestamp")


def import_cloud_calendar(calendar: dict[str, Any]) -> None:
    """Replace the desktop cache from the canonical Firestore snapshot."""
    events = calendar.get("events", [])
    with _db_lock, _connect(DEFAULT_DB_PATH) as conn:
        conn.execute("DELETE FROM event_history")
        conn.execute("DELETE FROM events")
        fallback_timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        for event in events:
            conn.execute(
                """INSERT INTO events (id, name, tag, details, frequency_value, frequency_unit, due_date,
                   last_done, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event["id"], event["name"], event.get("tag"), event.get("details"), event["frequencyValue"],
                 event["frequencyUnit"], event["dueDate"], event.get("lastDone"), event.get("updatedAt", fallback_timestamp),
                 event.get("updatedAt", fallback_timestamp)),
            )
            for history in event.get("history", []):
                conn.execute(
                    """INSERT INTO event_history (id, event_id, action, action_date, note, scheduled_due_date)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (history["id"], event["id"], history["action"], history["actionDate"], history.get("note"), history.get("scheduledDueDate")),
                )
        conn.commit()
