import { BROKER_URL, TOPIC_TELEMETRY, TOPIC_COMMAND, TOPIC_STATUS } from "./config.js";
import { pushTelemetry, setConnection } from "./state.js";

let client = null;

export function connect() {
    client = mqtt.connect(BROKER_URL, {
        clientId: "ladts-dashboard-" + Math.random().toString(16).slice(2, 8),
        reconnectPeriod: 2000,
        connectTimeout: 5000,
        clean: true,
    });

    client.on("connect", () => {
        setConnection(true);
        client.subscribe([TOPIC_TELEMETRY, TOPIC_STATUS], { qos: 0 }, (err) => {
            if (err) console.error("[mqtt] subscribe failed", err);
        });
    });

    client.on("reconnect", () => console.info("[mqtt] reconnecting…"));
    client.on("close",    () => setConnection(false));
    client.on("error",    (e) => console.error("[mqtt] error", e));

    client.on("message", (topic, payload) => {
        let body;
        try {
            body = JSON.parse(payload.toString());
        } catch (e) {
            console.warn("[mqtt] bad JSON on", topic, e);
            return;
        }
        if (topic === TOPIC_TELEMETRY) pushTelemetry(body);
    });

    return client;
}

export function publishCommand(cmd) {
    if (!client || !client.connected) {
        console.warn("[mqtt] not connected, command dropped", cmd);
        return false;
    }
    client.publish(TOPIC_COMMAND, JSON.stringify(cmd), { qos: 1 });
    return true;
}
