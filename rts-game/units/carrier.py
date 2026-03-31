import math
import random
from collections import deque
import pygame
import settings
import config as cfg

# Visual style
COLOR  = (80,  200, 140)   # unit fill
BORDER = (160, 255, 200)   # hitbox outline

# Trail style
TRAIL_COLOR  = (50,  40,  18)   # crushed grass / muddy track
LAND_COLOR   = (18,  38,  18)   # must match game_map.LAND_COLOR for fade target
TRAIL_FADE_S = 8.0               # seconds for trail to fully fade
TRAIL_STEP   = 1.5               # mm of movement before a new point is stored
TRAIL_MAX    = 600               # hard cap on stored points

HP_TEXT_COLOR = (255, 255, 255)
_font_cache: dict = {}

def _get_font(size: int):
    if size not in _font_cache:
        _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]


class Carrier:
    """
    The Carrier — player unit.
    Moves around in world-space (mm). Camera is locked to it so it always
    appears centered on screen. Arrow keys control movement.
    """

    def __init__(self):
        self.x  = 0.0
        self.y  = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.hp          = cfg.get("CARRIER_HP")
        self.max_hp      = self.hp
        self.fire_cooldown = random.uniform(0.0, 1.0)
        self.trail       = deque()   # entries: [world_x, world_y, age_0_to_1]
        self._trail_dist = 0.0       # accumulated distance since last trail point
        self.reset()

    def reset(self):
        """Move carrier to map center and zero velocity. Called on init and config reload."""
        self.x  = cfg.get("MAP_WIDTH_MM")  / 2
        self.y  = cfg.get("MAP_HEIGHT_MM") / 2
        self.vx = 0.0
        self.vy = 0.0
        self.hp            = cfg.get("CARRIER_HP")
        self.max_hp        = self.hp
        self.fire_cooldown = random.uniform(0.0, 1.0)
        self.trail.clear()
        self._trail_dist = 0.0

    def update(self, dt, keys):
        accel     = cfg.get("CARRIER_ACCELERATION")  # mm/s²
        top_speed = cfg.get("CARRIER_TOP_SPEED")      # mm/s

        # Input direction (-1, 0, or 1 per axis)
        dx = int(keys[pygame.K_d]) - int(keys[pygame.K_a])
        dy = int(keys[pygame.K_s]) - int(keys[pygame.K_w])

        def apply_axis(v, d):
            if d != 0:
                v += d * accel * dt
                v  = max(-top_speed, min(top_speed, v))
            else:
                step = accel * dt
                v    = 0.0 if abs(v) <= step else v - math.copysign(step, v)
            return v

        self.vx = apply_axis(self.vx, dx)
        self.vy = apply_axis(self.vy, dy)

        # Clamp combined vector speed — per-axis clamping alone allows
        # diagonal movement to reach top_speed * √2
        speed = math.hypot(self.vx, self.vy)
        if speed > top_speed:
            self.vx = self.vx / speed * top_speed
            self.vy = self.vy / speed * top_speed

        self.x += self.vx * dt
        self.y += self.vy * dt
        # Boundary collision handled by GameMap.resolve_carrier()

        # --- Trail ---
        # Accumulate distance; drop a new world-space point every TRAIL_STEP mm
        self._trail_dist += math.hypot(self.vx * dt, self.vy * dt)
        if self._trail_dist >= TRAIL_STEP:
            self._trail_dist = 0.0
            self.trail.append([self.x, self.y, 0.0])
            if len(self.trail) > TRAIL_MAX:
                self.trail.popleft()

        # Age every point; evict fully-faded ones from the front
        for pt in self.trail:
            pt[2] += dt / TRAIL_FADE_S
        while self.trail and self.trail[0][2] >= 1.0:
            self.trail.popleft()

    def _size_px(self):
        w = max(1, int(cfg.get("CARRIER_WIDTH_MM")  * settings.DPI / 25.4))
        h = max(1, int(cfg.get("CARRIER_HEIGHT_MM") * settings.DPI / 25.4))
        return w, h

    @property
    def hitbox(self):
        """Hitbox in screen space — always centered."""
        w, h   = self._size_px()
        hud_h  = max(1, int(settings.SCREEN_HEIGHT * cfg.get("HUD_SIZE") / 100))
        game_h = settings.SCREEN_HEIGHT - hud_h
        cx, cy = settings.SCREEN_WIDTH // 2, game_h // 2
        return pygame.Rect(cx - w // 2, cy - h // 2, w, h)

    def draw_trail(self, surface, camera_x_mm, camera_y_mm, game_h, px):
        """Draw the crushed-grass trail behind the carrier."""
        r = max(1, int(cfg.get("CARRIER_WIDTH_MM") * 0.30 * px))
        for wx, wy, age in self.trail:
            sx = int((wx - camera_x_mm) * px)
            sy = int((wy - camera_y_mm) * px)
            if -r <= sx < settings.SCREEN_WIDTH + r and -r <= sy < game_h + r:
                # Interpolate from track colour toward land colour as age → 1
                t = age
                color = (
                    int(TRAIL_COLOR[0] * (1 - t) + LAND_COLOR[0] * t),
                    int(TRAIL_COLOR[1] * (1 - t) + LAND_COLOR[1] * t),
                    int(TRAIL_COLOR[2] * (1 - t) + LAND_COLOR[2] * t),
                )
                pygame.draw.circle(surface, color, (sx, sy), r)

    def draw(self, surface, game_h):
        w, h   = self._size_px()
        cx, cy = settings.SCREEN_WIDTH // 2, game_h // 2
        rect   = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        pygame.draw.rect(surface, COLOR,  rect)
        pygame.draw.rect(surface, BORDER, rect, 1)
        font_size = max(8, min(w, h) - 4)
        font      = _get_font(font_size)
        surf      = font.render(str(int(self.hp)), True, HP_TEXT_COLOR)
        surface.blit(surf, surf.get_rect(center=(cx, cy)))
