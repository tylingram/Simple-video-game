"""
Standalone config editor — launched as a subprocess by the game.
Reads and writes config.json directly. No threading needed.
Run this file directly or let main.py launch it automatically.
"""
import json
import math
import tkinter as tk
from pathlib import Path

SAVE_FILE = Path(__file__).parent / "config.json"

DEFAULTS = {
    "HUD_SIZE":              {"value": 10.0,   "description": "Changes the % of screen taken up by HUD"},
    "CARRIER_WIDTH_MM":      {"value": 5.0,    "description": "Width of the Carrier unit in mm"},
    "CARRIER_HEIGHT_MM":     {"value": 10.0,   "description": "Height of the Carrier unit in mm"},
    "CARRIER_ACCELERATION":  {"value": 1.0,    "description": "Carrier acceleration in mm/s²"},
    "CARRIER_TOP_SPEED":     {"value": 20.0,   "description": "Carrier max speed in mm/s"},
    "MAP_WIDTH_MM":               {"value": 1000.0, "description": "Map width in mm"},
    "MAP_HEIGHT_MM":              {"value": 1000.0, "description": "Map height in mm"},
    "CARRIER_VISION_RADIUS_MM":   {"value": 50.0,   "description": "Radius of the Carrier's visible area in mm"},
    "DEFAULT_DRONE_DIAMETER_MM":  {"value": 3.0,    "description": "Diameter of a default drone in mm"},
    "DEFAULT_DRONE_VISION_MM":    {"value": 50.0,   "description": "Vision radius of a default drone in mm"},
    "STARTING_DRONES":            {"value": 5.0,    "description": "Number of drones at game start"},
    "DRONE_START_RADIUS_MM":       {"value": 20.0,   "description": "Distance from carrier centre to each drone at start in mm"},
    "DEFAULT_DRONE_ACCELERATION": {"value": 400.0,  "description": "Drone acceleration in mm/s²"},
    "DEFAULT_DRONE_MAX_SPEED":    {"value": 200.0,  "description": "Drone max speed in mm/s"},
    "DRONE_MAX_RADIUS_MM":        {"value": 300.0,  "description": "Max distance a drone can be commanded from the carrier in mm"},
    "ISLANDS_PER_MAP":            {"value": 3.0,    "description": "Number of random island obstacles on the map"},
    "ISLAND_SIZE_MM":             {"value": 30.0,   "description": "Full width/diameter of each island in mm"},
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

    # ── Header (fixed, outside scroll area) ─────────────────────────────────
    tk.Label(
        root, text="Game Configuration",
        bg="#1a1a2e", fg="#4ecca3",
        font=("Courier", 14, "bold")
    ).grid(row=0, column=0, columnspan=2, pady=(14, 10), padx=20, sticky="w")

    tk.Frame(root, bg="#4ecca3", height=1).grid(
        row=1, column=0, columnspan=2, sticky="ew", padx=20
    )

    # ── Scrollable canvas area ───────────────────────────────────────────────
    scroll_frame = tk.Frame(root, bg="#1a1a2e")
    scroll_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=0, pady=0)

    canvas = tk.Canvas(scroll_frame, bg="#1a1a2e", highlightthickness=0, width=420, height=420)
    scrollbar = tk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(canvas, bg="#1a1a2e")
    inner_window = canvas.create_window((0, 0), window=inner, anchor="nw")

    def on_inner_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_canvas_configure(event):
        canvas.itemconfig(inner_window, width=event.width)

    inner.bind("<Configure>", on_inner_configure)
    canvas.bind("<Configure>", on_canvas_configure)

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # ── Variable rows (inside scrollable frame) ──────────────────────────────
    entries = {}
    row = 0
    for key, meta in data.items():
        tk.Label(
            inner, text=key,
            bg="#1a1a2e", fg="#ffffff",
            font=("Courier", 11, "bold"), anchor="w"
        ).grid(row=row, column=0, sticky="w", padx=20, pady=(10, 0))

        var = tk.StringVar(value=str(meta["value"]))
        tk.Entry(
            inner, textvariable=var, width=10,
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
            inner, text=meta["description"],
            bg="#1a1a2e", fg="#7a7a9a",
            font=("Courier", 9), anchor="w"
        ).grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=20, pady=(2, 0))
        row += 2

    # Bottom padding inside scroll area
    tk.Frame(inner, bg="#1a1a2e", height=10).grid(row=row, column=0, columnspan=2)

    # ── Divider (fixed, outside scroll area) ─────────────────────────────────
    tk.Frame(root, bg="#3a3a5a", height=1).grid(
        row=3, column=0, columnspan=2, sticky="ew", padx=20, pady=12
    )

    # ── Status label (fixed) ─────────────────────────────────────────────────
    status = tk.Label(root, text="", bg="#1a1a2e", fg="#4ecca3",
                      font=("Courier", 9), wraplength=320, justify="left")

    def on_save():
        # Parse all values — must be positive integers
        errors = []
        parsed = {}
        for key, var in entries.items():
            raw = var.get().strip()
            try:
                val = float(raw)
                if val != int(val):
                    errors.append(f"{key}: must be a whole number (got {raw})")
                elif val <= 0:
                    errors.append(f"{key}: must be greater than 0 (got {raw})")
                else:
                    parsed[key] = int(val)
            except ValueError:
                errors.append(f"{key}: must be a positive integer (got '{raw}')")

        if errors:
            status.config(text="\n".join(errors), fg="#ff6b6b")
            return

        # Validation rules
        if parsed["MAP_HEIGHT_MM"] <= parsed["CARRIER_HEIGHT_MM"]:
            status.config(
                text=f"MAP_HEIGHT_MM ({parsed['MAP_HEIGHT_MM']}) must be greater than "
                     f"CARRIER_HEIGHT_MM ({parsed['CARRIER_HEIGHT_MM']})",
                fg="#ff6b6b"
            )
            return

        if parsed["MAP_WIDTH_MM"] <= parsed["CARRIER_WIDTH_MM"]:
            status.config(
                text=f"MAP_WIDTH_MM ({parsed['MAP_WIDTH_MM']}) must be greater than "
                     f"CARRIER_WIDTH_MM ({parsed['CARRIER_WIDTH_MM']})",
                fg="#ff6b6b"
            )
            return

        # Drone overlap check (N >= 2 only — 1 drone can't overlap itself)
        n = parsed["STARTING_DRONES"]
        r = parsed["DRONE_START_RADIUS_MM"]
        d = parsed["DEFAULT_DRONE_DIAMETER_MM"]
        if n >= 2:
            chord = 2 * r * math.sin(math.pi / n)
            if chord < d:
                min_r = math.ceil(d / (2 * math.sin(math.pi / n)))
                status.config(
                    text=f"Drones would overlap: {n} drones of {d}mm diameter "
                         f"at radius {r}mm.\nMinimum radius needed: {min_r}mm",
                    fg="#ff6b6b"
                )
                return

        # Drone start radius must fit within max radius
        if parsed["DRONE_START_RADIUS_MM"] > parsed["DRONE_MAX_RADIUS_MM"]:
            status.config(
                text=f"DRONE_START_RADIUS_MM ({parsed['DRONE_START_RADIUS_MM']}) "
                     f"cannot exceed DRONE_MAX_RADIUS_MM ({parsed['DRONE_MAX_RADIUS_MM']})",
                fg="#ff6b6b"
            )
            return

        # All good — commit and save
        for key, value in parsed.items():
            data[key]["value"] = value
        save(data)
        status.config(text="Saved. Carrier reset to map center.", fg="#4ecca3")

    tk.Button(
        root, text="  SAVE  ",
        command=on_save,
        bg="#4ecca3", fg="#0f0f23",
        font=("Courier", 11, "bold"),
        relief="flat", cursor="hand2",
        padx=10, pady=6,
        activebackground="#3ab892", activeforeground="#0f0f23"
    ).grid(row=4, column=0, columnspan=2, padx=20, sticky="ew")

    status.grid(row=5, column=0, columnspan=2, pady=(6, 14))

    root.mainloop()


if __name__ == "__main__":
    build_ui()
