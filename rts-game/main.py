import pygame
from settings import TITLE, SCREEN_WIDTH, SCREEN_HEIGHT, FPS, BLACK
from hud import HUD
from config_window import ConfigWindow
import config as cfg


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()

    hud = HUD()
    ConfigWindow()   # opens the config panel in a background thread

    running = True
    while running:
        clock.tick(FPS)

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # --- Layout (re-read every frame so config changes apply instantly) ---
        hud_h  = max(1, int(SCREEN_HEIGHT * cfg.get("HUD_SIZE") / 100))
        game_h = SCREEN_HEIGHT - hud_h

        # --- Draw ---
        pygame.draw.rect(screen, BLACK, (0, 0, SCREEN_WIDTH, game_h))
        hud.draw(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
