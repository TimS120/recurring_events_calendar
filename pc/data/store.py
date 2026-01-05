from __future__ import annotations

import calendar
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .models import EventRecord, HistoryRecord

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data_files"
DEFAULT_DB_PATH = DATA_DIR / "events.db"
DATE_FMT = "%Y-%m-%d"
TS_FMT = "%Y-%m-%dT%H:%M:%S"
FREQUENCY_UNITS: Tuple[str, ...] = ("days", "weeks", "months", "years")

_db_lock = threading.Lock()


def _connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _utcnow() -> datetime:
    return datetime.utcnow()


def _serialize_date(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


def _serialize_datetime(value: datetime) -> str:
    return value.strftime(TS_FMT)


def _parse_date(raw: Optional[str]) -> Optional[date]:
    return datetime.strptime(raw, DATE_FMT).date() if raw else None


def _parse_required_date(raw: str) -> date:
    return datetime.strptime(raw, DATE_FMT).date()


def _parse_datetime(raw: str) -> datetime:
    return datetime.strptime(raw, TS_FMT)


def _row_to_event(row: sqlite3.Row) -> EventRecord:
    return EventRecord(
        id=row["id"],
        name=row["name"],
        tag=row["tag"] if "tag" in row.keys() else None,
        details=row["details"] if "details" in row.keys() else None,
        frequency_value=row["frequency_value"],
        frequency_unit=row["frequency_unit"],
        due_date=_parse_required_date(row["due_date"]),
        last_done=_parse_date(row["last_done"]),
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
    )


def _row_to_history(row: sqlite3.Row) -> HistoryRecord:
    return HistoryRecord(
        id=row["id"],
        event_id=row["event_id"],
        action=row["action"],
        action_date=_parse_required_date(row["action_date"]),
        note=row["note"],
    )


def initialize_database(db_path: Path = DEFAULT_DB_PATH) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _db_lock, _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tag TEXT,
                details TEXT,
                frequency_value INTEGER NOT NULL CHECK (frequency_value > 0),
                frequency_unit TEXT NOT NULL CHECK (
                    frequency_unit IN ('days','weeks','months','years')
                ),
                due_date TEXT NOT NULL,
                last_done TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS event_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                action_date TEXT NOT NULL,
                note TEXT,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_event_history_event_id_date
                ON event_history(event_id, action_date DESC);
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(events)")}
        if "tag" not in columns:
            conn.execute("ALTER TABLE events ADD COLUMN tag TEXT")
        if "details" not in columns:
            conn.execute("ALTER TABLE events ADD COLUMN details TEXT")
        conn.commit()


def _add_months(base: date, months: int) -> date:
    if months == 0:
        return base
    month = base.month - 1 + months
    year = base.year + month // 12
    month = month % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _add_years(base: date, years: int) -> date:
    try:
        return base.replace(year=base.year + years)
    except ValueError:
        return base.replace(month=2, day=28, year=base.year + years)


def add_frequency(base: date, value: int, unit: str) -> date:
    if unit == "days":
        return base + timedelta(days=value)
    if unit == "weeks":
        return base + timedelta(weeks=value)
    if unit == "months":
        return _add_months(base, value)
    if unit == "years":
        return _add_years(base, value)
    raise ValueError(f"Unsupported frequency unit: {unit}")


def list_events(db_path: Path = DEFAULT_DB_PATH) -> List[EventRecord]:
    with _db_lock, _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, name, tag, details, frequency_value, frequency_unit, due_date,
                   last_done, created_at, updated_at
            FROM events
            ORDER BY due_date ASC, name COLLATE NOCASE ASC
            """
        ).fetchall()
    return [_row_to_event(row) for row in rows]


def get_event(event_id: int, db_path: Path = DEFAULT_DB_PATH) -> Optional[EventRecord]:
    with _db_lock, _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, name, tag, details, frequency_value, frequency_unit, due_date,
                   last_done, created_at, updated_at
            FROM events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()
    return _row_to_event(row) if row else None


def create_event(
    name: str,
    tag: Optional[str],
    details: Optional[str],
    due_date: date,
    frequency_value: int,
    frequency_unit: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> EventRecord:
    if frequency_unit not in FREQUENCY_UNITS:
        raise ValueError(f"Frequency unit must be one of {FREQUENCY_UNITS}")
    now = _utcnow()
    with _db_lock, _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO events (
                name, tag, details, frequency_value, frequency_unit, due_date,
                last_done, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                tag.strip() if tag and tag.strip() else None,
                details.strip() if details and details.strip() else None,
                frequency_value,
                frequency_unit,
                due_date.strftime(DATE_FMT),
                None,
                _serialize_datetime(now),
                _serialize_datetime(now),
            ),
        )
        event_id = cur.lastrowid
        conn.commit()
    record = get_event(event_id, db_path)
    if record is None:
        raise RuntimeError("Failed to create event")
    return record


def update_event(
    event_id: int,
    *,
    name: Optional[str] = None,
    tag: Optional[str] = None,
    details: Optional[str] = None,
    due_date: Optional[date] = None,
    frequency_value: Optional[int] = None,
    frequency_unit: Optional[str] = None,
    last_done: Optional[date] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> EventRecord:
    record = get_event(event_id, db_path)
    if record is None:
        raise ValueError(f"Event {event_id} does not exist")
    fields = []
    values: List[object] = []
    if name is not None:
        fields.append("name = ?")
        values.append(name.strip())
    if tag is not None:
        fields.append("tag = ?")
        cleaned = tag.strip()
        values.append(cleaned if cleaned else None)
    if details is not None:
        fields.append("details = ?")
        cleaned_details = details.strip()
        values.append(cleaned_details if cleaned_details else None)
    if due_date is not None:
        fields.append("due_date = ?")
        values.append(due_date.strftime(DATE_FMT))
    if frequency_value is not None:
        fields.append("frequency_value = ?")
        values.append(frequency_value)
    if frequency_unit is not None:
        if frequency_unit not in FREQUENCY_UNITS:
            raise ValueError(f"Frequency unit must be one of {FREQUENCY_UNITS}")
        fields.append("frequency_unit = ?")
        values.append(frequency_unit)
    if last_done is not None:
        fields.append("last_done = ?")
        values.append(last_done.strftime(DATE_FMT))
    if not fields:
        return record
    fields.append("updated_at = ?")
    values.append(_serialize_datetime(_utcnow()))
    values.append(event_id)
    with _db_lock, _connect(db_path) as conn:
        conn.execute(
            f"UPDATE events SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
    updated = get_event(event_id, db_path)
    if updated is None:
        raise RuntimeError("Failed to fetch updated event")
    return updated


def delete_event(event_id: int, db_path: Path = DEFAULT_DB_PATH) -> None:
    with _db_lock, _connect(db_path) as conn:
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()


def record_history(
    event_id: int,
    action: str,
    action_date_value: date,
    note: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> HistoryRecord:
    with _db_lock, _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO event_history (event_id, action, action_date, note)
            VALUES (?, ?, ?, ?)
            """,
            (
                event_id,
                action,
                action_date_value.strftime(DATE_FMT),
                note,
            ),
        )
        history_id = cur.lastrowid
        conn.commit()
        row = conn.execute(
            """
            SELECT id, event_id, action, action_date, note
            FROM event_history
            WHERE id = ?
            """,
            (history_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError("Failed to record history")
    return _row_to_history(row)


def mark_event_done(
    event_id: int,
    *,
    done_date: Optional[date] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> EventRecord:
    event = get_event(event_id, db_path)
    if event is None:
        raise ValueError(f"Event {event_id} does not exist")
    done = done_date or date.today()
    new_due = add_frequency(done, event.frequency_value, event.frequency_unit)
    now = _utcnow()
    with _db_lock, _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE events
            SET last_done = ?, due_date = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                done.strftime(DATE_FMT),
                new_due.strftime(DATE_FMT),
                _serialize_datetime(now),
                event_id,
            ),
        )
        conn.execute(
            """
            INSERT INTO event_history (event_id, action, action_date)
            VALUES (?, 'done', ?)
            """,
            (event_id, done.strftime(DATE_FMT)),
        )
        conn.commit()
    updated = get_event(event_id, db_path)
    if updated is None:
        raise RuntimeError("Failed to update event after completion")
    return updated


def _fetch_history_for_event_ids(
    event_ids: Sequence[int],
    limit_per_event: int,
    db_path: Path = DEFAULT_DB_PATH,
) -> Dict[int, List[HistoryRecord]]:
    if not event_ids:
        return {}
    placeholders = ",".join("?" for _ in event_ids)
    with _db_lock, _connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT id, event_id, action, action_date, note
            FROM event_history
            WHERE event_id IN ({placeholders})
            ORDER BY event_id ASC, action_date DESC
            """,
            event_ids,
        ).fetchall()
    histories: Dict[int, List[HistoryRecord]] = {event_id: [] for event_id in event_ids}
    for row in rows:
        bucket = histories[row["event_id"]]
        if len(bucket) < limit_per_event:
            bucket.append(_row_to_history(row))
    return histories


def list_events_with_history(
    *,
    history_limit: int = 10,
    db_path: Path = DEFAULT_DB_PATH,
) -> List[tuple[EventRecord, List[HistoryRecord]]]:
    events = list_events(db_path)
    event_ids = [event.id for event in events]
    history_map = _fetch_history_for_event_ids(event_ids, history_limit, db_path)
    return [(event, history_map.get(event.id, [])) for event in events]


def list_event_history(
    event_id: int,
    *,
    limit: Optional[int] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> List[HistoryRecord]:
    query = """
        SELECT id, event_id, action, action_date, note
        FROM event_history
        WHERE event_id = ?
        ORDER BY action_date DESC
    """
    params: List[object] = [event_id]
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    with _db_lock, _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_history(row) for row in rows]
