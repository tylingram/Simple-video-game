import pygame
import settings
from hud import HUD
from config_window import ConfigWindow
from units.carrier import Carrier
import config as cfg

WINDOWED_W = 1280
WINDOWED_H = 720


def make_screen(fullscreen):
    """Recreate the display surface in windowed or fullscreen mode."""
    if fullscreen:
        info = pygame.display.Info()
        settings.SCREEN_WIDTH  = info.current_w
        settings.SCREEN_HEIGHT = info.current_h
        return pygame.display.set_mode(
            (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT),
            pygame.FULLSCREEN
        )
    else:
        settings.SCREEN_WIDTH  = WINDOWED_W
        settings.SCREEN_HEIGHT = WINDOWED_H
        return pygame.display.set_mode(
            (WINDOWED_W, WINDOWED_H),
            pygame.RESIZABLE
        )


def main():
    pygame.init()

    fullscreen = False
    screen = make_screen(fullscreen)
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

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    screen = make_screen(fullscreen)

            elif event.type == pygame.WINDOWRESIZED:
                # Keep settings in sync when user resizes/maximizes the window
                settings.SCREEN_WIDTH  = event.x
                settings.SCREEN_HEIGHT = event.y

        # --- Layout ---
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
