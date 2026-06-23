# Architecture

LADTS реализует три слоя классической Digital-Twin-архитектуры (Grieves):

| Слой            | Реализация                          | Технологии                      |
|-----------------|-------------------------------------|---------------------------------|
| Physical Twin   | Симулятор привода с физмоделью      | Python, asyncio, paho-mqtt      |
| Digital Thread  | MQTT-канал телеметрии и команд      | Mosquitto (TCP 1883 + WS 9001)  |
| Virtual Twin    | 3D-визуализация и панель управления | Three.js, Chart.js, mqtt.js     |

## Модули симулятора

```
controller.py   PID + emergency_stop
    │
    │  F_motor_cmd
    ▼
actuator_model.py  m·dv/dt = F − F_friction − F_load   (RK4 200 Hz)
    │           ▲
    │           │ F_load
    │           │
    │    load_model.py  OU-процесс + случайные импульсы
    │
    │  state.x, state.v, state.a, F_motor_applied
    ▼
current_model.py  I = k1·|F_motor| + k2·|F_load| + I_idle
    │
    │ I
    ▼
thermal_model.py  dT/dt = α·I² − β·(T − T_env)
    │
    │ T
    ▼
sensors.py      добавление шума, дрейфа, задержки
    │
    │ measured x, v, a, I, T
    ▼
health.py       NORMAL / WARNING / ERROR  с гистерезисом
    │
    ▼
telemetry.py    TelemetryFrame  →  publisher.py  →  MQTT
```

Команды идут в обратную сторону: `command_consumer.py` подписан на топик
`digital_twin/actuator/command` и вызывает `PositionController.set_target`
или `trigger_estop`.

## Event loop

`simulator/main.py` запускает две asyncio-корутины:

* `_simulate` — фиксированный шаг **5 мс (200 Hz)**: интегрирование ОДУ,
  обновление всех моделей, классификация состояния. Последний кадр
  сохраняется в `self._latest`.
* `_publish_loop` — каждые **33 мс (30 Hz)** публикует `self._latest`
  в `digital_twin/actuator/telemetry`.

Разделение частот развязывает точность физики и темп сетевого вывода.
Если интегратор отстал (например, GC-пауза), целевое время сбрасывается
на текущее — это защита от spiral of doom.

## Слой команд

Команды публикуются с QoS 1 (важна доставка). Парсер устойчив к мусору:
повреждённый JSON и невалидные типы фильтруются и логируются. Состояние
PID — единственная shared-data между потоком paho-mqtt и asyncio-циклом;
доступ безопасен, потому что записи в `target_position` и
`emergency_stop` атомарны на уровне GIL.

## Слой представления

В браузере:

1. `mqtt_client.js` (mqtt.js поверх WebSocket) подключается к `ws://host:9001`,
   реконнект каждые 2 c.
2. Принятый кадр уходит в `state.js` — pub/sub-стор с кольцевым буфером
   истории.
3. `visualization.js` интерполирует положение каретки (LERP с коэффициентом
   0.25 на кадр rAF) и плавно меняет цвет материала через `Color.lerp`.
4. `hud.js` обновляется на каждое сообщение, `charts.js` дросселируется
   до 10 Гц (Chart.js — дорогой `update()`).

## Last Will & Testament

`TelemetryPublisher` ставит retained-сообщение `{"state":"offline"}` в
`digital_twin/actuator/status` через `will_set`. При штатном старте
публикуется `online`. Любой клиент, подписавшись на этот топик, мгновенно
получит retained-кадр и узнает, жив ли симулятор.
