"""Health classifier with hysteresis.

Pure rule-based for the prototype: thresholds on current and temperature.
Hysteresis prevents flicker around a threshold — once a level is
entered, it requires a margin to exit.

Severity is the worst of the per-signal verdicts (NORMAL < WARNING < ERROR).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HealthStatus = Literal["NORMAL", "WARNING", "ERROR"]
_LEVELS = {"NORMAL": 0, "WARNING": 1, "ERROR": 2}


@dataclass(frozen=True)
class HealthThresholds:
    temp_warn: float = 70.0     # °C
    temp_err: float = 90.0
    current_warn: float = 4.0   # A
    current_err: float = 6.5
    hysteresis_temp: float = 3.0
    hysteresis_current: float = 0.3


def _classify(value: float, warn: float, err: float, hysteresis: float, prev: HealthStatus) -> HealthStatus:
    """Single-signal classification with hysteresis around `prev`."""
    if prev == "ERROR":
        if value < err - hysteresis:
            return _classify(value, warn, err, hysteresis, "WARNING")
        return "ERROR"
    if prev == "WARNING":
        if value >= err:
            return "ERROR"
        if value < warn - hysteresis:
            return "NORMAL"
        return "WARNING"
    # prev == NORMAL
    if value >= err:
        return "ERROR"
    if value >= warn:
        return "WARNING"
    return "NORMAL"


class HealthClassifier:
    def __init__(self, thresholds: HealthThresholds | None = None) -> None:
        self.th = thresholds or HealthThresholds()
        self._t_state: HealthStatus = "NORMAL"
        self._i_state: HealthStatus = "NORMAL"

    def update(self, temperature: float, current: float) -> HealthStatus:
        self._t_state = _classify(
            temperature, self.th.temp_warn, self.th.temp_err,
            self.th.hysteresis_temp, self._t_state,
        )
        self._i_state = _classify(
            current, self.th.current_warn, self.th.current_err,
            self.th.hysteresis_current, self._i_state,
        )
        return max((self._t_state, self._i_state), key=lambda s: _LEVELS[s])
