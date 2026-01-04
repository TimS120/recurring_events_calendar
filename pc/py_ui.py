from __future__ import annotations

import atexit
import calendar
import ctypes
import socket
import subprocess
import sys
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, List, Optional, Sequence, Tuple

from event_store import (
    FREQUENCY_UNITS,
    EventRecord,
    HistoryRecord,
    add_frequency,
    create_event,
    delete_event,
    initialize_database,
    list_events_with_history,
    mark_event_done,
    update_event,
)
from server import API_PORT as SERVER_API_PORT, start_server_in_thread


@dataclass(frozen=True)
class HorizonSetting:
    span_days: int
    slider_min: int
    slider_max: int
    label_format: str


HORIZON_SETTINGS: dict[str, HorizonSetting] = {
    "Day": HorizonSetting(span_days=30, slider_min=-60, slider_max=120, label_format="%b %d"),
    "Month": HorizonSetting(span_days=180, slider_min=-365, slider_max=365, label_format="%b %Y"),
    "Year": HorizonSetting(span_days=720, slider_min=-365, slider_max=1825, label_format="%Y"),
}


@dataclass(frozen=True)
class ThemePalette:
    name: str
    background: str
    surface: str
    panel_surface: str
    canvas_background: str
    status_text: str
    text_primary: str
    text_secondary: str
    placeholder_text: str
    list_row_default: str
    list_row_overdue: str
    timeline_backdrop: str
    timeline_axis: str
    timeline_axis_text: str
    timeline_row_default: str
    timeline_row_overdue: str
    timeline_line: str
    history_dot: str
    due_upcoming: str
    due_overdue: str
    today_color: str
    slider_trough: str


LIGHT_THEME = ThemePalette(
    name="Light",
    background="#f2f2f2",
    surface="#ffffff",
    panel_surface="#f7f7f7",
    canvas_background="#f7f7f7",
    status_text="#444444",
    text_primary="#222222",
    text_secondary="#555555",
    placeholder_text="#777777",
    list_row_default="#ffffff",
    list_row_overdue="#ffecec",
    timeline_backdrop="#fafafa",
    timeline_axis="#333333",
    timeline_axis_text="#555555",
    timeline_row_default="#eef4ff",
    timeline_row_overdue="#ffecec",
    timeline_line="#8aa1c1",
    history_dot="#2f855a",
    due_upcoming="#2c5282",
    due_overdue="#c53030",
    today_color="#ff8800",
    slider_trough="#d6d6d6",
)


DARK_THEME = ThemePalette(
    name="Dark",
    background="#1e1f23",
    surface="#2b2d33",
    panel_surface="#23252a",
    canvas_background="#1c1d21",
    status_text="#d5d5d5",
    text_primary="#f3f3f3",
    text_secondary="#b5b5b5",
    placeholder_text="#7c7c7c",
    list_row_default="#2c2f36",
    list_row_overdue="#3a2525",
    timeline_backdrop="#1a1b1f",
    timeline_axis="#d0d0d0",
    timeline_axis_text="#c3c3c3",
    timeline_row_default="#1f2836",
    timeline_row_overdue="#422222",
    timeline_line="#5c7fa8",
    history_dot="#6ee7b7",
    due_upcoming="#63b3ed",
    due_overdue="#f87171",
    today_color="#f6ad55",
    slider_trough="#3b3d45",
)


def detect_system_prefers_dark() -> bool:
    if sys.platform == "win32":
        try:
            import winreg  # type: ignore

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return value == 0
        except OSError:
            pass
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0 and "Dark" in result.stdout
        except (OSError, FileNotFoundError):
            pass
    return False


def set_windows_titlebar_theme(window: tk.Tk, dark: bool) -> None:
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if hwnd == 0:
            hwnd = window.winfo_id()
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
                break
            except OSError:
                continue
    except (AttributeError, OSError):
        pass

VISIBLE_ROWS = 6
ROW_HEIGHT = 90
ROW_BASE_OFFSET = 70
LIST_BASE_OFFSET = 42
ROW_SPACING = 12
DELETE_SENTINEL_KEY = "__delete__"
MARK_DONE_SENTINEL_KEY = "__mark_done__"
TAG_PRIORITY_ALL = "All tags"

