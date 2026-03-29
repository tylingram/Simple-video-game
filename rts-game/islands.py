"""
Random island obstacles — impassable by carrier, passable by drones.
Islands are regenerated every time config is saved/reloaded.

Visuals: organic blobs with a sandy coast ring and smooth anti-aliased edges.
Collision: SAT against the actual polygon vertices (kept nearly-convex via smoothing).
"""
import random
import math
import pygame
import pygame.gfxdraw
import settings
import config as cfg

ISLAND_LAND  = (45,  100,  45)   # land green
ISLAND_COAST = (190, 160,  95)   # sandy beach ring


# ---------------------------------------------------------------------------
# Polygon generation
# ---------------------------------------------------------------------------

def _make_verts(cx, cy, half, style):
    """
    Generate world-space island vertices as an organic blob.
    style 0 = round,  1 = elongated,  2 = irregular.
    All variants stay nearly convex so SAT collision is reliable.
    """
    n = 22   # control points

    if style == 0:
        # Round — tight radial variation
        radii = [half * random.uniform(0.78, 1.00) for _ in range(n)]

    elif style == 1:
        # Elongated — ellipse base with gentle noise
        stretch    = random.uniform(1.35, 1.75)
        angle_off  = random.uniform(0, math.pi)
        radii = []
        for i in range(n):
            a = 2 * math.pi * i / n + angle_off
            # Polar ellipse radius
            r_e = (half * stretch) / math.sqrt(
                (stretch * math.cos(a)) ** 2 + math.sin(a) ** 2
            )
            r_e = min(r_e, half * stretch)   # cap so it stays sane
            radii.append(r_e * random.uniform(0.82, 1.00))

    else:
        # Irregular — wider variation but still smoothed into a blob
        radii = [half * random.uniform(0.60, 1.00) for _ in range(n)]

    # Gaussian-weighted smoothing — removes spikes, keeps organic feel
    for _ in range(6):
        w = [0.05, 0.20, 0.50, 0.20, 0.05]
        smoothed = []
        for i in range(n):
            val = sum(w[k] * radii[(i + k - 2) % n] for k in range(5))
            smoothed.append(val)
        radii = smoothed

    verts = []
    for i in range(n):
        angle = 2 * math.pi * i / n
        verts.append((cx + radii[i] * math.cos(angle),
                      cy + radii[i] * math.sin(angle)))
    return verts


def _scale_verts(verts, cx, cy, scale):
    """Scale polygon outward from its centre (for beach ring)."""
    return [(cx + (x - cx) * scale, cy + (y - cy) * scale)
            for x, y in verts]


# ---------------------------------------------------------------------------
# SAT collision helper
# ---------------------------------------------------------------------------

def _sat_push(carrier_x, carrier_y, box_verts, poly_verts):
    """
    SAT between carrier AABB (box_verts) and a convex polygon (poly_verts).
    Returns (push_x, push_y) to move the carrier out, or (0, 0) if no overlap.
    """
    poly_cx = sum(v[0] for v in poly_verts) / len(poly_verts)
    poly_cy = sum(v[1] for v in poly_verts) / len(poly_verts)

    axes = [(1.0, 0.0), (0.0, 1.0)]
    m = len(poly_verts)
    for i in range(m):
        x1, y1 = poly_verts[i]
        x2, y2 = poly_verts[(i + 1) % m]
        ex, ey = x2 - x1, y2 - y1
        length = math.hypot(ex, ey)
        if length > 0:
            axes.append((-ey / length, ex / length))

    min_overlap = float('inf')
    mtv = (0.0, 0.0)

    for ax, ay in axes:
        box_projs  = [ax * x + ay * y for x, y in box_verts]
        poly_projs = [ax * x + ay * y for x, y in poly_verts]

        box_min,  box_max  = min(box_projs),  max(box_projs)
        poly_min, poly_max = min(poly_projs), max(poly_projs)

        overlap = min(box_max, poly_max) - max(box_min, poly_min)
        if overlap <= 0:
            return 0.0, 0.0

        if overlap < min_overlap:
            min_overlap = overlap
            box_proj  = ax * carrier_x + ay * carrier_y
            poly_proj = ax * poly_cx   + ay * poly_cy
            sign = -1.0 if box_proj < poly_proj else 1.0
            mtv  = (sign * ax * overlap, sign * ay * overlap)

    return mtv


