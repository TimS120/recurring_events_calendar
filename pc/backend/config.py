from __future__ import annotations

from pathlib import Path

from data import DATA_DIR

BASE_DIR = Path(__file__).resolve().parent
FILES_DIR = DATA_DIR
FILES_DIR.mkdir(parents=True, exist_ok=True)

TOKEN_PATH = FILES_DIR / "token.txt"
SERVER_ID_PATH = FILES_DIR / "server_id.txt"
API_PORT = 8000
SERVICE_TYPE = "_recurringevents._tcp.local."
INSTANCE_PREFIX = "RecurringEvents-PC"
