# LADTS — Справочник ключевых фрагментов кода

> Порядок разделов соответствует конвейеру выполнения одного шага симуляции (5 мс, 200 Гц).
> Каждый раздел содержит: название файла, описание что делает код, сам код с комментариями.

---

## 1. simulator/motor_config.py — Конфигурация двигателей

**Что делает:** хранит все электромеханические параметры двигателей (R, L, Ke, Kt, J, p) и параметры ШВП.
Единственный источник истины о двигателе во всем проекте.
Добавить новый двигатель = добавить одну запись в MOTORS.

`python
# BallScrewParams — кинематика ШВП
# lead=20мм даёт r=3.183 мм/рад — реалистично для компактных актуаторов
_SCREW_20MM = BallScrewParams(lead=0.020, efficiency=0.90)

@dataclass(frozen=True)
class BallScrewParams:
    lead: float = 0.005       # м/об — шаг резьбы
    efficiency: float = 0.90  # η — КПД передачи

    @property
    def meters_per_radian(self):
        # r = lead/(2π) — м/рад, кинематический коэффициент ШВП
        return self.lead / (2.0 * math.pi)

    def force_to_torque(self, f):
        # Линейная сила [Н] → момент на валу [Н·м] (F × r / η)
        return f * self.meters_per_radian / self.efficiency

    def torque_to_force(self, torque):
        # Момент на валу [Н·м] → линейная сила [Н] (T × η / r)
        return torque * self.efficiency / self.meters_per_radian
`

`python
# Вариант 6 — BLH5100KC (100 Вт, 24 В DC)
# Нет функций Torque Limit и Hold-at-Stop
BLH5100KC = MotorConfig(
    motor_id="BLH5100KC",
    voltage_nominal=24.0,
    resistance=0.450,        # Ом — тепловыделение R*I^2
    inductance=0.800e-3,     # Гн — τ_э = L/R = 1.78 мс
    ke=0.076, kt=0.076,      # В/(рад/с), Н·м/А
    inertia=45.0e-6,         # кг·м² — отражается в m_эфф = J/r² = 4.44 кг
    pole_pairs=4,
    torque_nominal=0.320, torque_max=0.960, current_max=12.0,
    screw=_SCREW_20MM,
    torque_limit_enabled=False, hold_at_stop=False,
)

# Вариант 7 — BLE230 (30 Вт, AC-привод, серия BLE2)
# Есть Torque Limit 80% и Hold-at-Stop
BLE230 = MotorConfig(
    motor_id="BLE230",
    voltage_nominal=24.0,    # эквив. DC для модели фазы
    resistance=1.100,        # Ом — выше, но ном. ток ниже
    inductance=1.200e-3,     # Гн — τ_э = 1.09 мс
    ke=0.076, kt=0.076,
    inertia=12.0e-6,         # кг·м² — лёгкий ротор, m_эфф = 3.68 кг
    pole_pairs=4,
    torque_nominal=0.095, torque_max=0.285, current_max=4.0,
    screw=_SCREW_20MM,
    torque_limit_enabled=True, torque_limit_fraction=0.80,
    hold_at_stop=True,
    preset_speeds=(41.9, 83.8, 125.7, 167.6, 209.4, 251.3, 293.2, 335.1),  # рад/с
)

MOTORS = {"BLH5100KC": BLH5100KC, "BLE230": BLE230}
DEFAULT_MOTOR = "BLH5100KC"

def get_motor(motor_id):
    # Вернуть конфиг по ID; KeyError при неизвестном ID
    if motor_id not in MOTORS:
        raise KeyError(f"Unknown motor ID {motor_id!r}")
    return MOTORS[motor_id]
`

---
## 2. simulator/current_model.py — Электрическая модель фазы

