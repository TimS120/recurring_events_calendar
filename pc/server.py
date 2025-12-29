from __future__ import annotations

import secrets
import socket
import uuid
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, constr
from zeroconf import IPVersion, ServiceInfo, Zeroconf

from event_store import (
    EventRecord,
    HistoryRecord,
    create_event,
    delete_event,
    get_event,
    initialize_database,
    list_event_history,
    list_events,
    list_events_with_history,
    mark_event_done,
    update_event,
)

BASE_DIR = Path(__file__).resolve().parent
TOKEN_PATH = BASE_DIR / "token.txt"
SERVER_ID_PATH = BASE_DIR / "server_id.txt"
API_PORT = 8000
SERVICE_TYPE = "_recurringevents._tcp.local."
INSTANCE_PREFIX = "RecurringEvents-PC"

app = FastAPI(title="Recurring Events Server", version="1.0.0")
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


class FrequencyUnit(str, Enum):
    days = "days"
    weeks = "weeks"
    months = "months"
    years = "years"


class EventBase(BaseModel):
    name: constr(min_length=1, max_length=128)
    due_date: date
    frequency_value: int = Field(..., gt=0, le=1000)
    frequency_unit: FrequencyUnit


class EventCreateRequest(EventBase):
    pass


class EventUpdateRequest(BaseModel):
    name: Optional[constr(min_length=1, max_length=128)]
    due_date: Optional[date]
    frequency_value: Optional[int] = Field(None, gt=0, le=1000)
    frequency_unit: Optional[FrequencyUnit]


class EventCompletionRequest(BaseModel):
    done_date: Optional[date] = Field(None, description="Override completion date (defaults to today)")


class EventHistoryResponse(BaseModel):
    id: int
    event_id: int
    action: str
    action_date: date
    note: Optional[str]


class EventResponse(BaseModel):
    id: int
    name: str
    frequency_value: int
    frequency_unit: FrequencyUnit
    due_date: date
    last_done: Optional[date]
    created_at: datetime
    updated_at: datetime
    is_overdue: bool


class EventWithHistoryResponse(EventResponse):
    history: List[EventHistoryResponse] = []


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


def event_to_response(record: EventRecord, history: Optional[List[HistoryRecord]] = None) -> EventWithHistoryResponse:
    return EventWithHistoryResponse(
        id=record.id,
        name=record.name,
        frequency_value=record.frequency_value,
        frequency_unit=FrequencyUnit(record.frequency_unit),
        due_date=record.due_date,
        last_done=record.last_done,
        created_at=record.created_at,
        updated_at=record.updated_at,
        is_overdue=record.is_overdue(),
        history=[history_to_response(item) for item in (history or [])],
    )


def history_to_response(record: HistoryRecord) -> EventHistoryResponse:
    return EventHistoryResponse(
        id=record.id,
        event_id=record.event_id,
        action=record.action,
        action_date=record.action_date,
        note=record.note,
    )


@app.on_event("startup")
async def startup_event() -> None:
    global token_value, server_id
    initialize_database()
    token_value = load_or_create_token()
    server_id = load_or_create_server_id()
    print("=" * 40)
    print("Recurring Events Server")
    print(f"Token: {token_value}")
    print(f"Server ID: {server_id}")
    print("=" * 40)
    register_mdns_service()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    unregister_mdns_service()


@app.get("/api/health", response_model=HealthResponse, dependencies=[Depends(verify_token)])
async def health() -> HealthResponse:
    return HealthResponse(server_time=int(datetime.utcnow().timestamp() * 1000), server_id=server_id or "")


@app.get(
    "/api/events",
    response_model=List[EventWithHistoryResponse],
    dependencies=[Depends(verify_token)],
)
async def list_events_api(
    history_limit: int = Query(5, ge=0, le=365, description="Include up to this many history items per event"),
) -> List[EventWithHistoryResponse]:
    if history_limit > 0:
        records = list_events_with_history(history_limit=history_limit)
    else:
        records = [(event, []) for event in list_events()]
    return [event_to_response(event, history) for event, history in records]


@app.post(
    "/api/events",
    response_model=EventWithHistoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_token)],
)
async def create_event_api(payload: EventCreateRequest) -> EventWithHistoryResponse:
    record = create_event(
        name=payload.name,
        due_date=payload.due_date,
        frequency_value=payload.frequency_value,
        frequency_unit=payload.frequency_unit.value,
    )
    return event_to_response(record, [])


@app.get(
    "/api/events/{event_id}",
    response_model=EventWithHistoryResponse,
    dependencies=[Depends(verify_token)],
)
async def get_event_api(event_id: int, history_limit: int = Query(5, ge=0, le=365)) -> EventWithHistoryResponse:
    record = get_event(event_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    history = list_event_history(event_id, limit=history_limit) if history_limit > 0 else []
    return event_to_response(record, history)


@app.put(
    "/api/events/{event_id}",
    response_model=EventWithHistoryResponse,
    dependencies=[Depends(verify_token)],
)
async def update_event_api(event_id: int, payload: EventUpdateRequest) -> EventWithHistoryResponse:
    data = payload.dict(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")
    freq_unit = data.get("frequency_unit")
    try:
        record = update_event(
            event_id,
            name=data.get("name"),
            due_date=data.get("due_date"),
            frequency_value=data.get("frequency_value"),
            frequency_unit=freq_unit.value if freq_unit else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    history = list_event_history(event_id, limit=5)
    return event_to_response(record, history)


@app.delete(
    "/api/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_token)],
)
async def delete_event_api(event_id: int) -> None:
    if get_event(event_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    delete_event(event_id)


@app.post(
    "/api/events/{event_id}/complete",
    response_model=EventWithHistoryResponse,
    dependencies=[Depends(verify_token)],
)
async def complete_event_api(event_id: int, payload: EventCompletionRequest | None = None) -> EventWithHistoryResponse:
    try:
        record = mark_event_done(event_id, done_date=payload.done_date if payload else None)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    history = list_event_history(event_id, limit=5)
    return event_to_response(record, history)


@app.get(
    "/api/events/{event_id}/history",
    response_model=List[EventHistoryResponse],
    dependencies=[Depends(verify_token)],
)
async def event_history_api(
    event_id: int,
    limit: Optional[int] = Query(None, ge=1, le=1000),
) -> List[EventHistoryResponse]:
    if get_event(event_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    history = list_event_history(event_id, limit=limit)
    return [history_to_response(record) for record in history]


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=API_PORT)
