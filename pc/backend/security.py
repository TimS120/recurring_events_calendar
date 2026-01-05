from __future__ import annotations

import secrets
import uuid

from .config import SERVER_ID_PATH, TOKEN_PATH


def load_or_create_token() -> str:
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text(encoding="utf-8").strip()
    token = secrets.token_hex(16)
    TOKEN_PATH.write_text(token, encoding="utf-8")
    return token


def load_or_create_server_id() -> str:
    if SERVER_ID_PATH.exists():
        return SERVER_ID_PATH.read_text(encoding="utf-8").strip()
    sid = str(uuid.uuid4())
    SERVER_ID_PATH.write_text(sid, encoding="utf-8")
    return sid
