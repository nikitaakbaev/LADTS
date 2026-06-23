"""High-resolution timer helper.

On Windows the default system timer tick is 15.6 ms, which means
``asyncio.sleep(0.005)`` actually sleeps 16+ ms — limiting our 200 Hz
integrator to ~64 Hz in the worst case. The Win32 ``timeBeginPeriod(1)``
call drops the tick to 1 ms for the whole process. ``timeEndPeriod(1)``
restores the previous resolution on shutdown.

This is a no-op on non-Windows platforms — POSIX ``asyncio.sleep`` is
already accurate to sub-millisecond.
"""
from __future__ import annotations

import logging
import sys

log = logging.getLogger("ladts.clock")


class HighResTimer:
    """Context-manager-friendly wrapper around timeBeginPeriod / timeEndPeriod."""

    def __init__(self, period_ms: int = 1) -> None:
        self._period_ms = period_ms
        self._winmm = None

    def __enter__(self) -> "HighResTimer":
        if sys.platform == "win32":
            try:
                import ctypes
                self._winmm = ctypes.WinDLL("winmm")
                rc = self._winmm.timeBeginPeriod(self._period_ms)
                if rc != 0:
                    log.warning("timeBeginPeriod(%d) returned %d", self._period_ms, rc)
                else:
                    log.info("Windows timer resolution set to %d ms", self._period_ms)
            except Exception:  # noqa: BLE001 — non-fatal; we'll just run slower
                log.exception("Failed to raise Windows timer resolution")
                self._winmm = None
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._winmm is not None:
            try:
                self._winmm.timeEndPeriod(self._period_ms)
            except Exception:  # noqa: BLE001
                log.exception("Failed to release Windows timer resolution")
