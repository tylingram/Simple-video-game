import pygame
import settings
import config as cfg

# Visual style
COLOR  = (80, 200, 140)   # unit fill
BORDER = (160, 255, 200)  # hitbox outline


class Carrier:
    """
    The Carrier — player unit.
    Centered in the gameplay area. Size driven by config variables.
    The drawn rect is also the hitbox.
    """

    def _get_rect(self):
        # Convert mm → pixels
        w = max(1, int(cfg.get("CARRIER_WIDTH_MM")  * settings.DPI / 25.4))
        h = max(1, int(cfg.get("CARRIER_HEIGHT_MM") * settings.DPI / 25.4))

        # Gameplay area height (accounts for dynamic HUD size)
        hud_h  = max(1, int(settings.SCREEN_HEIGHT * cfg.get("HUD_SIZE") / 100))
        game_h = settings.SCREEN_HEIGHT - hud_h

        cx = settings.SCREEN_WIDTH  // 2
        cy = game_h                 // 2

        return pygame.Rect(cx - w // 2, cy - h // 2, w, h)

    @property
    def hitbox(self):
        return self._get_rect()

    def draw(self, surface):
        rect = self._get_rect()
        pygame.draw.rect(surface, COLOR,  rect)
        pygame.draw.rect(surface, BORDER, rect, 1)
