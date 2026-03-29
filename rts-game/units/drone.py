import math
import pygame
import settings
import config as cfg

# Visual style
COLOR  = (80,  160, 220)   # fill
BORDER = (140, 200, 255)   # outline


class Drone:
    """
    A single drone. Maintains a fixed mm offset from the carrier.
    Moves with the carrier — always rendered relative to screen centre.
    Drones operate above the map (can go off-map edges).
    """

    def __init__(self, offset_x_mm, offset_y_mm):
        self.offset_x = offset_x_mm   # mm offset from carrier (x)
        self.offset_y = offset_y_mm   # mm offset from carrier (y)

    def screen_pos(self, game_h):
        """Returns (sx, sy) pixel position on screen."""
        px = settings.DPI / 25.4
        cx = settings.SCREEN_WIDTH // 2
        cy = game_h                 // 2
        return (int(cx + self.offset_x * px),
                int(cy + self.offset_y * px))

    def draw(self, surface, game_h):
        px        = settings.DPI / 25.4
        radius_px = max(1, int(cfg.get("DEFAULT_DRONE_DIAMETER_MM") / 2 * px))
        sx, sy    = self.screen_pos(game_h)
        pygame.draw.circle(surface, COLOR,  (sx, sy), radius_px)
        pygame.draw.circle(surface, BORDER, (sx, sy), radius_px, 1)


def create_formation():
    """
    Arrange N drones equidistantly on a circle of DRONE_START_RADIUS_MM
    around the carrier.
    """
    n = int(cfg.get("STARTING_DRONES"))
    r = cfg.get("DRONE_START_RADIUS_MM")
    drones = []
    for i in range(n):
        angle = 2 * math.pi * i / n
        drones.append(Drone(r * math.cos(angle), r * math.sin(angle)))
    return drones
