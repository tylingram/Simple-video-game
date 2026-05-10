import pygame
import settings
import config as cfg

FOG_DARK = (15, 15, 15, 215)   # unexplored area colour + alpha
CLEAR    = (0,  0,  0,  0)     # fully transparent — vision punch-out


class FogOfWar:
    """
    Dark overlay. Accepts a list of (screen_x, screen_y, radius_px) vision
    circles and punches transparent holes for each one.

    The surface is allocated ONCE and reused every frame — only the draw
    operations (fill + circles) run when the circles change.  Allocating a
    new SRCALPHA surface every frame is very expensive in WebAssembly /
    software rendering, so we avoid it entirely.

    Position rounding (4 px) further reduces rebuild frequency so the fog
    only regenerates when any circle centre moves ≥ 4 screen pixels.
    """

    _ROUND = 4   # pixel rounding — set higher to rebuild even less often

    def __init__(self):
        self._surface  = None
        self._size     = (0, 0)
        self._last_key = None

    def reset(self):
        """Force a rebuild on the next draw (call after config reload)."""
        self._last_key = None

    def draw(self, surface, game_h, vision_circles):
        """
        vision_circles: list of (screen_x, screen_y, radius_px)
        """
        w    = settings.SCREEN_WIDTH
        size = (w, game_h)

        # Reallocate only when window size changes (rare)
        if self._surface is None or self._size != size:
            self._surface  = pygame.Surface(size, pygame.SRCALPHA)
            self._size     = size
            self._last_key = None   # force rebuild

        # Round positions so minor subpixel drift doesn't trigger a rebuild
        r = self._ROUND
        rounded = tuple(
            (sx // r * r, sy // r * r, rad)
            for sx, sy, rad in vision_circles
        )
        key = rounded

        if key != self._last_key:
            self._surface.fill(FOG_DARK)
            for sx, sy, rad in vision_circles:
                pygame.draw.circle(self._surface, CLEAR, (sx, sy), rad)
            self._last_key = key

        surface.blit(self._surface, (0, 0))
