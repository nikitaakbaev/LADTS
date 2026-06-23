"""External load model.

Generates a slowly varying random load force, occasionally spiked to
simulate an obstacle or a sudden mechanical resistance. Uses a first-
order Ornstein-Uhlenbeck-like update so the load is correlated in time
(real loads are not white noise).

    F_load[k+1] = F_load[k] + theta * (mu - F_load[k]) * dt + sigma * sqrt(dt) * N(0,1)

with an additional Poisson-like impulse process for spikes.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class LoadParams:
    mu: float = 4.0          # N, mean load
    theta: float = 0.5       # 1/s, mean-reversion rate
    sigma: float = 2.0       # N/sqrt(s), diffusion
    spike_prob: float = 0.002  # per step, probability of an impulse
    spike_magnitude: float = 15.0  # N, magnitude of an impulse
    f_max: float = 40.0      # N, absolute saturation


class LoadModel:
    def __init__(
        self,
        params: LoadParams | None = None,
        seed: int | None = None,
    ) -> None:
        self.p = params or LoadParams()
        self._rng = random.Random(seed)
        self._f: float = self.p.mu
        self._spike_decay: float = 0.0

    def step(self, dt: float) -> float:
        drift = self.p.theta * (self.p.mu - self._f) * dt
        diffusion = self.p.sigma * math.sqrt(dt) * self._rng.gauss(0.0, 1.0)
        self._f += drift + diffusion

        if self._rng.random() < self.p.spike_prob:
            self._spike_decay = self.p.spike_magnitude * self._rng.choice([-1, 1])
        self._f += self._spike_decay
        self._spike_decay *= 0.7  # quick exponential decay

        self._f = max(-self.p.f_max, min(self.p.f_max, self._f))
        return self._f

    @property
    def value(self) -> float:
        return self._f
