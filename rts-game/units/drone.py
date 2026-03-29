import math
import pygame
import settings
import config as cfg

# Visual style
COLOR_NORMAL    = (80,  160, 220)
BORDER_NORMAL   = (140, 200, 255)
COLOR_SELECTED  = (80,  220, 80)
BORDER_SELECTED = (140, 255, 140)

ARRIVE_THRESHOLD_MM = 0.3   # stop when this close to target (mm)


class Drone:
    """
    A single drone. Maintains a carrier-relative offset (mm).
    Can be commanded to a new offset target via set_target().
    Moves using acceleration/decelerate-to-stop physics.
    All position/velocity values are relative to the carrier.
    """

    def __init__(self, offset_x_mm, offset_y_mm):
        self.offset_x = offset_x_mm   # current carrier-relative offset (mm)
        self.offset_y = offset_y_mm
        self.target_x = offset_x_mm   # commanded target offset (mm)
        self.target_y = offset_y_mm
        self.vel_x    = 0.0            # velocity relative to carrier (mm/s)
        self.vel_y    = 0.0
        self.selected = False

    # ── Commanding ────────────────────────────────────────────────────────────

    def set_target(self, tx_mm, ty_mm):
        """
        Set target carrier-relative offset, clamping to DRONE_MAX_RADIUS_MM.
        If the requested point is outside the max radius, it is projected onto
        the circle along the carrier → target line.
        """
        max_r = cfg.get("DRONE_MAX_RADIUS_MM")
        d = math.sqrt(tx_mm ** 2 + ty_mm ** 2)
        if d > max_r and d > 0:
            tx_mm = tx_mm / d * max_r
            ty_mm = ty_mm / d * max_r
        self.target_x = tx_mm
        self.target_y = ty_mm

    # ── Physics update ────────────────────────────────────────────────────────

    def update(self, dt):
        """Advance offset toward target using arrive/decelerate physics."""
        accel     = cfg.get("DEFAULT_DRONE_ACCELERATION")   # mm/s²
        max_speed = cfg.get("DEFAULT_DRONE_MAX_SPEED")       # mm/s

        dx   = self.target_x - self.offset_x
        dy   = self.target_y - self.offset_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < ARRIVE_THRESHOLD_MM:
            self.offset_x = self.target_x
            self.offset_y = self.target_y
            self.vel_x    = 0.0
            self.vel_y    = 0.0
            return

        speed = math.sqrt(self.vel_x ** 2 + self.vel_y ** 2)

        # Stopping distance for current speed: v² / (2a)
        stopping_dist = (speed ** 2) / (2 * accel) if accel > 0 else 0

        if stopping_dist >= dist:
            # Begin deceleration
            new_speed = max(0.0, speed - accel * dt)
            if speed > 0:
                scale      = new_speed / speed
                self.vel_x *= scale
                self.vel_y *= scale
        else:
            # Accelerate toward target
            nx = dx / dist
            ny = dy / dist
            self.vel_x += nx * accel * dt
            self.vel_y += ny * accel * dt
            speed = math.sqrt(self.vel_x ** 2 + self.vel_y ** 2)
            if speed > max_speed:
                self.vel_x = self.vel_x / speed * max_speed
                self.vel_y = self.vel_y / speed * max_speed

        self.offset_x += self.vel_x * dt
        self.offset_y += self.vel_y * dt

    # ── Screen helpers ────────────────────────────────────────────────────────

    def screen_pos(self, game_h):
        """Pixel position on screen (carrier is always at screen centre)."""
        px = settings.DPI / 25.4
        cx = settings.SCREEN_WIDTH // 2
        cy = game_h               // 2
        return (int(cx + self.offset_x * px),
                int(cy + self.offset_y * px))

    def is_clicked(self, mx, my, game_h):
        """Return True if screen click (mx, my) lands on this drone."""
        px        = settings.DPI / 25.4
        radius_px = max(1, int(cfg.get("DEFAULT_DRONE_DIAMETER_MM") / 2 * px))
        sx, sy    = self.screen_pos(game_h)
        return math.sqrt((mx - sx) ** 2 + (my - sy) ** 2) <= radius_px + 4

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self, surface, game_h):
        px        = settings.DPI / 25.4
        radius_px = max(1, int(cfg.get("DEFAULT_DRONE_DIAMETER_MM") / 2 * px))
        sx, sy    = self.screen_pos(game_h)
        c = COLOR_SELECTED  if self.selected else COLOR_NORMAL
        b = BORDER_SELECTED if self.selected else BORDER_NORMAL
        pygame.draw.circle(surface, c, (sx, sy), radius_px)
        pygame.draw.circle(surface, b, (sx, sy), radius_px, 1)


# ── Formation factory ─────────────────────────────────────────────────────────

def create_formation():
    """Arrange N drones equidistantly on a circle above the carrier."""
    n = int(cfg.get("STARTING_DRONES"))
    r = cfg.get("DRONE_START_RADIUS_MM")
    drones = []
    for i in range(n):
        angle = -math.pi / 2 + 2 * math.pi * i / n
        drones.append(Drone(r * math.cos(angle), r * math.sin(angle)))
    return drones
