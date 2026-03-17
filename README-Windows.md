# Video App v5 on Windows

Инструкция описывает запуск проекта из архива на Windows 10 и Windows 11.

## Что потребуется

- Windows 10 или Windows 11
- Python 3.11+
- `ffmpeg` и `ffprobe` в `PATH`
- PowerShell
- интернет-соединение для установки Python-зависимостей

Примечание: отдельная активация виртуального окружения не обязательна. Проектный скрипт использует `.venv\Scripts\python.exe` напрямую.

## Состав архива

После распаковки в корне проекта должны быть, как минимум, следующие файлы и папки:

- `app`
- `static`
- `templates`
- `tests`
- `scripts`
- `requirements.txt`
- `Makefile.ps1`

Папки `input`, `outputs`, `logs`, `models` и файл `state.json` могут отсутствовать сразу после распаковки. Это нормально: они создаются приложением во время работы.

## Шаг 1. Проверить Python

Откройте PowerShell в папке проекта и выполните:

```powershell
python --version
```

Если Python не установлен, поставьте Python 3.11 или новее.

Если установлен Python Launcher, можно дополнительно проверить:

```powershell
py -V
```

## Шаг 2. Установить ffmpeg

Проект использует `ffmpeg` и `ffprobe` для проверки и конвертации видео.

Проверка:

```powershell
ffmpeg -version
ffprobe -version
```

Если команды не найдены, установите FFmpeg.

### Вариант A. Через официальный сайт FFmpeg

Это основной и предпочтительный способ для данной инструкции.

1. Перейдите на официальный сайт FFmpeg:
   - `https://ffmpeg.org/`
   - `https://ffmpeg.org/download.html`
2. На странице загрузки откройте раздел `Windows`.
3. Выберите Windows-сборку, на которую указывает официальный сайт FFmpeg.
4. Скачайте архив с готовой сборкой.
5. Распакуйте архив, например в `C:\ffmpeg`.
6. Добавьте `C:\ffmpeg\bin` в системную переменную `PATH`.
7. Закройте PowerShell и откройте его заново.
8. Повторно проверьте:

```powershell
ffmpeg -version
ffprobe -version
```

### Вариант B. Прямая ссылка на готовую сборку

Этот вариант можно использовать как более быстрый способ установки FFmpeg из PowerShell.

1. Откройте PowerShell.
2. Найдите доступные пакеты FFmpeg:

```powershell
winget search ffmpeg
```

3. Установите FFmpeg:

```powershell
winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
```

4. После завершения установки полностью закройте PowerShell.
5. Откройте новое окно PowerShell.
6. Проверьте установку:

```powershell
ffmpeg -version
ffprobe -version
```

Если команды выводят информацию о версии, FFmpeg установлен корректно.

## Шаг 3. Перейти в папку проекта

Пример:

```powershell
cd C:\Users\meshk\dev\climbing_project
```

## Шаг 4. Установить зависимости проекта

В проекте уже есть PowerShell-скрипт для Windows:

```powershell
.\Makefile.ps1 install
```

Что делает команда:

- создает виртуальное окружение `.venv`;
- обновляет `pip`;
- устанавливает зависимости из `requirements.txt`.

## Шаг 5. Запустить приложение

```powershell
.\Makefile.ps1 run
```

После запуска откройте в браузере:

```text
http://localhost:8888
```

## Альтернативный запуск через Docker

Этот вариант можно использовать, если Docker Desktop уже установлен и запущен.

### Шаг 1. Проверить Docker

Откройте PowerShell в папке проекта и выполните:

```powershell
docker --version
docker compose version
```

### Шаг 2. Подготовить локальные папки и файл состояния

Перед запуском `docker compose` создайте рабочие каталоги и подготовьте файл `state.json`:

```powershell
New-Item -ItemType Directory -Force input\videos
New-Item -ItemType Directory -Force input\protocols
New-Item -ItemType Directory -Force outputs\converted
New-Item -ItemType Directory -Force models
Set-Content state.json "{}"
```

Если файл `state.json` уже существует, повторно создавать его не нужно.

### Шаг 3. Собрать Docker-образ

```powershell
docker compose build
```

Сборка может занять заметное время, потому что в образ устанавливаются Python-зависимости для обработки видео и OCR.

### Шаг 4. Поднять контейнер

```powershell
docker compose up -d
```

### Шаг 5. Проверить, что сервис запущен

```powershell
docker compose ps
```

После запуска откройте:

```text
http://localhost:8888
```

### Остановка контейнера

```powershell
docker compose down
```

## Дополнительные команды

### Тесты

```powershell
.\Makefile.ps1 test
```

### Фоновый запуск

```powershell
.\Makefile.ps1 run-bg
```

### Проверка статуса фонового процесса

```powershell
.\Makefile.ps1 status
```

### Остановка фонового процесса

```powershell
.\Makefile.ps1 stop
```

### Очистка рабочих данных

```powershell
.\Makefile.ps1 clean
```

Команда очищает runtime-данные, включая:

- `input/videos`
- `outputs/converted`
- `state.json`

## Особенности Windows 10 и Windows 11

Для данного проекта существенной разницы между Windows 10 и Windows 11 нет. Инструкция одинакова для обеих систем.

Практические отличия могут быть только в окружении:

- на Windows 11 чаще уже доступен `winget`;
- на Windows 10 `winget` может отсутствовать, тогда `ffmpeg` удобнее установить вручную;
- в обеих системах PowerShell может ограничивать запуск скриптов.

## Типовые проблемы и решения

### PowerShell не дает запустить `Makefile.ps1`

Если появляется ошибка, связанная с execution policy, временно разрешите запуск скриптов для текущего процесса:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

После этого повторите:

```powershell
.\Makefile.ps1 install
.\Makefile.ps1 run
```

### Не найден `python`

Проверьте, установлен ли Python и добавлен ли он в `PATH`.

Если команда `python --version` не работает, но установлен launcher, попробуйте:

```powershell
py -3.11 --version
```

### Не найдены `ffmpeg` или `ffprobe`

Это означает, что FFmpeg не установлен, либо PowerShell был открыт до изменения `PATH`, либо папка `bin` не добавлена в `PATH`.

Проверьте команды:

```powershell
ffmpeg -version
ffprobe -version
```

Если FFmpeg только что был установлен, полностью закройте PowerShell и откройте его заново.

### Долго ставятся зависимости `ultralytics` и `easyocr`

Это ожидаемо. Эти зависимости тяжелее обычных веб-библиотек и могут устанавливаться заметно дольше.

### Отсутствуют папки `input`, `outputs`, `logs` или файл `state.json`

Это не ошибка. Рабочие каталоги создаются автоматически при работе приложения. Для Docker-запуска файл `state.json` нужно создать перед `docker compose up`.

## Минимальный сценарий проверки

Для подтверждения, что проект разворачивается на Windows, достаточно выполнить:

```powershell
python --version
ffmpeg -version
ffprobe -version
.\Makefile.ps1 install
.\Makefile.ps1 run
```

Если после этого страница `http://localhost:8888` открывается в браузере, базовое развертывание прошло успешно.
