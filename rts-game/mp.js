// Island RTS — Multiplayer transport layer
// 1v1: tries WebRTC peer-to-peer first; falls back to WebSocket relay.
// 2v2: uses WebSocket relay only (multi-peer WebRTC is too complex for 4 players).
// Exposes window.mp_ready / mp_send / mp_poll / mp_close for Python.
//
// WebRTC handshake (race-free, 1v1 only):
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
  var role      = params.get('role');  // 'host'|'guest' (1v1) or 't1p1'..'t2p2' (2v2)

  // 2v2 uses WS relay only; 1v1 gets WebRTC P2P attempt.
  var is2v2 = role && /^t[12]p[12]$/.test(role);

  // ── Message buffers ──────────────────────────────────────────────────────
  // 'input' packets: keep only the NEWEST per sender (stale ones are useless).
  // All other messages (fire, drone_cmd, game_over, …): keep in order.
  var latestStates = {};   // sender_role → raw string (latest 'input' from that sender)
  var eventBuf     = [];

  function handleGameData(raw) {
    if (raw.indexOf('"input"') !== -1) {
      // Extract the "from" field to key per-sender state.
      // Python's json.dumps always writes "from": "t1p1" with a space after colon.
      var m = raw.match(/"from"\s*:\s*"([^"]+)"/);
      var key = m ? m[1] : 'default';
      latestStates[key] = raw;   // replace — never queue stale input syncs
    } else {
      eventBuf.push(raw);
    }
  }

  // ── WebRTC (1v1 only) ────────────────────────────────────────────────────
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

  if (!is2v2) {
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
  } else {
    console.log('[MP] 2v2 mode — WebSocket relay only');
  }

  // ── WebSocket (signalling + data relay) ───────────────────────────────────
  var ws = new WebSocket(serverUrl);

  ws.onopen = function () {
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
      console.log('[MP] room_ready received, role=' + role);
      if (role === 'host' && pc) {
        createOffer();
      }

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
      // Game data arriving via WebSocket (fallback or 2v2 relay).
      handleGameData(e.data);
    }
  };

  ws.onerror = function (e) { console.error('[MP] WS error', e); };
  ws.onclose = function ()  { console.log('[MP] WS closed'); };

  // ── Public API (called by Python via js.window.*) ─────────────────────────
  window.mp_ready = function () {
    return (dc !== null && dc.readyState === 'open') ||
           (ws !== null && ws.readyState === 1);
  };

  window.mp_send = function (s) {
    // Prefer low-latency P2P data channel; fall back to WS relay.
    if (dc && dc.readyState === 'open') {
      dc.send(s);
    } else if (ws && ws.readyState === 1) {
      ws.send(s);
    }
  };

  window.mp_poll = function () {
    var msgs = [];
    // Collect the latest 'input' from every sender (drop stale ones).
    for (var k in latestStates) {
      if (latestStates[k] !== null) {
        msgs.push(latestStates[k]);
      }
    }
    latestStates = {};
    // Append all queued events (fire, drone_cmd, game_over, …) in order.
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
