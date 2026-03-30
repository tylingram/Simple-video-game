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
        """Set target carrier-relative offset, clamped to max radius."""
        max_r = cfg.get("DRONE_MAX_RADIUS_MM")
        d = math.sqrt(tx_mm ** 2 + ty_mm ** 2)
        if d > max_r and d > 0:
            tx_mm = tx_mm / d * max_r
            ty_mm = ty_mm / d * max_r
        self.target_x = tx_mm
        self.target_y = ty_mm

    # ── Physics update ────────────────────────────────────────────────────────

    def update(self, dt, carrier_vx=0.0, carrier_vy=0.0):
        """Arrive steering toward target.  Stops cleanly at destination.

        vel_x/y are carrier-relative.  carrier_vx/vy are used only for the
        world-space speed clamp so the limit is enforced relative to the map.
        Collision stopping is handled by the constraint pass in main.py.
        """
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

        arrive_nx = dx / dist
        arrive_ny = dy / dist

        desired_speed = min(max_speed, math.sqrt(2.0 * accel * dist))
        desired_vx    = arrive_nx * desired_speed
        desired_vy    = arrive_ny * desired_speed

        dvx = desired_vx - self.vel_x
        dvy = desired_vy - self.vel_y
        dv  = math.sqrt(dvx * dvx + dvy * dvy)
        max_dv = accel * dt
        if dv > max_dv and dv > 0:
            dvx = dvx / dv * max_dv
            dvy = dvy / dv * max_dv
        self.vel_x += dvx
        self.vel_y += dvy

        # Enforce max speed in world-space (map-relative).
        # Convert carrier-relative vel → world, clamp, convert back.
        world_vx  = self.vel_x + carrier_vx
        world_vy  = self.vel_y + carrier_vy
        world_spd = math.sqrt(world_vx ** 2 + world_vy ** 2)
        if world_spd > max_speed and world_spd > 0:
            self.vel_x = world_vx / world_spd * max_speed - carrier_vx
            self.vel_y = world_vy / world_spd * max_speed - carrier_vy

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
