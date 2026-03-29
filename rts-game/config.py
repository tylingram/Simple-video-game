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
    "CARRIER_ACCELERATION": {
        "value": 1.0,
        "description": "Carrier acceleration in mm/s²",
    },
    "CARRIER_TOP_SPEED": {
        "value": 20.0,
        "description": "Carrier max speed in mm/s",
    },
    "MAP_WIDTH_MM": {
        "value": 1000.0,
        "description": "Map width in mm",
    },
    "MAP_HEIGHT_MM": {
        "value": 1000.0,
        "description": "Map height in mm",
    },
    "CARRIER_VISION_RADIUS_MM": {
        "value": 50.0,
        "description": "Radius of the Carrier's visible area in mm",
    },
    "DEFAULT_DRONE_DIAMETER_MM": {
        "value": 3.0,
        "description": "Diameter of a default drone in mm",
    },
    "DEFAULT_DRONE_VISION_MM": {
        "value": 50.0,
        "description": "Vision radius of a default drone in mm",
    },
    "STARTING_DRONES": {
        "value": 5.0,
        "description": "Number of drones at game start",
    },
    "DRONE_START_RADIUS_MM": {
        "value": 20.0,
        "description": "Distance from carrier centre to each drone at start in mm",
    },
    "DEFAULT_DRONE_ACCELERATION": {
        "value": 400.0,
        "description": "Drone acceleration in mm/s²",
    },
    "DEFAULT_DRONE_MAX_SPEED": {
        "value": 200.0,
        "description": "Drone max speed in mm/s",
    },
    "DRONE_MAX_RADIUS_MM": {
        "value": 300.0,
        "description": "Max distance a drone can be commanded from the carrier in mm",
    },
    "ISLANDS_PER_MAP": {
        "value": 3.0,
        "description": "Number of random island obstacles on the map",
    },
    "ISLAND_SIZE_MM": {
        "value": 30.0,
        "description": "Full width/diameter of each island in mm",
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
