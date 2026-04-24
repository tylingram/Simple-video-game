"""
Island RTS - WebSocket relay server.

Two separate connection lifecycles:
  1. Lobby connections  — challenge/accept flow, create room_id, then navigate away
  2. Game connections   — reconnect with join_room(room_id, role), relay state

Rooms are stored in `game_rooms` keyed by room_id so they survive the lobby
WebSocket closing when the browser navigates to the game page.
"""
import asyncio
import json
import os
import uuid

import websockets
from websockets.server import serve

# ----- in-memory state --------------------------------------------------
# Lobby: active WebSocket sessions (may be lobby OR game clients)
clients: dict = {}   # client_id -> {ws, name, room}

# Rooms created during lobby challenge/accept, waiting for game clients
# game_rooms[room_id] = {"host": client_id_or_None, "guest": client_id_or_None}
game_rooms: dict = {}


# ----- helpers ----------------------------------------------------------

async def _send(client_id: str, data: dict):
    c = clients.get(client_id)
    if c:
        try:
            await c["ws"].send(json.dumps(data))
        except Exception:
            pass


def _opponent_id(room_id: str, client_id: str):
    room = game_rooms.get(room_id, {})
    if room.get("host") == client_id:
        return room.get("guest")
    return room.get("host")


async def _broadcast_lobby():
    lobby = [
        {"id": cid, "name": c["name"]}
        for cid, c in clients.items()
        if c["name"] and c["room"] is None
    ]
    msg = json.dumps({"type": "lobby_update", "players": lobby})
    for cid, c in list(clients.items()):
        if c["name"] and c["room"] is None:
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

    # ── Lobby messages ──────────────────────────────────────────────────
    if t == "join":
        raw = str(data.get("name", "")).strip()
        client["name"] = (raw or "Player")[:20]
        await _broadcast_lobby()

    elif t == "challenge":
        target = data.get("target_id")
        if target and target in clients and clients[target]["room"] is None:
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
        # Store in game_rooms — survives lobby WS disconnect
        game_rooms[room_id] = {"host": None, "guest": None}
        clients[host_id]["room"]  = room_id
        clients[guest_id]["room"] = room_id
        base = {"type": "match_start", "room_id": room_id}
        await _send(host_id,  {**base, "role": "host",  "opponent_name": clients[guest_id]["name"]})
        await _send(guest_id, {**base, "role": "guest", "opponent_name": clients[host_id]["name"]})
        await _broadcast_lobby()

    elif t == "challenge_decline":
        host_id = data.get("from_id")
        if host_id in clients:
            await _send(host_id, {"type": "challenge_declined", "from_name": client["name"]})

    # ── Game reconnect ───────────────────────────────────────────────────
    elif t == "join_room":
        room_id = data.get("room_id", "")
        role    = data.get("role", "")
        if role not in ("host", "guest"):
            return
        # Create room entry if it doesn't exist yet
        if room_id not in game_rooms:
            game_rooms[room_id] = {"host": None, "guest": None}
        game_rooms[room_id][role] = client_id
        client["room"] = room_id
        print(f"[room {room_id}] {role} joined as {client_id}  "
              f"(host={game_rooms[room_id]['host']} guest={game_rooms[room_id]['guest']})",
              flush=True)

    # ── In-game relay ────────────────────────────────────────────────────
    elif t in ("game_state", "fire", "game_over"):
        room_id = client["room"]
        if room_id:
            opp = _opponent_id(room_id, client_id)
            if opp:
                await _send(opp, data)
        if t == "game_over":
            if room_id:
                game_rooms.pop(room_id, None)
                client["room"] = None
            await _broadcast_lobby()

    elif t == "back_to_lobby":
        room_id = client["room"]
        if room_id:
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
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await _handle(client_id, data)
    finally:
        room_id = clients[client_id]["room"]
        if room_id and room_id in game_rooms:
            # Only notify opponent if they're a connected game client
            opp = _opponent_id(room_id, client_id)
            if opp and opp in clients:
                await _send(opp, {"type": "opponent_disconnected"})
            # Remove this client's slot from the room but keep the room
            # (the other player's slot stays valid)
            room = game_rooms.get(room_id, {})
            if room.get("host") == client_id:
                room["host"] = None
            elif room.get("guest") == client_id:
                room["guest"] = None
            # Clean up empty rooms
            if not room.get("host") and not room.get("guest"):
                game_rooms.pop(room_id, None)
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
