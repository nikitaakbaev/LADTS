"""Motor configuration catalogue.

Defines BLDC motor parameters for the digital twin simulator.
Each MotorConfig fully describes one motor's electromechanical properties
plus the ball-screw drive (ШВП) that converts rotation to linear motion.

Two motors are currently supported:
  * BLH5100KC — Oriental Motor BLH Series, 100 W, 24 V DC
  * BLE230     — Oriental Motor BLE2 Series, 30 W, 24 V DC (AC-side not modelled)

Ball-screw transmission (shared default, can be overridden per motor):
  lead   = 0.005 m/rev  (5 mm pitch, typical for compact actuators)
  η      = 0.90          (90 % mechanical efficiency)

Linear ↔ rotational conversions:
  ω  [rad/s]  = v [m/s] * 2π / lead
  T  [N·m]    = F [N]   * lead / (2π * η)   (torque needed at motor shaft)
  F  [N]      = T [N·m] * 2π * η / lead     (force produced by motor)

Electrical phase ODE (per-phase, simplified BLDC → equivalent DC bus):
  L · dI/dt = U - R·I - Ke·ω
  τ_e = L / R  (electrical time constant)

Mechanical rotational ODE (motor shaft, reflected inertia of screw neglected):
  J · dω/dt = Kt·I - T_load - b_rot·ω
where b_rot is a small rotational viscous damping (bearing losses).

The ActuatorModel handles linear mechanics (carriage mass, linear friction).
The MotorElectricalModel handles the phase ODE and maps current → motor force.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal


MotorID = Literal["BLH5100KC", "BLE230"]


@dataclass(frozen=True)
class BallScrewParams:
    """Ball-screw transmission parameters."""
    lead: float = 0.005   # m/rev — screw pitch (linear advance per revolution)
    efficiency: float = 0.90  # η — mechanical efficiency (0–1)

    @property
    def meters_per_radian(self) -> float:
        """Linear displacement per radian of shaft rotation."""
        return self.lead / (2.0 * math.pi)

    def velocity_to_omega(self, v: float) -> float:
        """Linear velocity [m/s] → shaft angular velocity [rad/s]."""
        return v / self.meters_per_radian

    def force_to_torque(self, f: float) -> float:
        """Linear force [N] → required motor torque [N·m] (accounting for η)."""
        return f * self.meters_per_radian / self.efficiency

    def torque_to_force(self, torque: float) -> float:
        """Motor torque [N·m] → output linear force [N] (accounting for η)."""
        return torque * self.efficiency / self.meters_per_radian


@dataclass(frozen=True)
class MotorConfig:
    """Full electromechanical description of one BLDC motor.

    Parameters follow IEC/manufacturer datasheets. All SI units.
    """
    # --- identity -----------------------------------------------------------
    motor_id: MotorID
    label: str          # human-readable name for UI / telemetry

    # --- electrical ---------------------------------------------------------
    voltage_nominal: float  # V  — rated supply voltage (bus voltage)
    resistance: float       # Ω  — phase resistance R
    inductance: float       # H  — phase inductance L  (stored as H, entered as mH)
    ke: float               # V/(rad/s) — back-EMF constant
    kt: float               # N·m/A    — torque constant

    # --- mechanical (rotational) --------------------------------------------
    inertia: float          # kg·m²  — rotor moment of inertia J
    pole_pairs: int         # p      — number of pole pairs
    speed_nominal: float    # rad/s  — nominal no-load shaft speed
    torque_nominal: float   # N·m   — rated output torque
    torque_max: float       # N·m   — peak / stall torque  (≈ 2–3 × nominal)
    current_max: float      # A     — peak phase current (driver limit)
    rotational_damping: float = 0.0  # N·m·s/rad — bearing viscous loss

    # --- transmission -------------------------------------------------------
    screw: BallScrewParams = field(default_factory=BallScrewParams)

    # --- BLE230-specific features (ignored for BLH5100KC) -------------------
    torque_limit_enabled: bool = False
    torque_limit_fraction: float = 1.0   # 0–1, fraction of torque_max
    hold_at_stop: bool = False           # active shaft lock when v ≈ 0
    preset_speeds: tuple[float, ...] = ()  # rad/s — up to 16 preset speeds

    # --- derived properties -------------------------------------------------
    @property
    def electrical_time_constant(self) -> float:
        """τ_e = L / R  [s]."""
        return self.inductance / self.resistance

    @property
    def force_max(self) -> float:
        """Peak linear force at motor shaft output [N]."""
        return self.screw.torque_to_force(self.torque_max)

    @property
    def force_nominal(self) -> float:
        """Nominal linear force [N]."""
        return self.screw.torque_to_force(self.torque_nominal)

    @property
    def thermal_resistance_approx(self) -> float:
        """Approximate winding thermal resistance from R and rated conditions.
        Used to seed ThermalModel.alpha:  alpha = R / C_th  where C_th is
        estimated from the motor size class.  Returns R as a proxy — the
        ThermalModel calibrates alpha separately."""
        return self.resistance


# ---------------------------------------------------------------------------
# Motor catalogue
# ---------------------------------------------------------------------------

# Ball-screw with 20 mm lead — realistic for compact actuators driven by these
# motors.  At lead=5 mm the reflected rotor inertia would exceed 70 kg (correct
# physics but impractical for a 100 W motor); 20 mm gives ~4.4 kg, which is a
# sensible ratio to the 2.5 kg carriage mass.
_SCREW_20MM = BallScrewParams(lead=0.020, efficiency=0.90)


#: Oriental Motor BLH Series — 100 W, 24 V DC, analogue speed control
BLH5100KC = MotorConfig(
    motor_id="BLH5100KC",
    label="Oriental Motor BLH5100KC (100 W)",
    # electrical
    voltage_nominal=24.0,
    resistance=0.450,           # Ω
    inductance=0.800e-3,        # H  (0.800 mH)
    ke=0.076,                   # V/(rad/s)
    kt=0.076,                   # N·m/A
    # mechanical
    inertia=45.0e-6,            # kg·m²
    pole_pairs=4,
    speed_nominal=3000 * 2 * math.pi / 60,   # 314.16 rad/s
    torque_nominal=0.320,        # N·m
    torque_max=0.960,            # N·m  (3 × nominal — typical BLDC peak)
    current_max=12.0,            # A    (estimated: Kt·I_peak ≈ torque_max)
    rotational_damping=2.0e-5,   # N·m·s/rad (small bearing loss)
    screw=_SCREW_20MM,
    # BLE-specific features: disabled
    torque_limit_enabled=False,
    hold_at_stop=False,
    preset_speeds=(),
)

#: Oriental Motor BLE2 Series — 30 W, AC-driven (modelled at motor-shaft level)
#: AC rectification not simulated — electromechanics use datasheet parameters.
BLE230 = MotorConfig(
    motor_id="BLE230",
    label="Oriental Motor BLE230 (30 W)",
    # electrical
    voltage_nominal=24.0,       # effective DC-bus equivalent for phase model
    resistance=1.100,           # Ω
    inductance=1.200e-3,        # H  (1.200 mH)
    ke=0.076,                   # V/(rad/s)
    kt=0.076,                   # N·m/A
    # mechanical
    inertia=12.0e-6,            # kg·m²  — lighter rotor → faster response
    pole_pairs=4,
    speed_nominal=3000 * 2 * math.pi / 60,   # 314.16 rad/s
    torque_nominal=0.095,        # N·m
    torque_max=0.285,            # N·m  (3 × nominal)
    current_max=4.0,             # A
    rotational_damping=8.0e-6,   # N·m·s/rad
    screw=_SCREW_20MM,
    # BLE2-specific features
    torque_limit_enabled=True,
    torque_limit_fraction=0.80,  # default 80 % of torque_max
    hold_at_stop=True,
    preset_speeds=(
        # 8 default preset speeds evenly spaced 400–3200 rpm (rad/s)
        400  * 2 * math.pi / 60,
        800  * 2 * math.pi / 60,
        1200 * 2 * math.pi / 60,
        1600 * 2 * math.pi / 60,
        2000 * 2 * math.pi / 60,
        2400 * 2 * math.pi / 60,
        2800 * 2 * math.pi / 60,
        3200 * 2 * math.pi / 60,
    ),
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

MOTORS: dict[MotorID, MotorConfig] = {
    "BLH5100KC": BLH5100KC,
    "BLE230": BLE230,
}

DEFAULT_MOTOR: MotorID = "BLH5100KC"


def get_motor(motor_id: MotorID) -> MotorConfig:
    """Return a MotorConfig by ID. Raises KeyError for unknown IDs."""
    if motor_id not in MOTORS:
        raise KeyError(f"Unknown motor ID {motor_id!r}. Available: {list(MOTORS)}")
    return MOTORS[motor_id]
