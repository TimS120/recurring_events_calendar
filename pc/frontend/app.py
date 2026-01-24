from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional, Sequence, Tuple

import tkinter as tk
from tkinter import messagebox, ttk

from data import (
    EventRecord,
    HistoryRecord,
    create_event,
    delete_event,
    initialize_database,
    list_events_with_history,
    mark_event_done,
    update_event,
)

from .constants import (
    DELETE_SENTINEL_KEY,
    DUE_TODAY_SENTINEL_KEY,
    MARK_DONE_SENTINEL_KEY,
    ROW_HEIGHT,
    ROW_SPACING,
    TAG_PRIORITY_ALL,
    VISIBLE_ROWS,
)
from .dialogs import EventDetailsWindow, EventDialog
from .server_controller import EmbeddedServerController
from .theme import (
    DARK_THEME,
    HORIZON_SETTINGS,
    LIGHT_THEME,
    ThemePalette,
    detect_system_prefers_dark,
    set_windows_titlebar_theme,
)
from .widgets.event_canvases import EventListCanvas, TimelineCanvas


class RecurringEventsUI:
    def __init__(self) -> None:
        initialize_database()
        self.server_controller = EmbeddedServerController()
        self.root = tk.Tk()
        self.root.title("Recurring Events Calendar")
        self.root.geometry("1200x720")
        self.root.minsize(1000, 640)
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close_request)

        self.system_prefers_dark = detect_system_prefers_dark()
        self._manual_theme_override: Optional[str] = None
        self.style = ttk.Style(self.root)
        self._scales: List[tk.Scale] = []
        self._titlebar_needs_update = False
        self.root.bind("<Map>", self._handle_root_mapped)

        self.horizon_var = tk.StringVar(value="Day")
        self.timeline_offset_var = tk.IntVar(value=0)
        self.scroll_var = tk.DoubleVar(value=0.0)
        self.scroll_offset = 0.0
        self.tag_priority_var = tk.StringVar(value=TAG_PRIORITY_ALL)
        self.status_var = tk.StringVar(value="Starting server...")
        self._suppress_scroll_callback = False

        self.events: List[Tuple[EventRecord, List[HistoryRecord]]] = []
        self._available_tags: List[str] = []
        self._display_events: List[Tuple[EventRecord, List[HistoryRecord]]] = []
        self.viewport_height = VISIBLE_ROWS * ROW_HEIGHT
        self._detail_windows: dict[int, EventDetailsWindow] = {}

        self._build_layout()
        self.apply_theme()
        self._bind_scroll_events()
        self._start_server_and_sync()

    @property
    def theme_mode(self) -> str:
        if self._manual_theme_override:
            return self._manual_theme_override
        return "dark" if self.system_prefers_dark else "light"

    def current_theme(self) -> ThemePalette:
        return DARK_THEME if self.theme_mode == "dark" else LIGHT_THEME

    def toggle_theme(self) -> None:
        current = self.theme_mode
        target = "light" if current == "dark" else "dark"
        system_default = "dark" if self.system_prefers_dark else "light"
        self._manual_theme_override = None if target == system_default else target
        self.apply_theme()
        self.update_view()

    def apply_theme(self) -> None:
        theme = self.current_theme()
        try:
            if "clam" in self.style.theme_names():
                self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.root.configure(bg=theme.background)
        self.style.configure("TFrame", background=theme.background)
        self.style.configure("TLabelframe", background=theme.background)
        self.style.configure("TLabel", background=theme.background, foreground=theme.text_primary)
        self.style.configure("Status.TLabel", background=theme.background, foreground=theme.status_text)
        self.style.configure("TButton", background=theme.surface, foreground=theme.text_primary)
        self.style.map("TButton", background=[("active", theme.panel_surface)])
        self.style.configure("TMenubutton", background=theme.surface, foreground=theme.text_primary)
        self.style.configure("TOptionMenu", background=theme.surface, foreground=theme.text_primary)
        entry_bg = theme.surface
        entry_fg = theme.text_primary
        self.style.configure("TEntry", fieldbackground=entry_bg, foreground=entry_fg, insertcolor=entry_fg)
        self.style.map("TEntry", fieldbackground=[("disabled", theme.panel_surface)])
        for style_name in ("TCombobox", "TSpinbox"):
            self.style.configure(style_name, fieldbackground=entry_bg, foreground=entry_fg, background=entry_bg)
            self.style.map(
                style_name,
                fieldbackground=[("readonly", entry_bg)],
                foreground=[("disabled", theme.text_secondary)],
                background=[("readonly", entry_bg)],
            )
        self.style.configure("TCombobox", arrowcolor=entry_fg)
        self.style.configure(
            "DatePickerTrigger.TButton",
            background=entry_bg,
            foreground=entry_fg,
            padding=(2, 0),
            relief="flat",
        )
        self.style.map(
            "DatePickerTrigger.TButton",
            background=[("active", theme.panel_surface)],
            foreground=[("disabled", theme.text_secondary)],
        )
        try:
            self.root.option_add("*TCombobox*Listbox.background", entry_bg)
            self.root.option_add("*TCombobox*Listbox.foreground", entry_fg)
        except tk.TclError:
            pass

        if hasattr(self, "theme_toggle_btn"):
            self.theme_toggle_btn.config(text=self._theme_button_text())
        if hasattr(self, "status_label"):
            self.status_label.configure(style="Status.TLabel")
        for scale in getattr(self, "_scales", []):
            scale.configure(
                background=theme.background,
                fg=theme.text_primary,
                troughcolor=theme.slider_trough,
                highlightbackground=theme.background,
                highlightcolor=theme.background,
                activebackground=theme.panel_surface,
            )
        if hasattr(self, "list_canvas"):
            self.list_canvas.redraw()
        if hasattr(self, "timeline_canvas"):
            self.timeline_canvas.redraw()
        if self.root.winfo_ismapped():
            set_windows_titlebar_theme(self.root, self.theme_mode == "dark")
            self._titlebar_needs_update = False
        else:
            self._titlebar_needs_update = True
        for window in list(self._detail_windows.values()):
            if window.winfo_exists():
                window.apply_theme(self.current_theme())

    def _theme_button_text(self) -> str:
        return "Switch to light mode" if self.theme_mode == "dark" else "Switch to dark mode"

    def _handle_root_mapped(self, _event: tk.Event) -> None:
        set_windows_titlebar_theme(self.root, self.theme_mode == "dark")
        self._titlebar_needs_update = False

    def _build_layout(self) -> None:
        controls = ttk.Frame(self.root)
        controls.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Button(controls, text="New Event", command=self.add_event).pack(side="left")
        ttk.Button(controls, text="Sync now", command=self.refresh_events).pack(side="right")
        self.theme_toggle_btn = ttk.Button(controls, text=self._theme_button_text(), command=self.toggle_theme)
        self.theme_toggle_btn.pack(side="right", padx=(0, 8))

        slider_frame = ttk.Frame(self.root)
        slider_frame.pack(fill="x", padx=12, pady=(0, 6))
        top_slider_row = ttk.Frame(slider_frame)
        top_slider_row.pack(fill="x")
        ttk.Label(top_slider_row, text="Timeline position").pack(side="left")
        horizon_container = ttk.Frame(top_slider_row)
        horizon_container.pack(side="left", padx=(16, 0))
        ttk.Label(horizon_container, text="Timeline horizon:").pack(side="left")
        horizon_menu = ttk.OptionMenu(
            horizon_container,
            self.horizon_var,
            self.horizon_var.get(),
            *HORIZON_SETTINGS.keys(),
            command=lambda _: self._on_horizon_change(),
        )
        horizon_menu.pack(side="left", padx=(6, 0))
        ttk.Button(top_slider_row, text="Jump to today", command=self.reset_timeline_slider).pack(side="right")
        tag_row = ttk.Frame(slider_frame)
        tag_row.pack(fill="x", pady=(4, 2))
        ttk.Label(tag_row, text="Prioritize tag:").pack(side="left")
        self.tag_filter_menu = ttk.OptionMenu(tag_row, self.tag_priority_var, self.tag_priority_var.get())
        self.tag_filter_menu.pack(side="left", padx=(6, 0))
        self.timeline_slider = tk.Scale(
            slider_frame,
            from_=HORIZON_SETTINGS["Day"].slider_min,
            to=HORIZON_SETTINGS["Day"].slider_max,
            orient="horizontal",
            variable=self.timeline_offset_var,
            command=lambda _: self.update_view(),
        )
        self.timeline_slider.pack(fill="x")
        self._scales.append(self.timeline_slider)

        table_frame = ttk.Frame(self.root)
        table_frame.pack(fill="both", expand=True, padx=12, pady=6)

        self.left_panel = ttk.Frame(table_frame, width=280)
        self.left_panel.pack(side="left", fill="y")
        ttk.Label(self.left_panel, text="Events", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 4))
        self.list_canvas = EventListCanvas(
            self.left_panel,
            on_edit=self._handle_edit_from_canvas,
            on_show_details=self._show_event_details,
            on_viewport_change=self._handle_list_viewport_change,
            theme_provider=self.current_theme,
        )
        self.list_canvas.pack(fill="both", expand=True)

        timeline_container = ttk.Frame(table_frame)
        timeline_container.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.timeline_canvas = TimelineCanvas(timeline_container, theme_provider=self.current_theme)
        self.timeline_canvas.pack(fill="both", expand=True)

        slider_column = ttk.Frame(table_frame)
        slider_column.pack(side="left", fill="y", padx=(12, 0))
        ttk.Label(slider_column, text="Vertical slider").pack()
        ttk.Button(slider_column, text="Top", command=self.scroll_to_top).pack(fill="x", pady=(4, 2))
        self.row_slider = tk.Scale(
            slider_column,
            from_=0,
            to=0,
            orient="vertical",
            variable=self.scroll_var,
            command=self._on_scroll_change,
            showvalue=False,
            resolution=1,
        )
        self.row_slider.pack(fill="y", expand=True)
        self._scales.append(self.row_slider)
        ttk.Button(slider_column, text="Bottom", command=self.scroll_to_bottom).pack(fill="x", pady=(2, 0))

        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", padx=12, pady=(0, 12))
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(anchor="w")
        self._update_tag_menu()

    def _update_tag_menu(self) -> None:
        if not hasattr(self, "tag_filter_menu"):
            return
        tag_map: dict[str, str] = {}
        for event, _history in self.events:
            value = (event.tag or "").strip() if event.tag else ""
            if not value:
                continue
            key = value.casefold()
            if key not in tag_map:
                tag_map[key] = value
        self._available_tags = sorted(tag_map.values(), key=str.casefold)
        options = [TAG_PRIORITY_ALL] + self._available_tags
        if self.tag_priority_var.get() not in options:
            self.tag_priority_var.set(TAG_PRIORITY_ALL)
        menu = self.tag_filter_menu["menu"]
        menu.delete(0, "end")
        for option in options:
            menu.add_command(
                label=option,
                command=lambda value=option: self._select_tag_option(value),
            )

    def _select_tag_option(self, value: str) -> None:
        self.tag_priority_var.set(value)
        self.update_view()

    def _apply_tag_priority(
        self, events: Sequence[Tuple[EventRecord, List[HistoryRecord]]]
    ) -> List[Tuple[EventRecord, List[HistoryRecord]]]:
        if not events:
            return []
        selected = self.tag_priority_var.get().strip()
        if not selected or selected == TAG_PRIORITY_ALL:
            return list(events)
        normalized = selected.casefold()
        prioritized: List[Tuple[EventRecord, List[HistoryRecord]]] = []
        remainder: List[Tuple[EventRecord, List[HistoryRecord]]] = []
        for item in events:
            tag_value = (item[0].tag or "").strip()
            if tag_value and tag_value.casefold() == normalized:
                prioritized.append(item)
            else:
                remainder.append(item)
        return prioritized + remainder

    def _bind_scroll_events(self) -> None:
        self.root.bind_all("<MouseWheel>", self._on_mouse_wheel)
        self.root.bind_all("<Shift-MouseWheel>", self._on_mouse_wheel)
        self.root.bind_all("<Button-4>", lambda event: self._on_mouse_wheel(event, delta_override=120))
        self.root.bind_all("<Button-5>", lambda event: self._on_mouse_wheel(event, delta_override=-120))

    def _start_server_and_sync(self) -> None:
        self.status_var.set("Starting local API server...")
        self.root.update_idletasks()
        try:
            self.server_controller.start()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Server start failed", f"Could not start the local API server:\n{exc}")
            self.status_var.set("Server unavailable - showing last known data")
            self.refresh_events()
            return
        self.status_var.set("Server online - syncing events")
        self.refresh_events()

    def _handle_close_request(self) -> None:
        for event_id in list(self._detail_windows.keys()):
            self._close_detail_window(event_id)
        try:
            self.server_controller.stop()
        finally:
            self.root.destroy()

    def _handle_list_viewport_change(self, height: int) -> None:
        if height <= 0:
            return
        new_height = max(100, height)
        if abs(new_height - self.viewport_height) < 1:
            return
        self.viewport_height = new_height
        self._configure_scroll_slider()
        self.update_view()

    def _on_mouse_wheel(self, event: tk.Event, delta_override: Optional[int] = None) -> None:
        delta = delta_override if delta_override is not None else getattr(event, "delta", 0)
        if delta == 0:
            return
        shift_pressed = bool(getattr(event, "state", 0) & 0x0001)
        if shift_pressed:
            step = self._timeline_scroll_step()
            change = -int(delta / 120 * step)
            if change == 0:
                change = -step if delta > 0 else step
            self._adjust_timeline_offset(change)
        else:
            pixel_step = ROW_HEIGHT / 2
            offset_change = -(delta / 120) * pixel_step
            self._set_scroll_offset(self.scroll_offset + offset_change)

    def add_event(self) -> None:
        dialog = EventDialog(
            self.root,
            "New Event",
            theme_provider=self.current_theme,
            tag_options=self._available_tags,
        )
        if dialog.result is None:
            return
        try:
            create_event(**dialog.result)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", f"Could not create event: {exc}")
            return
        self.refresh_events()

    def refresh_events(self) -> None:
        try:
            data = list_events_with_history(history_limit=12)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to read events: {exc}")
            return
        self.events = data
        self._update_tag_menu()
        self._refresh_detail_windows()
        self.update_view()
        self._configure_scroll_slider()
        self.status_var.set(f"{len(self.events)} event(s) - Refreshed at {datetime.now().strftime('%H:%M:%S')}")

    def _on_horizon_change(self) -> None:
        setting = HORIZON_SETTINGS[self.horizon_var.get()]
        self.timeline_slider.config(from_=setting.slider_min, to=setting.slider_max)
        if self.timeline_offset_var.get() < setting.slider_min:
            self.timeline_offset_var.set(setting.slider_min)
        elif self.timeline_offset_var.get() > setting.slider_max:
            self.timeline_offset_var.set(setting.slider_max)
        self.update_view()

    def _configure_scroll_slider(self) -> None:
        total_height = max(self.list_canvas.content_height + ROW_SPACING, self.viewport_height)
        viewport = self.viewport_height
        max_offset = max(0, total_height - viewport)
        self.row_slider.config(to=max_offset)
        if self.scroll_offset > max_offset:
            self.scroll_offset = max_offset
        self._set_scroll_offset(self.scroll_offset, update=False)

    def _on_scroll_change(self, value: str) -> None:
        if self._suppress_scroll_callback:
            return
        self.scroll_offset = float(value)
        self.update_view()

    def update_view(self) -> None:
        if not self.horizon_var.get():
            return
        display_events = self._apply_tag_priority(self.events)
        self._display_events = display_events
        setting = HORIZON_SETTINGS[self.horizon_var.get()]
        view_start = date.today() + timedelta(days=int(self.timeline_offset_var.get()))
        view_end = view_start + timedelta(days=setting.span_days)
        self.list_canvas.update_view(display_events, self.scroll_offset, self.viewport_height)
        row_heights = [self.list_canvas.row_heights.get(event.id, ROW_HEIGHT) for event, _history in display_events]
        self.timeline_canvas.update_view(
            display_events,
            view_start,
            view_end,
            self.horizon_var.get(),
            setting.label_format,
            self.scroll_offset,
            self.viewport_height,
            row_heights,
        )

    def _handle_edit_from_canvas(self, event_id: int) -> None:
        event = next((evt for evt, _history in self.events if evt.id == event_id), None)
        if event is None:
            return
        dialog = EventDialog(
            self.root,
            f"Edit {event.name}",
            event,
            theme_provider=self.current_theme,
            tag_options=self._available_tags,
        )
        if dialog.result is None:
            return
        if isinstance(dialog.result, dict):
            if dialog.result.get(DELETE_SENTINEL_KEY):
                try:
                    delete_event(event.id)
                except Exception as exc:  # noqa: BLE001
                    messagebox.showerror("Error", f"Failed to delete event: {exc}")
                    return
                self.refresh_events()
                return
            if dialog.result.get(DUE_TODAY_SENTINEL_KEY):
                try:
                    update_event(event.id, due_date=date.today())
                except Exception as exc:  # noqa: BLE001
                    messagebox.showerror("Error", f"Failed to update due date: {exc}")
                    return
                self.refresh_events()
                return
            if dialog.result.get(MARK_DONE_SENTINEL_KEY):
                self.complete_event(event.id)
                return
        try:
            update_event(
                event.id,
                name=dialog.result["name"],
                tag=dialog.result["tag"],
                details=dialog.result["details"],
                due_date=dialog.result["due_date"],
                frequency_value=dialog.result["frequency_value"],
                frequency_unit=dialog.result["frequency_unit"],
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to update event: {exc}")
            return
        self.refresh_events()

    def _show_event_details(self, event_id: int) -> None:
        data = next(((evt, history) for evt, history in self.events if evt.id == event_id), None)
        if data is None:
            return
        event, history = data
        window = self._detail_windows.get(event_id)
        if window and window.winfo_exists():
            window.update_content(event, history)
            window.apply_theme(self.current_theme())
            try:
                window.lift()
                window.focus_force()
            except tk.TclError:
                pass
            return

        def handle_close(closed_id: int) -> None:
            self._detail_windows.pop(closed_id, None)

        def handle_edit(target_id: int) -> None:
            self._close_detail_window(target_id)
            self._handle_edit_from_canvas(target_id)

        window = EventDetailsWindow(
            self.root,
            event,
            history,
            theme_provider=self.current_theme,
            on_edit=handle_edit,
            on_close=handle_close,
        )
        self._detail_windows[event_id] = window

    def _close_detail_window(self, event_id: int) -> None:
        window = self._detail_windows.pop(event_id, None)
        if window and window.winfo_exists():
            window.close()

    def _refresh_detail_windows(self) -> None:
        current = {event.id: (event, history) for event, history in self.events}
        for event_id, window in list(self._detail_windows.items()):
            if not window.winfo_exists() or event_id not in current:
                self._close_detail_window(event_id)
                continue
            event, history = current[event_id]
            window.update_content(event, history)
            window.apply_theme(self.current_theme())

    def reset_timeline_slider(self) -> None:
        self.timeline_offset_var.set(0)
        self.update_view()

    def scroll_to_top(self) -> None:
        self._set_scroll_offset(0.0)

    def scroll_to_bottom(self) -> None:
        max_offset = float(self.row_slider.cget("to"))
        self._set_scroll_offset(max_offset)

    def _set_scroll_offset(self, value: float, update: bool = True) -> None:
        max_offset = float(self.row_slider.cget("to"))
        bounded = max(0.0, min(max_offset, value))
        self.scroll_offset = bounded
        self._suppress_scroll_callback = True
        self.scroll_var.set(bounded)
        self._suppress_scroll_callback = False
        if update:
            self.update_view()

    def _timeline_scroll_step(self) -> int:
        setting = HORIZON_SETTINGS[self.horizon_var.get()]
        return max(1, setting.span_days // 30)

    def _adjust_timeline_offset(self, delta_days: int) -> None:
        if delta_days == 0:
            return
        slider_min = float(self.timeline_slider.cget("from"))
        slider_max = float(self.timeline_slider.cget("to"))
        current = float(self.timeline_offset_var.get())
        new_value = max(slider_min, min(slider_max, current + delta_days))
        if int(new_value) != int(current):
            self.timeline_offset_var.set(int(new_value))
            self.update_view()

    def complete_event(self, event_id: int) -> None:
        try:
            mark_event_done(event_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to mark as done: {exc}")
            return
        self.refresh_events()

    def run(self) -> None:
        self.root.mainloop()
