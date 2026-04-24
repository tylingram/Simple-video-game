"""
Island RTS — multiplayer WebSocket bridge.

In the browser (sys.platform == 'emscripten') this module drives a
JavaScript WebSocket via emscripten's `js` module so that pygbag's
event loop never blocks.  On desktop the module is imported but no
real connection is made (MP only runs on the web build).
"""
import json
import sys

# ── public state ──────────────────────────────────────────────────────────────
room_id:       str  = ""
role:          str  = ""      # "host" or "guest"
opponent_name: str  = "Opponent"
connected:     bool = False


# ── internal ─────────────────────────────────────────────────────────────────
_buf: list = []   # inbound message buffer (dicts)


def setup(server_url: str, r_id: str, r_role: str, opp: str) -> None:
    """Initialise the WebSocket connection.  Call once before the game loop."""
    global room_id, role, opponent_name
    room_id       = r_id
    role          = r_role
    opponent_name = opp

    if sys.platform != "emscripten":
        return   # no-op on desktop

    # Inject a tiny JS helper into the page that buffers inbound messages.
    # Python calls mp_send / mp_poll via the `js` module.
    _inject_js(server_url)


def is_ready() -> bool:
    """True once the WebSocket handshake is complete."""
    if sys.platform != "emscripten":
        return False
    try:
        from js import mp_ready
        return bool(mp_ready())
    except Exception:
        return False


def send(data: dict) -> None:
    """Queue a message to send (fire-and-forget)."""
    if sys.platform != "emscripten":
        return
    try:
        from js import mp_send
        mp_send(json.dumps(data))
    except Exception as e:
        print(f"mp.send error: {e}")


def poll() -> list[dict]:
    """Return and clear all received messages since last call."""
    if sys.platform != "emscripten":
        return []
    try:
        from js import mp_poll
        raw = mp_poll()
        return json.loads(str(raw)) if raw else []
    except Exception as e:
        print(f"mp.poll error: {e}")
        return []


def close() -> None:
    if sys.platform != "emscripten":
        return
    try:
        from js import mp_close
        mp_close()
    except Exception:
        pass


# ── private ───────────────────────────────────────────────────────────────────

def _inject_js(server_url: str) -> None:
    """Eval a JS snippet that creates a WebSocket and exposes helpers globally."""
    js_code = f"""
(function(){{
  var _buf = [];
  var _ws  = new WebSocket({json.dumps(server_url)});
  _ws.onopen    = function(){{ console.log('MP WS open'); }};
  _ws.onmessage = function(e){{ _buf.push(e.data); }};
  _ws.onerror   = function(e){{ console.error('MP WS error', e); }};
  _ws.onclose   = function(){{ console.log('MP WS closed'); }};

  window.mp_ready = function(){{ return _ws.readyState === 1; }};
  window.mp_send  = function(s){{
    if (_ws.readyState === 1) _ws.send(s);
  }};
  window.mp_poll  = function(){{
    var out = JSON.stringify(_buf);
    _buf = [];
    return out;
  }};
  window.mp_close = function(){{ _ws.close(); }};
}})();
"""
    try:
        import js
        js.eval(js_code)
    except Exception as e:
        print(f"mp._inject_js error: {e}")
