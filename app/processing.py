import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

from app.detector import DetectorUnavailableError, PersonNumberDetector
from app.matcher import ProtocolMatcher


class CancelledError(Exception):
    pass


class ProcessingError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ffprobe_duration(video_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        if stderr:
            raise RuntimeError(f"ffprobe failed: {stderr}")
        raise RuntimeError("ffprobe failed")

    try:
        return float((proc.stdout or "0").strip())
    except ValueError as exc:
        raise RuntimeError("cannot parse video duration") from exc


def validate_video_file(video_path: Path):
    try:
        _ffprobe_duration(video_path)
    except RuntimeError as exc:
        raise ProcessingError(f"invalid video file: {video_path.name}: {exc}") from exc


def _ffprobe_stream_info(video_path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError("ffprobe failed for stream info")
    return json.loads(proc.stdout or "{}")


def is_browser_playable(video_path: Path) -> bool:
    ext = video_path.suffix.lower()
    if ext not in {".mp4", ".webm", ".ogg"}:
        return False

    try:
        info = _ffprobe_stream_info(video_path)
    except Exception:
        return False

    streams = info.get("streams", [])
    vcodec = None
    acodec = None
    for stream in streams:
        if stream.get("codec_type") == "video" and not vcodec:
            vcodec = (stream.get("codec_name") or "").lower()
        if stream.get("codec_type") == "audio" and not acodec:
            acodec = (stream.get("codec_name") or "").lower()

    if not vcodec:
        return False

    if ext == ".mp4":
        return vcodec in {"h264", "avc1", "vp9", "av1", "hevc"}
    if ext == ".webm":
        return vcodec in {"vp8", "vp9", "av1"}
    if ext == ".ogg":
        return vcodec in {"theora"}

    return False


def _ffmpeg_time_to_seconds(raw: str) -> float:
    hh, mm, ss = raw.split(":")
    return int(hh) * 3600 + int(mm) * 60 + float(ss)


def convert_for_web(
    source_path: Path,
    converted_dir: Path,
    *,
    check_cancel,
    progress_cb,
    event_cb,
) -> Path:
    converted_dir.mkdir(parents=True, exist_ok=True)

    if check_cancel():
        raise CancelledError("cancelled before conversion")

    source_hash = _sha256_file(source_path)[:12]
    target_path = converted_dir / f"{source_path.stem}-{source_hash}.mp4"

    if target_path.exists():
        try:
            _ffprobe_duration(target_path)
            event_cb(f"Conversion cache hit: {target_path.name}")
            progress_cb(100)
            return target_path
        except RuntimeError:
            target_path.unlink(missing_ok=True)
            event_cb(f"Conversion cache invalidated: {target_path.name}")

    duration = _ffprobe_duration(source_path)
    event_cb(f"Converting with ffmpeg -> {target_path.name}")

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        str(target_path),
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    time_re = re.compile(r"time=(\d\d:\d\d:\d\d(?:\.\d+)?)")

    try:
        assert proc.stderr is not None
        for line in proc.stderr:
            if check_cancel():
                proc.kill()
                raise CancelledError("cancelled during conversion")

            match = time_re.search(line)
            if not match or duration <= 0:
                continue

            elapsed = _ffmpeg_time_to_seconds(match.group(1))
            progress = min(99, int((elapsed / duration) * 100))
            progress_cb(progress)
    finally:
        proc.wait()

    if proc.returncode != 0:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg conversion failed")

    try:
        _ffprobe_duration(target_path)
    except RuntimeError:
        target_path.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg produced invalid output")

    progress_cb(100)
    event_cb("Conversion complete")
    return target_path


def ensure_playable_input(
    source_path: Path,
    converted_dir: Path,
    *,
    check_cancel,
    progress_cb,
    event_cb,
) -> tuple[Path, bool]:
    if is_browser_playable(source_path):
        progress_cb(100)
        event_cb("Source video is browser-playable, conversion skipped")
        return source_path, False

    converted = convert_for_web(
        source_path,
        converted_dir,
        check_cancel=check_cancel,
        progress_cb=progress_cb,
        event_cb=event_cb,
    )
    return converted, True


def _format_time(seconds: float) -> str:
    s = max(0, int(seconds))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def run_protocol_analysis(
    video_path: Path,
    protocol_csv: Path,
    model_path: Path,
    *,
    check_cancel,
    progress_cb,
    event_cb,
) -> dict:
    try:
        import cv2
    except Exception as exc:  # pragma: no cover
        raise ProcessingError("opencv-python-headless is required for processing") from exc

    matcher = ProtocolMatcher(protocol_csv)
    if not matcher.db:
        raise ProcessingError("protocol CSV is missing or has unsupported columns")

    try:
        detector = PersonNumberDetector(model_path)
    except DetectorUnavailableError as exc:
        raise ProcessingError(str(exc)) from exc

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ProcessingError(f"cannot open video: {video_path.name}")

    duration = _ffprobe_duration(video_path)
    total_steps = max(1, int(duration * 2))
    step = 0
    frame_ms = 0

    # temporal smoothing / confirmation buffer from archive logic
    conf_limit = 3
    candidates: dict[str, dict] = {}
    confirmed = set()
    results = []
    latest_bboxes = []

    event_cb("Analysis started (YOLO fast, 2 fps)")

    try:
        while cap.isOpened() and step < total_steps:
            if check_cancel():
                raise CancelledError("cancelled during analysis")

            cap.set(cv2.CAP_PROP_POS_MSEC, frame_ms)
            ok, frame = cap.read()
            if not ok:
                break

            matched, bboxes = detector.detect(frame, matcher)
            latest_bboxes = bboxes

            time_str = _format_time(frame_ms / 1000)
            time_sec = round(frame_ms / 1000, 2)

            for num, name in matched:
                if num in confirmed:
                    continue
                if num not in candidates:
                    candidates[num] = {
                        "count": 1,
                        "first_time": time_str,
                        "first_sec": time_sec,
                        "name": name,
                    }
                else:
                    candidates[num]["count"] += 1
                    if candidates[num]["count"] >= conf_limit:
                        confirmed.add(num)
                        results.append({
                            "time": candidates[num]["first_sec"],
                            "label": f"#{num} {name}",
                            "num": num,
                            "name": name,
                            "time_text": candidates[num]["first_time"],
                        })
                        del candidates[num]

            progress = int(((step + 1) / total_steps) * 100)
            progress_cb(progress)

            if step % 20 == 0:
                event_cb(f"Analysis progress: {progress}%")

            step += 1
            frame_ms += 500

    finally:
        cap.release()

    results.sort(key=lambda x: x.get("time", 0))
    lines = [f"{item['time_text']} #{item['num']} {item['name']}" for item in results]

    event_cb("Analysis complete")
    return {
        "timestamps": [{"time": r["time"], "label": r["label"]} for r in results],
        "bboxes": latest_bboxes,
        "results_text": "\n".join(lines),
    }
