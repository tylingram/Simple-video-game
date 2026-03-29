"""
The game map — rendered as a large organic island sitting in the ocean.
MAP_WIDTH_MM / MAP_HEIGHT_MM define the bounding box; the island fills
roughly 85% of that area with an organic, smoothed coastline.

The carrier is confined to the island interior via containment collision
(edge-normal push-back + wall-slide velocity zeroing).
"""
import random
import math
import pygame
import pygame.gfxdraw
import settings
import config as cfg

OCEAN_COLOR = (30,  60, 120)   # surrounding sea
LAND_COLOR  = (18,  38,  18)   # interior land (dark — good contrast for units)
COAST_COLOR = (175, 145,  80)  # sandy coastline ring


def _make_island_verts(cx, cy, rx, ry):
    """
    Generate world-space vertices for the map island using layered sinusoidal
    noise — multiple octaves create large bays/peninsulas at low frequency and
    rocky detail at high frequency, giving a natural coastline appearance.
    rx / ry are the ellipse half-extents from MAP_WIDTH_MM / MAP_HEIGHT_MM.
    """
    n = 96  # dense enough for fine coastal detail at map scale

    angles = [2 * math.pi * i / n for i in range(n)]

    # Ellipse base so the island respects the map aspect ratio
    radii = []
    for a in angles:
        cos_a, sin_a = math.cos(a), math.sin(a)
        r_ellipse = (rx * ry) / math.sqrt((ry * cos_a) ** 2 + (rx * sin_a) ** 2)
        radii.append(r_ellipse * random.uniform(0.78, 0.95))

    # Layered sinusoidal noise — low freqs = large geographic features,
    # high freqs = fine coastal roughness
    octaves = [
        (2,  0.10),   # large bays / peninsulas
        (3,  0.08),
        (5,  0.06),   # medium inlets
        (8,  0.05),
        (13, 0.04),   # small coves
        (21, 0.03),   # rocky detail
        (34, 0.02),   # fine texture
    ]
    for freq, amp in octaves:
        phase = random.uniform(0, 2 * math.pi)
        avg_r = sum(radii) / n
        for i in range(n):
            radii[i] += avg_r * amp * math.sin(freq * angles[i] + phase)

    # Per-point micro-jitter
    radii = [r * random.uniform(0.97, 1.03) for r in radii]

    # Single light smoothing pass — smooths self-intersections only
    smoothed = []
    for i in range(n):
        smoothed.append((radii[(i - 1) % n] * 0.25 +
                         radii[i]           * 0.50 +
                         radii[(i + 1) % n] * 0.25))
    radii = smoothed

    return [(cx + radii[i] * math.cos(angles[i]),
             cy + radii[i] * math.sin(angles[i]))
            for i in range(n)]


# ---------------------------------------------------------------------------
# Concave-polygon helpers (shared with ponds logic, duplicated here to keep
# game_map.py self-contained)
# ---------------------------------------------------------------------------

def _point_in_poly(px, py, verts):
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


class GameMap:

    def __init__(self):
        self.verts       = []
        self.coast_verts = []
        self.cull_radius = 0.0
        self.reset()

    def reset(self):
        """Regenerate the island shape. Called on init and every config reload."""
        map_w = cfg.get("MAP_WIDTH_MM")
        map_h = cfg.get("MAP_HEIGHT_MM")
        cx, cy = map_w / 2, map_h / 2
        self.verts = _make_island_verts(cx, cy, map_w * 0.425, map_h * 0.425)
        # Coast polygon (1.15×) — the actual hard boundary for the carrier
        self.coast_verts = [(cx + (x - cx) * 1.15, cy + (y - cy) * 1.15)
                            for x, y in self.verts]
        self.cull_radius = max(math.hypot(x - cx, y - cy)
                               for x, y in self.coast_verts)

    # ------------------------------------------------------------------
    # Containment collision — keeps carrier inside the island
    # ------------------------------------------------------------------

    def resolve_carrier(self, carrier):
        """
        Keep the carrier's inscribed circle (radius = CARRIER_WIDTH_MM/2) inside
        the coast polygon.  Uses point-in-polygon so concave coastlines work.
        """
        half_w = cfg.get("CARRIER_WIDTH_MM") / 2

        inside = _point_in_poly(carrier.x, carrier.y, self.coast_verts)
        bx, by  = _nearest_boundary(carrier.x, carrier.y, self.coast_verts)
        dx, dy  = bx - carrier.x, by - carrier.y
        dist    = math.hypot(dx, dy)

        if inside and dist >= half_w:
            return   # circle fully inside — nothing to do

        if dist == 0:
            # Degenerate: nudge toward map centre
            carrier.x += cfg.get("MAP_WIDTH_MM")  / 2 - carrier.x
            return

        if not inside:
            # Centre outside: push past boundary by half_w
            push_x = dx / dist * (dist + half_w)
            push_y = dy / dist * (dist + half_w)
        else:
            # Centre inside but circle edge outside: push inward by deficit
            push_x = -dx / dist * (half_w - dist)
            push_y = -dy / dist * (half_w - dist)

        carrier.x += push_x
        carrier.y += push_y

        # Wall-slide: zero velocity component heading outward
        pd = math.hypot(push_x, push_y)
        if pd > 0:
            nx, ny = push_x / pd, push_y / pd
            v_in = carrier.vx * nx + carrier.vy * ny
            if v_in < 0:
                carrier.vx -= v_in * nx
                carrier.vy -= v_in * ny

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface, camera_x_mm, camera_y_mm, game_h):
        px = settings.DPI / 25.4

        # Ocean background
        pygame.draw.rect(surface, OCEAN_COLOR, (0, 0, settings.SCREEN_WIDTH, game_h))

        map_w = cfg.get("MAP_WIDTH_MM")
        map_h = cfg.get("MAP_HEIGHT_MM")
        cx_w, cy_w = map_w / 2, map_h / 2

        # Viewport cull (island entirely off-screen)
        cull = int(self.cull_radius * px)
        sx   = int((cx_w - camera_x_mm) * px)
        sy   = int((cy_w - camera_y_mm) * px)
        if sx + cull < 0 or sx - cull > settings.SCREEN_WIDTH:
            return
        if sy + cull < 0 or sy - cull > game_h:
            return

        def to_screen(wx, wy):
            return (int((wx - camera_x_mm) * px),
                    int((wy - camera_y_mm) * px))

        # Land — fills all the way to the coast boundary (no separate coast ring)
        land_verts = [to_screen(x, y) for x, y in self.coast_verts]
        pygame.gfxdraw.filled_polygon(surface, land_verts, LAND_COLOR)
        pygame.gfxdraw.aapolygon(surface, land_verts, LAND_COLOR)
