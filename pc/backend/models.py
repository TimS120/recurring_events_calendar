from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, constr

from data import EventRecord, HistoryRecord


class FrequencyUnit(str, Enum):
    days = "days"
    weeks = "weeks"
    months = "months"
    years = "years"


class EventBase(BaseModel):
    name: constr(min_length=1, max_length=128)
    tag: Optional[constr(min_length=1, max_length=64)] = None
    details: Optional[constr(max_length=2048)] = None
    due_date: date
    frequency_value: int = Field(..., gt=0, le=1000)
    frequency_unit: FrequencyUnit


class EventCreateRequest(EventBase):
    pass


class EventUpdateRequest(BaseModel):
    name: Optional[constr(min_length=1, max_length=128)]
    tag: Optional[constr(min_length=1, max_length=64)]
    details: Optional[constr(max_length=2048)] = Field(default=None)
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
    tag: Optional[str]
    details: Optional[str]
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


def history_to_response(record: HistoryRecord) -> EventHistoryResponse:
    return EventHistoryResponse(
        id=record.id,
        event_id=record.event_id,
        action=record.action,
        action_date=record.action_date,
        note=record.note,
    )


def event_to_response(record: EventRecord, history: Optional[List[HistoryRecord]] = None) -> EventWithHistoryResponse:
    return EventWithHistoryResponse(
        id=record.id,
        name=record.name,
        tag=record.tag,
        details=record.details,
        frequency_value=record.frequency_value,
        frequency_unit=FrequencyUnit(record.frequency_unit),
        due_date=record.due_date,
        last_done=record.last_done,
        created_at=record.created_at,
        updated_at=record.updated_at,
        is_overdue=record.is_overdue(),
        history=[history_to_response(item) for item in (history or [])],
    )
