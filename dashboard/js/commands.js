import { publishCommand } from "./mqtt_client.js";
import { ACTUATOR } from "./config.js";
import { clearHistory } from "./state.js";
import { timerReset, timerPause, timerResume } from "./timer.js";

let paused = false;
let recording = false;
let activeMotor = "BLH5100KC";

export function bindCommandUi() {
    const targetInput = document.getElementById("target-input");
    const sendBtn     = document.getElementById("send-target");
    const pauseBtn    = document.getElementById("pause");
    const resetBtn    = document.getElementById("reset");
    const recordBtn   = document.getElementById("record");
    const stopBtn     = document.getElementById("estop");

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

    // Motor selector buttons
    document.querySelectorAll(".motor-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const motorId = btn.dataset.motor;
            if (motorId === activeMotor) return;
            activeMotor = motorId;
            // Update active state on all motor buttons
            document.querySelectorAll(".motor-btn").forEach(b =>
                b.classList.toggle("active", b.dataset.motor === motorId)
            );
            publishCommand({ select_motor: motorId });
        });
    });
}

/** Sync the motor selector buttons to the motor_id reported in telemetry. */
export function syncMotorUi(motorId) {
    if (!motorId || motorId === activeMotor) return;
    activeMotor = motorId;
    document.querySelectorAll(".motor-btn").forEach(b =>
        b.classList.toggle("active", b.dataset.motor === motorId)
    );
}
