"""Simulator entry point — asyncio event loop.

Two cooperative tasks:

* `_simulate` — runs at SIM_HZ (200 Hz). Integrates the actuator ODE,
  updates thermal/electrical/load models, classifies health, and stores
  the latest measured frame.

* `_publish_loop` — runs at PUB_HZ (30 Hz). Publishes the latest frame
  via MQTT.

This split decouples physics fidelity from network throughput. The
publisher never blocks the integrator and vice versa.

Commands arrive on a separate paho client thread and are dispatched
into the controller via a thread-safe call (PositionController is
trivially thread-safe for our access pattern: writes are atomic field
assignments, reads happen one tick later — no shared mutable state to
tear).

Motor switching:
  A `select_motor` command triggers a hot-swap of all motor-dependent
  models (electrical, thermal, actuator inertia) without restarting the
  simulator loop.  The carriage position and PID state are preserved.
"""
from __future__ import annotations

import asyncio
import logging
import signal
import time

from pathlib import Path

from simulator.actuator_model import ActuatorModel, ActuatorParams
from simulator.clock import HighResTimer
from simulator.command_consumer import Command, CommandConsumer
from simulator.controller import PIDGains, PositionController
from simulator.current_model import MotorElectricalModel
from simulator.health import HealthClassifier, HealthThresholds
from simulator.load_model import LoadModel, LoadParams
from simulator.motor_config import DEFAULT_MOTOR, MotorConfig, get_motor
from simulator.publisher import TelemetryPublisher
from simulator.recorder import TelemetryRecorder
from simulator.sensors import SensorParams, SensorSuite, TrueState
from simulator.telemetry import TelemetryFrame
from simulator.thermal_model import ThermalModel, ThermalParams

log = logging.getLogger("ladts.main")

SIM_HZ = 200          # physics integration rate
PUB_HZ = 30           # MQTT publication rate
SIM_DT = 1.0 / SIM_HZ
PUB_DT = 1.0 / PUB_HZ
INITIAL_TARGET = 0.15  # m

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDINGS_DIR = REPO_ROOT / "recordings"


def _meta_snapshot(motor_cfg: MotorConfig) -> dict:
    """Snapshot of every parameter used by the simulator — for reproducibility."""
    from dataclasses import asdict
    return {
        "sim_hz": SIM_HZ, "pub_hz": PUB_HZ,
        "motor_id": motor_cfg.motor_id,
        "motor_label": motor_cfg.label,
        "actuator": asdict(ActuatorParams()),
        "load": asdict(LoadParams()),
        "sensors": asdict(SensorParams()),
        "pid": asdict(PIDGains()),
        "health": asdict(HealthThresholds()),
    }


