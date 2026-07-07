import { syncMotorUi } from "./commands.js";

const els = {
    x:       () => document.getElementById("hud-x"),
    v:       () => document.getElementById("hud-v"),
    i:       () => document.getElementById("hud-i"),
    t:       () => document.getElementById("hud-t"),
    health:  () => document.getElementById("hud-health"),
    motor:   () => document.getElementById("hud-motor"),
    connDot:  () => document.getElementById("conn-dot"),
    connText: () => document.getElementById("conn-text"),
};

const fmt = (n, d = 3) => (Number.isFinite(n) ? n.toFixed(d) : "—");

const MOTOR_LABELS = {
    BLH5100KC: "BLH5100KC · 100 Вт",
    BLE230:    "BLE230 · 30 Вт",
};

export function renderHud(state) {
    const dot  = els.connDot();
    const text = els.connText();
    dot.classList.toggle("on",  state.connected);
    dot.classList.toggle("off", !state.connected);
    text.textContent = state.connected ? "соединено" : "нет соединения";

    const f = state.last;
    if (!f) return;
    els.x().textContent = `${fmt(f.position, 4)} м`;
    els.v().textContent = `${fmt(f.velocity, 3)} м/с`;
    els.i().textContent = `${fmt(f.current, 2)} А`;
    els.t().textContent = `${fmt(f.temperature, 1)} °C`;

    const h = els.health();
    h.textContent = HEALTH_RU[f.health] ?? f.health;
    h.className = `status ${f.health}`;

    // Motor identity — sync label and selector buttons
    if (f.motor_id) {
        els.motor().textContent = MOTOR_LABELS[f.motor_id] ?? f.motor_id;
        syncMotorUi(f.motor_id);
    }
}

const HEALTH_RU = {
    NORMAL:  "НОРМА",
    WARNING: "ВНИМАНИЕ",
    ERROR:   "ОШИБКА",
};
