from __future__ import annotations

from datetime import date
from typing import Callable, List, Optional, Sequence

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from data import EventRecord, FREQUENCY_UNITS, HistoryRecord

from .constants import DELETE_SENTINEL_KEY, DUE_TODAY_SENTINEL_KEY, MARK_DONE_SENTINEL_KEY
from .theme import LIGHT_THEME, ThemePalette, set_windows_titlebar_theme
from .utils import format_display_date, parse_display_date
from .widgets.calendar_popup import CalendarPopup


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
            due_today_btn = ttk.Button(box, text="Due today", width=12, command=self._mark_due_today)
            due_today_btn.pack(side="left", padx=5, pady=5)
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

    def _mark_due_today(self) -> None:
        if self.event is None:
            return
        self.result = {DUE_TODAY_SENTINEL_KEY: True}
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
