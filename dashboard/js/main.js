import { connect } from "./mqtt_client.js";
import { onUpdate, state } from "./state.js";
import { createVisualization } from "./visualization.js";
import { renderHud } from "./hud.js";
import { initCharts, renderCharts } from "./charts.js";
import { bindCommandUi } from "./commands.js";
import { initTimer, timerStart } from "./timer.js";

const sceneEl = document.getElementById("scene");
const viz = createVisualization(sceneEl);

initCharts();
initTimer();
bindCommandUi();
connect();

let lastChartRender = 0;
let timerStarted = false;

onUpdate((s) => {
    renderHud(s);
    if (s.last) {
        viz.applyFrame(s.last);
        if (!timerStarted) {
            timerStart();
            timerStarted = true;
        }
    }

    // Throttle chart redraws — 10 Hz is plenty and keeps the UI smooth.
    const now = performance.now();
    if (now - lastChartRender > 100) {
        renderCharts(s);
        lastChartRender = now;
    }
});

// Initial render so HUD shows "disconnected" / dashes before any data arrives.
renderHud(state);
