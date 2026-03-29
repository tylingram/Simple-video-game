import pygame
import settings
import config as cfg

MAP_COLOR    = (0,   0,   0)     # inside the map — black
NONMAP_COLOR = (30,  60, 120)    # outside the map — blue


class GameMap:
    """Renders the play area. Black inside the map bounds, blue outside."""

    def draw(self, surface, camera_x_mm, camera_y_mm, game_h):
        """
        camera_x_mm / camera_y_mm: world-space mm coordinate at the
        top-left corner of the game viewport.
        """
        px = settings.DPI / 25.4   # pixels per mm

        map_w = cfg.get("MAP_WIDTH_MM")
        map_h = cfg.get("MAP_HEIGHT_MM")

        # Fill entire game area with blue (non-map space default)
        pygame.draw.rect(surface, NONMAP_COLOR,
                         (0, 0, settings.SCREEN_WIDTH, game_h))

        # Map edges in screen-space pixels
        map_left   = int((0     - camera_x_mm) * px)
        map_top    = int((0     - camera_y_mm) * px)
        map_right  = int((map_w - camera_x_mm) * px)
        map_bottom = int((map_h - camera_y_mm) * px)

        # Clip to the game viewport
        draw_left   = max(0, map_left)
        draw_top    = max(0, map_top)
        draw_right  = min(settings.SCREEN_WIDTH, map_right)
        draw_bottom = min(game_h, map_bottom)

        if draw_right > draw_left and draw_bottom > draw_top:
            pygame.draw.rect(surface, MAP_COLOR,
                             (draw_left, draw_top,
                              draw_right  - draw_left,
                              draw_bottom - draw_top))
