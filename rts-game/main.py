import os
import sys
import subprocess
import pygame
import settings
from hud import HUD
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


def launch_config_editor():
    """Open the config editor as a separate process so it can't affect the game."""
    editor = os.path.join(os.path.dirname(__file__), "config_editor.py")
    subprocess.Popen([sys.executable, editor])


def main():
    pygame.init()

    fullscreen = False
    screen = make_screen(fullscreen)
    pygame.display.set_caption(settings.TITLE)
    clock = pygame.time.Clock()

    hud     = HUD()
    carrier = Carrier()
    launch_config_editor()

    # Track config.json modification time to reload when editor saves
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    last_mtime  = os.path.getmtime(config_path) if os.path.exists(config_path) else 0

    running = True
    while running:
        clock.tick(settings.FPS)

        # --- Reload config if editor saved changes ---
        try:
            mtime = os.path.getmtime(config_path)
            if mtime > last_mtime:
                cfg.load_from_disk()
                last_mtime = mtime
        except OSError:
            pass

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    screen = make_screen(fullscreen)
            elif event.type == pygame.WINDOWRESIZED:
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
