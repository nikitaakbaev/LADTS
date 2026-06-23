"""Linear electromechanical actuator — rigid-body dynamics.

State vector: [x, v]  (position [m], velocity [m/s])
Equation of motion:

    m * dv/dt = F_motor - F_friction(v) - F_load
    dx/dt = v

Friction is split into Coulomb (dry) and viscous components:

    F_friction(v) = F_c * tanh(v / v_s) + b * v

`tanh` is used instead of `sign` to keep the ODE smooth and avoid
chattering of fixed-step integrators near v = 0.

Integration is fixed-step RK4. With dt = 5 ms it is stable for the
parameter range used in this project (settling time ~0.5 s, no stiff
modes).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ActuatorParams:
    mass: float = 2.5            # kg, moving carriage mass
    coulomb_friction: float = 3.0  # N, dry friction magnitude
    viscous_friction: float = 8.0  # N*s/m, viscous coefficient
    stribeck_velocity: float = 0.01  # m/s, smoothing scale for tanh
    x_min: float = 0.0           # m, mechanical stop (lower)
    x_max: float = 0.30          # m, mechanical stop (upper)
    f_motor_max: float = 60.0    # N, motor force saturation


@dataclass
class ActuatorState:
    x: float = 0.0   # position, m
    v: float = 0.0   # velocity, m/s
    a: float = 0.0   # acceleration, m/s^2 (computed, not integrated)


class ActuatorModel:
    """Rigid-body 1-DOF actuator with RK4 integration."""

    def __init__(self, params: ActuatorParams | None = None) -> None:
        self.p = params or ActuatorParams()
        self.state = ActuatorState()

    def _friction(self, v: float) -> float:
        import math
        return (
            self.p.coulomb_friction * math.tanh(v / self.p.stribeck_velocity)
            + self.p.viscous_friction * v
        )

    def _accel(self, v: float, f_motor: float, f_load: float) -> float:
        f_net = f_motor - self._friction(v) - f_load
        return f_net / self.p.mass

    def step(
        self,
        dt: float,
        f_motor: float,
        f_load: float,
    ) -> tuple[ActuatorState, float]:
        """Advance state by dt using RK4.

        Returns (new_state, f_motor_applied) — the second element is the
        motor force after saturation, which is what actually acted on
        the system this tick.
        """
        f_motor = max(-self.p.f_motor_max, min(self.p.f_motor_max, f_motor))
        f_motor_applied = f_motor
        x, v = self.state.x, self.state.v

        def deriv(_x: float, _v: float) -> tuple[float, float]:
            return _v, self._accel(_v, f_motor, f_load)

        k1x, k1v = deriv(x, v)
        k2x, k2v = deriv(x + 0.5 * dt * k1x, v + 0.5 * dt * k1v)
        k3x, k3v = deriv(x + 0.5 * dt * k2x, v + 0.5 * dt * k2v)
        k4x, k4v = deriv(x + dt * k3x, v + dt * k3v)

        x_new = x + (dt / 6.0) * (k1x + 2 * k2x + 2 * k3x + k4x)
        v_new = v + (dt / 6.0) * (k1v + 2 * k2v + 2 * k3v + k4v)

        # Mechanical stops: clamp position, zero velocity on hit.
        if x_new <= self.p.x_min:
            x_new, v_new = self.p.x_min, max(0.0, v_new)
        elif x_new >= self.p.x_max:
            x_new, v_new = self.p.x_max, min(0.0, v_new)

        a_new = self._accel(v_new, f_motor, f_load)
        self.state = ActuatorState(x=x_new, v=v_new, a=a_new)
        return self.state, f_motor_applied
