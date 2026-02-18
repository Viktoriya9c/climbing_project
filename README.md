# Video App v5

Локальный инструмент для:
- загрузки видео (файл / URL, включая `vk.com/video...` через `yt-dlp`),
- конвертации при необходимости (только если исходник не browser-playable),
- анализа видео (YOLO + OCR + матчинг по CSV протоколу),
- просмотра таймкодов, bbox и редактируемого итогового текста.

## Текущий pipeline
1. Upload видео или Download по URL.
2. Upload CSV протокола участников.
3. `Запустить анализ`:
- если видео browser-playable -> конвертация пропускается,
- иначе `ffmpeg` конвертирует в MP4,
- затем `processing`: YOLO детектит людей, OCR читает номер, номер матчится с CSV,
- подтверждённые находки попадают в таймкоды и итоговый текст.

## Требования
- Python 3.11+ (проверено на 3.14)
- `ffmpeg` и `ffprobe` в PATH
- для full processing:
  - `ultralytics`
  - `easyocr`
  - `opencv-python-headless`
- для URL загрузок с VK/YouTube: `yt-dlp`

## Быстрый старт
```bash
make install
make run
```

Открыть: `http://localhost:8000`

## Make targets
- `make install` — создать `.venv` и установить зависимости
- `make run` — запуск FastAPI/uvicorn
- `make test` — тесты
- `make clean` — очистка runtime-данных (uploads/converted/state)
- `make docker-build` — сборка docker образа
- `make docker-up` — запуск через docker compose
- `make docker-down` — остановка docker compose

## Docker
```bash
make docker-build
make docker-up
```

Сервис поднимается на `http://localhost:8000`.

## Структура проекта
- `app/main.py` — API, фоновые воркеры, orchestration pipeline
- `app/processing.py` — конвертация и анализ
- `app/detector.py` — YOLO + OCR детектор
- `app/matcher.py` — загрузка CSV и матчинг номеров
- `app/state.py` — state/event storage
- `templates/`, `static/` — UI
- `uploads/`, `converted/` — runtime файлы
- `input/protocols/` — загруженные CSV
- `models/` — YOLO weights (опционально)

## Важно
- Невалидные файлы (например `test.txt`) не принимаются как видео.
- В `state.json` сохраняются состояние пайплайна, UI-предпочтения и позиция плеера.
