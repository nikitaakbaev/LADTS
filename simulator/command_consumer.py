"""MQTT consumer for control commands.

Subscribes to `digital_twin/actuator/command` and dispatches parsed
commands to a user-supplied callback. Lives in its own paho client so
the publisher and consumer can be restarted independently.

Command schema (any subset of fields):

    { "target_position": 0.20,
      "emergency_stop": false }

Malformed payloads are logged and dropped, never raised — a bad message
must not kill the simulator loop.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Callable

import paho.mqtt.client as mqtt

from mqtt.config import (
    BROKER_HOST,
    BROKER_TCP_PORT,
    KEEPALIVE_SEC,
    QOS_COMMAND,
    RECONNECT_MAX_SEC,
    RECONNECT_MIN_SEC,
    TOPIC_COMMAND,
)

log = logging.getLogger("ladts.command")


@dataclass(frozen=True)
class Command:
    target_position: float | None = None
    emergency_stop: bool | None = None
    paused: bool | None = None
    reset: bool | None = None
    record: bool | None = None

    @staticmethod
    def parse(raw: bytes) -> "Command | None":
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            log.warning("Bad command payload: %s", e)
            return None
        if not isinstance(data, dict):
            log.warning("Command payload is not a JSON object: %r", data)
            return None
        return Command(
            target_position=_as_float(data.get("target_position")),
            emergency_stop=_as_bool(data.get("emergency_stop")),
            paused=_as_bool(data.get("paused")),
            reset=_as_bool(data.get("reset")),
            record=_as_bool(data.get("record")),
        )


def _as_float(v: object) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _as_bool(v: object) -> bool | None:
    if isinstance(v, bool):
        return v
    return None


class CommandConsumer:
    def __init__(
        self,
        handler: Callable[[Command], None],
        host: str = BROKER_HOST,
        port: int = BROKER_TCP_PORT,
        client_id: str = "ladts-command-consumer",
    ) -> None:
        self._handler = handler
        self._host = host
        self._port = port
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, clean_session=True
        )
        self._client.reconnect_delay_set(
            min_delay=RECONNECT_MIN_SEC, max_delay=RECONNECT_MAX_SEC
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def start(self) -> None:
        log.info("Connecting command consumer to %s:%d", self._host, self._port)
        self._client.connect_async(self._host, self._port, keepalive=KEEPALIVE_SEC)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(self, c, _u, _flags, reason_code, _props=None):  # noqa: ANN001
        if reason_code == 0:
            c.subscribe(TOPIC_COMMAND, qos=QOS_COMMAND)
            log.info("Subscribed to %s", TOPIC_COMMAND)
        else:
            log.error("Command consumer connect failed: %s", reason_code)

    def _on_message(self, _c, _u, msg):  # noqa: ANN001
        cmd = Command.parse(msg.payload)
        if cmd is None:
            return
        try:
            self._handler(cmd)
        except Exception:  # noqa: BLE001 — callback errors must not kill loop
            log.exception("Command handler raised")
