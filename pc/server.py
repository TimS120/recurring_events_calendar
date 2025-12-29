from __future__ import annotations

import secrets
import socket
import uuid
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from zeroconf import IPVersion, ServiceInfo, Zeroconf

from shared_state_store import (
    apply_lww_update,
    current_epoch_ms,
    get_state,
    initialize_database,
)

BASE_DIR = Path(__file__).resolve().parent
TOKEN_PATH = BASE_DIR / "token.txt"
SERVER_ID_PATH = BASE_DIR / "server_id.txt"
API_PORT = 8000
SERVICE_TYPE = "_sharednum._tcp.local."
INSTANCE_PREFIX = "SharedNum-PC"

app = FastAPI(title="Shared Number Server", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

auth_scheme = HTTPBearer(auto_error=False)

zeroconf: Optional[Zeroconf] = None
service_info: Optional[ServiceInfo] = None
server_id: Optional[str] = None
token_value: Optional[str] = None


class StateResponse(BaseModel):
    value: int
    updated_at: int = Field(..., description="UTC epoch milliseconds")
    source_id: str


class StateUpdateRequest(BaseModel):
    value: int
    updated_at: int
    source_id: str


class HealthResponse(BaseModel):
    status: str = "ok"
    server_time: int
    server_id: str


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


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def register_mdns_service() -> None:
    global zeroconf, service_info
    try:
        zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        hostname = socket.gethostname()
        instance_name = f"{INSTANCE_PREFIX}-{hostname}.{SERVICE_TYPE}"
        ip_address = socket.inet_aton(get_local_ip())
        properties = {
            b"path": b"/api",
            b"proto": b"1",
            b"server_id": (server_id or "").encode("utf-8"),
        }
        service_info = ServiceInfo(
            type_=SERVICE_TYPE,
            name=instance_name,
            addresses=[ip_address],
            port=API_PORT,
            properties=properties,
        )
        zeroconf.register_service(service_info)
        print(f"[mDNS] Advertised {instance_name} on port {API_PORT}")
    except Exception as exc:  # noqa: BLE001
        import traceback

        print(f"[mDNS] Registration failed: {exc!r}")
        traceback.print_exc()
        if zeroconf:
            zeroconf.close()
        zeroconf = None
        service_info = None


def unregister_mdns_service() -> None:
    global zeroconf, service_info
    if zeroconf:
        if service_info:
            zeroconf.unregister_service(service_info)
        zeroconf.close()
    zeroconf = None
    service_info = None


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    if credentials.credentials != token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


@app.on_event("startup")
async def startup_event() -> None:
    global token_value, server_id
    initialize_database()
    token_value = load_or_create_token()
    server_id = load_or_create_server_id()
    print("=" * 40)
    print("Shared Number Server")
    print(f"Token: {token_value}")
    print(f"Server ID: {server_id}")
    print("=" * 40)
    register_mdns_service()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    unregister_mdns_service()


@app.get("/api/health", response_model=HealthResponse, dependencies=[Depends(verify_token)])
async def health() -> HealthResponse:
    return HealthResponse(server_time=current_epoch_ms(), server_id=server_id or "")


@app.get("/api/state", response_model=StateResponse, dependencies=[Depends(verify_token)])
async def read_state() -> StateResponse:
    state = get_state()
    return StateResponse(**state)


@app.post("/api/state", response_model=StateResponse, dependencies=[Depends(verify_token)])
async def update_state(payload: StateUpdateRequest) -> StateResponse:
    state = apply_lww_update(
        value=payload.value,
        updated_at=payload.updated_at,
        source_id=payload.source_id,
    )
    return StateResponse(**state)


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=API_PORT)