FREQUENCY_UNIT_DAY_MAP = {
    "days": 1,
    "weeks": 7,
    "months": 30,
    "years": 365,
}

SERVER_BIND_HOST = "0.0.0.0"
SERVER_PROBE_HOST = "127.0.0.1"
SERVER_START_TIMEOUT = 15.0

DISPLAY_DATE_FMT = "%d.%m.%Y"


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


class EmbeddedServerController:
    def __init__(
        self,
        *,
        bind_host: str = SERVER_BIND_HOST,
        probe_host: str = SERVER_PROBE_HOST,
        port: int = SERVER_API_PORT,
    ) -> None:
        self.bind_host = bind_host
        self.probe_host = probe_host
        self.port = port
        self._server = None
        self._thread = None
        self._exit_hook_registered = False

    def start(self) -> None:
        if self._is_listening():
            return
        server, thread = start_server_in_thread(
            host=self.bind_host,
            port=self.port,
            log_level="warning",
            enable_mdns=False,
        )
        self._server = server
        self._thread = thread
        if not self._exit_hook_registered:
            atexit.register(self.stop)
            self._exit_hook_registered = True
        self._wait_until_ready()

    def stop(self) -> None:
        if not self._server:
            return
        self._server.should_exit = True
        self._server.force_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def _wait_until_ready(self) -> None:
        deadline = time.time() + SERVER_START_TIMEOUT
        while time.time() < deadline:
            if self._is_listening():
                return
            if self._server and self._server.should_exit:
                raise RuntimeError("Server stopped before finishing startup")
            time.sleep(0.2)
        raise TimeoutError(f"Timed out waiting for server to listen on {self.host}:{self.port}")

    def _is_listening(self) -> bool:
        try:
            with socket.create_connection((self.probe_host, self.port), timeout=0.5):
                return True
        except OSError:
            return False


