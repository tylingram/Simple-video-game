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

    def update(self, dt, all_drones):
        """Arrive steering + additive separation force.

        Separation is applied as a direct velocity nudge (not blended into the
        desired direction) so it generates lateral movement without fighting the
        arrive force.  Hard position constraints and wall-slide are handled in
        the main loop after all drones have moved.
        """
        accel     = cfg.get("DEFAULT_DRONE_ACCELERATION")   # mm/s²
        max_speed = cfg.get("DEFAULT_DRONE_MAX_SPEED")       # mm/s
        diameter  = cfg.get("DEFAULT_DRONE_DIAMETER_MM")     # mm

        dx   = self.target_x - self.offset_x
        dy   = self.target_y - self.offset_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < ARRIVE_THRESHOLD_MM:
            self.offset_x = self.target_x
            self.offset_y = self.target_y
            self.vel_x    = 0.0
            self.vel_y    = 0.0
            return

        # ── Arrive steering ───────────────────────────────────────────────────
        # Desired speed: v² = 2·a·d so the drone decelerates to a stop exactly
        # at the target.  Capped at max_speed.
        desired_speed = min(max_speed, math.sqrt(2.0 * accel * dist))
        nx = dx / dist
        ny = dy / dist
        desired_vx = nx * desired_speed
        desired_vy = ny * desired_speed

        dvx = desired_vx - self.vel_x
        dvy = desired_vy - self.vel_y
        dv  = math.sqrt(dvx * dvx + dvy * dvy)
        max_dv = accel * dt
        if dv > max_dv and dv > 0:
            dvx = dvx / dv * max_dv
            dvy = dvy / dv * max_dv
        self.vel_x += dvx
        self.vel_y += dvy

        # ── Separation force ──────────────────────────────────────────────────
        # Applied directly to velocity so it deflects the drone sideways around
        # nearby drones without opposing the arrive force head-on.
        avoid_r = diameter * 2.5
        for other in all_drones:
            if other is self:
                continue
            ox = self.offset_x - other.offset_x
            oy = self.offset_y - other.offset_y
            od = math.sqrt(ox * ox + oy * oy)
            if 0 < od < avoid_r:
                strength = (avoid_r - od) / avoid_r   # 1 at contact → 0 at avoid_r
                self.vel_x += (ox / od) * strength * accel * dt
                self.vel_y += (oy / od) * strength * accel * dt

        # Clamp to max speed after separation is applied
        speed = math.sqrt(self.vel_x * self.vel_x + self.vel_y * self.vel_y)
        if speed > max_speed and speed > 0:
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
