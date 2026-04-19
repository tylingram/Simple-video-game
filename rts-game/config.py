"""
Live game configuration variables.
Values are persisted to config.json so changes survive restarts.
"""
import json
import sys
import threading
from pathlib import Path

_lock = threading.Lock()
# When frozen by PyInstaller write config next to the .exe (writable);
# in normal dev use the source directory as before.
_SAVE_FILE = (Path(sys.executable).parent
              if getattr(sys, 'frozen', False)
              else Path(__file__).parent) / "config.json"

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
    "DRONE_MAX_COUNT": {
        "value": 10.0,
        "description": "Maximum number of player drones at any time",
    },
    "DRONE_RESPAWN_RATE": {
        "value": 15.0,
        "description": "Seconds between drone respawns while below max count",
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
    "PONDS_PER_MAP": {
        "value": 3.0,
        "description": "Number of random ponds on the map",
    },
    "POND_SIZE_MM": {
        "value": 30.0,
        "description": "Full width/diameter of each pond in mm",
    },
    "CARRIER_HP": {
        "value": 10.0,
        "description": "Starting HP for each carrier",
    },
    "DRONE_HP": {
        "value": 5.0,
        "description": "Starting HP for each drone",
    },
    "MISSILE_DAMAGE": {
        "value": 1.0,
        "description": "Damage dealt per missile hit",
    },
    "MISSILE_FIRE_RATE": {
        "value": 1.0,
        "description": "Missiles fired per second per unit",
    },
    "MISSILE_SPEED_MM": {
        "value": 200.0,
        "description": "Missile travel speed in mm/s",
    },
    "ENEMY_CARRIERS": {
        "value": 2.0,
        "description": "Number of enemy carriers spawned on the map",
    },
    "CARRIER_ATTACK_RANGE_MM": {
        "value": 20.0,
        "description": "Max range in mm at which a carrier can fire missiles",
    },
    "DRONE_ATTACK_RANGE_MM": {
        "value": 20.0,
        "description": "Max range in mm at which a drone can fire missiles",
    },
    "ENEMY_AGGRO_RANGE_MM": {
        "value": 150.0,
        "description": "Range in mm at which an enemy carrier will chase the player",
    },
    "EXPLOSIVE_BLAST_RADIUS_MM": {
        "value": 10.0,
        "description": "Blast radius of explosive missiles in mm",
    },
    "EXPLOSIVE_DAMAGE": {
        "value": 1.0,
        "description": "Damage dealt to each unit caught in the blast radius",
    },
    "EXPLOSIVE_FIRE_RATE": {
        "value": 0.25,
        "description": "Explosive missiles fired per second per unit (1 every 4 s)",
    },
    "ENEMY_EXPLOSIVE_DRONE_RATIO": {
        "value": 0.3,
        "description": "Fraction of enemy drones randomly assigned explosive missiles (0–1)",
    },
}


_DEFAULTS_FILE = Path(__file__).parent / "config.defaults.json"


def _load():
    """Load order: code defaults → config.defaults.json → config.json.
    config.defaults.json is tracked in git (shared baseline).
    config.json is gitignored (personal tweaks, hot-reloaded by editor).
    """
    data = {k: dict(v) for k, v in _defaults.items()}
    # 1. Apply shared defaults from tracked file
    if _DEFAULTS_FILE.exists():
        try:
            shared = json.loads(_DEFAULTS_FILE.read_text())
            for key, value in shared.items():
                if key in data:
                    data[key]["value"] = value
        except Exception:
            pass
    # 2. Apply personal overrides from local (gitignored) file
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
