import time
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import unquote, urlparse

import requests
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.processing import (
    CancelledError,
    ProcessingError,
    ensure_playable_input,
    run_protocol_analysis,
    validate_video_file,
)
from app.state import append_event, load_state, save_state, update_state

try:
    import yt_dlp
except ImportError:  # pragma: no cover - optional at runtime
    yt_dlp = None

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
CONVERTED_DIR = BASE_DIR / "converted"
PROTOCOL_DIR = BASE_DIR / "input" / "protocols"
MODEL_PATH = BASE_DIR / "models" / "yolov8n.pt"
UPLOAD_DIR.mkdir(exist_ok=True)
CONVERTED_DIR.mkdir(exist_ok=True)
PROTOCOL_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
ACTIVE_PHASES = {"uploading", "downloading", "converting", "processing"}

_worker_lock = Lock()
_worker_thread: Thread | None = None


def _set_worker(thread: Thread):
    global _worker_thread
    with _worker_lock:
        _worker_thread = thread


def _clear_worker():
    global _worker_thread
    with _worker_lock:
        _worker_thread = None


def _worker_active() -> bool:
    with _worker_lock:
        return _worker_thread is not None and _worker_thread.is_alive()


def _cancel_requested() -> bool:
    return bool(load_state().get("cancel_requested"))


def _safe_name(raw_name: str | None, fallback: str) -> str:
    cleaned = Path(unquote(raw_name or "")).name.strip()
    return cleaned or fallback


def _normalize_phase(raw: str | None) -> str:
    phase = (raw or "idle").strip().lower()
    if phase in {
        "idle", "uploading", "downloading", "uploaded", "downloaded",
        "converting", "converted", "processing", "done", "error"
    }:
        return phase
    return "idle"


def _reset_state(*, clear_events: bool = False):
    state = load_state()
    state.update({
        "video": None,
        "converted": None,
        "protocol_csv": None,
        "processing": False,
        "phase": "idle",
        "progress": 0,
        "cancel_requested": False,
        "results_text": "",
        "playback": {"source": None, "position": 0},
        "bboxes": [],
        "timestamps": [],
    })
    if clear_events:
        state["events"] = []
    save_state(state)


def _reconcile_runtime_state() -> dict:
    state = load_state()
    changed = False

    phase = _normalize_phase(state.get("phase"))
    if phase != state.get("phase"):
        state["phase"] = phase
        changed = True

    processing = bool(state.get("processing"))
    worker_active = _worker_active()
    active_phase = phase in ACTIVE_PHASES

    if (active_phase or processing) and not worker_active:
        state["processing"] = False
        state["cancel_requested"] = False
        state["phase"] = "idle"
        state["progress"] = 0
        changed = True
        append_event(
            "Runtime reconcile: worker missing, phase reset to idle",
            event_type="process",
            level="warning",
        )

    if changed:
        save_state(state)

    return state


