import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { ACTUATOR } from "./config.js";

const HEALTH_COLOR = {
    NORMAL:  0x2ecc71,
    WARNING: 0xf1c40f,
    ERROR:   0xe74c3c,
};

const SCENE_LENGTH = 1.6;     // visual length of the rail
const RAIL_RADIUS  = 0.04;
const CARRIAGE     = { w: 0.22, h: 0.18, d: 0.18 };

function physToScene(x) {
    // Map physical [x_min, x_max] to scene [-L/2, +L/2].
    const u = (x - ACTUATOR.xMin) / (ACTUATOR.xMax - ACTUATOR.xMin);
    return (u - 0.5) * SCENE_LENGTH;
}

export function createVisualization(container) {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b0f15);

    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 50);
    camera.position.set(1.3, 0.9, 1.6);
    camera.lookAt(0, 0.1, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0.18, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 0.6;
    controls.maxDistance = 5.0;
    controls.maxPolarAngle = Math.PI * 0.49;   // don't go below the floor
    controls.update();

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.45));
    const key = new THREE.DirectionalLight(0xffffff, 0.9);
    key.position.set(2, 3, 2);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x88aaff, 0.4);
    rim.position.set(-2, 1, -2);
    scene.add(rim);

    // Floor grid
    const grid = new THREE.GridHelper(4, 24, 0x223044, 0x1a2330);
    grid.position.y = -0.001;
    scene.add(grid);

    // Base plate
    const baseGeom = new THREE.BoxGeometry(SCENE_LENGTH + 0.2, 0.06, 0.4);
    const baseMat  = new THREE.MeshStandardMaterial({ color: 0x2c3440, metalness: 0.4, roughness: 0.7 });
    const base = new THREE.Mesh(baseGeom, baseMat);
    base.position.y = 0.03;
    scene.add(base);

    // End brackets
    for (const sx of [-1, 1]) {
        const bracket = new THREE.Mesh(
            new THREE.BoxGeometry(0.08, 0.22, 0.32),
            new THREE.MeshStandardMaterial({ color: 0x3a4654, metalness: 0.5, roughness: 0.6 }),
        );
        bracket.position.set(sx * (SCENE_LENGTH / 2 + 0.02), 0.16, 0);
        scene.add(bracket);
    }

    // Rail
    const railGeom = new THREE.CylinderGeometry(RAIL_RADIUS, RAIL_RADIUS, SCENE_LENGTH, 24);
    railGeom.rotateZ(Math.PI / 2);
    const railMat = new THREE.MeshStandardMaterial({ color: 0x8a96a6, metalness: 0.85, roughness: 0.25 });
    const rail = new THREE.Mesh(railGeom, railMat);
    rail.position.y = 0.18;
    scene.add(rail);

    // Carriage (its color follows health)
    const carriageMat = new THREE.MeshStandardMaterial({
        color: HEALTH_COLOR.NORMAL, metalness: 0.3, roughness: 0.4,
        emissive: HEALTH_COLOR.NORMAL, emissiveIntensity: 0.15,
    });
    const carriage = new THREE.Mesh(
        new THREE.BoxGeometry(CARRIAGE.w, CARRIAGE.h, CARRIAGE.d),
        carriageMat,
    );
    carriage.position.set(0, 0.18, 0);
    scene.add(carriage);

    // Target marker — a thin vertical pillar
    const targetMat = new THREE.MeshBasicMaterial({ color: 0x4cc2ff, transparent: true, opacity: 0.6 });
    const target = new THREE.Mesh(
        new THREE.BoxGeometry(0.01, 0.5, 0.01),
        targetMat,
    );
    target.position.set(0, 0.25, 0.22);
    scene.add(target);

    // --- API ---
    const api = {
        targetPos: 0,
        currentPos: 0,
        targetColor: new THREE.Color(HEALTH_COLOR.NORMAL),
    };

    function applyFrame(frame) {
        api.targetPos = physToScene(frame.position);
        api.targetColor.set(HEALTH_COLOR[frame.health] || HEALTH_COLOR.NORMAL);
        target.position.x = physToScene(frame.target_position);
    }

    function resize() {
        const { clientWidth: w, clientHeight: h } = container;
        if (w === 0 || h === 0) return;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
    }
    window.addEventListener("resize", resize);
    resize();

    // Smooth interpolation: telemetry arrives at ~30 Hz, render at 60 Hz.
    function tick() {
        api.currentPos += (api.targetPos - api.currentPos) * 0.25;
        carriage.position.x = api.currentPos;
        carriageMat.color.lerp(api.targetColor, 0.15);
        carriageMat.emissive.lerp(api.targetColor, 0.15);
        controls.update();
        renderer.render(scene, camera);
        requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);

    return { applyFrame };
}
