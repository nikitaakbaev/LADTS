"""Motor current model.

Simplified algebraic model — current is dominated by the force the motor
has to develop, with a small extra term proportional to the external
load (because the controller has to push harder to hold position):

    I = k1 * |F_motor| + k2 * |F_load| + I_idle + noise

`I_idle` represents no-load current of a real brushed DC motor (~0.2 A
for the small actuator we model). Sensor noise is *not* added here —
the raw physical current goes into the thermal model unmodified, and
sensor effects (noise/drift/lag) are applied later by `sensors.py`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrentParams:
    k1: float = 0.05    # A/N — motor force coefficient
    k2: float = 0.02    # A/N — load coefficient
    i_idle: float = 0.2  # A — no-load current
    i_max: float = 8.0   # A — physical fuse / driver limit


def compute_current(
    f_motor: float,
    f_load: float,
    params: CurrentParams | None = None,
) -> float:
    p = params or CurrentParams()
    i = p.k1 * abs(f_motor) + p.k2 * abs(f_load) + p.i_idle
    return min(i, p.i_max)
