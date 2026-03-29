import pygame
import settings
import config as cfg


class HUD:
    """Bottom dashboard panel. Height is driven by config HUD_SIZE."""

    def _layout(self):
        hud_h  = max(1, int(settings.SCREEN_HEIGHT * cfg.get("HUD_SIZE") / 100))
        game_h = settings.SCREEN_HEIGHT - hud_h
        return game_h, hud_h

    def update(self, elapsed_secs):
        pass

    def draw(self, surface):
        game_h, hud_h = self._layout()
        rect = pygame.Rect(0, game_h, settings.SCREEN_WIDTH, hud_h)

        pygame.draw.rect(surface, settings.HUD_BG, rect)
        pygame.draw.line(surface, settings.HUD_BORDER, (0, game_h), (settings.SCREEN_WIDTH, game_h), 2)
