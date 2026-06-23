// Test-duration timer.
// Counts wall-clock time from when the user clicked "Сброс" or when the
// page first received telemetry, whichever happened later. Pauses while
// the simulation is paused.

let startedAt = null;     // performance.now() at start
let accumulated = 0;       // ms accumulated before current run
let running = false;
let element = null;
let pauseStart = null;

function fmt(ms) {
    const total = Math.floor(ms / 100) / 10;          // tenths of a second
    const minutes = Math.floor(total / 60);
    const seconds = (total - minutes * 60).toFixed(1).padStart(4, "0");
    return `${String(minutes).padStart(2, "0")}:${seconds}`;
}

function tick() {
    if (!element) return;
    let ms = accumulated;
    if (running && startedAt !== null) {
        ms += performance.now() - startedAt;
    }
    element.textContent = fmt(ms);
    requestAnimationFrame(tick);
}

export function initTimer() {
    element = document.getElementById("timer");
    requestAnimationFrame(tick);
}

export function timerStart() {
    if (running) return;
    running = true;
    startedAt = performance.now();
}

export function timerPause() {
    if (!running) return;
    running = false;
    if (startedAt !== null) {
        accumulated += performance.now() - startedAt;
        startedAt = null;
    }
}

export function timerResume() {
    if (running) return;
    running = true;
    startedAt = performance.now();
}

export function timerReset() {
    accumulated = 0;
    startedAt = running ? performance.now() : null;
}
