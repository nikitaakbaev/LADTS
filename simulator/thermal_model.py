"""Thermal model of the motor winding.

Lumped first-order thermal model (one node — winding temperature):

    C_th · dT/dt = P_joule - P_cool
    P_joule = R · I²          [W]  — Joule heating in winding resistance
    P_cool  = (T - T_env) / R_th  [W]  — Newton cooling to ambient

Dividing through by C_th:

    dT/dt = (R / C_th) · I²  -  (1 / (R_th · C_th)) · (T - T_env)
          =  alpha · I²       -  beta · (T - T_env)

where:
    alpha = R_phase / C_th          [K/(s·A²)]  — Joule heating coefficient
    beta  = 1 / (R_th · C_th)      [1/s]        — Newton cooling coefficient
    tau   = 1 / beta = R_th · C_th [s]          — thermal time constant

Closed-form steady state for constant I:
    T_ss = T_env + (alpha / beta) · I²

The model is calibrated per motor using its phase resistance R_phase and
two tuning parameters: thermal_resistance R_th [K/W] and thermal_capacity
C_th [J/K].  These are estimated from the motor's size class:

  BLH5100KC (100 W, larger rotor):
    R_th  ≈ 3.5 K/W   (good heat dissipation)
    C_th  ≈ 25  J/K
    alpha = 0.450 / 25   = 0.018  K/(s·A²)
    beta  = 1/(3.5·25)  = 0.0114  1/s  → τ ≈ 87 s

  BLE230 (30 W, smaller rotor):
    R_th  ≈ 8.0 K/W
    C_th  ≈ 12  J/K
    alpha = 1.100 / 12   = 0.092  K/(s·A²)
    beta  = 1/(8.0·12)  = 0.0104  1/s  → τ ≈ 96 s

Integration: forward Euler (stable for dt ≤ 10 ms since tau >> dt).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.motor_config import MotorConfig


@dataclass(frozen=True)
class ThermalParams:
    """Thermal model coefficients derived from motor config.

    Can be constructed directly or via ThermalParams.from_motor().
    """
    alpha: float = 0.018     # K/(s·A²) — Joule heating: R_phase / C_th
    beta: float = 0.0114     # 1/s      — Newton cooling: 1/(R_th·C_th)
    t_env: float = 25.0      # °C — ambient temperature
    t_initial: float = 25.0  # °C — initial winding temperature

    @staticmethod
    def from_motor(
        motor_cfg: "MotorConfig",
        t_env: float = 25.0,
        t_initial: float = 25.0,
    ) -> "ThermalParams":
        """Derive thermal params from MotorConfig using size-class heuristics.

        Estimates C_th and R_th from motor output power class, then computes
        alpha = R_phase / C_th  and  beta = 1 / (R_th * C_th).
        """
        # Estimate thermal capacity from power class (empirical)
        # Small motors (<50 W): C_th ≈ 10–15 J/K
        # Medium (50–150 W):    C_th ≈ 20–30 J/K
        # These scale roughly with rotor volume ∝ inertia^(2/3)
        inertia_ug_m2 = motor_cfg.inertia * 1e6  # μg·m² for scaling
        # Heuristic: C_th grows with motor size proxy
        # BLH5100KC: inertia=45 μg·m²  → C_th≈25 J/K
        # BLE230:    inertia=12 μg·m²  → C_th≈12 J/K
        c_th = max(5.0, 7.0 * (inertia_ug_m2 ** 0.45))

        # R_th: thermal resistance to ambient [K/W]
        # Smaller motors have higher thermal resistance
        # BLH5100KC: 100W → R_th≈3.5 K/W
        # BLE230:     30W → R_th≈8.0 K/W
        p_nominal = motor_cfg.torque_nominal * motor_cfg.speed_nominal  # W approx
        r_th = max(1.5, 350.0 / max(p_nominal, 1.0))

        alpha = motor_cfg.resistance / c_th
        beta = 1.0 / (r_th * c_th)

        return ThermalParams(
            alpha=alpha,
            beta=beta,
            t_env=t_env,
            t_initial=t_initial,
        )


class ThermalModel:
    """First-order lumped thermal model. Forward Euler, stable for dt ≤ 10 ms."""

    def __init__(self, params: ThermalParams | None = None) -> None:
        self.p = params or ThermalParams()
        self.temperature: float = self.p.t_initial

    def step(self, dt: float, current: float) -> float:
        """Advance temperature by dt given phase current [A].

        Uses P_joule = R·I² implicitly via alpha = R/C_th:
            dT = (alpha·I² - beta·(T - T_env)) · dt
        """
        dT = (
            self.p.alpha * current * current
            - self.p.beta * (self.temperature - self.p.t_env)
        )
        self.temperature += dT * dt
        return self.temperature

    def reset(self) -> None:
        self.temperature = self.p.t_initial
