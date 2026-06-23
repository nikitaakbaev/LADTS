const charts = {};

const FONT_BASE = { family: "Inter, system-ui, sans-serif" };

const baseOpts = (label, color) => ({
    type: "line",
    data: {
        labels: [],
        datasets: [{
            label, data: [], borderColor: color, backgroundColor: color + "33",
            borderWidth: 1.5, pointRadius: 0, tension: 0.25, fill: true,
        }],
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
            legend: {
                labels: {
                    color: "#d6deeb",
                    font: { ...FONT_BASE, size: 15, weight: "600" },
                    boxWidth: 16,
                    padding: 10,
                },
            },
        },
        scales: {
            x: {
                ticks: { color: "#8b98a5", maxTicksLimit: 6, font: { ...FONT_BASE, size: 12 } },
                grid: { color: "#1f2630" },
            },
            y: {
                ticks: { color: "#8b98a5", font: { ...FONT_BASE, size: 12 } },
                grid: { color: "#1f2630" },
            },
        },
    },
});

const SPECS = [
    ["chart-position",    "position",    "Position, m",     "#4cc2ff"],
    ["chart-current",     "current",     "Current, A",      "#f1c40f"],
    ["chart-temperature", "temperature", "Temperature, °C", "#e74c3c"],
    ["chart-velocity",    "velocity",    "Velocity, m/s",   "#2ecc71"],
];

export function initCharts() {
    for (const [id, key, label, color] of SPECS) {
        const ctx = document.getElementById(id);
        if (!ctx) continue;
        charts[key] = new Chart(ctx, baseOpts(label, color));
    }
}

export function renderCharts(state) {
    const h = state.history;
    if (!h.t.length) return;
    const t0 = h.t[0];
    const labels = h.t.map(t => (t - t0).toFixed(1));
    for (const [, key] of SPECS.map(s => [s[0], s[1]])) {
        const c = charts[key];
        if (!c) continue;
        c.data.labels = labels;
        c.data.datasets[0].data = h[key];
        c.update("none");
    }
}
