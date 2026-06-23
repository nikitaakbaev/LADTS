#!/usr/bin/env bash
# Start Mosquitto with the project config.
# Requires mosquitto to be installed and on PATH.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec mosquitto -c "$ROOT/mqtt/mosquitto.conf" -v
