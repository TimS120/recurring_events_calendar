from __future__ import annotations

import threading
from datetime import datetime
from typing import List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from data import (
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

from .config import API_PORT
from .mdns import register_mdns_service, set_mdns_enabled, unregister_mdns_service
from .models import (
    EventCompletionRequest,
    EventCreateRequest,
    EventHistoryResponse,
    EventUpdateRequest,
    EventWithHistoryResponse,
    HealthResponse,
    event_to_response,
    history_to_response,
)
from .security import load_or_create_server_id, load_or_create_token

app = FastAPI(title="Recurring Events Server", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

auth_scheme = HTTPBearer(auto_error=False)

token_value: Optional[str] = None
server_id: Optional[str] = None


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
    print("Recurring Events Server")
    print(f"Token: {token_value}")
    print(f"Server ID: {server_id}")
    print("=" * 40)
    register_mdns_service(server_id)


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
        tag=payload.tag,
        details=payload.details,
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
    details_param: Optional[str]
    if "details" in data:
        raw_details = data.get("details")
        details_param = "" if raw_details is None else raw_details
    else:
        details_param = None
    try:
        record = update_event(
            event_id,
            name=data.get("name"),
            tag=data.get("tag"),
            details=details_param,
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


def create_uvicorn_config(
    *,
    host: str = "0.0.0.0",
    port: int = API_PORT,
    log_level: str = "info",
) -> uvicorn.Config:
    return uvicorn.Config(app=app, host=host, port=port, log_level=log_level)


def create_uvicorn_server(
    *,
    host: str = "0.0.0.0",
    port: int = API_PORT,
    log_level: str = "info",
) -> uvicorn.Server:
    return uvicorn.Server(create_uvicorn_config(host=host, port=port, log_level=log_level))


def run_server(*, host: str = "0.0.0.0", port: int = API_PORT, log_level: str = "info") -> None:
    uvicorn.run(app=app, host=host, port=port, log_level=log_level)


def start_server_in_thread(
    *,
    host: str = "0.0.0.0",
    port: int = API_PORT,
    log_level: str = "info",
    enable_mdns: bool = True,
) -> tuple[uvicorn.Server, threading.Thread]:
    set_mdns_enabled(enable_mdns)
    server = create_uvicorn_server(host=host, port=port, log_level=log_level)
    thread = threading.Thread(target=server.run, name="RecurringEventsServer", daemon=True)
    thread.start()
    return server, thread
