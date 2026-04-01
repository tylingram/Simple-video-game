import math
import pygame
import settings
import config as cfg

PLAYER_COLOR    = (100, 220, 255)   # cyan  — player missiles
ENEMY_COLOR     = (255, 160,  40)   # orange — enemy missiles
EXPLOSIVE_COLOR = (255, 230,  60)   # bright yellow — explosive missiles
RADIUS_PX       = 3


class Missile:
    """
    A homing projectile that always reaches its target.
    target      — the unit object being tracked (Drone or Carrier/EnemyCarrier)
    carrier_ref — the carrier that owns the target if target is a Drone, else None
    team        — 'player' or 'enemy' (controls colour)
    explosive   — if True, splashes MISSILE_DAMAGE to all units within
                  EXPLOSIVE_BLAST_RADIUS_MM of the impact point on hit
    """

    def __init__(self, x, y, target, carrier_ref, team, explosive=False):
        self.x           = float(x)
        self.y           = float(y)
        self.target      = target
        self.carrier_ref = carrier_ref
        self.team        = team
        self.explosive   = explosive
        self.alive       = True

    def _target_pos(self):
        if self.carrier_ref is not None:
            return (self.carrier_ref.x + self.target.offset_x,
                    self.carrier_ref.y + self.target.offset_y)
        return (self.target.x, self.target.y)

    def update(self, dt, splash_targets=None):
        if not self.alive:
            return
        if self.target.hp <= 0:
            self.alive = False
            return
        tx, ty = self._target_pos()
        dx, dy = tx - self.x, ty - self.y
        dist   = math.hypot(dx, dy)
        move   = cfg.get("MISSILE_SPEED_MM") * dt
        if dist <= move:
            self.target.hp -= cfg.get("MISSILE_DAMAGE")
            if self.explosive and splash_targets:
                blast_r  = cfg.get("EXPLOSIVE_BLAST_RADIUS_MM")
                splash_d = cfg.get("MISSILE_DAMAGE")
                for unit, wx, wy in splash_targets:
                    if unit is not self.target and unit.hp > 0:
                        if math.hypot(wx - tx, wy - ty) <= blast_r:
                            unit.hp -= splash_d
            self.alive = False
        else:
            self.x += dx / dist * move
            self.y += dy / dist * move

    def draw(self, surface, camera_x_mm, camera_y_mm, game_h, px):
        if not self.alive:
            return
        sx = int((self.x - camera_x_mm) * px)
        sy = int((self.y - camera_y_mm) * px)
        if -RADIUS_PX <= sx < settings.SCREEN_WIDTH + RADIUS_PX and \
           -RADIUS_PX <= sy < game_h + RADIUS_PX:
            if self.explosive:
                color = EXPLOSIVE_COLOR
            else:
                color = PLAYER_COLOR if self.team == 'player' else ENEMY_COLOR
            r = RADIUS_PX + 1 if self.explosive else RADIUS_PX
            pygame.draw.circle(surface, color, (sx, sy), r)
