import math
import os
import sys
import subprocess
import pygame
import settings
from hud import HUD
from game_map import GameMap
from ponds import Ponds
from fog_of_war import FogOfWar
from units.carrier import Carrier
from units.enemy_carrier import EnemyCarrier
from units.drone import create_formation
from units.missile import Missile
import config as cfg

WINDOWED_W = 1280
WINDOWED_H = 720

MAX_RADIUS_COLOR        = (90,  90, 125)   # grey-blue  — max drone roam radius
PLAYER_ATTACK_COLOR     = (50, 185, 100)   # vivid muted green — player attack range
ENEMY_ATTACK_COLOR      = (190,  50,  50)  # deeper red        — enemy attack range


def make_screen(fullscreen):
    """Recreate the display surface in windowed or fullscreen mode."""
    if fullscreen:
        info = pygame.display.Info()
        settings.SCREEN_WIDTH  = info.current_w
        settings.SCREEN_HEIGHT = info.current_h
        return pygame.display.set_mode(
            (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT),
            pygame.FULLSCREEN
        )
    else:
        settings.SCREEN_WIDTH  = WINDOWED_W
        settings.SCREEN_HEIGHT = WINDOWED_H
        return pygame.display.set_mode(
            (WINDOWED_W, WINDOWED_H),
            pygame.RESIZABLE
        )


def draw_dotted_circle(surface, color, cx, cy, radius_px, n_dashes=56, width=1):
    """Draw a dashed circle using short arc segments."""
    if radius_px <= 0:
        return
    rect      = pygame.Rect(cx - radius_px, cy - radius_px,
                             radius_px * 2,  radius_px * 2)
    dash_fill = 0.45   # fraction of each slot that is drawn — open/airy gaps
    for i in range(n_dashes):
        if i % 2 == 0:
            a1 = 2 * math.pi * i          / n_dashes
            a2 = 2 * math.pi * (i + dash_fill) / n_dashes
            pygame.draw.arc(surface, color, rect, a1, a2, width)


def launch_config_editor():
    """Open the config editor as a separate process so it can't affect the game."""
    if getattr(sys, 'frozen', False):
        # PyInstaller build: config_editor is a sibling executable in the same folder
        ext = ".exe" if sys.platform == "win32" else ""
        editor = os.path.join(os.path.dirname(sys.executable), f"config_editor{ext}")
        if os.path.exists(editor):
            subprocess.Popen([editor])
    else:
        editor = os.path.join(os.path.dirname(__file__), "config_editor.py")
        subprocess.Popen([sys.executable, editor])


def resolve_carrier_collisions(carriers):
    """
    AABB collision between every pair of carriers.
    Overlapping carriers are pushed apart along the minimum-overlap axis
    and their approaching velocity components are zeroed on both sides.
    """
    half_w = cfg.get("CARRIER_WIDTH_MM")  / 2
    half_h = cfg.get("CARRIER_HEIGHT_MM") / 2
    for i in range(len(carriers)):
        for j in range(i + 1, len(carriers)):
            a, b    = carriers[i], carriers[j]
            dx, dy  = b.x - a.x, b.y - a.y
            x_over  = 2 * half_w - abs(dx)
            y_over  = 2 * half_h - abs(dy)
            if x_over <= 0 or y_over <= 0:
                continue
            if x_over < y_over:
                push = x_over / 2
                sign = 1.0 if dx >= 0 else -1.0
                a.x -= sign * push;  b.x += sign * push
                if sign > 0:
                    if a.vx > 0: a.vx = 0.0
                    if b.vx < 0: b.vx = 0.0
                else:
                    if a.vx < 0: a.vx = 0.0
                    if b.vx > 0: b.vx = 0.0
            else:
                push = y_over / 2
                sign = 1.0 if dy >= 0 else -1.0
                a.y -= sign * push;  b.y += sign * push
                if sign > 0:
                    if a.vy > 0: a.vy = 0.0
                    if b.vy < 0: b.vy = 0.0
                else:
                    if a.vy < 0: a.vy = 0.0
                    if b.vy > 0: b.vy = 0.0


