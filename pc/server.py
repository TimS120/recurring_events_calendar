from __future__ import annotations

from backend.app import (
    app,
    create_uvicorn_config,
    create_uvicorn_server,
    run_server,
    start_server_in_thread,
)
from backend.config import API_PORT
from backend.models import (
    EventCompletionRequest,
    EventCreateRequest,
    EventHistoryResponse,
    EventUpdateRequest,
    EventWithHistoryResponse,
    FrequencyUnit,
    HealthResponse,
)

__all__ = [
    "API_PORT",
    "app",
    "create_uvicorn_config",
    "create_uvicorn_server",
    "EventCompletionRequest",
    "EventCreateRequest",
    "EventHistoryResponse",
    "EventUpdateRequest",
    "EventWithHistoryResponse",
    "FrequencyUnit",
    "HealthResponse",
    "run_server",
    "start_server_in_thread",
]


if __name__ == "__main__":
    run_server()
