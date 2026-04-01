import math
import random
import pygame
import settings
import config as cfg

# Visual style
COLOR_NORMAL      = (65,  155, 230)   # vivid steel-blue
BORDER_NORMAL     = (130, 200, 255)
COLOR_SELECTED    = (70,  220, 80)
BORDER_SELECTED   = (130, 255, 140)
GLOW_SELECTED     = (50,  180, 60)    # outer glow ring colour when selected
COLOR_ENEMY       = (210,  65,  65)   # crimson — matches enemy carrier hue
BORDER_ENEMY      = (255, 130, 130)
GLOW_EXPLOSIVE    = (255, 160,  40)   # orange ring — explosive missile mode

ARRIVE_THRESHOLD_MM = 0.3   # stop when this close to target (mm)
HP_TEXT_COLOR       = (255, 255, 255)

_font_cache: dict = {}


def _draw_hp_bar(surface, cx, top, diameter_px, hp, max_hp, height=2):
    """Thin HP bar centred below a drone circle."""
    if max_hp <= 0 or diameter_px < 2:
        return
    frac   = max(0.0, min(1.0, hp / max_hp))
    left   = cx - diameter_px // 2
    width  = diameter_px
    pygame.draw.rect(surface, (35, 10, 10), pygame.Rect(left, top, width, height))
    fill_w = max(1, int(width * frac))
    r = int(40  + 180 * (1.0 - frac))
    g = int(200 - 160 * (1.0 - frac))
    pygame.draw.rect(surface, (r, g, 40), pygame.Rect(left, top, fill_w, height))

def _get_font(size: int):
    if size not in _font_cache:
        _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]


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
        self.selected           = False
        self.missile_type       = 'normal'   # 'normal' | 'explosive'
        self.hp                 = cfg.get("DRONE_HP")
        self.max_hp             = self.hp
        self.fire_cooldown      = random.uniform(0.0, 1.0)
        self.fire_cooldown_max  = 1.0   # updated when a shot is fired

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

    def _draw_hp(self, surface, sx, sy, radius_px):
        """Render the HP number centred inside the drone circle."""
        font_size = max(8, radius_px * 2 - 2)
        font      = _get_font(font_size)
        surf      = font.render(str(int(self.hp)), True, HP_TEXT_COLOR)
        surface.blit(surf, surf.get_rect(center=(sx, sy)))

    def draw_world(self, surface, carrier_x, carrier_y,
                   camera_x_mm, camera_y_mm, game_h):
        """Draw this drone for a world-positioned (enemy) carrier."""
        px        = settings.DPI / 25.4
        radius_px = max(1, int(cfg.get("DEFAULT_DRONE_DIAMETER_MM") / 2 * px))
        wx = carrier_x + self.offset_x
        wy = carrier_y + self.offset_y
        sx = int((wx - camera_x_mm) * px)
        sy = int((wy - camera_y_mm) * px)
        if (-radius_px <= sx < settings.SCREEN_WIDTH + radius_px and
                -radius_px <= sy < game_h + radius_px):
            pygame.draw.circle(surface, COLOR_ENEMY,  (sx, sy), radius_px)
            pygame.draw.circle(surface, BORDER_ENEMY, (sx, sy), radius_px, 1)
            self._draw_hp(surface, sx, sy, radius_px)
            _draw_hp_bar(surface, sx, sy + radius_px + 2,
                         radius_px * 2, self.hp, self.max_hp)

    def draw(self, surface, game_h):
        px        = settings.DPI / 25.4
        radius_px = max(1, int(cfg.get("DEFAULT_DRONE_DIAMETER_MM") / 2 * px))
        sx, sy    = self.screen_pos(game_h)
        c = COLOR_SELECTED  if self.selected else COLOR_NORMAL
        b = BORDER_SELECTED if self.selected else BORDER_NORMAL
        if self.missile_type == 'explosive':
            # Outermost ring — explosive mode indicator
            pygame.draw.circle(surface, GLOW_EXPLOSIVE, (sx, sy), radius_px + 6, 2)
        if self.selected:
            # Selection glow ring — sits between explosive ring and body
            pygame.draw.circle(surface, GLOW_SELECTED, (sx, sy), radius_px + 3, 2)
        pygame.draw.circle(surface, c, (sx, sy), radius_px)
        pygame.draw.circle(surface, b, (sx, sy), radius_px, 1)
        self._draw_hp(surface, sx, sy, radius_px)
        _draw_hp_bar(surface, sx, sy + radius_px + 2,
                     radius_px * 2, self.hp, self.max_hp)
        # Cooldown recharge arc — sweeps clockwise from top as cooldown drains
        if self.fire_cooldown > 0 and self.fire_cooldown_max > 0:
            frac   = min(1.0, self.fire_cooldown / self.fire_cooldown_max)
            arc_r  = radius_px + (9 if self.missile_type == 'explosive' else 5)
            arc_rect = pygame.Rect(sx - arc_r, sy - arc_r, arc_r * 2, arc_r * 2)
            # pygame angles: 0=right, CCW. We want CW sweep from top.
            start_a = math.pi / 2                     # top (12 o'clock)
            end_a   = math.pi / 2 + 2 * math.pi * frac
            if end_a > start_a:
                arc_color = (200, 200, 80) if self.missile_type == 'explosive' else (160, 200, 255)
                pygame.draw.arc(surface, arc_color, arc_rect, start_a, end_a, 2)


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
