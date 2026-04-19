import asyncio
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
from units.missile import Missile, Explosion
import config as cfg

WINDOWED_W = 1280
WINDOWED_H = 720

MAX_RADIUS_COLOR        = (90,  90, 125)   # grey-blue  — max drone roam radius
PLAYER_ATTACK_COLOR     = (50, 185, 100)   # vivid muted green — player attack range
ENEMY_ATTACK_COLOR      = (190,  50,  50)  # deeper red        — enemy attack range

# Slot keys 1-0 mapped to formation index 1-0
_NUM_KEYS = {
    pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 3,
    pygame.K_4: 4, pygame.K_5: 5, pygame.K_6: 6,
    pygame.K_7: 7, pygame.K_8: 8, pygame.K_9: 9,
    pygame.K_0: 0,
}


def make_screen(fullscreen):
    """Recreate the display surface in windowed or fullscreen mode."""
    if sys.platform == 'emscripten':
        # Fixed internal resolution in browser — CSS handles the visual scaling
        settings.SCREEN_WIDTH  = WINDOWED_W
        settings.SCREEN_HEIGHT = WINDOWED_H
        return pygame.display.set_mode((WINDOWED_W, WINDOWED_H))
    elif fullscreen:
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


def draw_formation_overlay(surface, formations, num_hold_start, game_h):
    """Slot indicator strip + instructions for the formation editor."""
    now       = pygame.time.get_ticks()
    font_sm   = pygame.font.Font(None, 26)
    font_hint = pygame.font.Font(None, 22)

    # Top instruction bar
    hint = font_hint.render(
        "Hold 1-0 (1 s) = SAVE  |  Press 1-0 = RECALL  |  R = reset  |  ENTER = play",
        True, (160, 160, 180)
    )
    surface.blit(hint, hint.get_rect(centerx=settings.SCREEN_WIDTH // 2, top=8))

    # Slot boxes along the bottom of the game area
    slots  = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]
    sw, sh = 34, 34
    gap    = 6
    total  = len(slots) * sw + (len(slots) - 1) * gap
    x0     = (settings.SCREEN_WIDTH - total) // 2
    y0     = game_h - sh - 10

    key_for = {1: pygame.K_1, 2: pygame.K_2, 3: pygame.K_3,
               4: pygame.K_4, 5: pygame.K_5, 6: pygame.K_6,
               7: pygame.K_7, 8: pygame.K_8, 9: pygame.K_9,
               0: pygame.K_0}

    for i, slot in enumerate(slots):
        sx  = x0 + i * (sw + gap)
        kc  = key_for[slot]
        saved   = slot in formations
        holding = kc in num_hold_start

        bg = (50, 90, 50) if saved else (35, 35, 55)
        pygame.draw.rect(surface, bg,           pygame.Rect(sx, y0, sw, sh), border_radius=4)
        pygame.draw.rect(surface, (90, 90, 130), pygame.Rect(sx, y0, sw, sh), 1, border_radius=4)

        # Hold-progress bar at bottom of box
        if holding:
            frac   = min(1.0, (now - num_hold_start[kc]) / 1000.0)
            pw     = max(1, int((sw - 2) * frac))
            pygame.draw.rect(surface, (255, 200, 60),
                             pygame.Rect(sx + 1, y0 + sh - 4, pw, 3))

        label_color = (210, 255, 210) if saved else (140, 140, 165)
        lbl = font_sm.render(str(slot), True, label_color)
        surface.blit(lbl, lbl.get_rect(center=(sx + sw // 2, y0 + sh // 2)))


def draw_overlay(surface, state, kills=0):
    """Semi-transparent overlay for pause / win / loss screens."""
    overlay = pygame.Surface(
        (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA
    )
    overlay.fill((0, 0, 0, 160))
    surface.blit(overlay, (0, 0))
    cx, cy     = settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2
    big_font   = pygame.font.Font(None, 72)
    small_font = pygame.font.Font(None, 36)
    if state == 'paused':
        title = big_font.render("PAUSED", True, (220, 220, 100))
        hint  = small_font.render("P  —  resume", True, (180, 180, 180))
        surface.blit(title, title.get_rect(center=(cx, cy - 20)))
        surface.blit(hint,  hint.get_rect(center=(cx, cy + 40)))
    else:
        if state == 'won':
            title = big_font.render("VICTORY",  True, (100, 255, 120))
        else:
            title = big_font.render("DEFEATED", True, (255, 80, 80))
        kills_surf = small_font.render(
            f"Enemies destroyed: {kills}", True, (200, 200, 200)
        )
        hint = small_font.render("ENTER  —  play again", True, (180, 180, 180))
        surface.blit(title,      title.get_rect(center=(cx, cy - 40)))
        surface.blit(kills_surf, kills_surf.get_rect(center=(cx, cy + 20)))
        surface.blit(hint,       hint.get_rect(center=(cx, cy + 60)))


def _reset_game(game_map, ponds, fog, carrier):
    """Reinitialise all mutable game state.
    Returns (enemy_carriers, enemy_drones_list, drones, missiles)."""
    game_map.reset()
    ponds.reset()
    fog.reset()
    n_enemies = int(cfg.get("ENEMY_CARRIERS"))
    spawn     = game_map.edge_spawn_points(
        1 + n_enemies, cfg.get("DRONE_MAX_RADIUS_MM"), ponds
    )
    carrier.reset()
    carrier.x, carrier.y = spawn[0]
    enemy_drones_list = [create_formation() for _ in range(n_enemies)]
    enemy_carriers    = [EnemyCarrier(sx, sy, ed)
                         for (sx, sy), ed in zip(spawn[1:], enemy_drones_list)]
    drones   = create_formation()
    missiles = []
    return enemy_carriers, enemy_drones_list, drones, missiles


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


def _nearest_enemy(sx, sy, targets, can_see=None, attack_range=None, prefer_carrier=False):
    """Return (unit, cref) of the best live, visible, in-range target, or (None, None).
    prefer_carrier=True: if a carrier (cref=None) is in range, always pick it over drones."""
    best, best_d       = None, float('inf')
    carrier_hit        = None   # best in-range carrier target
    carrier_hit_d      = float('inf')
    range_sq           = attack_range ** 2 if attack_range is not None else None
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
        if prefer_carrier and cref is None:
            if d < carrier_hit_d:
                carrier_hit_d = d
                carrier_hit   = (unit, cref)
        else:
            if d < best_d:
                best_d = d
                best   = (unit, cref)
    if prefer_carrier and carrier_hit is not None:
        return carrier_hit
    return best if best else (None, None)


def _maybe_fire(shooter, sx, sy, targets, missiles, team, dt,
                can_see=None, attack_range=None):
    """Decrement cooldown; fire at nearest live visible in-range target when ready."""
    shooter.fire_cooldown -= dt
    if shooter.fire_cooldown > 0 or not targets:
        return
    prefer = (team == 'enemy')
    unit, cref = _nearest_enemy(sx, sy, targets, can_see, attack_range, prefer_carrier=prefer)
    if unit is not None:
        explosive = getattr(shooter, 'missile_type', 'normal') == 'explosive'
        rate      = cfg.get("EXPLOSIVE_FIRE_RATE") if explosive else cfg.get("MISSILE_FIRE_RATE")
        cooldown  = 1.0 / rate
        shooter.fire_cooldown = cooldown
        if hasattr(shooter, 'fire_cooldown_max'):
            shooter.fire_cooldown_max = cooldown
        if hasattr(shooter, 'has_fired'):
            shooter.has_fired = True
        missiles.append(Missile(sx, sy, unit, cref, team, explosive=explosive))


async def main():
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

    # Spawn player at edge; enemies spawned later when ENTER is pressed in formation editor
    spawn = game_map.edge_spawn_points(1, cfg.get("DRONE_MAX_RADIUS_MM"), ponds)
    carrier.x, carrier.y = spawn[0]
    enemy_carriers    = []
    enemy_drones_list = []
    drones            = create_formation()
    if sys.platform != 'emscripten':
        launch_config_editor()
    missiles   = []
    explosions = []
    game_state = 'formation'  # 'formation' | 'playing' | 'won' | 'lost'
    formations = {}            # slot (0-9) → [(offset_x, offset_y), ...]
    _num_hold_start = {}       # key_const → ticks when key was pressed
    paused     = False
    kills      = 0
    _last_click_drone = None
    _last_click_time  = 0
    _drag_start    = None   # (mx, my) screen pixels where LMB went down
    _drag_rect     = None   # current pygame.Rect of the drag box (None when not dragging)
    _click_markers = []     # [(offset_x, offset_y, expire_ms), ...]  — move destination pips

    # Track config.json modification time to reload when editor saves (desktop only)
    if sys.platform != 'emscripten':
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        last_mtime  = os.path.getmtime(config_path) if os.path.exists(config_path) else 0
    else:
        config_path = None
        last_mtime  = 0

    running = True
    while running:
        dt = clock.tick(settings.FPS) / 1000.0

        # --- Reload config (desktop only) ---
        if config_path is not None:
            try:
                mtime = os.path.getmtime(config_path)
                if mtime > last_mtime:
                    cfg.load_from_disk()
                    game_map.reset()
                    ponds.reset()
                    spawn = game_map.edge_spawn_points(1, cfg.get("DRONE_MAX_RADIUS_MM"), ponds)
                    carrier.reset()
                    carrier.x, carrier.y = spawn[0]
                    enemy_carriers    = []
                    enemy_drones_list = []
                    drones            = create_formation()
                    missiles          = []
                    explosions        = []
                    formations        = {}
                    _num_hold_start   = {}
                    game_state        = 'formation'
                    paused            = False
                    kills             = 0
                    _last_click_drone = None
                    _last_click_time  = 0
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
                if event.key == pygame.K_F11 and sys.platform != 'emscripten':
                    fullscreen = not fullscreen
                    screen = make_screen(fullscreen)
                elif event.key == pygame.K_p:
                    if game_state == 'playing':
                        paused = not paused
                elif event.key == pygame.K_RETURN and game_state == 'formation':
                    # Leave formation editor — spawn enemies well away from player
                    n_enemies = int(cfg.get("ENEMY_CARRIERS"))
                    # Use carrier vision radius as minimum spacing so enemies
                    # always start off-screen / outside the player's vision.
                    min_sep = max(
                        cfg.get("DRONE_MAX_RADIUS_MM"),
                        cfg.get("CARRIER_VISION_RADIUS_MM") * 2.5,
                    )
                    spawn = game_map.edge_spawn_points(
                        n_enemies, min_sep, ponds,
                        avoid=[(carrier.x, carrier.y)],
                    )
                    enemy_drones_list = [create_formation() for _ in range(n_enemies)]
                    enemy_carriers    = [EnemyCarrier(sx, sy, ed)
                                         for (sx, sy), ed in zip(spawn, enemy_drones_list)]
                    missiles          = []
                    kills             = 0
                    game_state        = 'playing'
                elif event.key == pygame.K_RETURN and game_state in ('won', 'lost'):
                    # Return to formation editor — keep saved formations
                    game_map.reset(); ponds.reset(); fog.reset()
                    spawn = game_map.edge_spawn_points(1, cfg.get("DRONE_MAX_RADIUS_MM"), ponds)
                    carrier.reset()
                    carrier.x, carrier.y = spawn[0]
                    drones            = create_formation()
                    enemy_carriers    = []
                    enemy_drones_list = []
                    missiles          = []
                    explosions        = []
                    kills             = 0
                    game_state        = 'formation'
                    paused            = False
                    _last_click_drone = None
                    _last_click_time  = 0
                elif event.key == pygame.K_r and game_state in ('formation', 'playing') and not paused:
                    n = len(drones)
                    if n > 0:
                        r_mm = cfg.get("DRONE_START_RADIUS_MM")
                        _bounce_exp_r = pygame.time.get_ticks() + 5000
                        for i, d in enumerate(drones):
                            angle = -math.pi / 2 + 2 * math.pi * i / n
                            d.set_target(r_mm * math.cos(angle),
                                         r_mm * math.sin(angle))
                            d.bounce_until = _bounce_exp_r
                        for d in drones:
                            d.selected = False
                elif event.key == pygame.K_SPACE and game_state in ('formation', 'playing') and not paused:
                    # Space: deselect all drones
                    for d in drones:
                        d.selected = False
                    _drag_start = None
                    _drag_rect  = None
                elif event.key in _NUM_KEYS and game_state in ('formation', 'playing') and not paused:
                    _num_hold_start[event.key] = pygame.time.get_ticks()

            elif event.type == pygame.KEYUP:
                if event.key in _NUM_KEYS and game_state in ('formation', 'playing') and not paused:
                    slot    = _NUM_KEYS[event.key]
                    held_ms = pygame.time.get_ticks() - _num_hold_start.get(
                                  event.key, pygame.time.get_ticks())
                    if held_ms >= 1000:
                        # Save current drone offsets to this slot
                        formations[slot] = [(d.offset_x, d.offset_y) for d in drones]
                    elif slot in formations:
                        # Recall saved formation
                        saved = formations[slot]
                        _bounce_exp_f = pygame.time.get_ticks() + 5000
                        for i, d in enumerate(drones):
                            if i < len(saved):
                                d.set_target(saved[i][0], saved[i][1])
                                d.bounce_until = _bounce_exp_f
                    _num_hold_start.pop(event.key, None)

            elif event.type == pygame.WINDOWRESIZED:
                if sys.platform != 'emscripten':
                    settings.SCREEN_WIDTH  = event.x
                    settings.SCREEN_HEIGHT = event.y

            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                  and game_state in ('formation', 'playing') and not paused):
                mx, my = event.pos
                if my < game_h:   # ignore clicks on HUD
                    hit = next((d for d in drones
                                if d.is_clicked(mx, my, game_h)), None)
                    if hit:
                        now = pygame.time.get_ticks()
                        if hit is _last_click_drone and now - _last_click_time < 300:
                            # Double-click: toggle missile type
                            hit.missile_type = (
                                'explosive' if hit.missile_type == 'normal' else 'normal'
                            )
                            _last_click_drone = None
                        else:
                            # Single click on drone: toggle selection, deselect others
                            already_selected = hit.selected
                            for d in drones:
                                d.selected = False
                            hit.selected = not already_selected
                            _last_click_drone = hit
                            _last_click_time  = now
                        _drag_start = None
                        _drag_rect  = None
                    else:
                        selected = [d for d in drones if d.selected]
                        if selected:
                            # Move selected drones in formation — preserve their
                            # relative offsets so touching drones stay together.
                            _last_click_drone = None
                            px_per_mm = settings.DPI / 25.4
                            # Target centroid in carrier-relative offset coords
                            ox = (mx - settings.SCREEN_WIDTH // 2) / px_per_mm
                            oy = (my - game_h               // 2) / px_per_mm
                            # Current centroid of the selected group
                            cx_g = sum(d.offset_x for d in selected) / len(selected)
                            cy_g = sum(d.offset_y for d in selected) / len(selected)
                            # Shift each drone by the same delta so spacing is kept
                            dx, dy = ox - cx_g, oy - cy_g
                            _bounce_expire = pygame.time.get_ticks() + 5000
                            for d in selected:
                                d.set_target(d.offset_x + dx, d.offset_y + dy)
                                d.bounce_until = _bounce_expire
                            _click_markers.append((ox, oy, pygame.time.get_ticks() + 1000))
                            # Keep selection — drones stay highlighted so the
                            # player can keep clicking new destinations without
                            # re-selecting.  Selection clears on: box-drag,
                            # single-drone click, or double-click missile toggle.
                            _drag_start = None
                            _drag_rect  = None
                        else:
                            # Start box-select drag
                            _last_click_drone = None
                            _drag_start = (mx, my)
                            _drag_rect  = None

            elif (event.type == pygame.MOUSEMOTION
                  and _drag_start is not None
                  and game_state in ('formation', 'playing') and not paused):
                mx, my = event.pos
                x0, y0 = _drag_start
                rx = min(x0, mx)
                ry = min(y0, my)
                rw = abs(mx - x0)
                rh = abs(my - y0)
                _drag_rect = pygame.Rect(rx, ry, rw, rh) if (rw > 4 or rh > 4) else None

            elif (event.type == pygame.MOUSEBUTTONUP and event.button == 1
                  and game_state in ('formation', 'playing') and not paused):
                if _drag_rect is not None and _drag_rect.width > 4 and _drag_rect.height > 4:
                    # Finalise box-select: select all drones whose screen pos is inside the rect
                    for d in drones:
                        d.selected = False
                    for d in drones:
                        dsx, dsy = d.screen_pos(game_h)
                        if _drag_rect.collidepoint(dsx, dsy):
                            d.selected = True
                _drag_start = None
                _drag_rect  = None

        # --- Update: carrier + player-drone physics (formation and playing) ---
        if game_state in ('formation', 'playing') and not paused:
            keys = pygame.key.get_pressed()
            carrier.update(dt, keys)
            game_map.resolve_carrier(carrier)
            ponds.resolve_carrier(carrier)
            for drone in drones:
                drone.update(dt, carrier.vx, carrier.vy)

            # --- Drone collision: bounce (first 5 s after a move) or hard-stop ---
            # While a drone's bounce_until timer is active it gets elastic bounce
            # behaviour; once expired it reverts to the original hard-stop.
            d_mm      = cfg.get("DEFAULT_DRONE_DIAMETER_MM")
            max_speed = cfg.get("DEFAULT_DRONE_MAX_SPEED")
            _now_ms   = pygame.time.get_ticks()
            for i in range(len(drones)):
                for j in range(i + 1, len(drones)):
                    a, b = drones[i], drones[j]
                    ddx = b.offset_x - a.offset_x
                    ddy = b.offset_y - a.offset_y
                    dist_sq = ddx * ddx + ddy * ddy
                    if dist_sq >= d_mm * d_mm or dist_sq == 0:
                        continue
                    dist_ab = math.sqrt(dist_sq)
                    nx, ny  = ddx / dist_ab, ddy / dist_ab  # unit vector A→B
                    overlap = d_mm - dist_ab

                    # Positional correction — push equally apart
                    a.offset_x -= nx * overlap * 0.5
                    a.offset_y -= ny * overlap * 0.5
                    b.offset_x += nx * overlap * 0.5
                    b.offset_y += ny * overlap * 0.5

                    a_moving = math.sqrt(a.vel_x ** 2 + a.vel_y ** 2) > 0.5
                    b_moving = math.sqrt(b.vel_x ** 2 + b.vel_y ** 2) > 0.5

                    # Bounce vs hard-stop rules:
                    #   both in motion         → always bounce (two navigating drones
                    #                            deflect off each other freely)
                    #   one moving, one static → bounce only while mover's 5 s timer
                    #                            is active; after that hard-stop
                    #   both static            → positional correction only
                    if a_moving and b_moving:
                        do_bounce = True
                    elif a_moving and not b_moving:
                        do_bounce = _now_ms < a.bounce_until
                    elif b_moving and not a_moving:
                        do_bounce = _now_ms < b.bounce_until
                    else:
                        do_bounce = False

                    if do_bounce:
                        va_n = a.vel_x * nx + a.vel_y * ny
                        vb_n = b.vel_x * nx + b.vel_y * ny
                        if va_n - vb_n > 0:
                            # Perfectly inelastic in the normal direction (e=0):
                            # set both normal components to their average so they
                            # stop pressing into each other but keep all tangential
                            # velocity — consistent "roll off" every time.
                            avg_n = (va_n + vb_n) * 0.5
                            a.vel_x += (avg_n - va_n) * nx
                            a.vel_y += (avg_n - va_n) * ny
                            b.vel_x += (avg_n - vb_n) * nx
                            b.vel_y += (avg_n - vb_n) * ny
                    elif a_moving or b_moving:
                        # Hard-stop the mover(s)
                        if a_moving:
                            a.vel_x = 0.0;  a.vel_y = 0.0
                            a.target_x = a.offset_x;  a.target_y = a.offset_y
                        if b_moving:
                            b.vel_x = 0.0;  b.vel_y = 0.0
                            b.target_x = b.offset_x;  b.target_y = b.offset_y

            # --- Drone boundary constraints ---
            # Drones must stay inside BOTH the max-radius circle AND the visible
            # screen area.  Only position and outward velocity are clamped —
            # targets are intentionally NOT touched so a group move command
            # issued while a drone is at the wall still takes effect.
            # (The drone's steering naturally won't push outward if the target
            # is inside the boundary; it will just slide along the wall.)
            _ppm      = settings.DPI / 25.4
            _drone_r  = cfg.get("DEFAULT_DRONE_DIAMETER_MM") / 2.0  # mm
            _half_w   = (settings.SCREEN_WIDTH / 2) / _ppm - _drone_r
            _half_h   = (game_h / 2) / _ppm - _drone_r
            _max_r    = cfg.get("DRONE_MAX_RADIUS_MM")
            for d in drones:
                # 1. Max-radius circle constraint
                r = math.sqrt(d.offset_x ** 2 + d.offset_y ** 2)
                if r > _max_r and r > 0:
                    scale      = _max_r / r
                    d.offset_x *= scale
                    d.offset_y *= scale
                    # Cancel outward velocity component only
                    nr_x, nr_y = d.offset_x / _max_r, d.offset_y / _max_r
                    v_out = d.vel_x * nr_x + d.vel_y * nr_y
                    if v_out > 0:
                        d.vel_x -= v_out * nr_x
                        d.vel_y -= v_out * nr_y

                # 2. Screen-edge (rectangular) constraint
                if d.offset_x < -_half_w:
                    d.offset_x = -_half_w
                    if d.vel_x < 0: d.vel_x = 0.0
                elif d.offset_x > _half_w:
                    d.offset_x =  _half_w
                    if d.vel_x > 0: d.vel_x = 0.0
                if d.offset_y < -_half_h:
                    d.offset_y = -_half_h
                    if d.vel_y < 0: d.vel_y = 0.0
                elif d.offset_y > _half_h:
                    d.offset_y =  _half_h
                    if d.vel_y > 0: d.vel_y = 0.0

        # --- Update: enemy AI, combat, cleanup (playing only) ---
        if game_state == 'playing' and not paused:
            for ec in enemy_carriers:
                ec.update(dt, carrier.x, carrier.y)
                game_map.resolve_carrier(ec)
                ponds.resolve_carrier(ec)
            resolve_carrier_collisions([carrier] + enemy_carriers)
            for ec, ed in zip(enemy_carriers, enemy_drones_list):
                for drone in ed:
                    drone.update(dt, ec.vx, ec.vy)

            # --- Cross-team drone collision ---
            # Player drones and enemy drones bounce off each other in world space.
            # Always elastic — both sides are in active motion with intent.
            _xd_mm  = cfg.get("DEFAULT_DRONE_DIAMETER_MM")
            _xspeed = cfg.get("DEFAULT_DRONE_MAX_SPEED")
            for pd in drones:
                for ec, ed in zip(enemy_carriers, enemy_drones_list):
                    for ed_d in ed:
                        # World positions (recompute each pair — offsets may shift)
                        pw_x = carrier.x + pd.offset_x
                        pw_y = carrier.y + pd.offset_y
                        ew_x = ec.x     + ed_d.offset_x
                        ew_y = ec.y     + ed_d.offset_y
                        ddx  = ew_x - pw_x
                        ddy  = ew_y - pw_y
                        dist_sq = ddx * ddx + ddy * ddy
                        if dist_sq >= _xd_mm * _xd_mm or dist_sq == 0:
                            continue
                        dist_ab = math.sqrt(dist_sq)
                        nx, ny  = ddx / dist_ab, ddy / dist_ab
                        overlap = _xd_mm - dist_ab

                        # Positional correction in world space → update offsets
                        pd.offset_x  -= nx * overlap * 0.5
                        pd.offset_y  -= ny * overlap * 0.5
                        ed_d.offset_x += nx * overlap * 0.5
                        ed_d.offset_y += ny * overlap * 0.5

                        # World-space velocities
                        pv_x = carrier.vx + pd.vel_x
                        pv_y = carrier.vy + pd.vel_y
                        ev_x = ec.vx     + ed_d.vel_x
                        ev_y = ec.vy     + ed_d.vel_y

                        # Perfectly inelastic in the normal direction (e=0)
                        pv_n = pv_x * nx + pv_y * ny
                        ev_n = ev_x * nx + ev_y * ny
                        if pv_n - ev_n > 0:
                            avg_n = (pv_n + ev_n) * 0.5
                            pv_x += (avg_n - pv_n) * nx;  pv_y += (avg_n - pv_n) * ny
                            ev_x += (avg_n - ev_n) * nx;  ev_y += (avg_n - ev_n) * ny
                            # Clamp world speed
                            p_spd = math.sqrt(pv_x ** 2 + pv_y ** 2)
                            e_spd = math.sqrt(ev_x ** 2 + ev_y ** 2)
                            if p_spd > _xspeed and p_spd > 0:
                                pv_x = pv_x / p_spd * _xspeed
                                pv_y = pv_y / p_spd * _xspeed
                            if e_spd > _xspeed and e_spd > 0:
                                ev_x = ev_x / e_spd * _xspeed
                                ev_y = ev_y / e_spd * _xspeed
                            # Convert back to carrier-relative velocities
                            pd.vel_x   = pv_x - carrier.vx
                            pd.vel_y   = pv_y - carrier.vy
                            ed_d.vel_x = ev_x - ec.vx
                            ed_d.vel_y = ev_y - ec.vy

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
            # Separate splash lists: enemy missiles only splash player units,
            # player missiles splash everyone (including each other) — this
            # prevents enemy scouts killing each other via friendly-fire explosions.
            player_splash = (
                [(carrier, carrier.x, carrier.y)] +
                [(d, carrier.x + d.offset_x, carrier.y + d.offset_y) for d in drones]
            )
            all_splash = (
                player_splash +
                [(ec, ec.x, ec.y) for ec in enemy_carriers] +
                [(d, ec.x + d.offset_x, ec.y + d.offset_y)
                 for ec, ed in zip(enemy_carriers, enemy_drones_list) for d in ed]
            )
            for m in missiles:
                targets = player_splash if m.team == 'enemy' else all_splash
                m.update(dt, targets)
                if not m.alive and m.explosive and m.impact_x is not None:
                    explosions.append(Explosion(m.impact_x, m.impact_y))
            missiles = [m for m in missiles if m.alive]

            for exp in explosions:
                exp.update(dt)
            explosions = [e for e in explosions if not e.done]

            # Remove dead player drones; carrier death wipes all of its drones
            drones = [d for d in drones if d.hp > 0]
            if carrier.hp <= 0:
                drones = []

            # Remove dead enemy drones; remove dead enemy carriers + their drones
            enemy_drones_list = [[d for d in ed if d.hp > 0]
                                 for ed in enemy_drones_list]
            _prev_n_enemies = len(enemy_carriers)
            alive = [(ec, ed) for ec, ed in zip(enemy_carriers, enemy_drones_list)
                     if ec.hp > 0]
            enemy_carriers    = [ec for ec, ed in alive]
            enemy_drones_list = [ed for ec, ed in alive]
            kills += _prev_n_enemies - len(enemy_carriers)
            # Sync each carrier's internal drone list so _command_drones counts
            # only living drones (prevents guards/scouts ratio counting dead ones).
            for ec, ed in zip(enemy_carriers, enemy_drones_list):
                ec.drones = ed

            # Win / loss check
            if not enemy_carriers:
                game_state = 'won'
            elif carrier.hp <= 0:
                game_state = 'lost'

        # Always available for draw — computed fresh if not set by combat block
        if game_state != 'playing' or paused:
            player_can_see = _make_can_see(carrier, drones)

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
        # Missiles and explosions — drawn above units, below fog
        for m in missiles:
            m.draw(screen, camera_x_mm, camera_y_mm, game_h, px_per_mm)
        for exp in explosions:
            exp.draw(screen, camera_x_mm, camera_y_mm, game_h, px_per_mm)

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
        # Enemy attack-range circles intentionally not drawn — hidden from player

        fog.draw(screen, game_h, vision_circles)

        # Max-radius dotted circle drawn after fog so it's always visible
        max_r_px = int(cfg.get("DRONE_MAX_RADIUS_MM") * px_per_mm)
        draw_dotted_circle(screen, MAX_RADIUS_COLOR, cx, cy, max_r_px)

        hud.draw(screen, carrier, drones, kills=kills)
        if game_state == 'formation':
            draw_formation_overlay(screen, formations, _num_hold_start, game_h)
        elif game_state != 'playing' or paused:
            draw_overlay(screen, 'paused' if paused else game_state, kills)

        # Draw click-move markers (carrier-relative offset → screen)
        _now_draw = pygame.time.get_ticks()
        _click_markers = [(ox, oy, exp) for ox, oy, exp in _click_markers if _now_draw < exp]
        for ox, oy, exp in _click_markers:
            frac  = (_now_draw - (exp - 1000)) / 1000.0   # 0→1 over lifetime
            alpha = int(255 * (1.0 - frac))
            r_px  = int(4 + 6 * frac)                     # ring expands slightly
            sx    = settings.SCREEN_WIDTH // 2 + int(ox * px_per_mm)
            sy    = game_h               // 2 + int(oy * px_per_mm)
            color = (100, 220, 255, alpha)
            # Draw two crossed lines + circle as a destination pip
            pygame.draw.circle(screen, (100, 220, 255), (sx, sy), r_px, 1)
            pygame.draw.line(screen, (100, 220, 255), (sx - r_px - 2, sy), (sx + r_px + 2, sy), 1)
            pygame.draw.line(screen, (100, 220, 255), (sx, sy - r_px - 2), (sx, sy + r_px + 2), 1)

        # Draw drag-select box
        if _drag_rect is not None and _drag_rect.width > 4 and _drag_rect.height > 4:
            box_surf = pygame.Surface((_drag_rect.width, _drag_rect.height), pygame.SRCALPHA)
            box_surf.fill((80, 160, 255, 40))          # translucent blue fill
            pygame.draw.rect(box_surf, (120, 200, 255, 180),
                             box_surf.get_rect(), 1)   # bright blue border
            screen.blit(box_surf, (_drag_rect.x, _drag_rect.y))

        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()


if __name__ == "__main__":
    # Windows defaults to ProactorEventLoop which blocks pygame keyboard input
    # in PyInstaller bundles. Force SelectorEventLoop so get_pressed() works.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
