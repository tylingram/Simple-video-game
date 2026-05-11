"""
Island RTS - WebSocket relay server.

Supports 1v1 and 2v2 modes.

Lobby lifecycle:
  join → (optional: partner_request/accept to form a team) →
  challenge / team_challenge → match_start → navigate to game

Game lifecycle:
  join_room(room_id, role) → room_ready (when all slots filled) →
  relay input/fire/drone_cmd/game_over until back_to_lobby
"""
import asyncio
import json
import os
import uuid

import websockets
from websockets.server import serve

# ----- in-memory state --------------------------------------------------
clients: dict     = {}   # client_id → {ws, name, room}
game_rooms: dict  = {}   # room_id   → {mode, slot_name: cid_or_None, ...}
lobby_teams: dict = {}   # team_id   → {p1: cid, p2: cid_or_None}
client_team: dict = {}   # cid       → team_id


# ----- helpers ----------------------------------------------------------

async def _send(client_id: str, data: dict):
    c = clients.get(client_id)
    if c:
        try:
            await c["ws"].send(json.dumps(data))
        except Exception:
            pass


def _room_player_ids(room_id: str) -> list:
    """All non-None client IDs currently in the room."""
    room = game_rooms.get(room_id, {})
    return [
        cid for key, cid in room.items()
        if key in ("host", "guest", "t1p1", "t1p2", "t2p1", "t2p2") and cid
    ]


def _opponent_id(room_id: str, client_id: str):
    """1v1 compat: return the single opponent in a host/guest room."""
    room = game_rooms.get(room_id, {})
    if room.get("host") == client_id:
        return room.get("guest")
    return room.get("host")


def _dissolve_team(team_id: str):
    """Remove a lobby team and clear each member's client_team entry."""
    team = lobby_teams.pop(team_id, {})
    for key in ("p1", "p2"):
        cid = team.get(key)
        if cid:
            client_team.pop(cid, None)


async def _broadcast_lobby():
    """Push current lobby state (solo players + available teams) to all idle clients."""
    solo = []
    teams = []
    seen_teams = set()

    for cid, c in clients.items():
        if not c["name"] or c["room"]:
            continue
        tid = client_team.get(cid)
        if tid is None:
            solo.append({"id": cid, "name": c["name"]})
        elif tid not in seen_teams:
            seen_teams.add(tid)
            team = lobby_teams.get(tid, {})
            p1, p2 = team.get("p1"), team.get("p2")
            if p1 and p2:   # only show complete teams
                p1n = (clients.get(p1) or {}).get("name", "?")
                p2n = (clients.get(p2) or {}).get("name", "?")
                teams.append({
                    "team_id": tid,
                    "p1_id": p1, "p1_name": p1n,
                    "p2_id": p2, "p2_name": p2n,
                })

    msg = json.dumps({"type": "lobby_update", "players": solo, "teams": teams})
    for c in list(clients.values()):
        if c["name"] and not c["room"]:
            try:
                await c["ws"].send(msg)
            except Exception:
                pass


# ----- message router ---------------------------------------------------

