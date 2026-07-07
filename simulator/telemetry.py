"""Telemetry frame: dataclass + JSON serialisation.

Single struct used by the publisher and (conceptually) by the
dashboard. Keeping the schema centralised here means the contract is
versioned in one place and any field renames break only one import.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Literal


HealthStatus = Literal["NORMAL", "WARNING", "ERROR"]


@dataclass(frozen=True)
class TelemetryFrame:
    timestamp: float
    position: float          # m
    velocity: float          # m/s
    acceleration: float      # m/s^2
    current: float           # A
    temperature: float       # °C
    force_motor: float       # N
    force_load: float        # N
    target_position: float   # m
    health: HealthStatus
    motor_id: str = "BLH5100KC"  # active motor identifier

    @staticmethod
    def now(**fields: float | str) -> "TelemetryFrame":
        return TelemetryFrame(timestamp=time.time(), **fields)  # type: ignore[arg-type]

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


@dataclass(frozen=True)
class StatusFrame:
    state: Literal["online", "offline"]
    since: float

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))
