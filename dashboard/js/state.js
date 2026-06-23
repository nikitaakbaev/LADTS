import { CHART_WINDOW } from "./config.js";

const subscribers = new Set();

export const state = {
    connected: false,
    last: null,         // last TelemetryFrame
    history: {
        t: [], position: [], velocity: [], current: [], temperature: [],
    },
};

export function onUpdate(fn) {
    subscribers.add(fn);
    return () => subscribers.delete(fn);
}

function notify() {
    for (const fn of subscribers) fn(state);
}

export function setConnection(connected) {
    state.connected = connected;
    notify();
}

export function clearHistory() {
    for (const k of Object.keys(state.history)) state.history[k] = [];
    state.last = null;
    notify();
}

export function pushTelemetry(frame) {
    state.last = frame;
    const h = state.history;
    h.t.push(frame.timestamp);
    h.position.push(frame.position);
    h.velocity.push(frame.velocity);
    h.current.push(frame.current);
    h.temperature.push(frame.temperature);
    if (h.t.length > CHART_WINDOW) {
        for (const k of Object.keys(h)) h[k].shift();
    }
    notify();
}