class CalendarPopup(tk.Toplevel):
    def __init__(
        self,
        master: tk.Widget,
        initial_date: date,
        on_select: Callable[[date], None],
        *,
        on_close: Optional[Callable[[], None]] = None,
        theme_provider: Optional[Callable[[], ThemePalette]] = None,
        anchor_widget: Optional[tk.Widget] = None,
    ) -> None:
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(False)
        self.resizable(False, False)
        self.title("Select date")
        self._on_select = on_select
        self._on_close = on_close
        self._theme_provider = theme_provider
        self._selected_date = initial_date
        self._display_month = initial_date.replace(day=1)
        self._today = date.today()
        self._container = tk.Frame(self)
        self._container.pack(fill="both", expand=True, padx=8, pady=8)
        self._build_widgets()
        self._apply_theme()
        self._refresh_days()
        self.transient(master)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._place_window(anchor_widget)
        self.deiconify()
        self.focus_force()
        self.bind("<Map>", self._apply_titlebar_theme, add="+")
        if self.winfo_ismapped():
            self._apply_titlebar_theme()
        else:
            self.after_idle(self._apply_titlebar_theme)

    def _build_widgets(self) -> None:
        self._header = tk.Frame(self._container)
        self._header.pack(fill="x")
        ttk.Button(self._header, text="<", width=3, command=lambda: self._shift_month(-1)).pack(side="left")
        self._month_label = tk.Label(self._header, text="", font=("Segoe UI", 10, "bold"))
        self._month_label.pack(side="left", expand=True)
        ttk.Button(self._header, text=">", width=3, command=lambda: self._shift_month(1)).pack(side="right")

        self._weekday_row = tk.Frame(self._container)
        self._weekday_row.pack(fill="x", pady=(6, 2))
        self._weekday_labels: List[tk.Label] = []
        for idx in range(7):
            label = tk.Label(self._weekday_row, text=calendar.day_abbr[idx], width=3, anchor="center")
            label.grid(row=0, column=idx, padx=2)
            self._weekday_labels.append(label)

        self._days_frame = tk.Frame(self._container)
        self._days_frame.pack()
        self._day_buttons: List[List[tk.Button]] = []
        for row in range(6):
            row_buttons: List[tk.Button] = []
            for col in range(7):
                btn = tk.Button(
                    self._days_frame,
                    text="",
                    width=3,
                    relief="flat",
                    borderwidth=0,
                    command=lambda: None,
                )
                btn.grid(row=row, column=col, padx=2, pady=2)
                row_buttons.append(btn)
            self._day_buttons.append(row_buttons)

    def _place_window(self, anchor_widget: Optional[tk.Widget]) -> None:
        if anchor_widget is None:
            self.geometry("+200+200")
            return
        try:
            self.update_idletasks()
            x = anchor_widget.winfo_rootx()
            y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            self.geometry("+200+200")

    def _apply_theme(self) -> None:
        theme = self._theme_provider() if self._theme_provider else None
        background = theme.panel_surface if theme else "#ffffff"
        text_color = theme.text_primary if theme else "#000000"
        accent_bg = theme.due_upcoming if theme else "#2563eb"
        accent_fg = "#ffffff"
        today_bg = theme.timeline_row_default if theme else "#e2e8f0"
        self.configure(bg=background)
        self._container.configure(bg=background)
        self._header.configure(bg=background)
        self._weekday_row.configure(bg=background)
        self._days_frame.configure(bg=background)
        self._month_label.configure(bg=background, fg=text_color)
        for label in self._weekday_labels:
            label.configure(bg=background, fg=text_color)
        self._button_bg = background
        self._button_fg = text_color
        self._accent_bg = accent_bg
        self._accent_fg = accent_fg
        self._today_bg = today_bg
        self._today_fg = text_color
        for row in self._day_buttons:
            for btn in row:
                btn.configure(
                    bg=self._button_bg,
                    fg=self._button_fg,
                    activebackground=self._button_bg,
                    activeforeground=self._button_fg,
                )

    def _refresh_days(self) -> None:
        month_name = self._display_month.strftime("%B %Y")
        self._month_label.configure(text=month_name)
        start_weekday, total_days = calendar.monthrange(self._display_month.year, self._display_month.month)
        day_counter = 1
        for row in range(6):
            for col in range(7):
                btn = self._day_buttons[row][col]
                grid_index = row * 7 + col
                if grid_index < start_weekday or day_counter > total_days:
                    btn.configure(text="", state="disabled", command=lambda: None, bg=self._button_bg)
                    continue
                current_date = self._display_month.replace(day=day_counter)
                btn.configure(
                    text=str(day_counter),
                    state="normal",
                    command=lambda value=current_date: self._select_date(value),
                )
                self._style_day_button(btn, current_date)
                day_counter += 1

    def _style_day_button(self, button: tk.Button, current: date) -> None:
        if current == self._selected_date:
            button.configure(
                bg=self._accent_bg,
                fg=self._accent_fg,
                activebackground=self._accent_bg,
                activeforeground=self._accent_fg,
            )
        elif current == self._today:
            button.configure(
                bg=self._today_bg,
                fg=self._today_fg,
                activebackground=self._today_bg,
                activeforeground=self._today_fg,
            )
        else:
            button.configure(
                bg=self._button_bg,
                fg=self._button_fg,
                activebackground=self._button_bg,
                activeforeground=self._button_fg,
            )

    def _apply_titlebar_theme(self, _event: Optional[tk.Event] = None) -> None:
        if self._theme_provider is None:
            return
        try:
            set_windows_titlebar_theme(self, self._theme_provider().name.lower() == "dark")
        except tk.TclError:
            pass

    def _shift_month(self, delta: int) -> None:
        month = self._display_month.month - 1 + delta
        year = self._display_month.year + month // 12
        month = month % 12 + 1
        self._display_month = self._display_month.replace(year=year, month=month, day=1)
        self._refresh_days()

    def _select_date(self, value: date) -> None:
        self._selected_date = value
        self._on_select(value)
        self._close()

    def _close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        if self._on_close:
            callback = self._on_close
            self._on_close = None
            callback()
        self.destroy()

    def close(self) -> None:
        self._close()
