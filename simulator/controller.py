"""PID position controller with derivative-on-measurement.

State variables:
  * `target_position` — set-point in metres.
  * `emergency_stop`  — when True, motor force becomes a strong brake
    proportional to velocity (real linear actuators with a self-locking
    screw or a brake clamp behave like this on power loss — they don't
    free-wheel under load). Without this, releasing the controller
    while a 4 N mean load is applied would slide the carriage to the
    nearest mechanical stop.

Derivative is taken from the measured velocity (not error derivative)
to avoid the well-known "derivative kick" on set-point steps.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PIDGains:
    kp: float = 1200.0
    ki: float = 30.0
    kd: float = 90.0
    integral_clamp: float = 5.0    # anti-windup limit on integral term
    estop_brake: float = 600.0     # N·s/m, viscous brake strength on E-stop


class PositionController:
    def __init__(self, gains: PIDGains | None = None) -> None:
        self.g = gains or PIDGains()
        self._integral: float = 0.0
        self.target_position: float = 0.0
        self.emergency_stop: bool = False

    def set_target(self, target: float) -> None:
        self.target_position = target

    def trigger_estop(self, on: bool) -> None:
        self.emergency_stop = on
        if on:
            self._integral = 0.0

    def step(self, dt: float, position: float, velocity: float) -> float:
        if self.emergency_stop:
            return -self.g.estop_brake * velocity
        err = self.target_position - position
        self._integral += err * dt
        clamp = self.g.integral_clamp
        self._integral = max(-clamp, min(clamp, self._integral))
        # derivative on measurement → minus velocity, not d(error)/dt
        return self.g.kp * err + self.g.ki * self._integral - self.g.kd * velocity
