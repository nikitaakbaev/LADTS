import { publishCommand } from "./mqtt_client.js";
import { ACTUATOR } from "./config.js";

export function bindCommandUi() {
    const targetInput = document.getElementById("target-input");
    const sendBtn = document.getElementById("send-target");
    const stopBtn = document.getElementById("estop");

    sendBtn.addEventListener("click", () => {
        const raw = parseFloat(targetInput.value);
        if (!Number.isFinite(raw)) return;
        const clamped = Math.max(ACTUATOR.xMin, Math.min(ACTUATOR.xMax, raw));
        publishCommand({ target_position: clamped, emergency_stop: false });
    });

    stopBtn.addEventListener("click", () => {
        publishCommand({ emergency_stop: true });
    });
}
