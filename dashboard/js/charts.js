const charts = {};
let modalChart = null;
let modalKey = null;

if (typeof Chart !== "undefined") {
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
    Chart.defaults.font.size = 14;
    Chart.defaults.color = "#d6deeb";
}

// Fixed Y ranges keep sensor noise from dominating the plot when the
// system is at rest. Limits chosen to cover the full physical range.
const SPECS = [
    { id: "chart-position",    key: "position",    label: "Позиция, м",       color: "#4cc2ff", yMin: 0,    yMax: 0.32 },
    { id: "chart-current",     key: "current",     label: "Ток, А",           color: "#f1c40f", yMin: 0,    yMax: 8.5  },
    { id: "chart-temperature", key: "temperature", label: "Температура, °C",  color: "#e74c3c", yMin: 20,   yMax: 110  },
    { id: "chart-velocity",    key: "velocity",    label: "Скорость, м/с",    color: "#2ecc71", yMin: -1.5, yMax: 1.5  },
];

const baseOpts = (label, color, yMin, yMax) => ({
    type: "line",
    data: {
        labels: [],
        datasets: [{
            label, data: [], borderColor: color, backgroundColor: color + "33",
            borderWidth: 2, pointRadius: 0, tension: 0.25, fill: true,
        }],
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        resizeDelay: 100,
        plugins: {
            legend: {
                labels: {
                    color: "#d6deeb",
                    font: { size: 17, weight: "600" },
                    boxWidth: 18,
                    padding: 12,
                },
            },
            tooltip: {
                titleFont: { size: 14 },
                bodyFont: { size: 14 },
            },
        },
        scales: {
            x: {
                ticks: { color: "#a5b1c2", maxTicksLimit: 6, font: { size: 13 } },
                grid: { color: "#1f2630" },
            },
            y: {
                min: yMin, max: yMax, beginAtZero: false,
                ticks: { color: "#a5b1c2", font: { size: 13 } },
                grid: { color: "#1f2630" },
            },
        },
    },
});

export function initCharts() {
    for (const s of SPECS) {
        const ctx = document.getElementById(s.id);
        if (!ctx) continue;
        charts[s.key] = new Chart(ctx, baseOpts(s.label, s.color, s.yMin, s.yMax));
    }
    bindChartZoom();
}

export function renderCharts(state) {
    const h = state.history;
    if (!h.t.length) return;
    const t0 = h.t[0];
    const labels = h.t.map(t => (t - t0).toFixed(1));
    for (const s of SPECS) {
        const c = charts[s.key];
        if (!c) continue;
        c.data.labels = labels;
        c.data.datasets[0].data = h[s.key];
        c.update("none");
    }
    if (modalChart && modalKey) {
        const s = SPECS.find(x => x.key === modalKey);
        modalChart.data.labels = labels;
        modalChart.data.datasets[0].data = h[s.key];
        modalChart.update("none");
    }
}

// --- Click-to-zoom modal --------------------------------------------------

function bindChartZoom() {
    const modal = document.getElementById("chart-modal");
    if (!modal) return;
    document.querySelectorAll(".chart-tile").forEach(tile => {
        tile.addEventListener("click", () => openModal(tile.dataset.chart));
    });
    modal.querySelectorAll("[data-close]").forEach(el => {
        el.addEventListener("click", closeModal);
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeModal();
    });
}

function openModal(key) {
    const spec = SPECS.find(s => s.key === key);
    if (!spec) return;
    modalKey = key;
    const modal = document.getElementById("chart-modal");
    const canvas = document.getElementById("chart-modal-canvas");
    modal.classList.remove("hidden");

    const opts = baseOpts(spec.label, spec.color, spec.yMin, spec.yMax);
    // Bigger fonts for the maximised view.
    opts.options.plugins.legend.labels.font = { size: 22, weight: "700" };
    opts.options.scales.x.ticks.font = { size: 15 };
    opts.options.scales.y.ticks.font = { size: 15 };

    if (modalChart) modalChart.destroy();
    modalChart = new Chart(canvas, opts);

    // Seed with current data immediately so it doesn't flash empty.
    const src = charts[key];
    if (src) {
        modalChart.data.labels = [...src.data.labels];
        modalChart.data.datasets[0].data = [...src.data.datasets[0].data];
        modalChart.update("none");
    }
}

function closeModal() {
    const modal = document.getElementById("chart-modal");
    if (!modal) return;
    modal.classList.add("hidden");
    if (modalChart) {
        modalChart.destroy();
        modalChart = null;
    }
    modalKey = null;
}
