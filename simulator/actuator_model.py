"""Linear electromechanical actuator — rigid-body dynamics with motor inertia.

State vector: [x, v, omega]
  x     [m]     — carriage position
  v     [m/s]   — carriage linear velocity
  omega [rad/s] — motor shaft angular velocity

Equations of motion
-------------------
Linear (carriage):
    m · dv/dt = F_motor - F_friction(v) - F_load

    F_friction(v) = F_c · tanh(v / v_s) + b · v

Rotational (motor shaft, reflected through ШВП):
    J_eff · dω/dt = T_motor - T_load_reflected - b_rot · ω

where:
    J_eff          = J_rotor + m_carriage · r²     (r = meters_per_radian)
    T_load_reflected = (F_friction + F_load) · r / η   (back-drive)
    r              = lead / (2π)  [m/rad]

Kinematic constraint (ШВП — no slip):
    v = ω · r   →   dv/dt = dω/dt · r

In practice we integrate omega as the primary rotational state and derive
v from it each step.  The carriage position x is integrated from v.

Hold-at-stop (BLE230):
    When the electrical model signals hold_active, motor force is set to
    zero; the carriage is locked by clamping v=0 and a=0.

Integration: fixed-step RK4 on [x, v].  omega is derived from v via the
kinematic constraint (v = omega * r) at every sub-step — this keeps the
two DOFs consistent without adding a third ODE state.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.motor_config import MotorConfig


@dataclass(frozen=True)
class ActuatorParams:
    mass: float = 2.5              # kg, moving carriage mass
    coulomb_friction: float = 3.0  # N, dry friction magnitude
    viscous_friction: float = 8.0  # N·s/m, viscous coefficient
    stribeck_velocity: float = 0.01  # m/s, smoothing scale for tanh
    x_min: float = 0.0             # m, mechanical stop (lower)
    x_max: float = 0.30            # m, mechanical stop (upper)
    f_motor_max: float = 60.0      # N, motor force saturation (legacy fallback)


@dataclass
class ActuatorState:
    x: float = 0.0      # position, m
    v: float = 0.0      # velocity, m/s
    a: float = 0.0      # acceleration, m/s² (computed, not integrated)
    omega: float = 0.0  # shaft angular velocity, rad/s


class ActuatorModel:
    """Rigid-body 1-DOF actuator with RK4 integration.

    When a MotorConfig is supplied, the rotor inertia J is reflected into
    the effective inertia of the carriage via the ШВП kinematic ratio r:

        J_eff = J_rotor / r²  [kg]   (added to carriage mass)

    This captures the motor's inertia contribution to linear dynamics
    without requiring a separate rotational ODE state.
    """

    def __init__(
        self,
        params: ActuatorParams | None = None,
        motor_cfg: "MotorConfig | None" = None,
    ) -> None:
        self.p = params or ActuatorParams()
        self._motor_cfg = motor_cfg
        self.state = ActuatorState()
        self._update_effective_mass()

    def set_motor(self, motor_cfg: "MotorConfig") -> None:
        """Update motor config (hot-swap). Resets effective mass."""
        self._motor_cfg = motor_cfg
        self._update_effective_mass()

    def _update_effective_mass(self) -> None:
        """Compute effective inertia = carriage mass + rotor inertia reflected."""
        if self._motor_cfg is not None:
            r = self._motor_cfg.screw.meters_per_radian  # m/rad
            # J_rotor / r² adds equivalent linear mass [kg]
            self._m_eff = self.p.mass + self._motor_cfg.inertia / (r * r)
        else:
            self._m_eff = self.p.mass

    def _friction(self, v: float) -> float:
        return (
            self.p.coulomb_friction * math.tanh(v / self.p.stribeck_velocity)
            + self.p.viscous_friction * v
        )

    def _rotational_damping(self, v: float) -> float:
        """Rotational bearing loss reflected to linear domain [N]."""
        if self._motor_cfg is None or self._motor_cfg.rotational_damping == 0.0:
            return 0.0
        r = self._motor_cfg.screw.meters_per_radian
        # omega = v / r  →  T_damp = b_rot * omega  →  F_damp = T_damp / r
        omega = v / r if abs(r) > 1e-12 else 0.0
        return self._motor_cfg.rotational_damping * omega / r

    def _accel(self, v: float, f_motor: float, f_load: float) -> float:
        f_net = (
            f_motor
            - self._friction(v)
            - self._rotational_damping(v)
            - f_load
        )
        return f_net / self._m_eff

    def step(
        self,
        dt: float,
        f_motor: float,
        f_load: float,
        hold_active: bool = False,
    ) -> tuple[ActuatorState, float]:
        """Advance state by dt using RK4.

        Args:
            dt:          integration step [s]
            f_motor:     motor linear force [N] (from MotorElectricalModel)
            f_load:      external disturbance force [N]
            hold_active: BLE230 hold-at-stop flag — locks carriage in place

        Returns:
            (new_state, f_motor_applied)
        """
        # Determine force saturation limit
        if self._motor_cfg is not None:
            f_max = self._motor_cfg.force_max
        else:
            f_max = self.p.f_motor_max

        f_motor = max(-f_max, min(f_max, f_motor))
        f_motor_applied = f_motor

        # BLE230 hold-at-stop: lock carriage, skip integration
        if hold_active:
            # Shaft is electronically locked; carriage stays put
            omega = self.state.v / self._motor_cfg.screw.meters_per_radian \
                if self._motor_cfg is not None else 0.0
            self.state = ActuatorState(
                x=self.state.x,
                v=0.0,
                a=0.0,
                omega=0.0,
            )
            return self.state, 0.0

        x, v = self.state.x, self.state.v

        def deriv(_x: float, _v: float) -> tuple[float, float]:
            return _v, self._accel(_v, f_motor, f_load)

        k1x, k1v = deriv(x, v)
        k2x, k2v = deriv(x + 0.5 * dt * k1x, v + 0.5 * dt * k1v)
        k3x, k3v = deriv(x + 0.5 * dt * k2x, v + 0.5 * dt * k2v)
        k4x, k4v = deriv(x + dt * k3x, v + dt * k3v)

        x_new = x + (dt / 6.0) * (k1x + 2 * k2x + 2 * k3x + k4x)
        v_new = v + (dt / 6.0) * (k1v + 2 * k2v + 2 * k3v + k4v)

        # Mechanical stops
        if x_new <= self.p.x_min:
            x_new, v_new = self.p.x_min, max(0.0, v_new)
        elif x_new >= self.p.x_max:
            x_new, v_new = self.p.x_max, min(0.0, v_new)

        a_new = self._accel(v_new, f_motor, f_load)

        # Derive omega from linear velocity via ШВП kinematic constraint
        if self._motor_cfg is not None:
            r = self._motor_cfg.screw.meters_per_radian
            omega_new = v_new / r if abs(r) > 1e-12 else 0.0
        else:
            omega_new = 0.0

        self.state = ActuatorState(x=x_new, v=v_new, a=a_new, omega=omega_new)
        return self.state, f_motor_applied