**Что делает:** интегрирует ОДУ фазового тока L*dI/dt = U - R*I - Ke*ω.
По требуемой силе вычисляет напряжение фазы, затем интегрирует ток неявным методом Эйлера.
Для BLE230 дополнительно реализует Torque Limit и Hold-at-Stop.
Возвращает реальную линейную силу и обновляет state.current.

`python
# simulator/current_model.py
class MotorElectricalModel:
    _HOLD_OMEGA_THRESHOLD = 2.0 * math.pi  # 1 об/с ≈ 60 об/мин
    _HOLD_CURRENT_FRACTION = 0.15          # 15% от I_макс — удерживающий ток

    def step(self, dt, f_demand, omega):
        cfg = self._cfg

        # Шаг 1. Линейная сила → момент на валу (через кинематику ШВП)
        t_demand = cfg.screw.force_to_torque(abs(f_demand))
        sign = 1.0 if f_demand >= 0.0 else -1.0

        # Шаг 2. Torque Limit (только BLE230)
        # Ограничивает момент, защищая механику от перегрузки
        if cfg.torque_limit_enabled:
            t_limit = cfg.torque_max * cfg.torque_limit_fraction  # 0.285*0.8=0.228 Н·м
            t_demand = min(t_demand, t_limit)

        # Шаг 3. Hold-at-Stop (только BLE230)
        # При остановке подаёт удерживающий ток вместо переходного, каретка не сползает
        holding = False
        if cfg.hold_at_stop and abs(omega) < self._HOLD_OMEGA_THRESHOLD:
            i_hold = cfg.current_max * 0.15  # 0.60 А для BLE230
            u_applied = cfg.resistance * i_hold + cfg.ke * abs(omega)
            holding = True
        else:
            # Фидерфорвард: U = R*I_зап + Ke*|ω|
            i_demand = min(t_demand / cfg.kt, cfg.current_max)
            u_applied = min(cfg.resistance * i_demand + cfg.ke * abs(omega),
                            cfg.voltage_nominal)

        # Шаг 4. Неявный (обратный) метод Эйлера — безусловно устойчив
        # При dt/τ_е >> 1 явный Эйлер был бы неустойчив (BLH: dt/τ=2.8, BLE: dt/τ=4.6)
        # I_нов = (I_стар + dt/L*(U - Ke*|ω|)) / (1 + dt*R/L)
        back_emf = cfg.ke * abs(omega)
        i_old = self.state.current
        numerator   = i_old + (dt / cfg.inductance) * (u_applied - back_emf)
        denominator = 1.0 + dt * cfg.resistance / cfg.inductance
        i_new = max(0.0, min(numerator / denominator, cfg.current_max))

        # Шаг 5. Момент → линейная сила
        # При hold: вал заблокирован, сила = 0
        t_actual = 0.0 if holding else min(cfg.kt * i_new, cfg.torque_max)
        f_actual = sign * cfg.screw.torque_to_force(t_actual)

        self.state.current = i_new
        self.state.voltage = u_applied
        return f_actual

    def switch_motor(self, motor_id):
        # Горячая замена: обновить конфиг и сбросить ток в ноль
        self._cfg = get_motor(motor_id)
        self.state = MotorElectricalState()
`

---
## 3. simulator/actuator_model.py — Динамика каретки

**Что делает:** интегрирует линейное движение каретки методом RK4 (5 мс).
Учитывает отражённую инерцию ротора J/r², кулоново и вязкое трение, механические упоры,
потери в подшипниках вала и режим Hold-at-Stop.

