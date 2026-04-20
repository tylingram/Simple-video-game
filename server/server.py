"""
Island RTS - WebSocket relay server.
Handles lobby presence and in-game state relay between two players.
Deploy to Render (free tier) — set PORT env var (Render injects it automatically).
"""
import asyncio
import json
import os
import uuid

import websockets
from websockets.server import serve

# ----- in-memory state --------------------------------------------------
clients: dict = {}   # client_id -> {ws, name, room}
rooms:   dict = {}   # room_id   -> {host: client_id, guest: client_id}


# ----- helpers ----------------------------------------------------------

async def _send(client_id: str, data: dict):
    c = clients.get(client_id)
    if c:
        try:
            await c["ws"].send(json.dumps(data))
        except Exception:
            pass


def _opponent(room_id: str, client_id: str) -> str | None:
    room = rooms.get(room_id, {})
    if room.get("host") == client_id:
        return room.get("guest")
    return room.get("host")


async def _cleanup_room(room_id: str):
    room = rooms.pop(room_id, None)
    if room:
        for cid in (room["host"], room["guest"]):
            if cid in clients:
                clients[cid]["room"] = None


async def _broadcast_lobby():
    """Push updated player list to every connected lobby member."""
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

    # --- Lobby ---
    if t == "join":
        raw  = str(data.get("name", "")).strip()
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
            # challenger disconnected or already matched
            return
        room_id = str(uuid.uuid4())[:8]
        rooms[room_id] = {"host": host_id, "guest": guest_id}
        clients[host_id]["room"] = room_id
        clients[guest_id]["room"] = room_id
        base = {
            "type":          "match_start",
            "room_id":       room_id,
        }
        await _send(host_id,  {**base, "role": "host",  "opponent_name": clients[guest_id]["name"]})
        await _send(guest_id, {**base, "role": "guest", "opponent_name": clients[host_id]["name"]})
        await _broadcast_lobby()

    elif t == "challenge_decline":
        host_id = data.get("from_id")
        if host_id in clients:
            await _send(host_id, {
                "type":      "challenge_declined",
                "from_name": client["name"],
            })

    # --- In-game relay (game_state / fire / game_over) ---
    elif t in ("game_state", "fire", "game_over"):
        room_id = client["room"]
        if room_id:
            opp = _opponent(room_id, client_id)
            if opp:
                await _send(opp, data)
        if t == "game_over":
            if room_id:
                await _cleanup_room(room_id)
            await _broadcast_lobby()

    elif t == "back_to_lobby":
        room_id = client["room"]
        if room_id:
            await _cleanup_room(room_id)
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
        if room_id:
            opp = _opponent(room_id, client_id)
            if opp:
                await _send(opp, {"type": "opponent_disconnected"})
            await _cleanup_room(room_id)
        clients.pop(client_id, None)
        print(f"[-] {client_id} disconnected (total={len(clients)})", flush=True)
        await _broadcast_lobby()


async def main():
    port = int(os.environ.get("PORT", 8765))
    print(f"Island RTS server listening on 0.0.0.0:{port}", flush=True)
    async with serve(handler, "0.0.0.0", port):
        await asyncio.Future()   # run forever


if __name__ == "__main__":
    asyncio.run(main())
