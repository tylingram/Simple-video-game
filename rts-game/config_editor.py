"""
Standalone config editor — launched as a subprocess by the game.
Reads and writes config.json directly. No threading needed.
Run this file directly or let main.py launch it automatically.
"""
import json
import tkinter as tk
from pathlib import Path

SAVE_FILE = Path(__file__).parent / "config.json"

DEFAULTS = {
    "HUD_SIZE":              {"value": 10.0,   "description": "Changes the % of screen taken up by HUD"},
    "CARRIER_WIDTH_MM":      {"value": 5.0,    "description": "Width of the Carrier unit in mm"},
    "CARRIER_HEIGHT_MM":     {"value": 10.0,   "description": "Height of the Carrier unit in mm"},
    "CARRIER_ACCELERATION":  {"value": 1.0,    "description": "Carrier acceleration in mm/s²"},
    "CARRIER_TOP_SPEED":     {"value": 20.0,   "description": "Carrier max speed in mm/s"},
    "MAP_WIDTH_MM":          {"value": 1000.0, "description": "Map width in mm"},
    "MAP_HEIGHT_MM":         {"value": 1000.0, "description": "Map height in mm"},
}


def load():
    data = {k: dict(v) for k, v in DEFAULTS.items()}
    if SAVE_FILE.exists():
        try:
            saved = json.loads(SAVE_FILE.read_text())
            for key, value in saved.items():
                if key in data:
                    data[key]["value"] = value
        except Exception:
            pass
    return data


def save(data):
    SAVE_FILE.write_text(json.dumps({k: v["value"] for k, v in data.items()}, indent=2))


def build_ui():
    data = load()

    root = tk.Tk()
    root.title("RTS Config")
    root.resizable(False, False)
    root.configure(bg="#1a1a2e")

    # ── Header ──────────────────────────────────────────────────────────────
    tk.Label(
        root, text="Game Configuration",
        bg="#1a1a2e", fg="#4ecca3",
        font=("Courier", 14, "bold")
    ).grid(row=0, column=0, columnspan=2, pady=(14, 10), padx=20, sticky="w")

    tk.Frame(root, bg="#4ecca3", height=1).grid(
        row=1, column=0, columnspan=2, sticky="ew", padx=20
    )

    # ── Variable rows ────────────────────────────────────────────────────────
    entries = {}
    row = 2
    for key, meta in data.items():
        tk.Label(
            root, text=key,
            bg="#1a1a2e", fg="#ffffff",
            font=("Courier", 11, "bold"), anchor="w"
        ).grid(row=row, column=0, sticky="w", padx=20, pady=(10, 0))

        var = tk.StringVar(value=str(meta["value"]))
        tk.Entry(
            root, textvariable=var, width=10,
            bg="#0f0f23", fg="#4ecca3",
            insertbackground="white",
            font=("Courier", 11),
            relief="flat", bd=6,
            highlightthickness=1,
            highlightcolor="#4ecca3",
            highlightbackground="#3a3a5a"
        ).grid(row=row, column=1, padx=(8, 20), pady=(10, 0), sticky="w")
        entries[key] = var

        tk.Label(
            root, text=meta["description"],
            bg="#1a1a2e", fg="#7a7a9a",
            font=("Courier", 9), anchor="w"
        ).grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=20, pady=(2, 0))
        row += 2

    # ── Divider ──────────────────────────────────────────────────────────────
    tk.Frame(root, bg="#3a3a5a", height=1).grid(
        row=row, column=0, columnspan=2, sticky="ew", padx=20, pady=12
    )

    # ── Status label ─────────────────────────────────────────────────────────
    status = tk.Label(root, text="", bg="#1a1a2e", fg="#4ecca3", font=("Courier", 9))

    def on_save():
        errors = []
        for key, var in entries.items():
            try:
                data[key]["value"] = float(var.get())
            except ValueError:
                errors.append(key)
        if errors:
            status.config(text=f"Invalid value: {', '.join(errors)}", fg="#ff6b6b")
        else:
            save(data)
            status.config(text="Saved.", fg="#4ecca3")

    tk.Button(
        root, text="  SAVE  ",
        command=on_save,
        bg="#4ecca3", fg="#0f0f23",
        font=("Courier", 11, "bold"),
        relief="flat", cursor="hand2",
        padx=10, pady=6,
        activebackground="#3ab892", activeforeground="#0f0f23"
    ).grid(row=row + 1, column=0, columnspan=2, padx=20, sticky="ew")

    status.grid(row=row + 2, column=0, columnspan=2, pady=(6, 14))

    root.mainloop()


if __name__ == "__main__":
    build_ui()
