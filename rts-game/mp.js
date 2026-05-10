// Island RTS — Multiplayer transport layer
// Tries WebRTC peer-to-peer first; falls back to WebSocket relay.
// Exposes window.mp_ready / mp_send / mp_poll / mp_close for Python.
//
// WebRTC handshake (race-free):
//   Both players call join_room on connect.
//   Server sends room_ready to BOTH once both are present.
//   Host creates offer on room_ready; guest waits for rtc_offer.
(function () {
  var params = new URLSearchParams(window.location.search);
  if (params.get('mp') !== '1') {
    // Not a multiplayer session — expose no-op stubs so Python never crashes.
    window.mp_ready = function () { return false; };
    window.mp_send  = function () {};
    window.mp_poll  = function () { return '[]'; };
    window.mp_close = function () {};
    return;
  }

  var serverUrl = params.get('server');
  var roomId    = params.get('room');
  var role      = params.get('role');  // 'host' or 'guest'

  // ── Message buffers ──────────────────────────────────────────────────────
  // game_state packets: keep only the newest one (old ones are stale).
  // All other messages (fire, game_over, …): keep in order.
  var latestState = null;
  var eventBuf    = [];

  function handleGameData(raw) {
    if (raw.indexOf('"input"') !== -1) {
      latestState = raw;      // replace — never queue stale input syncs
    } else {
      eventBuf.push(raw);
    }
  }

  // ── WebRTC ───────────────────────────────────────────────────────────────
  var pc = null;
  var dc = null;  // RTCDataChannel (once established)

  function setupDC(channel) {
    dc = channel;
    dc.onopen    = function () { console.log('[MP] WebRTC data channel open — P2P active'); };
    dc.onmessage = function (e) { handleGameData(e.data); };
    dc.onerror   = function (e) { console.error('[MP] DC error', e); };
    dc.onclose   = function ()  { console.log('[MP] DC closed'); dc = null; };
  }

  function createOffer() {
    if (!pc) return;
    pc.createOffer()
      .then(function (offer) { return pc.setLocalDescription(offer); })
      .then(function () {
        ws.send(JSON.stringify({
          type: 'rtc_offer', room_id: roomId,
          sdp: pc.localDescription.sdp
        }));
        console.log('[MP] sent rtc_offer');
      })
      .catch(function (err) { console.error('[MP] offer error:', err); });
  }

  try {
    pc = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
      ]
    });

    // Host creates the data channel; guest receives it via ondatachannel.
    if (role === 'host') {
      setupDC(pc.createDataChannel('game', { ordered: true }));
    }
    pc.ondatachannel = function (e) { setupDC(e.channel); };

    pc.onicecandidate = function (e) {
      if (e.candidate && ws && ws.readyState === 1) {
        ws.send(JSON.stringify({
          type: 'rtc_ice', room_id: roomId,
          c: e.candidate.candidate,
          m: e.candidate.sdpMid,
          i: e.candidate.sdpMLineIndex
        }));
      }
    };

    pc.onconnectionstatechange = function () {
      console.log('[MP] PC state:', pc.connectionState);
    };
  } catch (ex) {
    console.warn('[MP] WebRTC not available, using WS relay only:', ex);
    pc = null;
  }

  // ── WebSocket (signalling + fallback data) ────────────────────────────────
  var ws = new WebSocket(serverUrl);

  ws.onopen = function () {
    // Join the game room. Server will send room_ready to both players once
    // both have joined — this eliminates the race condition where rtc_ready
    // could arrive before the opponent's join_room was processed.
    ws.send(JSON.stringify({ type: 'join_room', room_id: roomId, role: role }));
    console.log('[MP] joined room ' + roomId + ' as ' + role);
  };

  ws.onmessage = function (e) {
    var msg;
    try { msg = JSON.parse(e.data); } catch (ex) {
      handleGameData(e.data);
      return;
    }

    var t = msg.type;

    if (t === 'room_ready') {
      // Server confirmed both players are present. Host starts the WebRTC offer.
      console.log('[MP] room_ready received, role=' + role);
      if (role === 'host' && pc) {
        createOffer();
      }
      // Guest just waits for the rtc_offer from the host.

    } else if (t === 'rtc_offer' && pc) {
      pc.setRemoteDescription({ type: 'offer', sdp: msg.sdp })
        .then(function () { return pc.createAnswer(); })
        .then(function (ans) { return pc.setLocalDescription(ans); })
        .then(function () {
          ws.send(JSON.stringify({
            type: 'rtc_answer', room_id: roomId,
            sdp: pc.localDescription.sdp
          }));
          console.log('[MP] sent rtc_answer');
        })
        .catch(function (err) { console.error('[MP] answer error:', err); });

    } else if (t === 'rtc_answer' && pc) {
      pc.setRemoteDescription({ type: 'answer', sdp: msg.sdp })
        .catch(function (err) { console.error('[MP] setRemote error:', err); });

    } else if (t === 'rtc_ice' && pc) {
      pc.addIceCandidate({ candidate: msg.c, sdpMid: msg.m, sdpMLineIndex: msg.i })
        .catch(function (err) { console.error('[MP] ICE error:', err); });

    } else {
      // Game data arriving via WebSocket fallback (before DC opens or if WebRTC
      // is unavailable).
      handleGameData(e.data);
    }
  };

  ws.onerror = function (e) { console.error('[MP] WS error', e); };
  ws.onclose = function ()  { console.log('[MP] WS closed'); };

  // ── Public API (called by Python via js.window.*) ─────────────────────────
  window.mp_ready = function () {
    // Ready as soon as WebSocket opens (game runs on WS until DC opens).
    return (dc !== null && dc.readyState === 'open') ||
           (ws !== null && ws.readyState === 1);
  };

  window.mp_send = function (s) {
    // Prefer the low-latency P2P data channel; fall back to WS relay.
    if (dc && dc.readyState === 'open') {
      dc.send(s);
    } else if (ws && ws.readyState === 1) {
      ws.send(s);
    }
  };

  window.mp_poll = function () {
    var msgs = [];
    if (latestState !== null) { msgs.push(latestState); latestState = null; }
    msgs = msgs.concat(eventBuf);
    eventBuf = [];
    return JSON.stringify(msgs);
  };

  window.mp_close = function () {
    if (dc) { dc.close(); dc = null; }
    if (pc) { pc.close(); pc = null; }
    if (ws) { ws.close(); ws = null; }
  };
})();