class Simulator:
    def __init__(self) -> None:
        self._motor_id: str = DEFAULT_MOTOR
        self._init_models()
        self.publisher = TelemetryPublisher()
        self.commands = CommandConsumer(handler=self._on_command)
        self.recorder = TelemetryRecorder(RECORDINGS_DIR)

        self._latest: TelemetryFrame | None = None
        self._stop = asyncio.Event()
        self._paused = False

    def _init_models(self, preserve_position: bool = False) -> None:
        """(Re)create all stateful models.

        Args:
            preserve_position: if True, keep carriage x/v from previous state
                               (used during hot motor swap).
        """
        motor_cfg: MotorConfig = get_motor(self._motor_id)  # type: ignore[arg-type]

        # Preserve carriage state across motor hot-swap
        x_prev = self.actuator.state.x if preserve_position and hasattr(self, "actuator") else 0.0
        v_prev = self.actuator.state.v if preserve_position and hasattr(self, "actuator") else 0.0

        # Actuator: rigid-body dynamics + reflected rotor inertia
        self.actuator = ActuatorModel(motor_cfg=motor_cfg)
        if preserve_position:
            from simulator.actuator_model import ActuatorState
            r = motor_cfg.screw.meters_per_radian
            self.actuator.state = ActuatorState(
                x=x_prev, v=v_prev, a=0.0,
                omega=v_prev / r if abs(r) > 1e-12 else 0.0,
            )

        # Electrical phase model (replaces old algebraic current model)
        self.electrical = MotorElectricalModel(motor_id=self._motor_id)

        # Thermal model calibrated from motor config
        thermal_params = ThermalParams.from_motor(motor_cfg)
        self.thermal = ThermalModel(thermal_params)

        self.load = LoadModel()
        self.sensors = SensorSuite()
        self.health = HealthClassifier()

        if not preserve_position:
            self.controller = PositionController()
            self.controller.set_target(INITIAL_TARGET)

    # --- command handling --------------------------------------------------

    def _on_command(self, cmd: Command) -> None:
        if cmd.reset:
            was_paused = self._paused
            self._init_models(preserve_position=False)
            self._paused = was_paused
            log.info("reset: all models reinitialised (paused=%s)", was_paused)

        if cmd.select_motor is not None:
            try:
                get_motor(cmd.select_motor)  # type: ignore[arg-type]
            except KeyError:
                log.warning("select_motor: unknown motor ID %r — ignored", cmd.select_motor)
            else:
                self._motor_id = cmd.select_motor
                self._init_models(preserve_position=True)
                log.info("select_motor: switched to %s", cmd.select_motor)

        if cmd.paused is not None:
            self._paused = cmd.paused
            log.info("paused=%s", cmd.paused)
        if cmd.emergency_stop is not None:
            self.controller.trigger_estop(cmd.emergency_stop)
            log.info("emergency_stop=%s", cmd.emergency_stop)
        if cmd.target_position is not None:
            self.controller.set_target(cmd.target_position)
            log.info("target_position=%.4f m", cmd.target_position)
        if cmd.record is not None:
            motor_cfg: MotorConfig = get_motor(self._motor_id)  # type: ignore[arg-type]
            if cmd.record and not self.recorder.is_recording:
                self.recorder.start(meta=_meta_snapshot(motor_cfg))
            elif not cmd.record and self.recorder.is_recording:
                self.recorder.stop()

    # --- physics tick ------------------------------------------------------

    def _tick(self, dt: float) -> TelemetryFrame:
        motor_cfg: MotorConfig = get_motor(self._motor_id)  # type: ignore[arg-type]

        # External load
        f_load = self.load.step(dt)

        # PID force demand (linear)
        f_demand = self.controller.step(
            dt, self.actuator.state.x, self.actuator.state.v
        )

        # Electrical model: ODE step → actual motor force + current
        omega = self.actuator.state.omega
        f_motor = self.electrical.step(dt, f_demand, omega)
        i = self.electrical.state.current

        # Detect hold-at-stop (BLE230) — shaft locked when nearly stopped
        hold_active = (
            motor_cfg.hold_at_stop
            and abs(omega) < MotorElectricalModel._HOLD_OMEGA_THRESHOLD
            and not self.controller.emergency_stop
        )

        # Mechanical integration
        state, f_motor_applied = self.actuator.step(
            dt, f_motor, f_load, hold_active=hold_active
        )

        # Thermal model: winding temperature from R·I² (via alpha=R/C_th)
        t_motor = self.thermal.step(dt, i)

        # Sensor noise / drift / lag
        meas = self.sensors.measure(
            TrueState(state.x, state.v, state.a, i, t_motor), dt,
        )
        status = self.health.update(meas.temperature, meas.current)

        return TelemetryFrame(
            timestamp=time.time(),
            position=meas.position,
            velocity=meas.velocity,
            acceleration=meas.acceleration,
            current=meas.current,
            temperature=meas.temperature,
            force_motor=f_motor_applied,
            force_load=f_load,
            target_position=self.controller.target_position,
            health=status,
            motor_id=self._motor_id,
        )

    # --- coroutines --------------------------------------------------------

    async def _simulate(self) -> None:
        next_tick = asyncio.get_running_loop().time()
        while not self._stop.is_set():
            if not self._paused:
                self._latest = self._tick(SIM_DT)
                self.recorder.write(self._latest)
            next_tick += SIM_DT
            sleep_for = next_tick - asyncio.get_running_loop().time()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            else:
                next_tick = asyncio.get_running_loop().time()

    async def _publish_loop(self) -> None:
        while not self._stop.is_set():
            if self._latest is not None:
                self.publisher.publish_telemetry(self._latest)
            await asyncio.sleep(PUB_DT)

    # --- lifecycle ---------------------------------------------------------

    async def run(self) -> None:
        self.publisher.start()
        self.commands.start()
        log.info("Simulator running at %d Hz, publishing at %d Hz", SIM_HZ, PUB_HZ)
        try:
            await asyncio.gather(self._simulate(), self._publish_loop())
        finally:
            self.recorder.stop()
            self.commands.stop()
            self.publisher.stop()
            log.info("Simulator stopped")

    def request_stop(self) -> None:
        self._stop.set()


def _install_signal_handlers(sim: Simulator) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, sim.request_stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_: sim.request_stop())


async def _main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    with HighResTimer(period_ms=1):
        sim = Simulator()
        _install_signal_handlers(sim)
        await sim.run()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