`python
# simulator/actuator_model.py

class ActuatorModel:

    def _update_effective_mass(self):
        # m_эфф = m_кар + J/r²
        # Отражённая инерция ротора добавляет эквив. линейную массу [kg]
        # BLH5100KC: 2.5 + 45e-6/(3.183e-3)^2 = 6.94 кг
        # BLE230:    2.5 + 12e-6/(3.183e-3)^2 = 3.68 кг
        r = self._motor_cfg.screw.meters_per_radian
        self._m_eff = self.p.mass + self._motor_cfg.inertia / (r * r)

    def _friction(self, v):
        # F_тр = Fc*tanh(v/vs) + b*v
        # tanh вместо sign — сглаживает дребезг интегратора около v=0
        return (self.p.coulomb_friction * math.tanh(v / self.p.stribeck_velocity)
                + self.p.viscous_friction * v)

    def _rotational_damping(self, v):
        # Потери в подшипниках вала, отражённые в линейную область:
        # F_подш = b_rot * (v/r) / r = b_rot * v / r^2
        r = self._motor_cfg.screw.meters_per_radian
        return self._motor_cfg.rotational_damping * v / (r * r)

    def step(self, dt, f_motor, f_load, hold_active=False):
        # Hold-at-Stop: заблокировать каретку, пропустить RK4
        if hold_active:
            self.state = ActuatorState(x=self.state.x, v=0.0, a=0.0, omega=0.0)
            return self.state, 0.0

        # Ограничение силы мотора
        f_max = self._motor_cfg.force_max
        f_motor = max(-f_max, min(f_max, f_motor))

        # RK4: k1..k4 для [x, v]
        def deriv(x, v): return v, self._accel(v, f_motor, f_load)
        k1x,k1v = deriv(x, v)
        k2x,k2v = deriv(x+0.5*dt*k1x, v+0.5*dt*k1v)
        k3x,k3v = deriv(x+0.5*dt*k2x, v+0.5*dt*k2v)
        k4x,k4v = deriv(x+dt*k3x,     v+dt*k3v)
        x_new = x + (dt/6)*(k1x+2*k2x+2*k3x+k4x)
        v_new = v + (dt/6)*(k1v+2*k2v+2*k3v+k4v)

        # Механические упоры: скорость обнуляется при достижении границы
        if x_new <= 0.0:   x_new, v_new = 0.0,  max(0.0, v_new)
        elif x_new >= 0.3: x_new, v_new = 0.3,  min(0.0, v_new)

        # Угловая скорость через кинематику ШВП: ω = v/r
        r = self._motor_cfg.screw.meters_per_radian
        omega_new = v_new / r

        self.state = ActuatorState(x=x_new, v=v_new,
                                   a=self._accel(v_new, f_motor, f_load),
                                   omega=omega_new)
        return self.state, f_motor
`

---
## 4. simulator/thermal_model.py — Тепловая модель

**Что делает:** моделирует нагрев обмотки через R*I² и охлаждение по ньютоновскому закону.
Параметры автоматически вычисляются из конфигурации двигателя (R, J как прокси размера мотора).

`python
# simulator/thermal_model.py

class ThermalModel:
    def step(self, dt, current):
        # dT/dt = α*I² - β*(T-T_окр) — явный Эйлер, устойчив т.к. τ_т >> dt
        # α = R/C_th — джоулев нагрев, β = 1/(R_th*C_th) — ньютоново охлаждение
        dT = self.p.alpha * current**2 - self.p.beta * (self.temperature - self.p.t_env)
        self.temperature += dT * dt
        return self.temperature

# Автоматическая калибровка параметров из даташита двигателя
@staticmethod
def from_motor(motor_cfg) -> ThermalParams:
    # C_th [Дж/К] — теплоёмкость, оценка по J как прокси объёма ротора
    # BLH5100KC(J=45): C_th≈25, BLE230(J=12): C_th≈15
    c_th = max(5.0, 7.0 * (motor_cfg.inertia * 1e6) ** 0.45)

    # R_th [К/Вт] — тепл. сопротивление, оценка по ном. мощности
    # BLH5100KC(100Вт): R_th≈3.5, BLE230(30Вт): R_th≈11.7
    p_nom = motor_cfg.torque_nominal * motor_cfg.speed_nominal
    r_th  = max(1.5, 350.0 / max(p_nom, 1.0))

    return ThermalParams(
        alpha = motor_cfg.resistance / c_th,  # = R/C_th
        beta  = 1.0 / (r_th * c_th),          # = 1/(R_th*C_th)
    )
`

