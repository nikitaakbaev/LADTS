"""CLI subscriber — pretty-print every message on the actuator topics.

Usage:
    python -m mqtt.test_subscriber                # all topics
    python -m mqtt.test_subscriber telemetry      # one topic only
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time

import paho.mqtt.client as mqtt

from mqtt.config import (
    BROKER_HOST,
    BROKER_TCP_PORT,
    KEEPALIVE_SEC,
    SUBSCRIBER_IDENTITY,
    TOPIC_COMMAND,
    TOPIC_STATUS,
    TOPIC_TELEMETRY,
)

TOPIC_MAP = {
    "telemetry": TOPIC_TELEMETRY,
    "command": TOPIC_COMMAND,
    "status": TOPIC_STATUS,
    "all": "digital_twin/actuator/#",
}


def _on_connect(client, _u, _flags, reason_code, _props=None):  # noqa: ANN001
    if reason_code != 0:
        print(f"connect failed: {reason_code}", file=sys.stderr)
        return
    topic = client._user_data_topic  # type: ignore[attr-defined]
    client.subscribe(topic, qos=1)
    print(f"subscribed to {topic}")


def _on_message(_c, _u, msg):  # noqa: ANN001
    ts = time.strftime("%H:%M:%S")
    try:
        body = json.loads(msg.payload.decode("utf-8"))
        pretty = json.dumps(body, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        pretty = repr(msg.payload)
    print(f"[{ts}] {msg.topic} {pretty}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LADTS test subscriber")
    parser.add_argument("topic", nargs="?", default="all", choices=list(TOPIC_MAP))
    parser.add_argument("--host", default=BROKER_HOST)
    parser.add_argument("--port", type=int, default=BROKER_TCP_PORT)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=SUBSCRIBER_IDENTITY.client_id
    )
    client._user_data_topic = TOPIC_MAP[args.topic]  # type: ignore[attr-defined]
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.connect(args.host, args.port, keepalive=KEEPALIVE_SEC)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\ninterrupted")


if __name__ == "__main__":
    main()
