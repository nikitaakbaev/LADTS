"""PID position controller with derivative-on-measurement.

State variables:
  * `target_position` — set-point in metres.
  * `emergency_stop`  — when True, motor force is forced to zero.

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
            return 0.0
        err = self.target_position - position
        self._integral += err * dt
        clamp = self.g.integral_clamp
        self._integral = max(-clamp, min(clamp, self._integral))
        # derivative on measurement → minus velocity, not d(error)/dt
        return self.g.kp * err + self.g.ki * self._integral - self.g.kd * velocity
