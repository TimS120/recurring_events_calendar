from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from data import EventRecord, add_frequency

from .constants import DISPLAY_DATE_FMT, FREQUENCY_UNIT_DAY_MAP


def _estimate_frequency_days(value: int, unit: str) -> int:
    base = FREQUENCY_UNIT_DAY_MAP.get(unit.lower(), 30)
    return max(1, value * base)


def format_display_date(value: date) -> str:
    return value.strftime(DISPLAY_DATE_FMT)


def parse_display_date(value: str) -> date:
    return datetime.strptime(value, DISPLAY_DATE_FMT).date()


def _event_cycle_length_days(event: EventRecord) -> int:
    end = event.due_date
    start = event.last_done if event.last_done and event.last_done < end else add_frequency(
        end, -event.frequency_value, event.frequency_unit
    )
    span = (end - start).days
    if span <= 0:
        span = max(1, _estimate_frequency_days(event.frequency_value, event.frequency_unit))
    return span


def _calculate_overdue_percentage(event: EventRecord, today: date) -> Optional[int]:
    if event.due_date >= today:
        return None
    cycle_days = _event_cycle_length_days(event)
    overdue_days = (today - event.due_date).days
    if overdue_days <= 0:
        return 0
    percent = overdue_days / cycle_days * 100
    return int(round(percent))


def _calculate_residual_percentage(event: EventRecord, today: date) -> Optional[int]:
    if event.due_date <= today:
        return None
    cycle_days = _event_cycle_length_days(event)
    remaining_days = (event.due_date - today).days
    percent = remaining_days / cycle_days * 100
    percent = max(0.0, min(100.0, percent))
    return int(round(percent))
