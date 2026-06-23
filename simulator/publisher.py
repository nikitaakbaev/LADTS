"""MQTT publisher for telemetry and status frames.

Thin wrapper over paho-mqtt with:

* Automatic reconnect with exponential backoff (handled by the
  underlying client, configured here).
* Last Will & Testament so subscribers see `offline` if the simulator
  crashes.
* Structured logging.
* `publish_telemetry` / `publish_status` helpers that hide the topic
  layout from callers.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

import paho.mqtt.client as mqtt

from mqtt.config import (
    BROKER_HOST,
    BROKER_TCP_PORT,
    KEEPALIVE_SEC,
    PUBLISHER_IDENTITY,
    QOS_STATUS,
    QOS_TELEMETRY,
    RECONNECT_MAX_SEC,
    RECONNECT_MIN_SEC,
    TOPIC_STATUS,
    TOPIC_TELEMETRY,
)
from simulator.telemetry import StatusFrame, TelemetryFrame

log = logging.getLogger("ladts.publisher")


class TelemetryPublisher:
    """Owns a single paho client used for publishing telemetry."""

    def __init__(
        self,
        host: str = BROKER_HOST,
        port: int = BROKER_TCP_PORT,
        on_connect: Callable[[], None] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._on_connect_cb = on_connect

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=PUBLISHER_IDENTITY.client_id,
            clean_session=True,
        )
        if PUBLISHER_IDENTITY.username:
            self._client.username_pw_set(
                PUBLISHER_IDENTITY.username, PUBLISHER_IDENTITY.password
            )

        offline = StatusFrame(state="offline", since=time.time()).to_json()
        self._client.will_set(TOPIC_STATUS, offline, qos=QOS_STATUS, retain=True)

        self._client.reconnect_delay_set(
            min_delay=RECONNECT_MIN_SEC, max_delay=RECONNECT_MAX_SEC
        )
        self._client.on_connect = self._handle_connect
        self._client.on_disconnect = self._handle_disconnect

    # --- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        log.info("Connecting to MQTT broker %s:%d", self._host, self._port)
        self._client.connect_async(self._host, self._port, keepalive=KEEPALIVE_SEC)
        self._client.loop_start()

    def stop(self) -> None:
        offline = StatusFrame(state="offline", since=time.time()).to_json()
        try:
            self._client.publish(TOPIC_STATUS, offline, qos=QOS_STATUS, retain=True)
        except Exception:  # noqa: BLE001 — best-effort on shutdown
            log.exception("Failed to publish offline status")
        self._client.loop_stop()
        self._client.disconnect()
        log.info("MQTT publisher stopped")

    # --- public API ---------------------------------------------------------

    def publish_telemetry(self, frame: TelemetryFrame) -> None:
        self._client.publish(TOPIC_TELEMETRY, frame.to_json(), qos=QOS_TELEMETRY)

    def publish_status_online(self) -> None:
        payload = StatusFrame(state="online", since=time.time()).to_json()
        self._client.publish(TOPIC_STATUS, payload, qos=QOS_STATUS, retain=True)

    # --- callbacks ----------------------------------------------------------

    def _handle_connect(self, _c, _u, _flags, reason_code, _props=None):  # noqa: ANN001
        if reason_code == 0:
            log.info("MQTT connected")
            self.publish_status_online()
            if self._on_connect_cb:
                self._on_connect_cb()
        else:
            log.error("MQTT connect failed: %s", reason_code)

    def _handle_disconnect(self, _c, _u, _flags, reason_code, _props=None):  # noqa: ANN001
        if reason_code == 0:
            log.info("MQTT disconnected cleanly")
        else:
            log.warning("MQTT disconnected unexpectedly (%s) — reconnecting", reason_code)
