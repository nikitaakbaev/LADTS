"""Telemetry recorder.

Writes one JSONL file per recording session. Sessions live under

    <repo>/recordings/<YYYY-MM-DD_HH-MM-SS>/telemetry.jsonl

Each line is one TelemetryFrame as JSON (same schema as MQTT). A
sidecar `meta.json` is written at the start of the session with the
parameters used by all the models — so a recording is fully
reproducible.

The recorder buffers writes and flushes once per second to keep the
hot loop fast.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from simulator.telemetry import TelemetryFrame

log = logging.getLogger("ladts.recorder")


def _timestamp_dirname() -> str:
    return time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())


class TelemetryRecorder:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._fp = None
        self._dir: Path | None = None
        self._buffer: list[str] = []
        self._last_flush: float = 0.0

    @property
    def is_recording(self) -> bool:
        return self._fp is not None

    @property
    def session_dir(self) -> Path | None:
        return self._dir

    # --- lifecycle ----------------------------------------------------------

    def start(self, meta: dict[str, Any] | None = None) -> Path:
        if self._fp is not None:
            return self._dir  # type: ignore[return-value]
        self._dir = self._root / _timestamp_dirname()
        self._dir.mkdir(parents=True, exist_ok=True)
        if meta is not None:
            (self._dir / "meta.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        self._fp = (self._dir / "telemetry.jsonl").open("w", encoding="utf-8")
        self._last_flush = time.monotonic()
        log.info("recording started: %s", self._dir)
        return self._dir

    def stop(self) -> Path | None:
        if self._fp is None:
            return None
        self._flush(force=True)
        self._fp.close()
        finished = self._dir
        self._fp = None
        self._dir = None
        log.info("recording stopped: %s", finished)
        return finished

    # --- per-tick API -------------------------------------------------------

    def write(self, frame: TelemetryFrame) -> None:
        if self._fp is None:
            return
        self._buffer.append(json.dumps(asdict(frame), separators=(",", ":")))
        self._flush()

    def _flush(self, force: bool = False) -> None:
        if not self._buffer or self._fp is None:
            return
        now = time.monotonic()
        if not force and now - self._last_flush < 1.0:
            return
        self._fp.write("\n".join(self._buffer) + "\n")
        self._fp.flush()
        self._buffer.clear()
        self._last_flush = now
