"""
Live game configuration variables.
Values are persisted to config.json so changes survive restarts.
"""
import json
import threading
from pathlib import Path

_lock      = threading.Lock()
_SAVE_FILE = Path(__file__).parent / "config.json"

# Defaults — only used when no saved value exists
_defaults = {
    "HUD_SIZE": {
        "value": 10.0,
        "description": "Changes the % of screen taken up by HUD",
    },
    "CARRIER_WIDTH_MM": {
        "value": 5.0,
        "description": "Width of the Carrier unit in mm",
    },
    "CARRIER_HEIGHT_MM": {
        "value": 10.0,
        "description": "Height of the Carrier unit in mm",
    },
}


def _load():
    """Merge saved values on top of defaults."""
    data = {k: dict(v) for k, v in _defaults.items()}
    if _SAVE_FILE.exists():
        try:
            saved = json.loads(_SAVE_FILE.read_text())
            for key, value in saved.items():
                if key in data:
                    data[key]["value"] = value
        except Exception:
            pass  # corrupt file — fall back to defaults
    return data


_data = _load()


def get(key):
    with _lock:
        return _data[key]["value"]


def set_value(key, value):
    with _lock:
        _data[key]["value"] = value


def save_to_disk():
    """Write current values to config.json."""
    with _lock:
        snapshot = {k: v["value"] for k, v in _data.items()}
    _SAVE_FILE.write_text(json.dumps(snapshot, indent=2))


def load_from_disk():
    """Reload values from config.json (picks up changes from the config editor)."""
    if not _SAVE_FILE.exists():
        return
    try:
        saved = json.loads(_SAVE_FILE.read_text())
        with _lock:
            for key, value in saved.items():
                if key in _data:
                    _data[key]["value"] = value
    except Exception:
        pass


def all_vars():
    """Returns a snapshot of all config entries."""
    with _lock:
        return {k: dict(v) for k, v in _data.items()}
