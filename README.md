# MisterTimer

Инструмент для OBS, который закрепляет любой виджет (таймер) на лбу стримера и двигает его вслед за движениями головы.

## Принцип работы

```
OBS Webcam Source → GetSourceScreenshot (скриншот через OBS API)
                              ↓
MediaPipe Face Mesh (478 точек лица) → позиция лба + углы поворота
                              ↓
SetSceneItemTransform (двигаем виджет через OBS WebSocket)
```

Таймер следует за лбом, поворачивается при наклоне головы, сжимается при поворотах (псевдо-3D перспектива).

## Требования

- OBS Studio 28+ (встроенный obs-websocket)
- Python 3.11+
- `uv` (менеджер пакетов)

## Установка и запуск

```bash
git clone https://github.com/demindx/mistercopustracker.git
cd mistercopustracker
uv sync
uv run python run.py
```

При первом запуске скачает модель MediaPipe (~5 МБ, кэшируется в `models/`).

## Настройка OBS

1. **Tools → WebSocket Server Settings** → включить «Enable WebSocket server» (порт 4455)
2. Если включена аутентификация — указать пароль в Settings приложения

## Использование

1. Открыть `http://localhost:8080`
2. Нажать **Connect OBS**
3. Выбрать сцену, источник таймера, источник веб-камеры
4. Настроить сглаживание (Smoothing), поворот (Rotation), отступ (Y Offset)
5. **Start** — виджет начинает двигаться за лбом

## Структура проекта

```
src/
├── face_detector.py      # MediaPipe FaceMesh: детекция лба, roll/pitch/yaw
├── obs_connector.py      # OBS WebSocket клиент
├── coordinate_mapper.py  # Маппинг координат лица → OBS canvas
├── smoother.py            # EMA-фильтр для плавности
└── head_tracker.py        # Главный поток трекинга
ui/
└── app.py                # NiceGUI интерфейс
```

## CLI

```
uv run python run.py               # Запуск (localhost:8080)
uv run python run.py --no-browser  # Без авто-открытия браузера
uv run python run.py --public      # Доступ по сети (0.0.0.0)
uv run python run.py --port 9000   # Свой порт
```

## Сборка в .exe (Windows)

```bash
# На Windows-машине (PyInstaller не кросс-компилирует):
bash build.sh
# Вывод: dist/MisterTimer/MisterTimer.exe
```

Требуется Python 3.11+ и `uv`. Перед сборкой скрипт скачает модель MediaPipe и запустит PyInstaller. Выходной .exe содержит всё необходимое, запускается без установки Python.
