from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, List, Optional, Sequence, Tuple

import tkinter as tk

from data import EventRecord, HistoryRecord, add_frequency

from ..constants import LIST_BASE_OFFSET, ROW_BASE_OFFSET, ROW_HEIGHT, ROW_SPACING, VISIBLE_ROWS
from ..theme import ThemePalette
from ..utils import (
    _calculate_overdue_percentage,
    _calculate_residual_percentage,
    _estimate_frequency_days,
    format_display_date,
)


class EventListCanvas(tk.Canvas):
    def __init__(
        self,
        master: tk.Widget,
        on_edit: Callable[[int], None],
        on_show_details: Callable[[int], None],
        on_viewport_change: Callable[[int], None],
        theme_provider: Callable[[], ThemePalette],
    ) -> None:
        self.theme_provider = theme_provider
        self._on_viewport_change = on_viewport_change
        super().__init__(master, background=self.theme_provider().canvas_background, highlightthickness=0)
        self.events: List[Tuple[EventRecord, List[HistoryRecord]]] = []
        self.on_edit = on_edit
        self.on_show_details = on_show_details
        self.scroll_offset = 0.0
        self.viewport_height = VISIBLE_ROWS * ROW_HEIGHT
        self.hit_regions: List[Tuple[str, int, float, float, float, float]] = []
        self.row_heights: dict[int, float] = {}
        self.content_height: float = LIST_BASE_OFFSET
        self.bind("<Configure>", self._handle_configure)
        self.bind("<Button-1>", self._handle_click)

    def update_view(
        self,
        events: Sequence[Tuple[EventRecord, List[HistoryRecord]]],
        scroll_offset: float,
        viewport_height: int,
    ) -> None:
        self.events = list(events)
        self.scroll_offset = scroll_offset
        self.viewport_height = viewport_height
        self.redraw()

    def _handle_click(self, event: tk.Event) -> None:
        x, y = event.x, event.y
        for action, event_id, x1, y1, x2, y2 in self.hit_regions:
            if x1 <= x <= x2 and y1 <= y <= y2:
                if action == "edit":
                    self.on_edit(event_id)
                elif action == "details":
                    self.on_show_details(event_id)
                break

    def redraw(self) -> None:
        self.delete("all")
        theme = self.theme_provider()
        self.configure(background=theme.canvas_background)
        width = self.winfo_width() or 260
        height = max(self.viewport_height + LIST_BASE_OFFSET, self.winfo_height())
        self.hit_regions.clear()
        self.row_heights.clear()
        y_offset = 0.0
        name_width = max(80, width - 160)
        if not self.events:
            self.create_text(
                width / 2,
                height / 2,
                text="No events yet",
                fill=theme.placeholder_text,
                font=("Segoe UI", 12),
            )
            self.content_height = LIST_BASE_OFFSET + ROW_HEIGHT
            self.config(scrollregion=(0, 0, width, max(height, self.content_height)))
            return
        today = date.today()
        for event, _history in self.events:
            row_start = LIST_BASE_OFFSET + y_offset
            row_top = row_start - self.scroll_offset
            rect_id = self.create_rectangle(10, row_top, width - 10, row_top + ROW_HEIGHT, outline="", fill="")
            bg_color = theme.list_row_overdue if event.due_date <= today else theme.list_row_default
            text_y = row_top + 12
            name_item = self.create_text(
                20,
                text_y,
                text=event.name,
                anchor="nw",
                width=name_width,
                justify="left",
                font=("Segoe UI", 11, "bold"),
                fill=theme.text_primary,
            )
            name_bbox = self.bbox(name_item)
            next_y = (name_bbox[3] if name_bbox else text_y + 18) + 4
            freq_text = f"Every {event.frequency_value} {event.frequency_unit}"
            if event.tag:
                freq_text = f"{freq_text} | Tag: {event.tag}"
            freq_item = self.create_text(
                20,
                next_y,
                text=freq_text,
                anchor="nw",
                font=("Segoe UI", 9),
                fill=theme.text_secondary,
            )
            freq_bbox = self.bbox(freq_item)

            status_color = theme.due_upcoming
            if event.due_date <= today:
                if event.due_date == today:
                    status_text = "Due today"
                else:
                    status_text = f"Overdue since {format_display_date(event.due_date)}"
                    overdue_pct = _calculate_overdue_percentage(event, today)
                    if overdue_pct is not None:
                        status_text = f"{status_text} ({overdue_pct}%)"
                status_color = theme.due_overdue
            else:
                status_text = f"Next due {format_display_date(event.due_date)}"
                residual_pct = _calculate_residual_percentage(event, today)
                if residual_pct is not None:
                    status_text = f"{status_text} ({residual_pct}%)"
            status_y = (freq_bbox[3] if freq_bbox else next_y + 16) + 4
            status_item = self.create_text(
                20,
                status_y,
                text=status_text,
                anchor="nw",
                font=("Segoe UI", 9, "bold"),
                fill=status_color,
            )

            has_details = bool((event.details or "").strip())
            indicator_bbox = None
            if has_details:
                indicator = self.create_text(
                    width - 40,
                    row_top + 8,
                    text="[i]",
                    anchor="ne",
                    font=("Segoe UI", 9, "bold"),
                    fill=theme.due_upcoming,
                )
                indicator_bbox = self.bbox(indicator)
                if indicator_bbox:
                    self.hit_regions.append(("details", event.id, *indicator_bbox))

            text_bboxes = [bbox for bbox in (name_bbox, freq_bbox, self.bbox(status_item)) if bbox]
            max_bottom = max((bbox[3] for bbox in text_bboxes), default=row_top + ROW_HEIGHT - 20)
            row_height = max(60.0, (max_bottom - row_top) + 20)
            row_bottom = row_top + row_height
            self.coords(rect_id, 10, row_top, width - 10, row_bottom)
            self.itemconfigure(rect_id, fill=bg_color, outline=theme.text_secondary)

            edit_item = self.create_text(
                width - 20,
                row_bottom - 18,
                text="[Edit]",
                anchor="ne",
                font=("Segoe UI", 9, "underline"),
                fill=theme.due_upcoming,
            )
            edit_bbox = self.bbox(edit_item)
            if edit_bbox:
                self.hit_regions.append(("edit", event.id, *edit_bbox))
            self.hit_regions.append(("details", event.id, 12, row_top, width - 60, row_bottom))
            self.row_heights[event.id] = row_height
            y_offset += row_height + ROW_SPACING

        self.content_height = LIST_BASE_OFFSET + y_offset
        scroll_height = max(height, self.content_height + ROW_SPACING)
        self.config(scrollregion=(0, 0, width, scroll_height))

    def _handle_configure(self, event: tk.Event) -> None:
        new_height = int(getattr(event, "height", self.viewport_height))
        if new_height > 0:
            self._on_viewport_change(new_height)
        self.redraw()