---
## 5. simulator/load_model.py — Стохастическая нагрузка

**Что делает:** генерирует внешнюю нагрузку как процесс Орнштейна-Уленбека (коррелированный шум)
с редкими ударными импульсами (спайками).
Имитирует реальную нагрузку (сила резания, трение направляющих, удары при зацеплении).

`python
# simulator/load_model.py

class LoadModel:
    def step(self, dt):
        # OU-процесс: dF = θ*(μ-F)*dt + σ*sqrt(dt)*N(0,1)
        # μ=4Н — средняя нагрузка; θ=0.5 — скорость возврата; σ=2 — диффузия
        drift     = self.p.theta * (self.p.mu - self._f) * dt
        diffusion = self.p.sigma * math.sqrt(dt) * self._rng.gauss(0.0, 1.0)
        self._f  += drift + diffusion

        # Спайк с вероятностью 0.002/шаг (ударная нагрузка, зацепление)
        if self._rng.random() < self.p.spike_prob:
            self._spike_decay = self.p.spike_magnitude * self._rng.choice([-1, 1])
        self._f          += self._spike_decay
        self._spike_decay *= 0.7  # экспоненциальное затухание

        self._f = max(-self.p.f_max, min(self.p.f_max, self._f))
        return self._f
`

---
## 6. simulator/sensors.py — Датчики

**Что делает:** добавляет к истинному состоянию гауссов шум, медленный дрейф и задержку измерений.
Дашборд видит неидеальные данные — нельзя читать истинное состояние напрямую.

`python
# simulator/sensors.py
# Параметры: position_noise=0.2мм, velocity_noise=1мм/с,
#              current_noise=50мА, temperature_noise=0.1°C, lag_steps=2

def measure(self, true: TrueState, dt: float) -> MeasuredState:
    # Кольцевой буфер — задержка 2 шага (~10 мс при 200 Гц)
    self._buffer.append(true)
    delayed = self._buffer[0] if len(self._buffer) > self.params.lag_steps else true

    # Медленный дрейф (bias instability реального аналого датчика)
    self._t_drift += self.params.drift_rate_temp    * dt  # 0.5 м°C/с
    self._i_drift += self.params.drift_rate_current * dt  # 0.2 мА/с

    g = self._rng.gauss
    return MeasuredState(
        position     = delayed.position     + g(0, 0.0002),  # σ=0.2 мм
        velocity     = delayed.velocity     + g(0, 0.001),   # σ=1 мм/с
        acceleration = delayed.acceleration + g(0, 0.02),
        current      = delayed.current  + self._i_drift + g(0, 0.05),   # σ=50 мА
        temperature  = delayed.temperature + self._t_drift + g(0, 0.1), # σ=0.1°C
    )
`

---
## 7. simulator/health.py — Классификатор состояния

**Что делает:** определяет статус NORMAL/WARNING/ERROR по температуре и току.
Гистерезис предотвращает дребезг статуса при шумных сигналах вблизи порога.
Итоговый статус — максимум по двум каналам.

`python
# simulator/health.py
# Пороги: temp_warn=70°C, temp_err=90°C, hyst=3°C
#          current_warn=4A, current_err=6.5A, hyst=0.3A

def _classify(value, warn, err, hysteresis, prev):
    # Для выхода из ERROR нужно упасть ниже err-hysteresis
    if prev == "ERROR":
        if value < err - hysteresis: return _classify(value, warn, err, hysteresis, "WARNING")
        return "ERROR"
    if prev == "WARNING":
        if value >= err: return "ERROR"
        if value < warn - hysteresis: return "NORMAL"
        return "WARNING"
    # prev == NORMAL
    if value >= err:  return "ERROR"
    if value >= warn: return "WARNING"
    return "NORMAL"

class HealthClassifier:
    def update(self, temperature, current):
        self._t_state = _classify(temperature, 70, 90, 3.0, self._t_state)
        self._i_state = _classify(current,      4,  6.5, 0.3, self._i_state)
        # Итог = наихудший из двух каналов
        return max((self._t_state, self._i_state), key=lambda s: _LEVELS[s])
`

