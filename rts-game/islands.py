"""
Random island obstacles — impassable by carrier, passable by drones.
Islands are regenerated every time config is saved/reloaded.
Collision is shape-accurate: AABB for rect, circle test for circle, SAT for triangle.
"""
import random
import math
import pygame
import settings
import config as cfg

ISLAND_COLOR  = (60,  40,  20)   # dark earth
ISLAND_BORDER = (110, 75,  40)   # lighter brown outline


# ---------------------------------------------------------------------------
# SAT helper for convex polygon vs AABB
# ---------------------------------------------------------------------------

def _sat_push(carrier_x, carrier_y, box_verts, poly_verts):
    """
    Separating Axis Theorem: convex polygon vs AABB.
    Returns (push_x, push_y) to move the box OUT of the polygon,
    or (0, 0) if no overlap.
    Axes tested: world X/Y + each polygon edge normal.
    """
    poly_cx = sum(v[0] for v in poly_verts) / len(poly_verts)
    poly_cy = sum(v[1] for v in poly_verts) / len(poly_verts)

    # Build axes: world-aligned + polygon edge normals
    axes = [(1.0, 0.0), (0.0, 1.0)]
    n = len(poly_verts)
    for i in range(n):
        x1, y1 = poly_verts[i]
        x2, y2 = poly_verts[(i + 1) % n]
        ex, ey = x2 - x1, y2 - y1
        length = math.hypot(ex, ey)
        if length > 0:
            axes.append((-ey / length, ex / length))

    min_overlap = float('inf')
    mtv = (0.0, 0.0)

    for ax, ay in axes:
        box_projs = [ax * x + ay * y for x, y in box_verts]
        box_min, box_max = min(box_projs), max(box_projs)

        poly_projs = [ax * x + ay * y for x, y in poly_verts]
        poly_min, poly_max = min(poly_projs), max(poly_projs)

        overlap = min(box_max, poly_max) - max(box_min, poly_min)
        if overlap <= 0:
            return 0.0, 0.0   # separating axis found — no collision

        if overlap < min_overlap:
            min_overlap = overlap
            # Push box away from poly centre
            box_proj  = ax * carrier_x + ay * carrier_y
            poly_proj = ax * poly_cx   + ay * poly_cy
            sign = -1.0 if box_proj < poly_proj else 1.0
            mtv  = (sign * ax * overlap, sign * ay * overlap)

    return mtv


