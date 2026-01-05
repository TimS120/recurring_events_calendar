from __future__ import annotations

import ctypes
import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass


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