async def _handle(client_id: str, data: dict):
    t      = data.get("type")
    client = clients.get(client_id)
    if not client:
        return

    # ── Lobby: join ──────────────────────────────────────────────────────
    if t == "join":
        raw = str(data.get("name", "")).strip()
        client["name"] = (raw or "Player")[:20]
        await _broadcast_lobby()

    # ── Lobby: partner management ────────────────────────────────────────
    elif t == "partner_request":
        target = data.get("target_id")
        if (target and target in clients
                and not clients[target]["room"]
                and client_team.get(target) is None
                and client_team.get(client_id) is None):
            await _send(target, {
                "type":      "partner_request",
                "from_id":   client_id,
                "from_name": client["name"],
            })

    elif t == "partner_accept":
        inviter_id = data.get("from_id")
        if not inviter_id or inviter_id not in clients:
            return
        if (client_team.get(client_id) is not None
                or client_team.get(inviter_id) is not None
                or clients[inviter_id]["room"] or client["room"]):
            return
        tid = str(uuid.uuid4())[:8]
        lobby_teams[tid] = {"p1": inviter_id, "p2": client_id}
        client_team[inviter_id] = tid
        client_team[client_id]  = tid
        await _send(inviter_id, {
            "type": "partner_formed", "team_id": tid,
            "partner_id": client_id, "partner_name": client["name"],
        })
        await _send(client_id, {
            "type": "partner_formed", "team_id": tid,
            "partner_id": inviter_id, "partner_name": clients[inviter_id]["name"],
        })
        await _broadcast_lobby()

    elif t == "partner_decline":
        inviter_id = data.get("from_id")
        if inviter_id in clients:
            await _send(inviter_id, {"type": "partner_declined", "from_name": client["name"]})

    elif t == "partner_cancel":
        tid = client_team.get(client_id)
        if tid:
            team   = lobby_teams.get(tid, {})
            other  = team.get("p2") if team.get("p1") == client_id else team.get("p1")
            _dissolve_team(tid)
            if other and other in clients:
                await _send(other, {"type": "partner_cancelled"})
        await _broadcast_lobby()

    # ── Lobby: 1v1 challenge ─────────────────────────────────────────────
    elif t == "challenge":
        target = data.get("target_id")
        if (target and target in clients
                and not clients[target]["room"]
                and client_team.get(target) is None):
            await _send(target, {
                "type":      "challenge_received",
                "from_id":   client_id,
                "from_name": client["name"],
            })

    elif t == "challenge_accept":
        host_id  = data.get("from_id")
        guest_id = client_id
        if not host_id or host_id not in clients or clients[host_id]["room"]:
            return
        room_id = str(uuid.uuid4())[:8]
        game_rooms[room_id] = {"mode": "1v1", "host": None, "guest": None}
        clients[host_id]["room"]  = room_id
        clients[guest_id]["room"] = room_id
        base = {"type": "match_start", "room_id": room_id, "mode": "1v1"}
        await _send(host_id,  {**base, "role": "host",  "opponent_name": clients[guest_id]["name"]})
        await _send(guest_id, {**base, "role": "guest", "opponent_name": clients[host_id]["name"]})
        await _broadcast_lobby()

    elif t == "challenge_decline":
        host_id = data.get("from_id")
        if host_id in clients:
            await _send(host_id, {"type": "challenge_declined", "from_name": client["name"]})

    # ── Lobby: 2v2 team challenge ────────────────────────────────────────
    elif t == "team_challenge":
        target_tid = data.get("target_team_id")
        my_tid     = client_team.get(client_id)
        if not my_tid or not target_tid:
            return
        my_team     = lobby_teams.get(my_tid,     {})
        target_team = lobby_teams.get(target_tid, {})
        if not my_team.get("p2") or not target_team.get("p2"):
            return   # both teams must be full (2 players each)
        my_name = (
            f"{(clients.get(my_team['p1']) or {}).get('name','?')} "
            f"& {(clients.get(my_team['p2']) or {}).get('name','?')}"
        )
        for pid in (target_team.get("p1"), target_team.get("p2")):
            if pid and pid in clients:
                await _send(pid, {
                    "type":         "team_challenge_received",
                    "from_team_id": my_tid,
                    "team_name":    my_name,
                })

    elif t == "team_challenge_accept":
        from_tid = data.get("from_team_id")
        my_tid   = client_team.get(client_id)
        if not from_tid or not my_tid:
            return
        challenger = lobby_teams.get(from_tid, {})
        defender   = lobby_teams.get(my_tid,   {})
        if not challenger.get("p2") or not defender.get("p2"):
            return
        t1p1, t1p2 = challenger["p1"], challenger["p2"]
        t2p1, t2p2 = defender["p1"],   defender["p2"]
        room_id = str(uuid.uuid4())[:8]
        game_rooms[room_id] = {
            "mode": "2v2",
            "t1p1": None, "t1p2": None,
            "t2p1": None, "t2p2": None,
        }
        for cid in (t1p1, t1p2, t2p1, t2p2):
            clients[cid]["room"] = room_id

        def _name(cid):
            return (clients.get(cid) or {}).get("name", "?")

        base = {"type": "match_start", "room_id": room_id, "mode": "2v2"}
        await _send(t1p1, {**base, "role": "t1p1", "ally": _name(t1p2),
                           "enemies": [_name(t2p1), _name(t2p2)]})
        await _send(t1p2, {**base, "role": "t1p2", "ally": _name(t1p1),
                           "enemies": [_name(t2p1), _name(t2p2)]})
        await _send(t2p1, {**base, "role": "t2p1", "ally": _name(t2p2),
                           "enemies": [_name(t1p1), _name(t1p2)]})
        await _send(t2p2, {**base, "role": "t2p2", "ally": _name(t2p1),
                           "enemies": [_name(t1p1), _name(t1p2)]})
        _dissolve_team(from_tid)
        _dissolve_team(my_tid)
        await _broadcast_lobby()

    elif t == "team_challenge_decline":
        from_tid = data.get("from_team_id")
        if from_tid:
            team = lobby_teams.get(from_tid, {})
            for pid in (team.get("p1"), team.get("p2")):
                if pid and pid in clients:
                    await _send(pid, {
                        "type":      "team_challenge_declined",
                        "from_name": client["name"],
                    })

    # ── Game reconnect ───────────────────────────────────────────────────
    elif t == "join_room":
        room_id = data.get("room_id", "")
        role    = data.get("role", "")
        if role not in ("host", "guest", "t1p1", "t1p2", "t2p1", "t2p2"):
            return
        if room_id not in game_rooms:
            mode = "2v2" if role.startswith("t") else "1v1"
            game_rooms[room_id] = (
                {"mode": "2v2", "t1p1": None, "t1p2": None, "t2p1": None, "t2p2": None}
                if mode == "2v2" else
                {"mode": "1v1", "host": None, "guest": None}
            )
        game_rooms[room_id][role] = client_id
        client["room"] = room_id
        room = game_rooms[room_id]
        mode = room.get("mode", "1v1")
        print(f"[room {room_id}] {role} → {client_id}  state={room}", flush=True)
        # Send room_ready when all expected slots are filled
        if mode == "2v2":
            ready = all(room.get(r) for r in ("t1p1", "t1p2", "t2p1", "t2p2"))
        else:
            ready = bool(room.get("host") and room.get("guest"))
        if ready:
            rr = {"type": "room_ready", "room_id": room_id}
            for cid in _room_player_ids(room_id):
                await _send(cid, rr)
            print(f"[room {room_id}] all players present — sent room_ready", flush=True)

    # ── WebRTC signalling (1v1 only) ─────────────────────────────────────
    elif t in ("rtc_ready", "rtc_offer", "rtc_answer", "rtc_ice"):
        room_id = data.get("room_id") or client["room"]
        if room_id:
            opp = _opponent_id(room_id, client_id)
            if opp:
                await _send(opp, data)

    # ── In-game relay — broadcast to all other room members ───────────────
    elif t in ("input", "drone_cmd", "game_state", "fire", "game_over"):
        room_id = client["room"]
        if room_id:
            for opp in _room_player_ids(room_id):
                if opp != client_id:
                    await _send(opp, data)
        if t == "game_over":
            await _broadcast_lobby()

    elif t == "back_to_lobby":
        room_id = client["room"]
        if room_id and room_id in game_rooms:
            room = game_rooms[room_id]
            for key in ("host", "guest", "t1p1", "t1p2", "t2p1", "t2p2"):
                if room.get(key) == client_id:
                    room[key] = None
            if not _room_player_ids(room_id):
                game_rooms.pop(room_id, None)
        client["room"] = None
        await _broadcast_lobby()


