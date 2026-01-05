from __future__ import annotations

import calendar
from datetime import date
from typing import Callable, List, Optional

import tkinter as tk
from tkinter import ttk

from ..theme import ThemePalette, set_windows_titlebar_theme


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