---
## 8. simulator/main.py — Физический тик (1 шаг = 5 мс)

**Что делает:** один шаг симуляции — последовательно вызывает все модели и формирует TelemetryFrame.

`python
# simulator/main.py
def _tick(self, dt):
    motor_cfg = get_motor(self._motor_id)

    f_load   = self.load.step(dt)                          # 1. Внешняя нагрузка (OU+спайки)
    f_demand = self.controller.step(                       # 2. ПИД: требуемая сила
        dt, self.actuator.state.x, self.actuator.state.v)
    omega    = self.actuator.state.omega
    f_motor  = self.electrical.step(dt, f_demand, omega)   # 3. ОДУ тока -> реальная сила
    i        = self.electrical.state.current

    hold_active = (                                        # 4. Hold-at-Stop (BLE230)
        motor_cfg.hold_at_stop
        and abs(omega) < MotorElectricalModel._HOLD_OMEGA_THRESHOLD
        and not self.controller.emergency_stop
    )
    state, f_applied = self.actuator.step(                 # 5. RK4 механика
        dt, f_motor, f_load, hold_active)
    t_motor = self.thermal.step(dt, i)                     # 6. Тепловая модель
    meas    = self.sensors.measure(                        # 7. Шум/дрейф/задержка
        TrueState(state.x, state.v, state.a, i, t_motor), dt)
    status  = self.health.update(meas.temperature, meas.current)  # 8. NORMAL/WARNING/ERROR

    return TelemetryFrame(                                 # 9. JSON для MQTT
        timestamp=time.time(), position=meas.position,
        velocity=meas.velocity, acceleration=meas.acceleration,
        current=meas.current, temperature=meas.temperature,
        force_motor=f_applied, force_load=f_load,
        target_position=self.controller.target_position,
        health=status, motor_id=self._motor_id,
    )
`

---
## 9. simulator/main.py — Запуск и asyncio-циклы

**Что делает:** запускает два параллельных asyncio-цикла.
Физический (200 Гц) и публикация (30 Гц) развязаны — сеть не замедляет физику.

`python
# simulator/main.py
SIM_HZ = 200          # частота физики
PUB_HZ = 30           # частота публикации в MQTT

async def _simulate(self):
    next_tick = asyncio.get_running_loop().time()
    while not self._stop.is_set():
        if not self._paused:
            self._latest = self._tick(SIM_DT)   # 1 шаг физики
            self.recorder.write(self._latest)    # запись в JSONL
        next_tick += SIM_DT
        sleep_for = next_tick - asyncio.get_running_loop().time()
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)
        else:
            # Отстали — сброс таймера (защита от spiral of doom)
            next_tick = asyncio.get_running_loop().time()

async def _publish_loop(self):
    while not self._stop.is_set():
        if self._latest is not None:
            self.publisher.publish_telemetry(self._latest)  # QoS 0, 30 Гц
        await asyncio.sleep(PUB_DT)

async def run(self):
    self.publisher.start()   # paho-mqtt фоновый поток
    self.commands.start()    # подписка на команды
    await asyncio.gather(self._simulate(), self._publish_loop())

if __name__ == "__main__":
    asyncio.run(_main())  # запуск: python simulator/main.py
`

---
## 10. simulator/command_consumer.py + main.py — Обработка команд

**Что делает:** принимает JSON-команды через MQTT, парсит их и диспетчеризует в модели.
Повреждённый JSON логируется и отбрасывается — не прерывая цикл симулятора.

