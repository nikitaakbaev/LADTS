"""Centralised MQTT configuration.

Single source of truth for the broker address, ports, topic names and
QoS levels used by both the simulator and the dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass


# --- Broker -----------------------------------------------------------------

BROKER_HOST: str = "localhost"
BROKER_TCP_PORT: int = 1883
BROKER_WS_PORT: int = 9001
KEEPALIVE_SEC: int = 30
RECONNECT_MIN_SEC: int = 1
RECONNECT_MAX_SEC: int = 30


# --- Topics -----------------------------------------------------------------

TOPIC_TELEMETRY: str = "digital_twin/actuator/telemetry"
TOPIC_COMMAND: str = "digital_twin/actuator/command"
TOPIC_STATUS: str = "digital_twin/actuator/status"


# --- QoS --------------------------------------------------------------------

QOS_TELEMETRY: int = 0   # high frequency, drop-tolerant
QOS_COMMAND: int = 1     # at-least-once, must arrive
QOS_STATUS: int = 1


# --- Identity ---------------------------------------------------------------

@dataclass(frozen=True)
class ClientIdentity:
    client_id: str
    username: str | None = None
    password: str | None = None


PUBLISHER_IDENTITY = ClientIdentity(client_id="ladts-simulator")
SUBSCRIBER_IDENTITY = ClientIdentity(client_id="ladts-test-subscriber")
