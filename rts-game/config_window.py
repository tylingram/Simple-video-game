"""
Configuration window — runs in a background thread alongside the game.
Edit values and hit Save to apply them instantly to the running game.
"""
import threading
import tkinter as tk
import config as cfg


class ConfigWindow:
    def __init__(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        root = tk.Tk()
        root.title("RTS Config")
        root.resizable(False, False)
        root.configure(bg="#1a1a2e")

        # ── Header ──────────────────────────────────────────────────────────
        tk.Label(
            root, text="Game Configuration",
            bg="#1a1a2e", fg="#4ecca3",
            font=("Courier", 14, "bold")
        ).grid(row=0, column=0, columnspan=2, pady=(14, 10), padx=20, sticky="w")

        tk.Frame(root, bg="#4ecca3", height=1).grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=20
        )

        # ── Variable rows ────────────────────────────────────────────────────
        self._entries = {}
        vars_data = cfg.all_vars()
        row = 2

        for key, data in vars_data.items():
            # Variable name
            tk.Label(
                root, text=key,
                bg="#1a1a2e", fg="#ffffff",
                font=("Courier", 11, "bold"), anchor="w"
            ).grid(row=row, column=0, sticky="w", padx=20, pady=(10, 0))

            # Value entry
            var = tk.StringVar(value=str(data["value"]))
            entry = tk.Entry(
                root, textvariable=var, width=10,
                bg="#0f0f23", fg="#4ecca3",
                insertbackground="white",
                font=("Courier", 11),
                relief="flat", bd=6,
                highlightthickness=1,
                highlightcolor="#4ecca3",
                highlightbackground="#3a3a5a"
            )
            entry.grid(row=row, column=1, padx=(8, 20), pady=(10, 0), sticky="w")
            self._entries[key] = var

            # Description
            tk.Label(
                root, text=data["description"],
                bg="#1a1a2e", fg="#7a7a9a",
                font=("Courier", 9), anchor="w"
            ).grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=20, pady=(2, 0))

            row += 2

        # ── Divider ──────────────────────────────────────────────────────────
        tk.Frame(root, bg="#3a3a5a", height=1).grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=20, pady=12
        )

        # ── Save button ──────────────────────────────────────────────────────
        tk.Button(
            root, text="  SAVE  ",
            command=lambda: self._save(status_label),
            bg="#4ecca3", fg="#0f0f23",
            font=("Courier", 11, "bold"),
            relief="flat", cursor="hand2",
            padx=10, pady=6,
            activebackground="#3ab892", activeforeground="#0f0f23"
        ).grid(row=row + 1, column=0, columnspan=2, padx=20, sticky="ew")

        # ── Status label ─────────────────────────────────────────────────────
        status_label = tk.Label(
            root, text="",
            bg="#1a1a2e", fg="#4ecca3",
            font=("Courier", 9)
        )
        status_label.grid(row=row + 2, column=0, columnspan=2, pady=(6, 14))

        root.mainloop()

    def _save(self, status_label):
        errors = []
        for key, var in self._entries.items():
            try:
                cfg.set_value(key, float(var.get()))
            except ValueError:
                errors.append(key)

        if errors:
            status_label.config(text=f"Invalid value: {', '.join(errors)}", fg="#ff6b6b")
        else:
            status_label.config(text="Saved — applied to game.", fg="#4ecca3")
