import { publishCommand } from "./mqtt_client.js";
import { ACTUATOR } from "./config.js";
import { clearHistory } from "./state.js";

let paused = false;

export function bindCommandUi() {
    const targetInput = document.getElementById("target-input");
    const sendBtn = document.getElementById("send-target");
    const pauseBtn = document.getElementById("pause");
    const resetBtn = document.getElementById("reset");
    const stopBtn = document.getElementById("estop");

    sendBtn.addEventListener("click", () => {
        const raw = parseFloat(targetInput.value);
        if (!Number.isFinite(raw)) return;
        const clamped = Math.max(ACTUATOR.xMin, Math.min(ACTUATOR.xMax, raw));
        publishCommand({ target_position: clamped, emergency_stop: false });
    });

    pauseBtn.addEventListener("click", () => {
        paused = !paused;
        publishCommand({ paused });
        pauseBtn.textContent = paused ? "Продолжить" : "Пауза";
        pauseBtn.classList.toggle("active", paused);
    });

    resetBtn.addEventListener("click", () => {
        publishCommand({ reset: true });
        clearHistory();
        // If we were paused, also resume so the user immediately sees the reset state.
        if (paused) {
            paused = false;
            publishCommand({ paused: false });
            pauseBtn.textContent = "Пауза";
            pauseBtn.classList.remove("active");
        }
    });

    stopBtn.addEventListener("click", () => {
        publishCommand({ emergency_stop: true });
    });
}
