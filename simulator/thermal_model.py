"""Thermal model of the motor.

Lumped first-order thermal model:

    dT/dt = alpha * I^2 - beta * (T - T_env)

* alpha [K / (s * A^2)] — heating coefficient (Joule heating per unit dt
  per unit I^2, divided by thermal capacity).
* beta  [1/s]          — Newton cooling coefficient.
* T_env [°C]           — ambient temperature.

Closed-form steady state for constant I:

    T_ss = T_env + (alpha / beta) * I^2

For the default parameters and I = 3 A, T_ss ≈ 25 + (0.6 / 0.02) * 9
                                              ≈ 25 + 270 °C  → way too hot,
which is exactly what we want for an over-current scenario to trigger
the WARNING/ERROR thresholds. At the nominal I ≈ 1.5 A the steady state
is ~25 + 67 ≈ 92 °C, in the realistic range for a brushed DC motor.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThermalParams:
    # Calibrated so the steady-state temperatures match a realistic
    # brushed DC actuator of this size:
    #   T_ss = T_env + (alpha/beta) * I^2
    #   I = 0.6 A (holding) → ~31 °C
    #   I = 1.5 A (nominal) → ~60 °C
    #   I = 3.0 A (overload) → ~165 °C → triggers ERROR
    # Time constant tau = 1/beta = 20 s — fast enough to settle within
    # the 8 s chart window when the load drops.
    alpha: float = 0.78     # K/(s*A^2)
    beta: float = 0.05      # 1/s
    t_env: float = 25.0     # °C
    t_initial: float = 25.0  # °C


class ThermalModel:
    """First-order lumped thermal model. Forward Euler is enough at dt≤10 ms."""

    def __init__(self, params: ThermalParams | None = None) -> None:
        self.p = params or ThermalParams()
        self.temperature: float = self.p.t_initial

    def step(self, dt: float, current: float) -> float:
        dT = self.p.alpha * current * current - self.p.beta * (
            self.temperature - self.p.t_env
        )
        self.temperature += dT * dt
        return self.temperature

    def reset(self) -> None:
        self.temperature = self.p.t_initial