class Island:
    """A single island obstacle.  shape is 'rect', 'circle', or 'triangle'."""

    def __init__(self, cx, cy, half, shape):
        self.cx    = cx     # world-space centre x in mm
        self.cy    = cy     # world-space centre y in mm
        self.half  = half   # half-extent / radius in mm
        self.shape = shape  # 'rect' | 'circle' | 'triangle'

    def _tri_verts(self):
        """Triangle vertices (world space): equilateral-ish pointing upward."""
        return [
            (self.cx,             self.cy - self.half),   # top
            (self.cx - self.half, self.cy + self.half),   # bottom-left
            (self.cx + self.half, self.cy + self.half),   # bottom-right
        ]

    # ------------------------------------------------------------------
    # Collision
    # ------------------------------------------------------------------

    def collide_carrier(self, carrier):
        """
        Shape-accurate collision.
        Returns (push_x, push_y) in mm to move carrier out of the island.
        Returns (0, 0) if no overlap.
        """
        half_w = cfg.get("CARRIER_WIDTH_MM")  / 2
        half_h = cfg.get("CARRIER_HEIGHT_MM") / 2

        cl = carrier.x - half_w;  cr = carrier.x + half_w
        ct = carrier.y - half_h;  cb = carrier.y + half_h

        if self.shape == 'rect':
            # AABB vs AABB
            ox = min(cr, self.cx + self.half) - max(cl, self.cx - self.half)
            oy = min(cb, self.cy + self.half) - max(ct, self.cy - self.half)
            if ox <= 0 or oy <= 0:
                return 0.0, 0.0
            if ox < oy:
                return (-ox if carrier.x < self.cx else ox), 0.0
            else:
                return 0.0, (-oy if carrier.y < self.cy else oy)

        elif self.shape == 'circle':
            # Carrier AABB vs circle: find closest point on carrier box to circle centre
            closest_x = max(cl, min(self.cx, cr))
            closest_y = max(ct, min(self.cy, cb))
            dx = closest_x - self.cx
            dy = closest_y - self.cy
            dist_sq = dx * dx + dy * dy

            if dist_sq >= self.half * self.half:
                return 0.0, 0.0

            if dist_sq == 0:
                # Carrier centre is inside the circle — push out to nearest side
                gaps = [
                    (cr - (self.cx - self.half),  1.0, 0.0),   # overlap from left
                    ((self.cx + self.half) - cl, -1.0, 0.0),   # overlap from right
                    (cb - (self.cy - self.half),  0.0, 1.0),   # overlap from top
                    ((self.cy + self.half) - ct,  0.0, -1.0),  # overlap from bottom
                ]
                ov, sx, sy = min(gaps, key=lambda t: t[0])
                return sx * ov, sy * ov

            dist = math.sqrt(dist_sq)
            overlap = self.half - dist
            # Push carrier so its closest edge sits exactly on the circle boundary
            return (dx / dist) * overlap, (dy / dist) * overlap

        else:  # triangle — SAT
            box_verts = [(cl, ct), (cr, ct), (cr, cb), (cl, cb)]
            return _sat_push(carrier.x, carrier.y, box_verts, self._tri_verts())

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface, camera_x_mm, camera_y_mm, game_h):
        px   = settings.DPI / 25.4
        h_px = max(2, int(self.half * px))
        sx   = int((self.cx - camera_x_mm) * px)
        sy   = int((self.cy - camera_y_mm) * px)

        if sx + h_px < 0 or sx - h_px > settings.SCREEN_WIDTH:
            return
        if sy + h_px < 0 or sy - h_px > game_h:
            return

        if self.shape == 'rect':
            rect = pygame.Rect(sx - h_px, sy - h_px, h_px * 2, h_px * 2)
            pygame.draw.rect(surface, ISLAND_COLOR,  rect)
            pygame.draw.rect(surface, ISLAND_BORDER, rect, 1)

        elif self.shape == 'circle':
            pygame.draw.circle(surface, ISLAND_COLOR,  (sx, sy), h_px)
            pygame.draw.circle(surface, ISLAND_BORDER, (sx, sy), h_px, 1)

        elif self.shape == 'triangle':
            pts = [
                (sx,        sy - h_px),
                (sx - h_px, sy + h_px),
                (sx + h_px, sy + h_px),
            ]
            pygame.draw.polygon(surface, ISLAND_COLOR,  pts)
            pygame.draw.polygon(surface, ISLAND_BORDER, pts, 1)


# ---------------------------------------------------------------------------
# Islands manager
# ---------------------------------------------------------------------------

SHAPES = ['rect', 'circle', 'triangle']


class Islands:

    def __init__(self):
        self.islands = []
        self.reset()

    def reset(self):
        """Randomly place islands, avoiding the carrier spawn (map centre)."""
        self.islands = []
        n     = int(cfg.get("ISLANDS_PER_MAP"))
        half  = cfg.get("ISLAND_SIZE_MM") / 2
        map_w = cfg.get("MAP_WIDTH_MM")
        map_h = cfg.get("MAP_HEIGHT_MM")

        carrier_x     = map_w / 2
        carrier_y     = map_h / 2
        carrier_clear = half + math.hypot(cfg.get("CARRIER_WIDTH_MM"),
                                          cfg.get("CARRIER_HEIGHT_MM"))

        placed = 0
        attempts = 0
        while placed < n and attempts < 2000:
            attempts += 1
            shape = SHAPES[placed % len(SHAPES)]
            cx = random.uniform(half, map_w - half)
            cy = random.uniform(half, map_h - half)

            if math.hypot(cx - carrier_x, cy - carrier_y) < carrier_clear:
                continue

            self.islands.append(Island(cx, cy, half, shape))
            placed += 1

    def draw(self, surface, camera_x_mm, camera_y_mm, game_h):
        for island in self.islands:
            island.draw(surface, camera_x_mm, camera_y_mm, game_h)

    def resolve_carrier(self, carrier):
        """Push carrier out of any overlapping island and zero velocity on pushed axes."""
        for island in self.islands:
            px, py = island.collide_carrier(carrier)
            if px:
                carrier.x  += px
                carrier.vx  = 0.0
            if py:
                carrier.y  += py
                carrier.vy  = 0.0