def _download_with_ytdlp(url: str) -> Path:
    if yt_dlp is None:
        raise RuntimeError("yt-dlp is not installed")

    append_event("Downloader selected: yt-dlp", event_type="process", details={"url": url})

    output_template = str(UPLOAD_DIR / "%(id)s.%(ext)s")

    def hook(data: dict):
        if _cancel_requested():
            raise CancelledError("download cancelled")

        if data.get("status") != "downloading":
            return

        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
        downloaded = data.get("downloaded_bytes") or 0
        if total:
            update_state({"progress": int((downloaded * 100) / total)})

    opts = {
        "format": "best[ext=mp4][height<=1080]/best[ext=mp4]/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
        "overwrites": True,
        "restrictfilenames": True,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = Path(ydl.prepare_filename(info)).resolve()

    if file_path.parent != UPLOAD_DIR.resolve() or not file_path.exists():
        raise RuntimeError("yt-dlp did not produce a local file")

    append_event("yt-dlp download complete", event_type="process", details={"file": file_path.name})
    return file_path


def _download_direct(url: str) -> Path:
    parsed = urlparse(url)
    fallback_name = f"download-{int(time.time())}.mp4"
    local_name = _safe_name(parsed.path, fallback_name)
    if "." not in local_name:
        local_name = f"{local_name}.mp4"

    file_path = (UPLOAD_DIR / local_name).resolve()
    if file_path.parent != UPLOAD_DIR.resolve():
        raise RuntimeError("invalid download path")

    append_event("Downloader selected: direct HTTP", event_type="process", details={"file": local_name})

    with requests.get(url, stream=True, timeout=30) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0

        with file_path.open("wb") as out:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                if _cancel_requested():
                    file_path.unlink(missing_ok=True)
                    raise CancelledError("download cancelled")

                out.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    update_state({"progress": int((downloaded * 100) / total)})

    if not file_path.exists() or file_path.stat().st_size == 0:
        raise RuntimeError("downloaded file is empty")

    return file_path


@app.middleware("http")
async def log_requests(request: Request, call_next):
    path = request.url.path
    skip_prefixes = ("/static",)
    should_log = path not in {"/state", "/health"} and not path.startswith(skip_prefixes)

    started_at = time.perf_counter()
    if should_log:
        append_event(
            f"{request.method} {path} started",
            event_type="request",
            details={"query": str(request.url.query)}
        )

    try:
        response = await call_next(request)
    except Exception as exc:
        if should_log:
            append_event(
                f"{request.method} {path} failed: {exc}",
                event_type="request",
                level="error",
            )
        raise

    if should_log:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        append_event(
            f"{request.method} {path} -> {response.status_code}",
            event_type="request",
            details={"elapsed_ms": elapsed_ms}
        )

    return response


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/video/{filename}")
async def get_video(filename: str):
    file_path = (UPLOAD_DIR / filename).resolve()
    if file_path.parent != UPLOAD_DIR.resolve() or not file_path.exists():
        raise HTTPException(status_code=404, detail="video not found")
    return FileResponse(path=file_path)


@app.get("/converted/{filename}")
async def get_converted_video(filename: str):
    file_path = (CONVERTED_DIR / filename).resolve()
    if file_path.parent != CONVERTED_DIR.resolve() or not file_path.exists():
        raise HTTPException(status_code=404, detail="converted video not found")
    return FileResponse(path=file_path)


@app.get("/state")
async def get_state():
    return _reconcile_runtime_state()


@app.post("/state")
async def patch_state(payload: dict):
    allowed = {"results_text", "ui", "playback"}
    patch = {k: payload[k] for k in allowed if k in payload}
    if not patch:
        return JSONResponse({"error": "no allowed fields"}, status_code=400)

    if "ui" in patch and not isinstance(patch["ui"], dict):
        return JSONResponse({"error": "ui must be object"}, status_code=400)
    if "playback" in patch:
        playback = patch["playback"]
        if not isinstance(playback, dict):
            return JSONResponse({"error": "playback must be object"}, status_code=400)
        source = playback.get("source")
        position = playback.get("position")
        if source is not None and not isinstance(source, str):
            return JSONResponse({"error": "playback.source must be string or null"}, status_code=400)
        if not isinstance(position, (int, float)):
            return JSONResponse({"error": "playback.position must be number"}, status_code=400)
        patch["playback"] = {"source": source, "position": max(0, float(position))}

    update_state(patch)
    return {"status": "ok"}


@app.post("/state/reset")
async def reset_state(payload: dict | None = None):
    if _worker_active():
        return JSONResponse({"error": "cannot reset during active process"}, status_code=409)

    clear_events = bool((payload or {}).get("clear_events"))
    _reset_state(clear_events=clear_events)
    append_event("State reset requested from UI", event_type="event", level="warning")
    return {"status": "ok"}


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    file_name = _safe_name(file.filename, "upload.bin")
    file_path = UPLOAD_DIR / file_name

    update_state({
        "phase": "uploading",
        "progress": 0,
        "processing": True,
        "cancel_requested": False,
    })
    append_event("Upload started", event_type="process", details={"file": file_name})

    total_read = 0
    try:
        with file_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                total_read += len(chunk)
                if total_read > MAX_UPLOAD_BYTES:
                    out.close()
                    file_path.unlink(missing_ok=True)
                    update_state({"phase": "error", "processing": False, "progress": 0})
                    append_event(
                        "Upload rejected: file exceeds 2GB",
                        event_type="process",
                        level="error",
                    )
                    return JSONResponse({"error": "file too large"}, status_code=413)

                out.write(chunk)
                if total_read % (20 * 1024 * 1024) == 0:
                    append_event(
                        f"Upload progress: {total_read // (1024 * 1024)} MB",
                        event_type="process"
                    )
    except Exception as exc:
        update_state({"phase": "error", "processing": False, "progress": 0})
        append_event(f"Upload failed: {exc}", event_type="process", level="error")
        return JSONResponse({"error": "upload failed"}, status_code=500)

    try:
        validate_video_file(file_path)
    except ProcessingError as exc:
        file_path.unlink(missing_ok=True)
        patch = {"phase": "error", "processing": False, "progress": 0}
        if load_state().get("video") == file_name:
            patch["video"] = None
            patch["converted"] = None
        update_state(patch)
        append_event(f"Upload failed: {exc}", event_type="process", level="error")
        return JSONResponse({"error": "uploaded file is not a valid video"}, status_code=400)

    update_state({
        "video": file_name,
        "converted": None,
        "protocol_csv": load_state().get("protocol_csv"),
        "phase": "uploaded",
        "progress": 100,
        "processing": False,
        "cancel_requested": False,
        "bboxes": [],
        "timestamps": [],
        "results_text": "",
    })
    append_event("Upload complete", event_type="process", details={"file": file_name})

    return {"status": "ok", "filename": file_name}


@app.post("/protocol/upload")
async def upload_protocol(file: UploadFile = File(...)):
    file_name = _safe_name(file.filename, "protocol.csv")
    if not file_name.lower().endswith(".csv"):
        return JSONResponse({"error": "protocol file must be .csv"}, status_code=400)

    path = (PROTOCOL_DIR / file_name).resolve()
    if path.parent != PROTOCOL_DIR.resolve():
        return JSONResponse({"error": "invalid protocol filename"}, status_code=400)

    data = await file.read()
    if not data:
        return JSONResponse({"error": "empty csv"}, status_code=400)

    path.write_bytes(data)
    update_state({"protocol_csv": file_name})
    append_event("Protocol CSV uploaded", event_type="process", details={"file": file_name})
    return {"status": "ok", "filename": file_name}


def _download_worker(url: str):
    try:
        update_state({
            "phase": "downloading",
            "progress": 0,
            "processing": True,
            "cancel_requested": False,
        })
        append_event("Download started", event_type="process", details={"url": url})

        host = (urlparse(url).hostname or "").lower()
        use_ytdlp = ("vk.com" in host or "youtube.com" in host or "youtu.be" in host)

        try:
            if use_ytdlp:
                file_path = _download_with_ytdlp(url)
            else:
                file_path = _download_direct(url)
        except Exception as primary_error:
            if use_ytdlp:
                if yt_dlp is None:
                    raise RuntimeError(
                        "yt-dlp is required for this URL (install dependency and restart service)"
                    ) from primary_error
                append_event(
                    f"yt-dlp failed, fallback to direct download: {primary_error}",
                    event_type="process",
                    level="warning",
                )
                file_path = _download_direct(url)
            else:
                raise

        validate_video_file(file_path)

        update_state({
            "video": file_path.name,
            "converted": None,
            "protocol_csv": load_state().get("protocol_csv"),
            "phase": "downloaded",
            "progress": 100,
            "processing": False,
            "cancel_requested": False,
            "bboxes": [],
            "timestamps": [],
            "results_text": "",
        })
        append_event("Download complete", event_type="process", details={"file": file_path.name})

    except CancelledError:
        update_state({"phase": "idle", "progress": 0, "processing": False, "cancel_requested": False})
        append_event("Download cancelled", event_type="process", level="warning")
    except Exception as exc:
        update_state({"phase": "error", "processing": False})
        append_event(f"Download failed: {exc}", event_type="process", level="error")
    finally:
        _clear_worker()


@app.post("/download")
async def download_video(payload: dict):
    if _worker_active():
        return JSONResponse({"error": "another process is running"}, status_code=409)

    url = str(payload.get("url", "")).strip()
    if not url:
        return JSONResponse({"error": "no url"}, status_code=400)

    worker = Thread(target=_download_worker, args=(url,), daemon=True)
    _set_worker(worker)
    worker.start()
    return {"status": "accepted"}


def _processing_worker(source_name: str):
    try:
        source_path = (UPLOAD_DIR / source_name).resolve()
        if source_path.parent != UPLOAD_DIR.resolve() or not source_path.exists():
            raise FileNotFoundError("source video is missing")
        state = load_state()
        protocol_name = state.get("protocol_csv")
        if not protocol_name:
            raise ProcessingError("upload CSV protocol before processing")

        protocol_path = (PROTOCOL_DIR / protocol_name).resolve()
        if protocol_path.parent != PROTOCOL_DIR.resolve() or not protocol_path.exists():
            raise ProcessingError("protocol CSV not found on disk")

        update_state({
            "phase": "converting",
            "progress": 0,
            "processing": True,
            "cancel_requested": False,
            "bboxes": [],
            "timestamps": [],
            "results_text": "",
        })
        append_event("Pipeline started", event_type="process", details={"video": source_name})

        analysis_path, was_converted = ensure_playable_input(
            source_path,
            CONVERTED_DIR,
            check_cancel=_cancel_requested,
            progress_cb=lambda p: update_state({"progress": p}),
            event_cb=lambda msg: append_event(msg, event_type="process"),
        )

        if _cancel_requested():
            raise CancelledError("cancelled after conversion")

        update_state({
            "phase": "converted",
            "progress": 100,
            "converted": analysis_path.name if was_converted else None,
        })

        update_state({"phase": "processing", "progress": 0})
        analysis = run_protocol_analysis(
            analysis_path,
            protocol_path,
            MODEL_PATH,
            check_cancel=_cancel_requested,
            progress_cb=lambda p: update_state({"progress": p}),
            event_cb=lambda msg: append_event(msg, event_type="process"),
        )

        if _cancel_requested():
            raise CancelledError("cancelled before finishing")

        update_state({
            "phase": "done",
            "progress": 100,
            "processing": False,
            "cancel_requested": False,
            **analysis,
        })
        append_event("Pipeline done", event_type="process")

    except CancelledError:
        update_state({"phase": "idle", "progress": 0, "processing": False, "cancel_requested": False})
        append_event("Pipeline cancelled", event_type="process", level="warning")
    except FileNotFoundError:
        update_state({"phase": "error", "processing": False})
        append_event("Pipeline failed: source video not found", event_type="process", level="error")
    except ProcessingError as exc:
        update_state({"phase": "error", "processing": False})
        append_event(f"Pipeline failed: {exc}", event_type="process", level="error")
    except Exception as exc:
        update_state({"phase": "error", "processing": False})
        append_event(f"Pipeline failed: {exc}", event_type="process", level="error")
    finally:
        _clear_worker()


@app.post("/process/start")
async def start_processing():
    if _worker_active():
        return JSONResponse({"error": "another process is running"}, status_code=409)

    state = load_state()
    source_name = state.get("video")
    if not source_name:
        return JSONResponse({"error": "no video selected"}, status_code=400)
    source_path = (UPLOAD_DIR / source_name).resolve()
    if source_path.parent != UPLOAD_DIR.resolve() or not source_path.exists():
        update_state({"phase": "error", "processing": False, "progress": 0, "video": None})
        append_event("Pipeline failed: selected video not found", event_type="process", level="error")
        return JSONResponse({"error": "selected video not found"}, status_code=400)
    try:
        validate_video_file(source_path)
    except ProcessingError as exc:
        update_state({"phase": "error", "processing": False, "progress": 0, "video": None, "converted": None})
        append_event(f"Pipeline failed: {exc}", event_type="process", level="error")
        return JSONResponse({"error": "selected file is not a valid video"}, status_code=400)
    protocol_name = state.get("protocol_csv")
    if not protocol_name:
        return JSONResponse({"error": "no protocol csv uploaded"}, status_code=400)
    protocol_path = (PROTOCOL_DIR / protocol_name).resolve()
    if protocol_path.parent != PROTOCOL_DIR.resolve() or not protocol_path.exists():
        return JSONResponse({"error": "protocol csv not found"}, status_code=400)

    worker = Thread(target=_processing_worker, args=(source_name,), daemon=True)
    _set_worker(worker)
    worker.start()
    return {"status": "accepted"}


@app.post("/process/cancel")
async def cancel_processing():
    if not _worker_active():
        return JSONResponse({"error": "no active process"}, status_code=409)

    update_state({"cancel_requested": True})
    append_event("Cancellation requested", event_type="process", level="warning")
    return {"status": "accepted"}
