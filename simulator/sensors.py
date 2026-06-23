"""Sensor layer.

Wraps the *true* physical state vector and produces *measured* values
with realistic distortions:

* Additive Gaussian noise per channel.
* Slow linear drift accumulating over time (bias instability).
* Measurement lag: a small ring buffer that delays the value by N steps.

Kept deliberately simple — first-order effects only. The point is that
downstream code (health classifier, dashboard) sees imperfect data, so
it cannot cheat by reading the ground-truth state.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Deque


@dataclass(frozen=True)
class SensorParams:
    position_noise: float = 0.0002    # m, std
    velocity_noise: float = 0.001     # m/s, std
    accel_noise: float = 0.02         # m/s^2, std
    current_noise: float = 0.05       # A, std
    temperature_noise: float = 0.1    # °C, std

    drift_rate_temp: float = 0.0005   # °C/s, slow bias growth
    drift_rate_current: float = 0.0002  # A/s

    lag_steps: int = 2                # delay in simulation steps


@dataclass
class TrueState:
    position: float
    velocity: float
    acceleration: float
    current: float
    temperature: float


@dataclass
class MeasuredState:
    position: float
    velocity: float
    acceleration: float
    current: float
    temperature: float


@dataclass
class SensorSuite:
    params: SensorParams = field(default_factory=SensorParams)
    seed: int | None = None

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self._t_drift: float = 0.0
        self._i_drift: float = 0.0
        self._buffer: Deque[TrueState] = deque(maxlen=max(1, self.params.lag_steps + 1))

    def measure(self, true: TrueState, dt: float) -> MeasuredState:
        self._buffer.append(true)
        delayed = self._buffer[0] if len(self._buffer) > self.params.lag_steps else true

        self._t_drift += self.params.drift_rate_temp * dt
        self._i_drift += self.params.drift_rate_current * dt

        g = self._rng.gauss
        return MeasuredState(
            position=delayed.position + g(0.0, self.params.position_noise),
            velocity=delayed.velocity + g(0.0, self.params.velocity_noise),
            acceleration=delayed.acceleration + g(0.0, self.params.accel_noise),
            current=delayed.current + self._i_drift + g(0.0, self.params.current_noise),
            temperature=delayed.temperature + self._t_drift + g(0.0, self.params.temperature_noise),
        )
