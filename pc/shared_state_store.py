
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, Tuple

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "shared_state.db"

_db_lock = threading.Lock()


def _connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Create the database and seed the initial state if it is empty."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _db_lock, _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shared_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                value INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                source_id TEXT NOT NULL
            )
            """
        )
        row = conn.execute("SELECT id FROM shared_state WHERE id = 1").fetchone()
        if row is None:
            now = current_epoch_ms()
            conn.execute(
                "INSERT INTO shared_state (id, value, updated_at, source_id) VALUES (1, ?, ?, ?)",
                (0, now, "server")
            )
        conn.commit()


def current_epoch_ms() -> int:
    return int(time.time() * 1000)


def get_state(db_path: Path = DEFAULT_DB_PATH) -> Dict[str, int | str]:
    with _db_lock, _connect(db_path) as conn:
        row = conn.execute(
            "SELECT value, updated_at, source_id FROM shared_state WHERE id = 1"
        ).fetchone()
        if row is None:
            initialize_database(db_path)
            return get_state(db_path)
        return {"value": int(row["value"]), "updated_at": int(row["updated_at"]), "source_id": row["source_id"]}


def _should_replace(incoming: Tuple[int, int, str], current: Tuple[int, int, str]) -> bool:
    in_updated = incoming[1]
    cur_updated = current[1]
    if in_updated > cur_updated:
        return True
    if in_updated < cur_updated:
        return False
    return incoming[2] > current[2]


def apply_lww_update(
    value: int,
    updated_at: int,
    source_id: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> Dict[str, int | str]:
    """Apply incoming state using Last-Write-Wins semantics and return the persisted state."""
    with _db_lock, _connect(db_path) as conn:
        row = conn.execute(
            "SELECT value, updated_at, source_id FROM shared_state WHERE id = 1"
        ).fetchone()
        if row is None:
            initialize_database(db_path)
            row = conn.execute(
                "SELECT value, updated_at, source_id FROM shared_state WHERE id = 1"
            ).fetchone()
        current = (int(row["value"]), int(row["updated_at"]), row["source_id"])
        incoming = (int(value), int(updated_at), str(source_id))
        if _should_replace(incoming, current):
            conn.execute(
                "UPDATE shared_state SET value = ?, updated_at = ?, source_id = ? WHERE id = 1",
                (incoming[0], incoming[1], incoming[2])
            )
            conn.commit()
            current = incoming
        return {"value": current[0], "updated_at": current[1], "source_id": current[2]}


def apply_local_update(
    value: int,
    source_id: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> Dict[str, int | str]:
    """Forcefully update the state using the current timestamp for local edits."""
    now = current_epoch_ms()
    return apply_lww_update(value, now, source_id, db_path)
