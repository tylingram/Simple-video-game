"""
Pond obstacles — impassable by carrier, passable by drones.
Ponds are regenerated every time config is saved/reloaded.
Collision is shape-accurate via SAT against the actual polygon vertices.
"""
import random
import math
import pygame
import pygame.gfxdraw
import settings
import config as cfg

POND_WATER = (30,  60, 120)   # matches ocean color — blends outside the island


# ---------------------------------------------------------------------------
# Polygon generation (same organic blob approach as the map island)
# ---------------------------------------------------------------------------

def _make_verts(cx, cy, half, style):
    """
    Generate natural-looking pond vertices using layered sinusoidal noise
    (multiple octaves at different frequencies), giving irregular coastlines
    rather than smooth blobs.
    style 0 = compact/round,  1 = elongated,  2 = very irregular.
    """
    n = 64  # dense point count for fine edge detail

    angles = [2 * math.pi * i / n for i in range(n)]

    if style == 1:
        # Elongated base — ellipse-shaped pond
        stretch   = random.uniform(1.4, 1.9)
        angle_off = random.uniform(0, math.pi)
        radii = []
        for a in angles:
            r_e = (half * stretch) / math.sqrt(
                (stretch * math.cos(a + angle_off)) ** 2 + math.sin(a + angle_off) ** 2
            )
            radii.append(min(r_e, half * stretch))
    else:
        radii = [half] * n

    # Layered sinusoidal noise — low frequencies for large bays/peninsulas,
    # high frequencies for rocky detail.
    if style == 0:
        octaves = [(2, 0.12), (3, 0.09), (5, 0.07), (9,  0.05), (15, 0.03)]
    elif style == 1:
        octaves = [(2, 0.10), (4, 0.08), (7, 0.06), (12, 0.04), (19, 0.03)]
    else:
        octaves = [(2, 0.18), (3, 0.14), (6, 0.10), (10, 0.07), (17, 0.04)]

    for freq, amp in octaves:
        phase = random.uniform(0, 2 * math.pi)
        for i in range(n):
            radii[i] += half * amp * math.sin(freq * angles[i] + phase)

    # Per-point micro-jitter for extra roughness
    jitter = 0.04 if style == 0 else 0.07
    radii = [r * random.uniform(1.0 - jitter, 1.0 + jitter) for r in radii]

    # One light smoothing pass — removes self-intersections without destroying detail
    smoothed = []
    for i in range(n):
        smoothed.append((radii[(i - 1) % n] * 0.25 +
                         radii[i]           * 0.50 +
                         radii[(i + 1) % n] * 0.25))
    radii = smoothed

    # Clamp so ponds never collapse to a point
    min_r = half * 0.25
    radii = [max(r, min_r) for r in radii]

    return [(cx + radii[i] * math.cos(angles[i]),
             cy + radii[i] * math.sin(angles[i]))
            for i in range(n)]


# ---------------------------------------------------------------------------
# Concave-polygon collision helpers (point-in-polygon + nearest boundary)
# ---------------------------------------------------------------------------

def _point_in_poly(px, py, verts):
    """Ray-casting point-in-polygon test — works for concave polygons."""
    inside = False
    n = len(verts)
    j = n - 1
    for i in range(n):
        xi, yi = verts[i]
        xj, yj = verts[j]
        if (yi > py) != (yj > py):
            if px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def _nearest_boundary(px, py, verts):
    """Return the closest point on the polygon boundary to (px, py)."""
    best_sq = float('inf')
    bx, by  = verts[0]
    n = len(verts)
    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        ex, ey = x2 - x1, y2 - y1
        lsq = ex * ex + ey * ey
        t   = max(0.0, min(1.0, ((px - x1) * ex + (py - y1) * ey) / lsq)) if lsq else 0.0
        cx, cy = x1 + t * ex, y1 + t * ey
        dsq = (px - cx) ** 2 + (py - cy) ** 2
        if dsq < best_sq:
            best_sq = dsq
            bx, by  = cx, cy
    return bx, by


# ---------------------------------------------------------------------------
# Pond
# ---------------------------------------------------------------------------

class Pond:
    """A single pond obstacle."""

    def __init__(self, cx, cy, half, style):
        self.cx    = cx
        self.cy    = cy
        self.half  = half
        self.verts = _make_verts(cx, cy, half, style)
        self.cull_radius = max(math.hypot(x - cx, y - cy)
                               for x, y in self.verts) * 1.15

    def collide_carrier(self, carrier):
        half_w = cfg.get("CARRIER_WIDTH_MM") / 2

        # Fast reject: carrier circle can't possibly reach the pond
        if math.hypot(carrier.x - self.cx, carrier.y - self.cy) > self.cull_radius + half_w:
            return 0.0, 0.0

        inside = _point_in_poly(carrier.x, carrier.y, self.verts)
        bx, by = _nearest_boundary(carrier.x, carrier.y, self.verts)
        dx, dy  = bx - carrier.x, by - carrier.y
        dist    = math.hypot(dx, dy)

        # No collision if carrier circle isn't touching the pond
        if not inside and dist >= half_w:
            return 0.0, 0.0
        if dist == 0:
            return half_w, 0.0  # degenerate fallback

        # push = normalize(B-C) * (dist - half_w)
        # Inside pond:  dist-half_w > 0  → push outward to boundary, step back half_w  ✓
        # Outside/close: dist-half_w < 0 → push back so circle just touches boundary    ✓
        scale = dist - half_w
        return dx / dist * scale, dy / dist * scale

    def draw(self, surface, camera_x_mm, camera_y_mm, game_h):
        px   = settings.DPI / 25.4
        cull = int(self.cull_radius * px)
        sx   = int((self.cx - camera_x_mm) * px)
        sy   = int((self.cy - camera_y_mm) * px)

        if sx + cull < 0 or sx - cull > settings.SCREEN_WIDTH:
            return
        if sy + cull < 0 or sy - cull > game_h:
            return

        def to_screen(wx, wy):
            return (int((wx - camera_x_mm) * px),
                    int((wy - camera_y_mm) * px))

        # Water fill only — same color as ocean so ponds blend outside the island.
        # The island's brown coast ring provides the natural outline where they intersect.
        water_verts = [to_screen(x, y) for x, y in self.verts]
        pygame.gfxdraw.filled_polygon(surface, water_verts, POND_WATER)


# ---------------------------------------------------------------------------
# Ponds manager
# ---------------------------------------------------------------------------

STYLES = [0, 1, 2]


class Ponds:

    def __init__(self):
        self.ponds = []
        self.reset()

    def reset(self):
        self.ponds = []
        n     = int(cfg.get("PONDS_PER_MAP"))
        half  = cfg.get("POND_SIZE_MM") / 2
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

            self.ponds.append(Pond(cx, cy, half, style))
            placed += 1

    def draw(self, surface, camera_x_mm, camera_y_mm, game_h):
        for pond in self.ponds:
            pond.draw(surface, camera_x_mm, camera_y_mm, game_h)

    def resolve_carrier(self, carrier):
        for pond in self.ponds:
            px, py = pond.collide_carrier(carrier)
            if px:
                carrier.x  += px
                carrier.vx  = 0.0
            if py:
                carrier.y  += py
                carrier.vy  = 0.0
