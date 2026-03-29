import pygame
import settings
import config as cfg

FOG_DARK  = (15, 15, 15, 215)   # colour + alpha of the unexplored area
CLEAR     = (0,  0,  0,  0)     # fully transparent — punched out for vision


class FogOfWar:
    """
    Dark overlay that hides everything outside the carrier's vision radius.
    The carrier is always at screen centre, so the clear circle is too.
    """

    def __init__(self):
        self._surface   = None
        self._last_key  = None   # (screen_w, game_h, radius_px) — rebuild when any changes

    def draw(self, surface, game_h):
        radius_px = max(1, int(cfg.get("CARRIER_VISION_RADIUS_MM") * settings.DPI / 25.4))
        w         = settings.SCREEN_WIDTH
        key       = (w, game_h, radius_px)

        # Rebuild the fog surface only when dimensions or radius change
        if key != self._last_key:
            self._surface  = pygame.Surface((w, game_h), pygame.SRCALPHA)
            self._surface.fill(FOG_DARK)
            cx = w        // 2
            cy = game_h   // 2
            pygame.draw.circle(self._surface, CLEAR, (cx, cy), radius_px)
            self._last_key = key

        surface.blit(self._surface, (0, 0))
