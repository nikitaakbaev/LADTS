# MQTT protocol

Брокер: Mosquitto.
Listener'ы: `1883/tcp` (Python-клиенты) и `9001/tcp` (WebSocket-клиенты браузера).
Анонимный доступ для прототипа; для прода добавить `password_file` + ACL.

## Topics

| Topic                                      | Direction         | QoS | Retain | Payload schema |
|--------------------------------------------|-------------------|-----|--------|----------------|
| `digital_twin/actuator/telemetry`          | Sim → Dashboard   | 0   | no     | TelemetryFrame |
| `digital_twin/actuator/command`            | Dashboard → Sim   | 1   | no     | Command        |
| `digital_twin/actuator/status`             | Sim → Dashboard   | 1   | yes    | StatusFrame    |

QoS 0 для телеметрии — это поток ~30 Гц, потеря отдельных кадров
терпима. QoS 1 для команд — потеря недопустима. Status retained — чтобы
новый подписчик мгновенно получал актуальное состояние симулятора.

## TelemetryFrame

```json
{
  "timestamp": 1782224200.441106,
  "position": 0.15016,
  "velocity": -0.00774,
  "acceleration": 0.04084,
  "current": 0.408,
  "temperature": 67.99,
  "force_motor": -2.48,
  "force_load": -0.57,
  "target_position": 0.15,
  "health": "NORMAL"
}
```

| Поле              | Тип    | Ед. изм. | Описание                                      |
|-------------------|--------|----------|-----------------------------------------------|
| `timestamp`       | float  | сек, Unix| `time.time()` в момент сборки кадра           |
| `position`        | float  | м        | измеренное положение каретки                  |
| `velocity`        | float  | м/с      | измеренная скорость                           |
| `acceleration`    | float  | м/с²     | измеренное ускорение                          |
| `current`         | float  | А        | ток мотора (с шумом и дрейфом)                |
| `temperature`     | float  | °C       | температура мотора                            |
| `force_motor`     | float  | Н        | сила, *приложенная* мотором (после сатурации) |
| `force_load`      | float  | Н        | внешняя нагрузка                              |
| `target_position` | float  | м        | текущая уставка PID                           |
| `health`          | string | —        | `NORMAL` \| `WARNING` \| `ERROR`              |

## Command

Любые поля опциональны. Неизвестные / нечисловые — игнорируются.

```json
{
  "target_position": 0.20,
  "emergency_stop": false
}
```

| Поле              | Тип    | Ед. изм. | Описание                                  |
|-------------------|--------|----------|--------------------------------------------|
| `target_position` | float  | м        | новая уставка PID (`0…0.30`)               |
| `emergency_stop`  | bool   | —        | `true` обнуляет силу мотора до отмены      |

## StatusFrame

```json
{ "state": "online", "since": 1782224100.89 }
```

`state` — `online` (явно публикуется при коннекте) или `offline`
(публикуется при штатном `stop()` или брокером через LWT при разрыве
коннекта симулятора).

## Примеры использования

CLI-сабскрайбер на все три топика:

```bash
python -m mqtt.test_subscriber all
```

Послать команду из CLI:

```bash
mosquitto_pub -h localhost -t digital_twin/actuator/command \
  -m '{"target_position": 0.10}'
```

Обнуление аварийного стопа:

```bash
mosquitto_pub -h localhost -t digital_twin/actuator/command \
  -m '{"emergency_stop": false}'
```
