"""
Live game configuration variables.
All values are readable from any module and updated instantly when saved
from the config window.
"""
import threading

_lock = threading.Lock()

_data = {
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


def get(key):
    with _lock:
        return _data[key]["value"]


def set_value(key, value):
    with _lock:
        _data[key]["value"] = value


def all_vars():
    """Returns a snapshot of all config entries."""
    with _lock:
        return {k: dict(v) for k, v in _data.items()}
