"""Small authenticated Firestore document store used by the desktop client."""
from __future__ import annotations

from typing import Any

import requests

from firebase_auth import FirebaseSession


class FirestoreStore:
    def __init__(self, session: FirebaseSession) -> None:
        self.session = session

    def read_calendar(self) -> dict[str, Any] | None:
        response = requests.get(self._url(), headers=self._headers(), timeout=20)
        if response.status_code == 404:
            return None
        _raise_for_status(response)
        return _decode_document_fields(response.json().get("fields", {}))

    def write_calendar(self, calendar: dict[str, Any]) -> None:
        response = requests.patch(
            self._url(),
            headers=self._headers(),
            json={"fields": _encode_document_fields(calendar)},
            timeout=20,
        )
        _raise_for_status(response)

    def clear_calendar(self) -> None:
        """Replace the shared calendar with a deliberate empty current-format snapshot."""
        self.write_calendar({"schemaVersion": 1, "events": []})

    def _url(self) -> str:
        return ("https://firestore.googleapis.com/v1/projects/" + self.session.config.project_id +
                "/databases/(default)/documents/users/" + self.session.uid + "/calendars/main")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.session.token()}", "Content-Type": "application/json"}


def _encode(value: Any) -> dict[str, Any]:
    if value is None: return {"nullValue": None}
    if isinstance(value, bool): return {"booleanValue": value}
    if isinstance(value, int): return {"integerValue": str(value)}
    if isinstance(value, float): return {"doubleValue": value}
    if isinstance(value, str): return {"stringValue": value}
    if isinstance(value, list): return {"arrayValue": {"values": [_encode(item) for item in value]}}
    if isinstance(value, dict): return {"mapValue": {"fields": {key: _encode(item) for key, item in value.items()}}}
    raise TypeError(type(value))


def _encode_document_fields(document: dict[str, Any]) -> dict[str, Any]:
    """A Firestore Document has a field map, not a Value wrapper at its root."""
    return {name: _encode(value) for name, value in document.items()}


def _decode(value: Any) -> Any:
    if not value: return {}
    key, raw = next(iter(value.items()))
    if key == "nullValue": return None
    if key == "booleanValue": return raw
    if key == "integerValue": return int(raw)
    if key == "doubleValue": return raw
    if key == "stringValue": return raw
    if key == "arrayValue": return [_decode(item) for item in raw.get("values", [])]
    if key == "mapValue": return {name: _decode(item) for name, item in raw.get("fields", {}).items()}
    raise ValueError(f"Unsupported Firestore value: {key}")


def _decode_document_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {name: _decode(value) for name, value in fields.items()}


def _raise_for_status(response: requests.Response) -> None:
    """Expose Firebase's useful JSON error instead of requests' generic HTTP text."""
    if response.ok:
        return
    try:
        detail = response.json().get("error", {}).get("message")
    except ValueError:
        detail = response.text
    if detail:
        raise RuntimeError(f"Firebase Firestore error {response.status_code}: {detail}")
    response.raise_for_status()
