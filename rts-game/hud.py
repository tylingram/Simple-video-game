import pygame
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, HUD_BG, HUD_BORDER
import config as cfg


class HUD:
    """Bottom dashboard panel. Height is driven by config HUD_SIZE."""

    def _layout(self):
        hud_h  = max(1, int(SCREEN_HEIGHT * cfg.get("HUD_SIZE") / 100))
        game_h = SCREEN_HEIGHT - hud_h
        return game_h, hud_h

    def update(self, elapsed_secs):
        pass

    def draw(self, surface):
        game_h, hud_h = self._layout()
        rect = pygame.Rect(0, game_h, SCREEN_WIDTH, hud_h)

        pygame.draw.rect(surface, HUD_BG, rect)
        pygame.draw.line(surface, HUD_BORDER, (0, game_h), (SCREEN_WIDTH, game_h), 2)
