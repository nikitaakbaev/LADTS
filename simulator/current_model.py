"""Motor electrical phase model — full ODE with back-EMF dynamics.

Replaces the former algebraic approximation with a proper first-order
electrical ODE for the motor phase current:

    L · dI/dt = U - R·I - Ke·ω

where:
  U   [V]       — phase voltage (PWM duty × bus voltage, set by controller)
  R   [Ω]       — phase resistance
  L   [H]       — phase inductance
  Ke  [V/(rad/s)] — back-EMF constant
  ω   [rad/s]   — motor shaft angular velocity

The voltage U is derived from the force demand coming out of the PID
controller via the motor's torque constant Kt:

    T_demand = F_linear_demand * lead / (2π * η)   (ШВП conversion)
    I_demand = T_demand / Kt
    U        = R·I_demand + Ke·ω   (steady-state feed-forward)

This feed-forward U is then integrated by the ODE, giving realistic
electrical transients (τ_e = L/R ≈ 1–2 ms for these motors).

BLE230-specific features modelled here:
  * Torque limit  — clips T (and hence I_demand / U) to a fraction of T_max
  * Hold-at-stop  — when |ω| < ω_hold_threshold, U is set to R·I_hold to
                    maintain a small holding current (shaft locked by the
                    driver's electronic brake)

Integration: forward Euler with the simulator's fixed dt = 5 ms.
The electrical time constant τ_e ≈ 1–2 ms is shorter than dt, which means
the ODE is mildly stiff — we use an implicit (backward Euler) step for I
to keep it unconditionally stable:

    I_new = (I_old + dt/L * (U - Ke·ω)) / (1 + dt·R/L)

This is equivalent to the exact solution of the linear ODE when U and ω
are held constant over dt, and it is stable for any dt/τ_e ratio.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from simulator.motor_config import MotorConfig, get_motor, DEFAULT_MOTOR


@dataclass
class MotorElectricalState:
    current: float = 0.0   # A — phase current
    voltage: float = 0.0   # V — last applied phase voltage


class MotorElectricalModel:
    """Full electrical phase model for one BLDC motor.

    Usage in the simulator tick:
        omega = screw.velocity_to_omega(v_linear)
        f_motor = model.step(dt, f_demand_linear, omega)
        i       = model.state.current
    """

    # Angular velocity below which hold-at-stop activates (BLE230 only)
    _HOLD_OMEGA_THRESHOLD: float = 2.0 * math.pi  # 1 rev/s ≈ 60 rpm

    # Small holding current fraction of rated current when hold-at-stop active
    _HOLD_CURRENT_FRACTION: float = 0.15

    def __init__(self, motor_id: str = DEFAULT_MOTOR) -> None:
        self._cfg: MotorConfig = get_motor(motor_id)  # type: ignore[arg-type]
        self.state = MotorElectricalState()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def config(self) -> MotorConfig:
        return self._cfg

    def switch_motor(self, motor_id: str) -> None:
        """Hot-swap the motor configuration. Resets electrical state."""
        self._cfg = get_motor(motor_id)  # type: ignore[arg-type]
        self.state = MotorElectricalState()

    def reset(self) -> None:
        self.state = MotorElectricalState()

    def step(
        self,
        dt: float,
        f_demand: float,
        omega: float,
    ) -> float:
        """Advance electrical model by dt and return actual motor force [N].

        Args:
            dt:       integration step [s]
            f_demand: linear force requested by PID controller [N]
                      (positive = extend, negative = retract)
            omega:    current shaft angular velocity [rad/s]
                      (derived from linear velocity via ШВП)

        Returns:
            f_actual: actual linear force produced this tick [N]
        """
        cfg = self._cfg
        screw = cfg.screw

        # 1. Convert linear force demand → torque demand at motor shaft
        t_demand = screw.force_to_torque(abs(f_demand))
        sign = 1.0 if f_demand >= 0.0 else -1.0

        # 2. BLE230 torque limit
        if cfg.torque_limit_enabled:
            t_limit = cfg.torque_max * cfg.torque_limit_fraction
            t_demand = min(t_demand, t_limit)

        # 3. BLE230 hold-at-stop: override with holding current when nearly stopped
        holding = False
        if cfg.hold_at_stop and abs(omega) < self._HOLD_OMEGA_THRESHOLD:
            # Electronic brake: maintain small holding current, ignore PID demand
            i_hold = cfg.current_max * self._HOLD_CURRENT_FRACTION
            u_applied = cfg.resistance * i_hold + cfg.ke * abs(omega)
            holding = True
        else:
            # Feed-forward voltage from torque demand
            i_demand = t_demand / cfg.kt if cfg.kt > 0 else 0.0
            i_demand = min(i_demand, cfg.current_max)
            # Steady-state U = R·I_demand + Ke·|ω|  (back-EMF always opposes motion)
            u_ff = cfg.resistance * i_demand + cfg.ke * abs(omega)
            # Clamp to bus voltage
            u_applied = min(u_ff, cfg.voltage_nominal)

        # 4. Implicit (backward) Euler integration — stable for any τ_e/dt ratio
        #    I_new = (I_old + dt/L * (U - Ke·|ω|)) / (1 + dt·R/L)
        back_emf = cfg.ke * abs(omega)
        i_old = self.state.current
        numerator = i_old + (dt / cfg.inductance) * (u_applied - back_emf)
        denominator = 1.0 + dt * cfg.resistance / cfg.inductance
        i_new = numerator / denominator

        # 5. Clamp to physical current limit (driver fuse)
        i_new = max(0.0, min(i_new, cfg.current_max))

        # 6. Actual torque and linear force produced
        if holding:
            # Hold-at-stop: force is just enough to counteract gravity/load,
            # but we don't know load here — model it as zero net force
            # (the actuator is locked; position is maintained externally).
            t_actual = 0.0
        else:
            t_actual = cfg.kt * i_new

        # Clamp torque to motor's peak torque rating
        t_actual = min(t_actual, cfg.torque_max)
        f_actual = sign * screw.torque_to_force(t_actual)

        # Update state
        self.state.current = i_new
        self.state.voltage = u_applied

        return f_actual
