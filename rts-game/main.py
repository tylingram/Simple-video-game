import pygame
from settings import TITLE, SCREEN_WIDTH, SCREEN_HEIGHT, FPS, BLACK, GAME_HEIGHT
from hud import HUD


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()
    hud = HUD()
    elapsed = 0.0

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0  # seconds since last frame
        elapsed += dt

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # --- Update ---
        hud.update(elapsed)

        # --- Draw ---
        # Gameplay area — black
        pygame.draw.rect(screen, BLACK, (0, 0, SCREEN_WIDTH, GAME_HEIGHT))

        # HUD panel
        hud.draw(screen)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
