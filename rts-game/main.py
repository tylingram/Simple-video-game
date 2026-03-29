import pygame
import settings
from hud import HUD
from config_window import ConfigWindow
from units.carrier import Carrier
import config as cfg


def main():
    pygame.init()

    # Use native screen resolution for true fullscreen
    info = pygame.display.Info()
    settings.SCREEN_WIDTH  = info.current_w
    settings.SCREEN_HEIGHT = info.current_h

    screen = pygame.display.set_mode(
        (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT),
        pygame.FULLSCREEN
    )
    pygame.display.set_caption(settings.TITLE)
    clock = pygame.time.Clock()

    hud     = HUD()
    carrier = Carrier()
    ConfigWindow()   # opens the config panel in a background thread

    running = True
    while running:
        clock.tick(settings.FPS)

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_F11):
                    pygame.display.toggle_fullscreen()

        # --- Layout (re-read every frame so config changes apply instantly) ---
        hud_h  = max(1, int(settings.SCREEN_HEIGHT * cfg.get("HUD_SIZE") / 100))
        game_h = settings.SCREEN_HEIGHT - hud_h

        # --- Draw ---
        pygame.draw.rect(screen, settings.BLACK, (0, 0, settings.SCREEN_WIDTH, game_h))
        carrier.draw(screen)
        hud.draw(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