def _world_pos(unit, cref):
    """World-space position of a unit. cref is the owning carrier for drones."""
    if cref is not None:
        return cref.x + unit.offset_x, cref.y + unit.offset_y
    return unit.x, unit.y


def _make_can_see(observer_carrier, observer_drones):
    """
    Snapshot the team's vision and return a predicate can_see(wx, wy).
    A world point is visible if it lies within CARRIER_VISION_RADIUS_MM of
    the carrier OR within DEFAULT_DRONE_VISION_MM of any drone.
    Call once per frame; the returned closure captures positions at that instant.
    """
    carrier_vis_sq = cfg.get("CARRIER_VISION_RADIUS_MM") ** 2
    drone_vis_sq   = cfg.get("DEFAULT_DRONE_VISION_MM")  ** 2
    ocx, ocy       = observer_carrier.x, observer_carrier.y
    drone_pos      = [(ocx + d.offset_x, ocy + d.offset_y)
                      for d in observer_drones]

    def can_see(wx, wy):
        if (wx - ocx) ** 2 + (wy - ocy) ** 2 <= carrier_vis_sq:
            return True
        for dpx, dpy in drone_pos:
            if (wx - dpx) ** 2 + (wy - dpy) ** 2 <= drone_vis_sq:
                return True
        return False

    return can_see


def _nearest_enemy(sx, sy, targets, can_see=None, attack_range=None):
    """Return (unit, cref) of the closest live, visible, in-range target, or (None, None)."""
    best, best_d  = None, float('inf')
    range_sq      = attack_range ** 2 if attack_range is not None else None
    for unit, cref in targets:
        if unit.hp <= 0:
            continue
        tx, ty = _world_pos(unit, cref)
        if can_see is not None and not can_see(tx, ty):
            continue
        dsq = (tx - sx) ** 2 + (ty - sy) ** 2
        if range_sq is not None and dsq > range_sq:
            continue
        d = math.sqrt(dsq)
        if d < best_d:
            best_d = d
            best   = (unit, cref)
    return best if best else (None, None)


def _maybe_fire(shooter, sx, sy, targets, missiles, team, dt,
                can_see=None, attack_range=None):
    """Decrement cooldown; fire at nearest live visible in-range target when ready."""
    shooter.fire_cooldown -= dt
    if shooter.fire_cooldown > 0 or not targets:
        return
    shooter.fire_cooldown = 1.0 / cfg.get("MISSILE_FIRE_RATE")
    unit, cref = _nearest_enemy(sx, sy, targets, can_see, attack_range)
    if unit is not None:
        missiles.append(Missile(sx, sy, unit, cref, team))


