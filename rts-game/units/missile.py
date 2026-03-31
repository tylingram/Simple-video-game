import math
import pygame
import settings
import config as cfg

PLAYER_COLOR = (100, 220, 255)   # cyan  — player missiles
ENEMY_COLOR  = (255, 160,  40)   # orange — enemy missiles
RADIUS_PX    = 3


class Missile:
    """
    A homing projectile that always reaches its target.
    target      — the unit object being tracked (Drone or Carrier/EnemyCarrier)
    carrier_ref — the carrier that owns the target if target is a Drone, else None
    team        — 'player' or 'enemy' (controls colour)
    """

    def __init__(self, x, y, target, carrier_ref, team):
        self.x           = float(x)
        self.y           = float(y)
        self.target      = target
        self.carrier_ref = carrier_ref
        self.team        = team
        self.alive       = True

    def _target_pos(self):
        if self.carrier_ref is not None:
            return (self.carrier_ref.x + self.target.offset_x,
                    self.carrier_ref.y + self.target.offset_y)
        return (self.target.x, self.target.y)

    def update(self, dt):
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
            color = PLAYER_COLOR if self.team == 'player' else ENEMY_COLOR
            pygame.draw.circle(surface, color, (sx, sy), RADIUS_PX)