`python
# simulator/command_consumer.py
@dataclass(frozen=True)
class Command:
    target_position: float | None = None  # м — новая уставка ПИД [0..0.30]
    emergency_stop:  bool  | None = None  # аварийный стоп (вязкое торможение)
    paused:          bool  | None = None  # заморозить интегратор
    reset:           bool  | None = None  # пересоздать все модели (x=0, T=25°C)
    record:          bool  | None = None  # начать/стоп запись JSONL
    select_motor:    str   | None = None  # горячая замена: "BLH5100KC" или "BLE230"

    @staticmethod
    def parse(raw: bytes):
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            log.warning("Bad command payload: %s", e)  # не убивает цикл
            return None
        return Command(
            target_position = _as_float(data.get("target_position")),
            emergency_stop  = _as_bool(data.get("emergency_stop")),
            paused          = _as_bool(data.get("paused")),
            reset           = _as_bool(data.get("reset")),
            record          = _as_bool(data.get("record")),
            select_motor    = _as_str(data.get("select_motor")),
        )
`

`python
# simulator/main.py — диспетчер команд
def _on_command(self, cmd):
    if cmd.reset:
        # Полный сброс: x=0, T=25°C, I=0, история графиков очищается
        self._init_models(preserve_position=False)

    if cmd.select_motor is not None:
        # Горячая замена: позиция сохраняется, модели пересоздаются
        try: get_motor(cmd.select_motor)
        except KeyError: pass  # неизвестный ID игнорируется
        else:
            self._motor_id = cmd.select_motor
            self._init_models(preserve_position=True)  # x,v сохраняются

    if cmd.paused is not None:          self._paused = cmd.paused
    if cmd.emergency_stop is not None:  self.controller.trigger_estop(cmd.emergency_stop)
    if cmd.target_position is not None: self.controller.set_target(cmd.target_position)
    if cmd.record is not None:
        if cmd.record:   self.recorder.start(meta=_meta_snapshot(get_motor(self._motor_id)))
        else:            self.recorder.stop()
`

---
## 11. simulator/publisher.py — MQTT-издатель

**Что делает:** публикует TelemetryFrame через paho-mqtt.
Настраивает LWT (последнее желание) — брокер автоматически опубликует "offline" при обрыве.

`python
# simulator/publisher.py
class TelemetryPublisher:
    def __init__(self, ...):
        # LWT: брокер опубликует "offline" если клиент упал без disconnect()
        offline = StatusFrame(state="offline", since=time.time()).to_json()
        self._client.will_set(TOPIC_STATUS, offline, qos=1, retain=True)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)

    def publish_telemetry(self, frame: TelemetryFrame):
        # QoS 0: высокая частота, потеря кадров допустима
        self._client.publish(TOPIC_TELEMETRY, frame.to_json(), qos=0)

    def publish_status_online(self):
        # QoS 1, retain=True: новый подписчик сразу узнаёт статус
        payload = StatusFrame(state="online", since=time.time()).to_json()
        self._client.publish(TOPIC_STATUS, payload, qos=1, retain=True)
`

---

## Схема JSON-сообщений MQTT

**TelemetryFrame** (digital_twin/actuator/telemetry, QoS 0, 30 Гц):
`json
{
  "timestamp": 1782224200.44,  "position": 0.1502,
  "velocity": -0.0077,         "acceleration": 0.041,
  "current": 1.42,             "temperature": 58.3,
  "force_motor": -2.48,        "force_load": -0.57,
  "target_position": 0.15,     "health": "NORMAL",
  "motor_id": "BLH5100KC"
}
`

**Command** (digital_twin/actuator/command, QoS 1):
`json
{ "target_position": 0.25 }
{ "select_motor": "BLE230" }
{ "emergency_stop": true }
{ "reset": true }
{ "record": true }
{ "paused": true }
`
