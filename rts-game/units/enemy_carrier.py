import math
import random
from collections import deque
import pygame
import settings
import config as cfg

# Visual style — red to distinguish from the player's green carrier
COLOR  = (210,  45,  45)   # deeper crimson
BORDER = (255, 120, 120)

# Trail style — dark reddish-brown (crushed grass, enemy tread)
TRAIL_COLOR  = (80,  25,  15)
LAND_COLOR   = (18,  38,  18)   # must match game_map.LAND_COLOR
TRAIL_FADE_S = 8.0
TRAIL_STEP   = 1.5               # mm of movement before a new trail point
TRAIL_MAX    = 600

ARRIVE_DIST   = 15.0             # mm — pick new waypoint when this close to target

HP_TEXT_COLOR = (255, 255, 255)
_font_cache: dict = {}


def _draw_hp_bar(surface, left, top, width, hp, max_hp, height=3):
    """Thin horizontal HP bar: green at full, red at empty."""
    if max_hp <= 0 or width < 2:
        return
    frac = max(0.0, min(1.0, hp / max_hp))
    pygame.draw.rect(surface, (35, 10, 10), pygame.Rect(left, top, width, height))
    fill_w = max(1, int(width * frac))
    r = int(40  + 180 * (1.0 - frac))
    g = int(200 - 160 * (1.0 - frac))
    pygame.draw.rect(surface, (r, g, 40), pygame.Rect(left, top, fill_w, height))

def _get_font(size: int):
    if size not in _font_cache:
        _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]


