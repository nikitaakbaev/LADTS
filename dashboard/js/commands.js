import { publishCommand } from "./mqtt_client.js";
import { ACTUATOR } from "./config.js";
import { clearHistory } from "./state.js";
import { timerReset, timerPause, timerResume } from "./timer.js";

let paused = false;
let recording = false;

export function bindCommandUi() {
    const targetInput = document.getElementById("target-input");
    const sendBtn = document.getElementById("send-target");
    const pauseBtn = document.getElementById("pause");
    const resetBtn = document.getElementById("reset");
    const recordBtn = document.getElementById("record");
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
        if (paused) timerPause(); else timerResume();
    });

    resetBtn.addEventListener("click", () => {
        // Preserve pause state across reset. The simulator does the same.
        publishCommand({ reset: true });
        clearHistory();
        timerReset();
    });

    recordBtn.addEventListener("click", () => {
        recording = !recording;
        publishCommand({ record: recording });
        recordBtn.textContent = recording ? "Остановить запись" : "Запись";
        recordBtn.classList.toggle("active", recording);
    });

    stopBtn.addEventListener("click", () => {
        publishCommand({ emergency_stop: true });
    });
}