class EventDialog(simpledialog.Dialog):
    def __init__(
        self,
        master: tk.Widget,
        title: str,
        event: Optional[EventRecord] = None,
        theme_provider: Optional[Callable[[], ThemePalette]] = None,
        tag_options: Optional[Sequence[str]] = None,
    ) -> None:
        self.event = event
        self.result_data: Optional[dict] = None
        self.theme_provider = theme_provider
        self._tag_options = sorted(
            {option.strip() for option in (tag_options or []) if option and option.strip()},
            key=str.casefold,
        )
        self._tag_popup: Optional[tk.Toplevel] = None
        self._tag_popup_listbox: Optional[tk.Listbox] = None
        self.due_entry: Optional[ttk.Entry] = None
        self._date_picker: Optional[CalendarPopup] = None
        self._due_trigger_btn: Optional[ttk.Button] = None
        self.details_input: Optional[tk.Text] = None
        super().__init__(master, title)

    def body(self, master: tk.Widget) -> tk.Widget:
        self._apply_theme(master)
        row = 0
        ttk.Label(master, text="Event name").grid(row=row, column=0, sticky="w", pady=(0, 4))
        row += 1
        self.name_var = tk.StringVar(value=self.event.name if self.event else "")
        ttk.Entry(master, textvariable=self.name_var, width=30).grid(row=row, column=0, columnspan=2, sticky="we", pady=(0, 8))
        row += 1

        ttk.Label(master, text="Tag (optional)").grid(row=row, column=0, sticky="w")
        row += 1
        tag_value = self.event.tag if (self.event and self.event.tag) else ""
        self.tag_var = tk.StringVar(value=tag_value)
        tag_values = list(self._tag_options)
        if tag_value and tag_value not in tag_values:
            tag_values.append(tag_value)
        self.tag_input = ttk.Combobox(master, textvariable=self.tag_var, values=tag_values, width=30)
        self.tag_input.grid(row=row, column=0, columnspan=2, sticky="we", pady=(0, 8))
        self._setup_tag_autocomplete()
        row += 1

        ttk.Label(master, text="Additional details (optional)").grid(row=row, column=0, sticky="w")
        row += 1
        details_text = (self.event.details or "") if self.event else ""
        self.details_input = tk.Text(master, height=4, width=36, wrap="word")
        self.details_input.grid(row=row, column=0, columnspan=2, sticky="we", pady=(0, 8))
        self.details_input.insert("1.0", details_text)
        self._apply_text_widget_theme(self.details_input)
        row += 1

        ttk.Label(master, text="Next due date (DD.MM.YYYY)").grid(row=row, column=0, sticky="w")
        row += 1
        default_due = self.event.due_date if self.event else date.today()
        self.due_var = tk.StringVar(value=format_display_date(default_due))
        due_row = ttk.Frame(master)
        due_row.grid(row=row, column=0, columnspan=2, sticky="we", pady=(0, 8))
        due_row.columnconfigure(0, weight=1)
        self.due_entry = ttk.Entry(due_row, textvariable=self.due_var, width=20)
        self.due_entry.grid(row=0, column=0, sticky="we")
        self.due_entry.bind("<Alt-Down>", self._handle_due_picker_key, add="+")
        self.due_entry.bind("<F4>", self._handle_due_picker_key, add="+")
        self._due_trigger_btn = ttk.Button(
            due_row,
            width=2,
            text="C",
            style="DatePickerTrigger.TButton",
            command=self._toggle_due_calendar,
        )
        self._due_trigger_btn.grid(row=0, column=1, sticky="e", padx=(4, 0))
        row += 1

        ttk.Label(master, text="Frequency").grid(row=row, column=0, sticky="w")
        row += 1
        self.freq_value_var = tk.StringVar(value=str(self.event.frequency_value if self.event else 30))
        freq_spin = ttk.Spinbox(master, from_=1, to=3650, textvariable=self.freq_value_var, width=6)
        freq_spin.grid(row=row, column=0, sticky="w")

        unit_label = self.event.frequency_unit if self.event else FREQUENCY_UNITS[0]
        self.freq_unit_var = tk.StringVar(value=unit_label)
        ttk.OptionMenu(master, self.freq_unit_var, unit_label, *FREQUENCY_UNITS).grid(row=row, column=1, sticky="w", padx=(6, 0))

        return master

    def validate(self) -> bool:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Invalid data", "Please enter a name for the event.")
            return False
        try:
            due_date = parse_display_date(self.due_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid data", "Due date must be in DD.MM.YYYY format.")
            return False
        try:
            freq_value = int(self.freq_value_var.get())
            if freq_value <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid data", "Frequency must be a positive number.")
            return False
        unit = self.freq_unit_var.get()
        if unit not in FREQUENCY_UNITS:
            messagebox.showerror("Invalid data", "Please choose a valid frequency unit.")
            return False
        tag_text = self.tag_var.get().strip()
        if len(tag_text) > 64:
            messagebox.showerror("Invalid data", "Tags must be 64 characters or fewer.")
            return False
        details_text = ""
        if self.details_input is not None:
            details_text = self.details_input.get("1.0", "end").strip()
        if len(details_text) > 2048:
            messagebox.showerror("Invalid data", "Details must be 2048 characters or fewer.")
            return False
        self.result_data = {
            "name": name,
            "tag": tag_text,
            "details": details_text,
            "due_date": due_date,
            "frequency_value": freq_value,
            "frequency_unit": unit,
        }
        return True

    def apply(self) -> None:
        self.result = self.result_data

    def buttonbox(self) -> None:  # type: ignore[override]
        box = ttk.Frame(self)
        save_btn = ttk.Button(box, text="Save", width=10, command=self.ok)
        save_btn.pack(side="left", padx=5, pady=5)
        if self.event is not None:
            done_btn = ttk.Button(box, text="Done today", width=12, command=self._mark_done)
            done_btn.pack(side="left", padx=5, pady=5)
        if self.event is not None:
            delete_btn = ttk.Button(box, text="Delete", width=10, command=self._delete_event)
            delete_btn.pack(side="left", padx=5, pady=5)
        cancel_btn = ttk.Button(box, text="Cancel", width=10, command=self.cancel)
        cancel_btn.pack(side="left", padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def _delete_event(self) -> None:
        if self.event is None:
            return
        if not messagebox.askyesno("Delete event", f"Delete '{self.event.name}'?"):
            return
        self.result = {DELETE_SENTINEL_KEY: True}
        self.destroy()

    def _mark_done(self) -> None:
        if self.event is None:
            return
        self.result = {MARK_DONE_SENTINEL_KEY: True}
        self.destroy()
        self._hide_tag_popup()

    def _toggle_due_calendar(self) -> None:
        if self._date_picker is None:
            self._open_due_calendar()
        else:
            self._date_picker.close()

    def _handle_due_picker_key(self, _event: tk.Event) -> str:
        self._toggle_due_calendar()
        return "break"

    def _open_due_calendar(self) -> None:
        if self._date_picker is not None:
            self._date_picker.close()
        try:
            current_value = parse_display_date(self.due_var.get().strip())
        except ValueError:
            current_value = date.today()
        self._date_picker = CalendarPopup(
            self,
            current_value,
            self._handle_calendar_selection,
            on_close=self._handle_calendar_closed,
            theme_provider=self.theme_provider,
            anchor_widget=self.due_entry,
        )

    def _handle_calendar_selection(self, value: date) -> None:
        self.due_var.set(format_display_date(value))

    def _handle_calendar_closed(self) -> None:
        self._date_picker = None

    def destroy(self) -> None:  # type: ignore[override]
        if self._date_picker is not None:
            try:
                self._date_picker.close()
            except tk.TclError:
                pass
            self._date_picker = None
        super().destroy()

    def _setup_tag_autocomplete(self) -> None:
        if not hasattr(self, "tag_input"):
            return
        tag_values = [value for value in self.tag_input.cget("values") if value]
        cached_options = sorted({value.strip() for value in tag_values if value.strip()}, key=str.casefold)

        def filter_options(prefix: str) -> List[str]:
            if not prefix:
                return []
            lowered = prefix.casefold()
            return [value for value in cached_options if value.casefold().startswith(lowered)]

        def update_suggestions() -> List[str]:
            text = self.tag_var.get().strip()
            matches = filter_options(text)
            return matches

        def handle_key(_event: tk.Event) -> None:
            matches = update_suggestions()
            self._show_tag_popup(matches)

        def handle_focus(_event: tk.Event) -> None:
            matches = update_suggestions()
            self._show_tag_popup(matches)

        def handle_selection(_event: tk.Event) -> None:
            current = self.tag_input.get()
            self.tag_var.set(current)
            self.tag_input.icursor("end")
            self._hide_tag_popup()

        self.tag_input.bind("<KeyRelease>", handle_key, add="+")
        self.tag_input.bind("<FocusIn>", handle_focus, add="+")
        self.tag_input.bind("<<ComboboxSelected>>", handle_selection, add="+")
        self.tag_input.bind("<FocusOut>", self._handle_tag_input_focus_out, add="+")
        self.tag_input.bind("<Down>", self._focus_tag_popup, add="+")

    def _show_tag_popup(self, options: Sequence[str]) -> None:
        self._hide_tag_popup()
        values = [value for value in options if value]
        current = self.tag_var.get().strip()
        if not values:
            return
        if current and len(values) == 1 and values[0].casefold() == current.casefold():
            return
        popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)
        popup.attributes("-topmost", True)
        theme = self.theme_provider() if self.theme_provider is not None else LIGHT_THEME
        bg = theme.surface
        fg = theme.text_primary
        frame = tk.Frame(popup, bg=bg, highlightthickness=1, highlightbackground=theme.text_secondary)
        frame.pack(fill="both", expand=True)
        listbox = tk.Listbox(
            frame,
            activestyle="none",
            selectmode="browse",
            bg=bg,
            fg=fg,
            highlightthickness=0,
            relief="flat",
        )
        for value in values:
            listbox.insert("end", value)
        listbox.pack(fill="both", expand=True)
        listbox.bind("<ButtonRelease-1>", lambda _e: self._select_tag_from_popup())
        listbox.bind("<Return>", lambda _e: self._select_tag_from_popup())
        listbox.bind("<Escape>", lambda _e: self._hide_tag_popup())
        listbox.bind("<FocusOut>", lambda _e: self.after_idle(self._hide_tag_popup))
        self._tag_popup = popup
        self._tag_popup_listbox = listbox
        self.after_idle(lambda: self._position_tag_popup())

    def _position_tag_popup(self) -> None:
        if not self._tag_popup or not self.tag_input:
            return
        try:
            x = self.tag_input.winfo_rootx()
            y = self.tag_input.winfo_rooty() + self.tag_input.winfo_height()
            width = self.tag_input.winfo_width()
        except tk.TclError:
            self._hide_tag_popup()
            return
        height = min(160, len(self._tag_popup_listbox.get(0, "end")) * 22 + 4) if self._tag_popup_listbox else 120
        self._tag_popup.geometry(f"{width}x{height}+{x}+{y}")

    def _hide_tag_popup(self) -> None:
        if self._tag_popup_listbox:
            try:
                self._tag_popup_listbox.destroy()
            except tk.TclError:
                pass
        self._tag_popup_listbox = None
        if self._tag_popup:
            try:
                self._tag_popup.destroy()
            except tk.TclError:
                pass
        self._tag_popup = None

    def _select_tag_from_popup(self) -> None:
        if not self._tag_popup_listbox:
            return
        selection = self._tag_popup_listbox.curselection()
        if selection:
            value = self._tag_popup_listbox.get(selection[0])
            self.tag_var.set(value)
            self.tag_input.focus_set()
            self.tag_input.icursor("end")
        self._hide_tag_popup()

    def _focus_tag_popup(self, _event: Optional[tk.Event] = None) -> str | None:
        if self._tag_popup_listbox:
            self._tag_popup_listbox.focus_set()
            if not self._tag_popup_listbox.curselection():
                self._tag_popup_listbox.selection_set(0)
            return "break"
        return None

    def _handle_tag_input_focus_out(self, _event: tk.Event) -> None:
        next_widget = self.focus_get()
        if self._tag_popup_listbox and next_widget is self._tag_popup_listbox:
            return
        self.after_idle(self._hide_tag_popup)

    def _apply_theme(self, body_frame: tk.Widget) -> None:
        if self.theme_provider is None:
            return
        theme = self.theme_provider()
        try:
            self.configure(bg=theme.background)
        except tk.TclError:
            pass
        try:
            body_frame.configure(bg=theme.background)
        except tk.TclError:
            pass
        if self.details_input is not None:
            self._apply_text_widget_theme(self.details_input)
        self.bind("<Map>", self._apply_titlebar_theme, add="+")
        if self.winfo_ismapped():
            self._apply_titlebar_theme()
        else:
            self.after_idle(self._apply_titlebar_theme)

    def _apply_titlebar_theme(self, _event: Optional[tk.Event] = None) -> None:
        if self.theme_provider is None:
            return
        theme = self.theme_provider()
        set_windows_titlebar_theme(self, theme.name.lower() == "dark")

    def _apply_text_widget_theme(self, widget: tk.Text) -> None:
        if self.theme_provider is None:
            return
        theme = self.theme_provider()
        try:
            widget.configure(
                bg=theme.surface,
                fg=theme.text_primary,
                insertbackground=theme.text_primary,
                selectbackground=theme.timeline_row_default,
                selectforeground=theme.text_primary,
                highlightbackground=theme.panel_surface,
                highlightcolor=theme.panel_surface,
            )
        except tk.TclError:
            pass


class EventDetailsWindow(tk.Toplevel):
    def __init__(
        self,
        master: tk.Widget,
        event: EventRecord,
        history: Sequence[HistoryRecord],
        *,
        theme_provider: Optional[Callable[[], ThemePalette]] = None,
        on_edit: Optional[Callable[[int], None]] = None,
        on_close: Optional[Callable[[int], None]] = None,
    ) -> None:
        super().__init__(master)
        self.withdraw()
        self._event = event
        self._history = list(history)
        self._theme_provider = theme_provider
        self._on_edit = on_edit
        self._on_close = on_close
        self._closed = False
        self.title("Event details")
        self.resizable(True, False)
        self._build_widgets()
        self.update_content(event, history)
        self.apply_theme()
        self.protocol("WM_DELETE_WINDOW", self._handle_close)
        self.transient(master)
        self.deiconify()
        self.focus_force()
        self.bind("<Map>", self._apply_titlebar_theme, add="+")
        if self.winfo_ismapped():
            self._apply_titlebar_theme()
        else:
            self.after_idle(self._apply_titlebar_theme)

    def _build_widgets(self) -> None:
        self._container = tk.Frame(self)
        self._container.pack(fill="both", expand=True, padx=12, pady=12)
        self._container.columnconfigure(0, weight=1)
        self._container.rowconfigure(3, weight=1)
        self._name_label = tk.Label(self._container, font=("Segoe UI", 13, "bold"))
        self._name_label.grid(row=0, column=0, sticky="w")

        info_frame = tk.Frame(self._container)
        info_frame.grid(row=1, column=0, sticky="we", pady=(8, 4))
        info_frame.columnconfigure(0, weight=1)
        self._info_frame = info_frame

        self._due_label = tk.Label(info_frame, text="")
        self._due_label.grid(row=0, column=0, sticky="w")
        self._cadence_label = tk.Label(info_frame, text="")
        self._cadence_label.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self._tag_label = tk.Label(info_frame, text="")
        self._tag_label.grid(row=2, column=0, sticky="w", pady=(2, 0))
        self._last_done_label = tk.Label(info_frame, text="")
        self._last_done_label.grid(row=3, column=0, sticky="w", pady=(2, 0))
        self._history_label = tk.Label(info_frame, text="")
        self._history_label.grid(row=4, column=0, sticky="w", pady=(2, 0))

        ttk.Label(self._container, text="Additional details").grid(row=2, column=0, sticky="w", pady=(12, 4))
        self._details_frame = tk.Frame(self._container, borderwidth=1, relief="solid")
        self._details_frame.grid(row=3, column=0, sticky="nsew")
        self._details_frame.columnconfigure(0, weight=1)
        self._details_text = tk.Text(
            self._details_frame,
            height=8,
            wrap="word",
            relief="flat",
            highlightthickness=0,
            state="disabled",
        )
        self._details_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self._details_frame, orient="vertical", command=self._details_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._details_text.configure(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(self._container)
        button_frame.grid(row=4, column=0, sticky="e", pady=(12, 0))
        ttk.Button(button_frame, text="Edit event", command=self._handle_edit).pack(side="left", padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=self._handle_close).pack(side="left")

    def update_content(self, event: EventRecord, history: Sequence[HistoryRecord]) -> None:
        self._event = event
        self._history = list(history)
        self._name_label.configure(text=event.name)
        self._due_label.configure(text=f"Next due: {format_display_date(event.due_date)}")
        freq_text = f"Every {event.frequency_value} {event.frequency_unit}"
        self._cadence_label.configure(text=f"Cadence: {freq_text}")
        tag_value = (event.tag or "").strip() or "No tag"
        self._tag_label.configure(text=f"Tag: {tag_value}")
        if event.last_done:
            last_done_text = format_display_date(event.last_done)
        else:
            last_done_text = "n/a"
        self._last_done_label.configure(text=f"Last done: {last_done_text}")
        if self._history:
            latest = self._history[0]
            hist_text = f"Latest: {latest.action} on {format_display_date(latest.action_date)}"
        else:
            hist_text = "No recent history."
        self._history_label.configure(text=hist_text)
        details_text = (event.details or "").strip()
        if not details_text:
            details_text = "No additional information was provided for this event."
        self._details_text.configure(state="normal")
        self._details_text.delete("1.0", "end")
        self._details_text.insert("1.0", details_text)
        self._details_text.configure(state="disabled")

    def apply_theme(self, theme: Optional[ThemePalette] = None) -> None:
        palette = theme or (self._theme_provider() if self._theme_provider else None)
        background = palette.background if palette else "#ffffff"
        surface = palette.surface if palette else "#f7f7f7"
        panel = palette.panel_surface if palette else "#f0f0f0"
        text_primary = palette.text_primary if palette else "#000000"
        border = palette.timeline_axis if palette else "#666666"
        try:
            self.configure(bg=background)
            self._container.configure(bg=background)
            if hasattr(self, "_info_frame"):
                self._info_frame.configure(bg=background)
        except tk.TclError:
            pass
        for widget in (
            self._name_label,
            self._due_label,
            self._cadence_label,
            self._tag_label,
            self._last_done_label,
            self._history_label,
        ):
            widget.configure(background=background, foreground=text_primary)
        try:
            self._details_frame.configure(bg=panel, highlightbackground=border, highlightcolor=border)
            self._details_text.configure(
                bg=surface,
                fg=text_primary,
                insertbackground=text_primary,
                selectbackground=palette.timeline_row_default if palette else "#d0d0d0",
                selectforeground=text_primary,
            )
        except tk.TclError:
            pass
        self._apply_titlebar_theme()

    def _handle_edit(self) -> None:
        if self._on_edit and self._event:
            callback = self._on_edit
            event_id = self._event.id
            self._handle_close()
            callback(event_id)

    def _handle_close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._on_close and self._event:
                self._on_close(self._event.id)
        finally:
            try:
                self.destroy()
            except tk.TclError:
                pass

    def close(self) -> None:
        self._handle_close()

    def _apply_titlebar_theme(self, _event: Optional[tk.Event] = None) -> None:
        if self._theme_provider is None:
            return
        try:
            set_windows_titlebar_theme(self, self._theme_provider().name.lower() == "dark")
        except tk.TclError:
            pass

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
        self.root.bind_all("<Control-MouseWheel>", self._on_mouse_wheel)
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
        ctrl_pressed = bool(getattr(event, "state", 0) & 0x0004)
        if ctrl_pressed:
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


if __name__ == "__main__":
    RecurringEventsUI().run()