def main():
    pygame.init()

    fullscreen = False
    screen     = make_screen(fullscreen)
    pygame.display.set_caption(settings.TITLE)
    clock = pygame.time.Clock()

    hud      = HUD()
    game_map = GameMap()
    ponds    = Ponds()
    fog      = FogOfWar()
    carrier  = Carrier()

    # Spawn player + enemies at the island edge, spaced by drone max radius
    n_enemies = int(cfg.get("ENEMY_CARRIERS"))
    spawn     = game_map.edge_spawn_points(1 + n_enemies,
                                           cfg.get("DRONE_MAX_RADIUS_MM"), ponds)
    carrier.x, carrier.y = spawn[0]
    enemy_drones_list = [create_formation() for _ in range(n_enemies)]
    enemy_carriers    = [EnemyCarrier(sx, sy, ed)
                         for (sx, sy), ed in zip(spawn[1:], enemy_drones_list)]
    drones            = create_formation()
    launch_config_editor()
    missiles = []

    # Track config.json modification time to reload when editor saves
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    last_mtime  = os.path.getmtime(config_path) if os.path.exists(config_path) else 0

    running = True
    while running:
        dt = clock.tick(settings.FPS) / 1000.0

        # --- Reload config ---
        try:
            mtime = os.path.getmtime(config_path)
            if mtime > last_mtime:
                cfg.load_from_disk()
                game_map.reset()
                ponds.reset()
                n_enemies = int(cfg.get("ENEMY_CARRIERS"))
                spawn     = game_map.edge_spawn_points(1 + n_enemies,
                                                       cfg.get("DRONE_MAX_RADIUS_MM"), ponds)
                carrier.reset()
                carrier.x, carrier.y = spawn[0]
                enemy_drones_list = [create_formation() for _ in range(n_enemies)]
                enemy_carriers    = [EnemyCarrier(sx, sy, ed)
                                     for (sx, sy), ed in zip(spawn[1:], enemy_drones_list)]
                drones            = create_formation()
                missiles = []
                fog.reset()
                last_mtime = mtime
        except OSError:
            pass

        # --- Layout ---
        hud_h  = max(1, int(settings.SCREEN_HEIGHT * cfg.get("HUD_SIZE") / 100))
        game_h = settings.SCREEN_HEIGHT - hud_h

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    screen = make_screen(fullscreen)

            elif event.type == pygame.WINDOWRESIZED:
                settings.SCREEN_WIDTH  = event.x
                settings.SCREEN_HEIGHT = event.y

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if my < game_h:   # ignore clicks on HUD
                    hit = next((d for d in drones
                                if d.is_clicked(mx, my, game_h)), None)
                    if hit:
                        # Toggle selection; deselect all others
                        already_selected = hit.selected
                        for d in drones:
                            d.selected = False
                        hit.selected = not already_selected
                    else:
                        # Move selected drone to clicked position
                        sel = next((d for d in drones if d.selected), None)
                        if sel:
                            px_per_mm = settings.DPI / 25.4
                            ox = (mx - settings.SCREEN_WIDTH // 2) / px_per_mm
                            oy = (my - game_h               // 2) / px_per_mm
                            sel.set_target(ox, oy)

        # --- Update ---
        keys = pygame.key.get_pressed()
        carrier.update(dt, keys)
        game_map.resolve_carrier(carrier)
        ponds.resolve_carrier(carrier)
        for ec in enemy_carriers:
            ec.update(dt, carrier.x, carrier.y)
            game_map.resolve_carrier(ec)
            ponds.resolve_carrier(ec)
        resolve_carrier_collisions([carrier] + enemy_carriers)
        for ec, ed in zip(enemy_carriers, enemy_drones_list):
            for drone in ed:
                drone.update(dt, ec.vx, ec.vy)
        for drone in drones:
            drone.update(dt, carrier.vx, carrier.vy)

        # --- Drone collision: hard stop on contact ---
        # Moving drone hits another drone → pushed back to non-overlapping
        # position and fully stopped (vel zeroed, target snapped to position).
        # The stationary drone is never moved.  If two drones are both moving
        # and collide, both stop.
        d_mm = cfg.get("DEFAULT_DRONE_DIAMETER_MM")
        for i in range(len(drones)):
            for j in range(i + 1, len(drones)):
                a, b = drones[i], drones[j]
                ddx = b.offset_x - a.offset_x
                ddy = b.offset_y - a.offset_y
                dist_sq = ddx * ddx + ddy * ddy
                if dist_sq >= d_mm * d_mm or dist_sq == 0:
                    continue
                dist_ab = math.sqrt(dist_sq)
                nx, ny  = ddx / dist_ab, ddy / dist_ab   # unit vector A→B
                overlap = d_mm - dist_ab
                a_moving = math.sqrt(a.vel_x ** 2 + a.vel_y ** 2) > 0.5
                b_moving = math.sqrt(b.vel_x ** 2 + b.vel_y ** 2) > 0.5
                if a_moving and not b_moving:
                    # A ran into stationary B — push A back, stop A
                    a.offset_x -= nx * overlap
                    a.offset_y -= ny * overlap
                    a.vel_x = 0.0
                    a.vel_y = 0.0
                    a.target_x = a.offset_x
                    a.target_y = a.offset_y
                elif b_moving and not a_moving:
                    # B ran into stationary A — push B back, stop B
                    b.offset_x += nx * overlap
                    b.offset_y += ny * overlap
                    b.vel_x = 0.0
                    b.vel_y = 0.0
                    b.target_x = b.offset_x
                    b.target_y = b.offset_y
                else:
                    # Both moving — push apart equally, stop both
                    a.offset_x -= nx * overlap * 0.5
                    a.offset_y -= ny * overlap * 0.5
                    b.offset_x += nx * overlap * 0.5
                    b.offset_y += ny * overlap * 0.5
                    a.vel_x = 0.0;  a.vel_y = 0.0
                    b.vel_x = 0.0;  b.vel_y = 0.0
                    a.target_x = a.offset_x;  a.target_y = a.offset_y
                    b.target_x = b.offset_x;  b.target_y = b.offset_y

        # --- Combat ---
        # Build per-team target lists: (unit, carrier_ref_or_None)
        enemy_targets  = ([(ec, None) for ec in enemy_carriers] +
                          [(d, ec)
                           for ec, ed in zip(enemy_carriers, enemy_drones_list)
                           for d in ed])
        player_targets = ([(carrier, None)] +
                          [(d, carrier) for d in drones])

        # Snapshot vision for each team — used for both targeting and drawing
        player_can_see = _make_can_see(carrier, drones)

        c_range = cfg.get("CARRIER_ATTACK_RANGE_MM")
        d_range = cfg.get("DRONE_ATTACK_RANGE_MM")

        # Player carrier fires — must see AND be within carrier attack range
        if carrier.hp > 0:
            _maybe_fire(carrier, carrier.x, carrier.y,
                        enemy_targets, missiles, 'player', dt,
                        player_can_see, c_range)
        # Player drones fire — must see AND be within drone attack range
        for d in drones:
            if d.hp > 0:
                _maybe_fire(d, carrier.x + d.offset_x, carrier.y + d.offset_y,
                            enemy_targets, missiles, 'player', dt,
                            player_can_see, d_range)
        # Each enemy carrier is its own "player" with its own vision + attack range
        for ec, ed in zip(enemy_carriers, enemy_drones_list):
            ec_can_see = _make_can_see(ec, ed)
            if ec.hp > 0:
                _maybe_fire(ec, ec.x, ec.y,
                            player_targets, missiles, 'enemy', dt,
                            ec_can_see, c_range)
            for d in ed:
                if d.hp > 0:
                    _maybe_fire(d, ec.x + d.offset_x, ec.y + d.offset_y,
                                player_targets, missiles, 'enemy', dt,
                                ec_can_see, d_range)

        # Update missiles and remove spent ones
        for m in missiles:
            m.update(dt)
        missiles = [m for m in missiles if m.alive]

        # Remove dead player drones; carrier death wipes all of its drones
        drones = [d for d in drones if d.hp > 0]
        if carrier.hp <= 0:
            drones = []

        # Remove dead enemy drones; remove dead enemy carriers + their drones
        enemy_drones_list = [[d for d in ed if d.hp > 0]
                             for ed in enemy_drones_list]
        alive = [(ec, ed) for ec, ed in zip(enemy_carriers, enemy_drones_list)
                 if ec.hp > 0]
        enemy_carriers    = [ec for ec, ed in alive]
        enemy_drones_list = [ed for ec, ed in alive]

        # --- Camera ---
        px_per_mm   = settings.DPI / 25.4
        camera_x_mm = carrier.x - (settings.SCREEN_WIDTH / 2) / px_per_mm
        camera_y_mm = carrier.y - (game_h              / 2) / px_per_mm

        # --- Vision circles ---
        carrier_vis_px = max(1, int(cfg.get("CARRIER_VISION_RADIUS_MM") * px_per_mm))
        drone_vis_px   = max(1, int(cfg.get("DEFAULT_DRONE_VISION_MM")  * px_per_mm))
        cx, cy         = settings.SCREEN_WIDTH // 2, game_h // 2
        vision_circles = [(cx, cy, carrier_vis_px)]
        for drone in drones:
            sx, sy = drone.screen_pos(game_h)
            vision_circles.append((sx, sy, drone_vis_px))

        # --- Draw ---
        # Layer order (bottom → top):
        #   map → ponds → all trails → carriers → player drones → enemy drones
        # Trails are drawn first so they never cover any drone.
        # Enemy drones sit above player drones so they are always visible.
        game_map.draw(screen, camera_x_mm, camera_y_mm, game_h)
        ponds.draw(screen, camera_x_mm, camera_y_mm, game_h)
        # 1. Trails — enemy trails only when their carrier is in player vision
        for ec in enemy_carriers:
            if player_can_see(ec.x, ec.y):
                ec.draw_trail(screen, camera_x_mm, camera_y_mm, game_h, px_per_mm)
        carrier.draw_trail(screen, camera_x_mm, camera_y_mm, game_h, px_per_mm)
        # 2. Carrier bodies — enemy carriers only when visible
        for ec in enemy_carriers:
            if player_can_see(ec.x, ec.y):
                ec.draw(screen, camera_x_mm, camera_y_mm, game_h, px_per_mm)
        carrier.draw(screen, game_h)
        # 3. Player drones
        for drone in drones:
            drone.draw(screen, game_h)
        # 4. Enemy drones — only when their world position is in player vision
        for ec, ed in zip(enemy_carriers, enemy_drones_list):
            for drone in ed:
                wx = ec.x + drone.offset_x
                wy = ec.y + drone.offset_y
                if player_can_see(wx, wy):
                    drone.draw_world(screen, ec.x, ec.y,
                                     camera_x_mm, camera_y_mm, game_h)
        # Missiles — drawn above units, below fog
        for m in missiles:
            m.draw(screen, camera_x_mm, camera_y_mm, game_h, px_per_mm)

        # Attack-range dotted circles — drawn under fog so enemy circles are
        # automatically hidden wherever the fog has not been lifted.
        c_atk_px = max(1, int(cfg.get("CARRIER_ATTACK_RANGE_MM") * px_per_mm))
        d_atk_px = max(1, int(cfg.get("DRONE_ATTACK_RANGE_MM")   * px_per_mm))
        # Player carrier
        draw_dotted_circle(screen, PLAYER_ATTACK_COLOR, cx, cy, c_atk_px)
        # Player drones
        for drone in drones:
            dsx, dsy = drone.screen_pos(game_h)
            draw_dotted_circle(screen, PLAYER_ATTACK_COLOR, dsx, dsy, d_atk_px)
        # Enemy carriers (fog hides them when out of vision)
        for ec in enemy_carriers:
            esx = int((ec.x - camera_x_mm) * px_per_mm)
            esy = int((ec.y - camera_y_mm) * px_per_mm)
            draw_dotted_circle(screen, ENEMY_ATTACK_COLOR, esx, esy, c_atk_px)
        # Enemy drones
        for ec, ed in zip(enemy_carriers, enemy_drones_list):
            for drone in ed:
                ewx = ec.x + drone.offset_x
                ewy = ec.y + drone.offset_y
                esx = int((ewx - camera_x_mm) * px_per_mm)
                esy = int((ewy - camera_y_mm) * px_per_mm)
                draw_dotted_circle(screen, ENEMY_ATTACK_COLOR, esx, esy, d_atk_px)

        fog.draw(screen, game_h, vision_circles)

        # Max-radius dotted circle drawn after fog so it's always visible
        max_r_px = int(cfg.get("DRONE_MAX_RADIUS_MM") * px_per_mm)
        draw_dotted_circle(screen, MAX_RADIUS_COLOR, cx, cy, max_r_px)

        hud.draw(screen, carrier, drones)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
