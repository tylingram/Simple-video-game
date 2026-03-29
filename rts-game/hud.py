import pygame
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, HUD_HEIGHT, GAME_HEIGHT, HUD_BG, HUD_BORDER, WHITE, GRAY


class HUD:
    """Bottom dashboard panel — stats, messages, general info."""

    def __init__(self):
        self.rect = pygame.Rect(0, GAME_HEIGHT, SCREEN_WIDTH, HUD_HEIGHT)
        self.font_sm = pygame.font.SysFont("monospace", 13)
        self.font_md = pygame.font.SysFont("monospace", 15, bold=True)

        # Placeholder data (swap in real values later)
        self.stats = {
            "Minerals": 50,
            "Gas":      0,
            "Supply":   "0/10",
            "Time":     "00:00",
        }
        self.message = "Welcome — game not yet started."

    def update(self, elapsed_secs):
        mins = int(elapsed_secs) // 60
        secs = int(elapsed_secs) % 60
        self.stats["Time"] = f"{mins:02d}:{secs:02d}"

    def draw(self, surface):
        # Background
        pygame.draw.rect(surface, HUD_BG, self.rect)

        # Top border line
        pygame.draw.line(
            surface, HUD_BORDER,
            (0, GAME_HEIGHT), (SCREEN_WIDTH, GAME_HEIGHT), 2
        )

        # --- Stats block (left side) ---
        x, y = 16, GAME_HEIGHT + 8
        for label, value in self.stats.items():
            text = self.font_md.render(f"{label}:", True, (140, 180, 140))
            surface.blit(text, (x, y))
            val  = self.font_sm.render(str(value), True, WHITE)
            surface.blit(val, (x + 80, y + 2))
            x += 140

        # --- Message bar (right side) ---
        msg = self.font_sm.render(self.message, True, (180, 180, 200))
        surface.blit(msg, (SCREEN_WIDTH - msg.get_width() - 16, GAME_HEIGHT + 10))