class TimelineCanvas(tk.Canvas):
    def __init__(self, master: tk.Widget, theme_provider: Callable[[], ThemePalette]) -> None:
        self.theme_provider = theme_provider
        super().__init__(master, background=self.theme_provider().timeline_backdrop, highlightthickness=0)
        self.events: List[Tuple[EventRecord, List[HistoryRecord]]] = []
        self.view_start = date.today()
        self.view_end = self.view_start + timedelta(days=30)
        self.label_format = "%b %d"
        self.horizon_name = "Day"
        self.scroll_offset = 0.0
        self.viewport_height = VISIBLE_ROWS * ROW_HEIGHT
        self.row_heights: List[float] = []
        self.bind("<Configure>", lambda _: self.redraw())

    def update_view(
        self,
        events: Sequence[Tuple[EventRecord, List[HistoryRecord]]],
        view_start: date,
        view_end: date,
        horizon_name: str,
        label_format: str,
        scroll_offset: float,
        viewport_height: int,
        row_heights: Sequence[float],
    ) -> None:
        self.events = list(events)
        self.view_start = view_start
        self.view_end = view_end
        self.horizon_name = horizon_name
        self.label_format = label_format
        self.scroll_offset = scroll_offset
        self.viewport_height = viewport_height
        self.row_heights = list(row_heights)
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        theme = self.theme_provider()
        self.configure(background=theme.timeline_backdrop)
        width = max(self.winfo_width(), 600)
        if not self.row_heights and self.events:
            self.row_heights = [ROW_HEIGHT for _ in self.events]
        row_spacing = ROW_SPACING
        total_rows_height = sum(self.row_heights) + row_spacing * max(len(self.row_heights) - 1, 0)
        height = max(
            self.viewport_height + ROW_BASE_OFFSET + 50,
            ROW_BASE_OFFSET + total_rows_height + 50,
            self.winfo_height(),
        )
        margin = 60
        axis_y = 40
        today = date.today()
        span_days = max((self.view_end - self.view_start).days, 1)
        self.config(scrollregion=(0, 0, width, height))

        self.create_rectangle(0, 0, width, height, fill=theme.timeline_backdrop, outline="")
        self.create_text(
            margin,
            15,
            text=f"{self.horizon_name} horizon",
            font=("Segoe UI", 11, "bold"),
            anchor="w",
            fill=theme.text_primary,
        )
        self.create_line(margin, axis_y, width - margin, axis_y, fill=theme.timeline_axis, width=2)

        def date_to_x(value: date) -> float:
            delta = (value - self.view_start).days
            fraction = delta / span_days
            usable_width = width - margin * 2
            return margin + max(0, min(usable_width, fraction * usable_width))

        tick_step = max(1, span_days // 8)
        tick_date = self.view_start
        while tick_date <= self.view_end:
            x = date_to_x(tick_date)
            self.create_line(x, axis_y - 5, x, axis_y + 5, fill=theme.timeline_axis_text)
            self.create_text(
                x,
                axis_y - 12,
                text=tick_date.strftime(self.label_format),
                font=("Segoe UI", 8),
                fill=theme.timeline_axis_text,
            )
            tick_date += timedelta(days=tick_step)

        today_line_x: Optional[float] = None
        if self.view_start <= today <= self.view_end:
            candidate_x = date_to_x(today)
            if margin <= candidate_x <= width - margin:
                today_line_x = candidate_x

        if not self.events:
            self.create_text(
                width / 2,
                axis_y + 100,
                text="No events scheduled yet.\nUse the New button to create one.",
                font=("Segoe UI", 12),
                fill=theme.placeholder_text,
                justify="center",
            )
            return

        y_offset = 0.0
        for index, (event, history) in enumerate(self.events):
            row_height = self.row_heights[index] if index < len(self.row_heights) else ROW_HEIGHT - 10
            row_top = ROW_BASE_OFFSET + y_offset - self.scroll_offset
            row_bottom = row_top + row_height
            row_mid = (row_top + row_bottom) / 2
            if row_bottom < axis_y or row_top > height:
                y_offset += row_height + row_spacing
                continue
            bg_color = theme.timeline_row_overdue if event.is_overdue() else theme.timeline_row_default
            self.create_rectangle(margin, row_top, width - margin, row_bottom, fill=bg_color, outline="")
            self.create_line(margin, row_mid, width - margin, row_mid, fill=theme.timeline_line)
            if (event.details or "").strip():
                self.create_oval(
                    margin - 35,
                    row_top + 8,
                    margin - 15,
                    row_top + 28,
                    fill=theme.due_upcoming,
                    outline="",
                )

            for entry in history:
                if not (self.view_start <= entry.action_date <= self.view_end):
                    continue
                hx = date_to_x(entry.action_date)
                self.create_oval(hx - 4, row_mid - 4, hx + 4, row_mid + 4, fill=theme.history_dot, outline="")

            due_marker = event.due_date
            freq_days = _estimate_frequency_days(event.frequency_value, event.frequency_unit)
            max_iterations = max(24, int(span_days / max(1, freq_days)) + 24)
            iterations = 0
            while due_marker <= self.view_end and iterations < max_iterations:
                if due_marker >= self.view_start:
                    mx = date_to_x(due_marker)
                    overdue = due_marker <= today
                    color = theme.due_overdue if overdue else theme.due_upcoming
                    self.create_line(mx, row_mid - 14, mx, row_mid + 14, fill=color, width=3)
                    self.create_text(
                        mx,
                        row_mid + 20,
                        text=due_marker.strftime("%b %d"),
                        font=("Segoe UI", 8),
                        fill=color,
                    )
                due_marker = add_frequency(due_marker, event.frequency_value, event.frequency_unit)
                iterations += 1

            y_offset += row_height + row_spacing

        if today_line_x is not None:
            self.create_line(today_line_x, axis_y, today_line_x, height, dash=(4, 4), fill=theme.today_color, width=2)
            self.create_text(
                today_line_x + 4,
                axis_y + 12,
                text="Today",
                anchor="w",
                font=("Segoe UI", 8),
                fill=theme.today_color,
            )
