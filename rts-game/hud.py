import math
import pygame
import settings
import config as cfg

TEXT_COLOR  = (180, 220, 180)   # soft green — readable against dark HUD
LABEL_COLOR = (120, 160, 210)   # muted blue for section labels / divider


class HUD:
    """Bottom dashboard panel. Height is driven by config HUD_SIZE."""

    def __init__(self):
        self._font = None   # built lazily after pygame.init()

    def _get_font(self, size):
        if self._font is None or self._font.size("A")[1] != size:
            self._font = pygame.font.Font(None, size)
        return self._font

    def _layout(self):
        hud_h  = max(1, int(settings.SCREEN_HEIGHT * cfg.get("HUD_SIZE") / 100))
        game_h = settings.SCREEN_HEIGHT - hud_h
        return game_h, hud_h

    def update(self, elapsed_secs):
        pass

    def draw(self, surface, carrier=None, drones=None):
        game_h, hud_h = self._layout()
        rect = pygame.Rect(0, game_h, settings.SCREEN_WIDTH, hud_h)

        pygame.draw.rect(surface, settings.HUD_BG, rect)
        pygame.draw.line(surface, settings.HUD_BORDER,
                         (0, game_h), (settings.SCREEN_WIDTH, game_h), 2)
        # Thin accent strip just inside the top border
        pygame.draw.line(surface, settings.HUD_ACCENT,
                         (0, game_h + 2), (settings.SCREEN_WIDTH, game_h + 2), 1)

        if carrier is None:
            return

        cx   = carrier.x - cfg.get("MAP_WIDTH_MM")  / 2
        cy   = carrier.y - cfg.get("MAP_HEIGHT_MM") / 2
        spd  = math.hypot(carrier.vx, carrier.vy)

        n_drones     = len(drones) if drones else 0
        # Show each drone's HP individually — use min (most-damaged) and max per unit
        if drones:
            drone_hp_min = min(int(d.hp)     for d in drones)
            drone_hp_max = int(drones[0].max_hp)
        else:
            drone_hp_min = 0
            drone_hp_max = 0

        font_size = max(12, hud_h // 2)
        font      = self._get_font(font_size)

        nav_text    = (f"POS  X:{int(cx):+5d}  Y:{int(cy):+5d} mm"
                       f"   SPD {int(spd):4d} mm/s")
        combat_text = (f"CARRIER  HP {int(carrier.hp)}/{int(carrier.max_hp)}"
                       f"   DRONES {n_drones}"
                       f"  HP {drone_hp_min}/{drone_hp_max} ea")

        nav_surf    = font.render(nav_text,    True, TEXT_COLOR)
        combat_surf = font.render(combat_text, True, TEXT_COLOR)

        pad  = max(6, hud_h // 6)
        mid  = settings.SCREEN_WIDTH // 2
        y_tx = game_h + (hud_h - nav_surf.get_height()) // 2

        surface.blit(nav_surf,    (pad, y_tx))
        surface.blit(combat_surf, (mid + pad, y_tx))

        # Vertical divider between nav and combat sections
        div_pad = max(4, hud_h // 8)
        pygame.draw.line(surface, settings.HUD_BORDER,
                         (mid, game_h + div_pad),
                         (mid, game_h + hud_h - div_pad), 1)