# ---------------------------------------------------------------------------
# Island
# ---------------------------------------------------------------------------

class Island:

    def __init__(self, cx, cy, half, style):
        self.cx    = cx
        self.cy    = cy
        self.half  = half
        self.verts = _make_verts(cx, cy, half, style)
        # Furthest vertex distance * 1.15 for the beach ring — used for cull check
        self.cull_radius = max(math.hypot(x - cx, y - cy)
                               for x, y in self.verts) * 1.15

    # ------------------------------------------------------------------
    # Collision
    # ------------------------------------------------------------------

    def collide_carrier(self, carrier):
        half_w = cfg.get("CARRIER_WIDTH_MM")  / 2
        half_h = cfg.get("CARRIER_HEIGHT_MM") / 2
        cl = carrier.x - half_w;  cr = carrier.x + half_w
        ct = carrier.y - half_h;  cb = carrier.y + half_h
        box_verts = [(cl, ct), (cr, ct), (cr, cb), (cl, cb)]
        return _sat_push(carrier.x, carrier.y, box_verts, self.verts)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface, camera_x_mm, camera_y_mm, game_h):
        px    = settings.DPI / 25.4
        cull  = int(self.cull_radius * px)
        sx    = int((self.cx - camera_x_mm) * px)
        sy    = int((self.cy - camera_y_mm) * px)

        if sx + cull < 0 or sx - cull > settings.SCREEN_WIDTH:
            return
        if sy + cull < 0 or sy - cull > game_h:
            return

        def to_screen(wx, wy):
            return (int((wx - camera_x_mm) * px),
                    int((wy - camera_y_mm) * px))

        # Sandy beach ring (polygon scaled outward ~15%)
        coast_verts = [to_screen(self.cx + (x - self.cx) * 1.15,
                                  self.cy + (y - self.cy) * 1.15)
                       for x, y in self.verts]
        pygame.gfxdraw.filled_polygon(surface, coast_verts, ISLAND_COAST)
        pygame.gfxdraw.aapolygon(surface, coast_verts, ISLAND_COAST)

        # Land fill
        land_verts = [to_screen(x, y) for x, y in self.verts]
        pygame.gfxdraw.filled_polygon(surface, land_verts, ISLAND_LAND)
        pygame.gfxdraw.aapolygon(surface, land_verts, ISLAND_LAND)


# ---------------------------------------------------------------------------
# Islands manager
# ---------------------------------------------------------------------------

STYLES = [0, 1, 2]   # round, elongated, irregular


class Islands:

    def __init__(self):
        self.islands = []
        self.reset()

    def reset(self):
        self.islands = []
        n     = int(cfg.get("ISLANDS_PER_MAP"))
        half  = cfg.get("ISLAND_SIZE_MM") / 2
        map_w = cfg.get("MAP_WIDTH_MM")
        map_h = cfg.get("MAP_HEIGHT_MM")

        carrier_x     = map_w / 2
        carrier_y     = map_h / 2
        carrier_clear = half * 1.15 + math.hypot(cfg.get("CARRIER_WIDTH_MM"),
                                                  cfg.get("CARRIER_HEIGHT_MM"))

        placed = 0
        attempts = 0
        while placed < n and attempts < 2000:
            attempts += 1
            style = STYLES[placed % len(STYLES)]
            cx = random.uniform(half * 1.15, map_w - half * 1.15)
            cy = random.uniform(half * 1.15, map_h - half * 1.15)

            if math.hypot(cx - carrier_x, cy - carrier_y) < carrier_clear:
                continue

            self.islands.append(Island(cx, cy, half, style))
            placed += 1

    def draw(self, surface, camera_x_mm, camera_y_mm, game_h):
        for island in self.islands:
            island.draw(surface, camera_x_mm, camera_y_mm, game_h)

    def resolve_carrier(self, carrier):
        for island in self.islands:
            px, py = island.collide_carrier(carrier)
            if px:
                carrier.x  += px
                carrier.vx  = 0.0
            if py:
                carrier.y  += py
                carrier.vy  = 0.0
