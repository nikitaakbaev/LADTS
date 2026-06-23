# LADTS — Linear Actuator Digital Twin

Учебный прототип цифрового двойника линейного электромеханического привода:
физический симулятор на Python публикует телеметрию в MQTT, а в браузере
запущен Three.js-дашборд, который визуализирует состояние и шлёт команды
обратно. Реализован полный цикл «Physical → Digital Thread → Virtual».

## Структура

```
LADTS/
├── simulator/           # Physical Twin: physics, sensors, MQTT publisher
├── mqtt/                # broker config + test subscriber
├── dashboard/           # Virtual Twin: Three.js + Chart.js + mqtt.js
├── scripts/             # run_broker / run_simulator / run_dashboard
├── docs/                # architecture, math model, MQTT protocol
└── requirements.txt
```

## Зависимости

* Python 3.11+
* Mosquitto 2.x с поддержкой WebSocket-listener'а
* Современный браузер (ES-modules, importmap)

```powershell
python -m pip install -r requirements.txt
winget install EclipseFoundation.Mosquitto    # если ещё не стоит
```

## Запуск (Windows / PowerShell)

> В PowerShell скрипты из текущей папки запускаются с префиксом `.\`.
> Если получите ошибку про execution policy, один раз выполните:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Однокнопочный запуск

```powershell
.\scripts\start-all.bat
```

Откроет три окна (брокер, симулятор, HTTP-сервер дашборда) и сам зайдёт
в браузер на `http://localhost:8080`. Если Mosquitto уже работает как
служба Windows — повторно его не поднимет.

### Запуск по отдельности

Откройте три терминала:

```powershell
# 1) MQTT-брокер на 1883 (TCP) + 9001 (WebSocket)
.\scripts\run_broker.ps1

# 2) Симулятор (200 Hz physics, 30 Hz publish)
.\scripts\run_simulator.ps1

# 3) HTTP-сервер для дашборда
.\scripts\run_dashboard.ps1
```

## Управление приводом из дашборда

* **Target position, m** + **Send target** — публикует команду
  `target_position` в `digital_twin/actuator/command`. PID отрабатывает
  новую уставку.
* **EMERGENCY STOP** — обнуляет силу мотора. Чтобы продолжить, отправьте
  новую цель (она автоматически снимет стоп).
* В 3D-сцене работает мышь: левая кнопка — вращение, правая — панорама,
  колесо — зум.

## Troubleshooting

**Дашборд показывает «disconnected» и каретка не двигается.** Это значит,
что брокер не слушает WebSocket-порт 9001. Чаще всего так бывает, когда
после `winget install` Mosquitto висит как Windows-сервис со стандартным
конфигом (только TCP 1883). Решения:

* **На один сеанс.** Запустите PowerShell от Администратора и остановите
  сервис, после чего перезапустите `start-all.bat`:
  ```powershell
  net stop mosquitto
  ```
* **Навсегда.** Перенаправьте сервис на наш конфиг (один раз, от
  Администратора):
  ```powershell
  sc stop mosquitto
  sc config mosquitto binPath= "\"C:\Program Files\mosquitto\mosquitto.exe\" run -c \"D:\Project\LADTS\mqtt\mosquitto.conf\""
  sc start mosquitto
  ```
  После этого `run_broker.ps1` запускать вообще не нужно — служба сама
  поднимает оба listener'а на старте Windows.

Откройте `http://localhost:8080` в браузере.

Linux/macOS — те же скрипты с расширением `.sh`.

## Что видно в дашборде

* 3D-сцена с движущейся кареткой (положение синхронизировано с симулятором).
* Цвет каретки меняется по статусу: зелёный — `NORMAL`, жёлтый — `WARNING`,
  красный — `ERROR`.
* HUD: позиция, скорость, ток, температура, статус, индикатор соединения.
* 4 графика Chart.js со скользящим окном ~8 секунд.
* Поле «Target position» и кнопка «Send target» — публикуют команду в MQTT.
* «EMERGENCY STOP» — обнуляет силу мотора до отмены.

## Отладка без браузера

Подписка на все топики из CLI:

```powershell
python -m mqtt.test_subscriber all
```

## Дальше

* [docs/architecture.md](docs/architecture.md) — общая архитектура и потоки данных.
* [docs/math_model.md](docs/math_model.md) — уравнения движения, термомодели и тока.
* [docs/mqtt_protocol.md](docs/mqtt_protocol.md) — топики, схемы JSON-сообщений, QoS.
* [docs/system_diagram.txt](docs/system_diagram.txt) — ASCII-схема.
