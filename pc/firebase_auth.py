"""Persistent Firebase email/password session for the desktop client."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import keyring
import requests
import truststore

# Use the Windows certificate store. This supports managed/home networks that
# install their trusted TLS root there instead of in certifi's bundled list.
truststore.inject_into_ssl()

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "data_files" / "firebase_config.json"
KEYRING_SERVICE = "recurring-events-calendar"


@dataclass(frozen=True)
class FirebaseConfig:
    api_key: str
    project_id: str


class FirebaseSession:
    def __init__(self, config: FirebaseConfig) -> None:
        self.config = config
        self._id_token: str | None = None
        self._uid: str | None = None

    @property
    def uid(self) -> str:
        if not self._uid:
            raise RuntimeError("Sign in first")
        return self._uid

    @property
    def is_signed_in(self) -> bool:
        return self._id_token is not None

    def sign_in(self, email: str, password: str) -> None:
        response = self._identity_request("accounts:signInWithPassword", email, password)
        _raise_for_firebase_error(response)
        self._accept_tokens(response.json())

    def create_account(self, email: str, password: str) -> None:
        response = self._identity_request("accounts:signUp", email, password)
        _raise_for_firebase_error(response)
        self._accept_tokens(response.json())

    def send_password_reset(self, email: str) -> None:
        response = requests.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={self.config.api_key}",
            json={"requestType": "PASSWORD_RESET", "email": email.strip()},
            timeout=20,
        )
        _raise_for_firebase_error(response)

    def restore(self) -> bool:
        refresh_token = keyring.get_password(KEYRING_SERVICE, self.config.project_id)
        if not refresh_token:
            return False
        response = requests.post(
            f"https://securetoken.googleapis.com/v1/token?key={self.config.api_key}",
            data={"grant_type": "refresh_token", "refresh_token": refresh_token}, timeout=20,
        )
        if not response.ok:
            keyring.delete_password(KEYRING_SERVICE, self.config.project_id)
            return False
        data = response.json()
        self._id_token, self._uid = data["id_token"], data["user_id"]
        keyring.set_password(KEYRING_SERVICE, self.config.project_id, data["refresh_token"])
        return True

    def token(self) -> str:
        if not self._id_token:
            raise RuntimeError("Sign in first")
        return self._id_token

    def _accept_tokens(self, payload: dict[str, Any]) -> None:
        self._id_token, self._uid = payload["idToken"], payload["localId"]
        keyring.set_password(KEYRING_SERVICE, self.config.project_id, payload["refreshToken"])

    def _identity_request(self, action: str, email: str, password: str) -> requests.Response:
        return requests.post(
            f"https://identitytoolkit.googleapis.com/v1/{action}?key={self.config.api_key}",
            json={"email": email.strip(), "password": password, "returnSecureToken": True}, timeout=20,
        )


def load_config() -> FirebaseConfig:
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            "Firebase configuration is missing. Copy firebase_config.example.json "
            "to firebase_config.json and enter this project's Firebase values."
        )
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return FirebaseConfig(api_key=raw["api_key"], project_id=raw["project_id"])


def _raise_for_firebase_error(response: requests.Response) -> None:
    """Turn Firebase Auth's JSON response into a useful local error message."""
    if response.ok:
        return
    try:
        message = response.json().get("error", {}).get("message")
    except ValueError:
        message = response.text
    if message:
        raise RuntimeError(f"Firebase account error {response.status_code}: {message}")
    response.raise_for_status()
