// Mirror of mqtt/config.py — keep in sync if the Python side changes.

export const BROKER_URL = `ws://${location.hostname || "localhost"}:9001`;

export const TOPIC_TELEMETRY = "digital_twin/actuator/telemetry";
export const TOPIC_COMMAND   = "digital_twin/actuator/command";
export const TOPIC_STATUS    = "digital_twin/actuator/status";

export const ACTUATOR = {
    xMin: 0.0,
    xMax: 0.30,   // m, matches ActuatorParams.x_max
};

export const CHART_WINDOW = 240;   // samples kept on charts (~8 s at 30 Hz)
