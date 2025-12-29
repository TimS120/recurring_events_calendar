from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from shared_state_store import (
    apply_local_update,
    get_state,
    initialize_database,
)

SOURCE_ID = "pc-ui"


class SharedNumberUI:
    def __init__(self) -> None:
        initialize_database()
        self.root = tk.Tk()
        self.root.title("Shared Number")
        self.root.resizable(False, False)
        self.root.columnconfigure(1, weight=1)

        self.value_var = tk.StringVar()
        self.status_var = tk.StringVar()

        tk.Label(self.root, text="Current number:").grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")
        self.value_label = tk.Label(self.root, textvariable=self.value_var, font=("Helvetica", 14, "bold"))
        self.value_label.grid(row=0, column=1, padx=10, pady=(10, 0), sticky="w")

        tk.Label(self.root, text="New number:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry = tk.Entry(self.root)
        self.entry.grid(row=1, column=1, padx=10, pady=10, sticky="we")

        button_frame = tk.Frame(self.root)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)

        tk.Button(button_frame, text="Apply locally", command=self.apply_local).grid(row=0, column=0, padx=5)
        tk.Button(button_frame, text="Refresh", command=self.refresh_state).grid(row=0, column=1, padx=5)

        self.status_label = tk.Label(self.root, textvariable=self.status_var, fg="gray")
        self.status_label.grid(row=3, column=0, columnspan=2, pady=(0, 10))

        self.refresh_state()

    def run(self) -> None:
        self.root.mainloop()

    def refresh_state(self) -> None:
        try:
            state = get_state()
            self.value_var.set(str(state["value"]))
            self.status_var.set(f"updated_at: {state['updated_at']} | source: {state['source_id']}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to read state: {exc}")

    def apply_local(self) -> None:
        raw_value = self.entry.get().strip()
        if not raw_value:
            messagebox.showerror("Input error", "Please enter a number.")
            return
        try:
            value = int(raw_value)
        except ValueError:
            messagebox.showerror("Input error", "Value must be an integer.")
            return
        try:
            state = apply_local_update(value=value, source_id=SOURCE_ID)
            self.value_var.set(str(state["value"]))
            self.status_var.set(f"Locally updated at {state['updated_at']}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to update state: {exc}")


if __name__ == "__main__":
    SharedNumberUI().run()
