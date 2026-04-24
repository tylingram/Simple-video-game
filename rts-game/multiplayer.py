"""
Island RTS — multiplayer bridge.

The WebSocket is set up entirely in JavaScript (injected into index.html
by the deploy workflow) before pygbag/pyodide even loads.  Python just
calls four simple window functions via `import js`:

  window.mp_ready()  → bool   — True once the WS handshake is complete
  window.mp_send(s)  → void   — send a JSON string
  window.mp_poll()   → str    — JSON array of received message strings, clears buffer
  window.mp_close()  → void   — close the connection

This avoids all pyodide-specific APIs (create_proxy, pyodide.ffi, etc.)
and works reliably in pygbag's emscripten runtime.
"""
import json
import sys

# ── public ────────────────────────────────────────────────────────────────────
room_id:       str = ""
role:          str = ""
opponent_name: str = "Opponent"


def setup(server_url: str, r_id: str, r_role: str, opp: str) -> None:
    """Record room metadata. WebSocket is already open (JS set it up in <head>)."""
    global room_id, role, opponent_name
    room_id       = r_id
    role          = r_role
    opponent_name = opp
    # No WebSocket setup needed here — JS handles it before the game loads.


def is_ready() -> bool:
    if sys.platform != "emscripten":
        return False
    try:
        import js
        return bool(js.window.mp_ready())
    except Exception as e:
        print(f"[MP] is_ready error: {e}", flush=True)
        return False


def send(data: dict) -> None:
    if sys.platform != "emscripten":
        return
    try:
        import js
        js.window.mp_send(json.dumps(data))
    except Exception as e:
        print(f"[MP] send error: {e}", flush=True)


def poll() -> list:
    """Return and clear all messages received from the server since last call."""
    if sys.platform != "emscripten":
        return []
    try:
        import js
        raw = js.window.mp_poll()
        if not raw:
            return []
        strings = json.loads(str(raw))   # list of JSON strings
        msgs = []
        for s in strings:
            try:
                msgs.append(json.loads(s))
            except Exception:
                pass
        return msgs
    except Exception as e:
        print(f"[MP] poll error: {e}", flush=True)
        return []


def close() -> None:
    if sys.platform != "emscripten":
        return
    try:
        import js
        js.window.mp_close()
    except Exception:
        pass
