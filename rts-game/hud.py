import pygame
from settings import SCREEN_WIDTH, GAME_HEIGHT, HUD_HEIGHT, HUD_BG, HUD_BORDER


class HUD:
    """Bottom dashboard panel."""

    def __init__(self):
        self.rect = pygame.Rect(0, GAME_HEIGHT, SCREEN_WIDTH, HUD_HEIGHT)

    def update(self, elapsed_secs):
        pass

    def draw(self, surface):
        # Background
        pygame.draw.rect(surface, HUD_BG, self.rect)

        # Top border line
        pygame.draw.line(
            surface, HUD_BORDER,
            (0, GAME_HEIGHT), (SCREEN_WIDTH, GAME_HEIGHT), 2
        )