# ----- connection handler -----------------------------------------------

async def handler(ws):
    client_id = str(uuid.uuid4())[:8]
    clients[client_id] = {"ws": ws, "name": None, "room": None}
    print(f"[+] {client_id} connected  (total={len(clients)})", flush=True)
    try:
        async for raw in ws:
            # Fast path: relay high-frequency game messages without JSON decode
            client = clients.get(client_id)
            if client and client["room"]:
                if '"input"' in raw or '"fire"' in raw or '"drone_cmd"' in raw:
                    for opp_cid in _room_player_ids(client["room"]):
                        if opp_cid != client_id:
                            c = clients.get(opp_cid)
                            if c:
                                try:
                                    await c["ws"].send(raw)
                                except Exception:
                                    pass
                    continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await _handle(client_id, data)

    finally:
        room_id = clients[client_id]["room"]
        if room_id and room_id in game_rooms:
            # Notify remaining room members
            for opp_cid in _room_player_ids(room_id):
                if opp_cid != client_id:
                    await _send(opp_cid, {"type": "opponent_disconnected"})
            # Vacate this client's slot; clean up empty rooms
            room = game_rooms.get(room_id, {})
            for key in ("host", "guest", "t1p1", "t1p2", "t2p1", "t2p2"):
                if room.get(key) == client_id:
                    room[key] = None
            if not _room_player_ids(room_id):
                game_rooms.pop(room_id, None)

        # Clean up lobby team membership
        tid = client_team.pop(client_id, None)
        if tid and tid in lobby_teams:
            team  = lobby_teams[tid]
            other = team.get("p2") if team.get("p1") == client_id else team.get("p1")
            _dissolve_team(tid)
            if other and other in clients:
                await _send(other, {"type": "partner_cancelled"})

        clients.pop(client_id, None)
        print(f"[-] {client_id} disconnected (total={len(clients)})", flush=True)
        await _broadcast_lobby()


async def main():
    port = int(os.environ.get("PORT", 8765))
    print(f"Island RTS server listening on 0.0.0.0:{port}", flush=True)
    async with serve(handler, "0.0.0.0", port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
