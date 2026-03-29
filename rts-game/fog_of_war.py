import pygame
import settings
import config as cfg

FOG_DARK = (15, 15, 15, 215)   # unexplored area colour + alpha
CLEAR    = (0,  0,  0,  0)     # fully transparent — vision punch-out


class FogOfWar:
    """
    Dark overlay. Accepts a list of (screen_x, screen_y, radius_px) vision
    circles and punches transparent holes for each one.
    The surface is cached and only rebuilt when the circles or window change.
    """

    def __init__(self):
        self._surface  = None
        self._last_key = None

    def reset(self):
        """Force a rebuild on the next draw (call after config reload)."""
        self._last_key = None

    def draw(self, surface, game_h, vision_circles):
        """
        vision_circles: list of (screen_x, screen_y, radius_px)
        """
        w   = settings.SCREEN_WIDTH
        key = (w, game_h, tuple(vision_circles))

        if key != self._last_key:
            self._surface = pygame.Surface((w, game_h), pygame.SRCALPHA)
            self._surface.fill(FOG_DARK)
            for (sx, sy, r) in vision_circles:
                pygame.draw.circle(self._surface, CLEAR, (sx, sy), r)
            self._last_key = key

        surface.blit(self._surface, (0, 0))
