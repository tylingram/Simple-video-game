"""
Island RTS — multiplayer WebSocket client for pygbag (emscripten/pyodide).
Uses pyodide's js module + create_proxy to hook Python callbacks directly
into the browser WebSocket, avoiding js.eval() which is unreliable.
"""
import json
import sys

# ── public ────────────────────────────────────────────────────────────────────
room_id:       str = ""
role:          str = ""
opponent_name: str = "Opponent"

# ── internal ──────────────────────────────────────────────────────────────────
_ws   = None          # JS WebSocket object
_buf  = []            # raw JSON strings received
_proxies = []         # keep create_proxy refs alive (prevents GC)


def setup(server_url: str, r_id: str, r_role: str, opp: str) -> None:
    global room_id, role, opponent_name, _ws, _buf, _proxies
    room_id       = r_id
    role          = r_role
    opponent_name = opp
    _buf          = []
    _proxies      = []

    if sys.platform != "emscripten":
        return

    try:
        import js
        from pyodide.ffi import create_proxy

        _ws = js.WebSocket.new(server_url)

        def _on_open(evt):
            print(f"[MP] WebSocket connected to {server_url}", flush=True)

        def _on_message(evt):
            _buf.append(str(evt.data))

        def _on_error(evt):
            print("[MP] WebSocket error", flush=True)

        def _on_close(evt):
            print("[MP] WebSocket closed", flush=True)

        # create_proxy keeps Python callables alive as JS function objects
        p_open    = create_proxy(_on_open)
        p_message = create_proxy(_on_message)
        p_error   = create_proxy(_on_error)
        p_close   = create_proxy(_on_close)
        _proxies  = [p_open, p_message, p_error, p_close]  # prevent GC

        _ws.onopen    = p_open
        _ws.onmessage = p_message
        _ws.onerror   = p_error
        _ws.onclose   = p_close

    except Exception as e:
        print(f"[MP] setup error: {e}", flush=True)


def is_ready() -> bool:
    if _ws is None:
        return False
    try:
        return int(_ws.readyState) == 1   # WebSocket.OPEN
    except Exception:
        return False


def send(data: dict) -> None:
    if _ws is None:
        return
    try:
        if int(_ws.readyState) == 1:
            _ws.send(json.dumps(data))
    except Exception as e:
        print(f"[MP] send error: {e}", flush=True)


def poll() -> list:
    """Return and clear all received messages as parsed dicts."""
    msgs = []
    while _buf:
        raw = _buf.pop(0)
        try:
            msgs.append(json.loads(raw))
        except Exception:
            pass
    return msgs


def close() -> None:
    global _ws, _proxies
    try:
        if _ws is not None:
            _ws.close()
    except Exception:
        pass
    _ws      = None
    _proxies = []
