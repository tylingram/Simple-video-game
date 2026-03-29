import math
import os
import sys
import subprocess
import pygame
import settings
from hud import HUD
from game_map import GameMap
from fog_of_war import FogOfWar
from units.carrier import Carrier
from units.drone import create_formation
import config as cfg

WINDOWED_W = 1280
WINDOWED_H = 720

MAX_RADIUS_COLOR = (80, 80, 100)   # light grey-blue dotted circle


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


def draw_dotted_circle(surface, color, cx, cy, radius_px, n_dashes=56, width=1):
    """Draw a dashed circle using short arc segments."""
    if radius_px <= 0:
        return
    rect      = pygame.Rect(cx - radius_px, cy - radius_px,
                             radius_px * 2,  radius_px * 2)
    dash_fill = 0.55   # fraction of each slot that is drawn
    for i in range(n_dashes):
        if i % 2 == 0:
            a1 = 2 * math.pi * i          / n_dashes
            a2 = 2 * math.pi * (i + dash_fill) / n_dashes
            pygame.draw.arc(surface, color, rect, a1, a2, width)


def launch_config_editor():
    """Open the config editor as a separate process so it can't affect the game."""
    editor = os.path.join(os.path.dirname(__file__), "config_editor.py")
    subprocess.Popen([sys.executable, editor])


def main():
    pygame.init()

    fullscreen = False
    screen     = make_screen(fullscreen)
    pygame.display.set_caption(settings.TITLE)
    clock = pygame.time.Clock()

    hud      = HUD()
    game_map = GameMap()
    fog      = FogOfWar()
    carrier  = Carrier()
    drones   = create_formation()
    launch_config_editor()

    # Track config.json modification time to reload when editor saves
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    last_mtime  = os.path.getmtime(config_path) if os.path.exists(config_path) else 0

    running = True
    while running:
        dt = clock.tick(settings.FPS) / 1000.0

        # --- Reload config ---
        try:
            mtime = os.path.getmtime(config_path)
            if mtime > last_mtime:
                cfg.load_from_disk()
                carrier.reset()
                fog.reset()
                drones     = create_formation()
                last_mtime = mtime
        except OSError:
            pass

        # --- Layout ---
        hud_h  = max(1, int(settings.SCREEN_HEIGHT * cfg.get("HUD_SIZE") / 100))
        game_h = settings.SCREEN_HEIGHT - hud_h

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

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if my < game_h:   # ignore clicks on HUD
                    hit = next((d for d in drones
                                if d.is_clicked(mx, my, game_h)), None)
                    if hit:
                        # Toggle selection; deselect all others
                        already_selected = hit.selected
                        for d in drones:
                            d.selected = False
                        hit.selected = not already_selected
                    else:
                        # Move selected drone to clicked position
                        sel = next((d for d in drones if d.selected), None)
                        if sel:
                            px_per_mm = settings.DPI / 25.4
                            ox = (mx - settings.SCREEN_WIDTH // 2) / px_per_mm
                            oy = (my - game_h               // 2) / px_per_mm
                            sel.set_target(ox, oy)

        # --- Update ---
        keys = pygame.key.get_pressed()
        carrier.update(dt, keys)
        for drone in drones:
            drone.update(dt)

        # --- Camera ---
        px_per_mm   = settings.DPI / 25.4
        camera_x_mm = carrier.x - (settings.SCREEN_WIDTH / 2) / px_per_mm
        camera_y_mm = carrier.y - (game_h              / 2) / px_per_mm

        # --- Vision circles ---
        carrier_vis_px = max(1, int(cfg.get("CARRIER_VISION_RADIUS_MM") * px_per_mm))
        drone_vis_px   = max(1, int(cfg.get("DEFAULT_DRONE_VISION_MM")  * px_per_mm))
        cx, cy         = settings.SCREEN_WIDTH // 2, game_h // 2
        vision_circles = [(cx, cy, carrier_vis_px)]
        for drone in drones:
            sx, sy = drone.screen_pos(game_h)
            vision_circles.append((sx, sy, drone_vis_px))

        # --- Draw ---
        game_map.draw(screen, camera_x_mm, camera_y_mm, game_h)
        carrier.draw(screen, game_h)
        for drone in drones:
            drone.draw(screen, game_h)
        fog.draw(screen, game_h, vision_circles)

        # Max-radius dotted circle drawn after fog so it's always visible
        max_r_px = int(cfg.get("DRONE_MAX_RADIUS_MM") * px_per_mm)
        draw_dotted_circle(screen, MAX_RADIUS_COLOR, cx, cy, max_r_px)

        hud.draw(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
