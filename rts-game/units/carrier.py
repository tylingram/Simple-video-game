import math
import pygame
import settings
import config as cfg

# Visual style
COLOR  = (80,  200, 140)   # unit fill
BORDER = (160, 255, 200)   # hitbox outline


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
        self.reset()

    def reset(self):
        """Move carrier to map center and zero velocity. Called on init and config reload."""
        self.x  = cfg.get("MAP_WIDTH_MM")  / 2
        self.y  = cfg.get("MAP_HEIGHT_MM") / 2
        self.vx = 0.0
        self.vy = 0.0

    def update(self, dt, keys):
        accel     = cfg.get("CARRIER_ACCELERATION")  # mm/s²
        top_speed = cfg.get("CARRIER_TOP_SPEED")      # mm/s
        map_w     = cfg.get("MAP_WIDTH_MM")
        map_h     = cfg.get("MAP_HEIGHT_MM")
        half_w    = cfg.get("CARRIER_WIDTH_MM")  / 2
        half_h    = cfg.get("CARRIER_HEIGHT_MM") / 2

        # Input direction (-1, 0, or 1 per axis)
        dx = int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])
        dy = int(keys[pygame.K_DOWN])  - int(keys[pygame.K_UP])

        def apply_axis(v, d):
            if d != 0:
                v += d * accel * dt
                v  = max(-top_speed, min(top_speed, v))
            else:
                # Decelerate at the same rate
                step = accel * dt
                v    = 0.0 if abs(v) <= step else v - math.copysign(step, v)
            return v

        self.vx = apply_axis(self.vx, dx)
        self.vy = apply_axis(self.vy, dy)

        # Update position
        self.x += self.vx * dt
        self.y += self.vy * dt

        # Clamp to map bounds (carrier edges stay inside)
        if self.x < half_w:
            self.x  = half_w
            self.vx = 0.0
        elif self.x > map_w - half_w:
            self.x  = map_w - half_w
            self.vx = 0.0

        if self.y < half_h:
            self.y  = half_h
            self.vy = 0.0
        elif self.y > map_h - half_h:
            self.y  = map_h - half_h
            self.vy = 0.0

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

    def draw(self, surface, game_h):
        w, h   = self._size_px()
        cx, cy = settings.SCREEN_WIDTH // 2, game_h // 2
        rect   = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        pygame.draw.rect(surface, COLOR,  rect)
        pygame.draw.rect(surface, BORDER, rect, 1)
