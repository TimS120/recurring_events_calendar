from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(slots=True)
class EventRecord:
    id: int
    name: str
    tag: Optional[str]
    details: Optional[str]
    frequency_value: int
    frequency_unit: str
    due_date: date
    last_done: Optional[date]
    created_at: datetime
    updated_at: datetime

    @property
    def frequency_text(self) -> str:
        unit = self.frequency_unit
        if self.frequency_value == 1 and unit.endswith("s"):
            unit = unit[:-1]
        return f"{self.frequency_value} {unit}"

    def next_due(self) -> date:
        return self.due_date

    def is_overdue(self, today: Optional[date] = None) -> bool:
        today = today or date.today()
        return self.due_date <= today


@dataclass(slots=True)
class HistoryRecord:
    id: int
    event_id: int
    action: str
    action_date: date
    note: Optional[str]
