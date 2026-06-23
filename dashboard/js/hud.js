const els = {
    x: () => document.getElementById("hud-x"),
    v: () => document.getElementById("hud-v"),
    i: () => document.getElementById("hud-i"),
    t: () => document.getElementById("hud-t"),
    health: () => document.getElementById("hud-health"),
    connDot: () => document.getElementById("conn-dot"),
    connText: () => document.getElementById("conn-text"),
};

const fmt = (n, d = 3) => (Number.isFinite(n) ? n.toFixed(d) : "—");

export function renderHud(state) {
    const dot = els.connDot();
    const text = els.connText();
    dot.classList.toggle("on", state.connected);
    dot.classList.toggle("off", !state.connected);
    text.textContent = state.connected ? "connected" : "disconnected";

    const f = state.last;
    if (!f) return;
    els.x().textContent = `${fmt(f.position, 4)} m`;
    els.v().textContent = `${fmt(f.velocity, 3)} m/s`;
    els.i().textContent = `${fmt(f.current, 2)} A`;
    els.t().textContent = `${fmt(f.temperature, 1)} °C`;

    const h = els.health();
    h.textContent = f.health;
    h.className = `status ${f.health}`;
}