class EnemyCarrier:
    """
    A carrier that is currently AI-driven but is built to be multiplayer-ready.

    Physics (update) and input (_think) are intentionally separated so that
    _think() can later be replaced with network / keyboard input without
    touching the movement or drawing code.
    """

    def __init__(self, x, y, drones):
        self.x      = float(x)
        self.y      = float(y)
        self.vx     = 0.0
        self.vy     = 0.0
        self.hp            = cfg.get("CARRIER_HP")
        self.max_hp        = self.hp
        self.fire_cooldown = random.uniform(0.0, 1.0)
        self.drones = drones
        self.trail       = deque()
        self._trail_dist = 0.0
        self._pick_waypoint()
        self._drone_timer    = 0.0
        self._drone_interval = random.uniform(2.0, 5.0)  # stagger across carriers

    # ------------------------------------------------------------------
    # AI input — swap this method out for network/keyboard input later
    # ------------------------------------------------------------------

    def _command_drones(self, player_visible=False):
        """
        Split drones: ~60% stay close as normal-missile guards,
        ~40% spread far as scouts (explosive when player is visible).
        """
        n = len(self.drones)
        if n == 0:
            return
        max_r    = cfg.get("DRONE_MAX_RADIUS_MM")
        n_guards = max(1, int(n * 0.6))
        close_r  = max_r * 0.3

        for i, drone in enumerate(self.drones):
            if i < n_guards:
                # Guard — tight cluster around carrier, always normal
                angle = 2 * math.pi * i / n_guards
                r     = random.uniform(close_r * 0.4, close_r)
                drone.set_target(r * math.cos(angle), r * math.sin(angle))
                drone.missile_type = 'normal'
            else:
                # Scout — spread far, explosive only when they can see the player
                angle = random.uniform(0, 2 * math.pi)
                r     = random.uniform(max_r * 0.6, max_r * 0.9)
                drone.set_target(r * math.cos(angle), r * math.sin(angle))
                drone.missile_type = 'explosive' if player_visible else 'normal'

    def _pick_waypoint(self):
        """Choose a random destination well inside the island."""
        map_w = cfg.get("MAP_WIDTH_MM")
        map_h = cfg.get("MAP_HEIGHT_MM")
        cx, cy  = map_w / 2, map_h / 2
        max_r   = min(map_w, map_h) * 0.35   # stay comfortably inside coast
        angle   = random.uniform(0, 2 * math.pi)
        r       = random.uniform(max_r * 0.15, max_r)
        self._target_x = cx + r * math.cos(angle)
        self._target_y = cy + r * math.sin(angle)

    def _can_see(self, wx, wy):
        """True if (wx, wy) is within this carrier's or its drones' vision."""
        carrier_vis_sq = cfg.get("CARRIER_VISION_RADIUS_MM") ** 2
        drone_vis_sq   = cfg.get("DEFAULT_DRONE_VISION_MM")  ** 2
        if (wx - self.x) ** 2 + (wy - self.y) ** 2 <= carrier_vis_sq:
            return True
        for d in self.drones:
            dx = self.x + d.offset_x - wx
            dy = self.y + d.offset_y - wy
            if dx * dx + dy * dy <= drone_vis_sq:
                return True
        return False

    def _think(self, player_x=None, player_y=None):
        """
        Return (dx, dy) in [-1 ,1] representing the desired movement direction.
        AI implementation: chase the player when visible (same vision rules as
        the player's fog-of-war), otherwise wander between random waypoints.
        Replace with e.g. network packet parsing for multiplayer.
        """
        # Flee from player when visible — let drones do the fighting
        if player_x is not None and player_y is not None:
            if self._can_see(player_x, player_y):
                dist_to_player = math.hypot(player_x - self.x, player_y - self.y)
                if dist_to_player > 0:
                    return (-(player_x - self.x) / dist_to_player,
                            -(player_y - self.y) / dist_to_player)
                return 0.0, 0.0

        # Default: wander between random waypoints
        dx = self._target_x - self.x
        dy = self._target_y - self.y
        dist = math.hypot(dx, dy)
        if dist < ARRIVE_DIST:
            self._pick_waypoint()
            dx = self._target_x - self.x
            dy = self._target_y - self.y
            dist = math.hypot(dx, dy)
        if dist > 0:
            return dx / dist, dy / dist
        return 0.0, 0.0

    # ------------------------------------------------------------------
    # Physics update — identical to player carrier, input-source agnostic
    # ------------------------------------------------------------------

    def update(self, dt, player_x=None, player_y=None):
        accel     = cfg.get("CARRIER_ACCELERATION")
        top_speed = cfg.get("CARRIER_TOP_SPEED")

        player_visible = (player_x is not None and player_y is not None
                          and self._can_see(player_x, player_y))
        ix, iy = self._think(player_x, player_y)   # input: unit direction vector (or 0,0)

        def apply_axis(v, d):
            if d != 0:
                v += d * accel * dt
                v  = max(-top_speed, min(top_speed, v))
            else:
                step = accel * dt
                v    = 0.0 if abs(v) <= step else v - math.copysign(step, v)
            return v

        self.vx = apply_axis(self.vx, ix)
        self.vy = apply_axis(self.vy, iy)

        speed = math.hypot(self.vx, self.vy)
        if speed > top_speed:
            self.vx = self.vx / speed * top_speed
            self.vy = self.vy / speed * top_speed

        self.x += self.vx * dt
        self.y += self.vy * dt

        # Drone commands — periodically scatter drones to new positions
        self._drone_timer += dt
        if self._drone_timer >= self._drone_interval:
            self._drone_timer    = 0.0
            self._drone_interval = random.uniform(2.0, 5.0)
            self._command_drones(player_visible)

        # Trail — record position, age points, evict faded ones
        self._trail_dist += math.hypot(self.vx * dt, self.vy * dt)
        if self._trail_dist >= TRAIL_STEP:
            self._trail_dist = 0.0
            self.trail.append([self.x, self.y, 0.0])
            if len(self.trail) > TRAIL_MAX:
                self.trail.popleft()
        for pt in self.trail:
            pt[2] += dt / TRAIL_FADE_S
        while self.trail and self.trail[0][2] >= 1.0:
            self.trail.popleft()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw_trail(self, surface, camera_x_mm, camera_y_mm, game_h, px):
        r = max(1, int(cfg.get("CARRIER_WIDTH_MM") * 0.30 * px))
        for wx, wy, age in self.trail:
            sx = int((wx - camera_x_mm) * px)
            sy = int((wy - camera_y_mm) * px)
            if -r <= sx < settings.SCREEN_WIDTH + r and -r <= sy < game_h + r:
                t = age
                color = (
                    int(TRAIL_COLOR[0] * (1 - t) + LAND_COLOR[0] * t),
                    int(TRAIL_COLOR[1] * (1 - t) + LAND_COLOR[1] * t),
                    int(TRAIL_COLOR[2] * (1 - t) + LAND_COLOR[2] * t),
                )
                pygame.draw.circle(surface, color, (sx, sy), r)

    def draw(self, surface, camera_x_mm, camera_y_mm, game_h, px):
        w  = max(1, int(cfg.get("CARRIER_WIDTH_MM")  * px))
        h  = max(1, int(cfg.get("CARRIER_HEIGHT_MM") * px))
        sx = int((self.x - camera_x_mm) * px)
        sy = int((self.y - camera_y_mm) * px)
        if (-w <= sx < settings.SCREEN_WIDTH + w and
                -h <= sy < game_h + h):
            rect = pygame.Rect(sx - w // 2, sy - h // 2, w, h)
            pygame.draw.rect(surface, COLOR,  rect)
            pygame.draw.rect(surface, BORDER, rect, 1)
            font_size = max(8, min(w, h) - 4)
            font      = _get_font(font_size)
            surf      = font.render(str(int(self.hp)), True, HP_TEXT_COLOR)
            surface.blit(surf, surf.get_rect(center=(sx, sy)))
            # HP bar — thin strip above carrier body
            _draw_hp_bar(surface, sx - w // 2, sy - h // 2 - 5, w, self.hp, self.max_hp)
