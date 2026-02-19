import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "state.json"

_lock = RLock()
_runtime_state: dict | None = None


def _default_state():
    return {
        "video": None,
        "converted": None,
        "protocol_csv": None,
        "processing": False,
        "phase": "idle",
        "progress": 0,
        "phase_started_at": None,
        "cancel_requested": False,
        "results_text": "",
        "playback": {
            "source": None,
            "position": 0
        },
        "video_bytes": None,
        "converted_bytes": None,
        "bboxes": [],
        "timestamps": [],
        "events": [],
        "settings": {
            "frame_interval_sec": 3,
            "conf_limit": 3,
            "session_timeout_sec": 240,
            "phantom_timeout_sec": 60,
        },
        "ui": {
            "sidebar_hidden": False,
            "right_panel_collapsed": True,
            "sidebar_pinned": True,
            "right_panel_pinned": False,
            "events_open": True,
            "state_open": False,
        }
    }


def _persisted_state(state: dict) -> dict:
    """Persist only launch settings to keep each run fresh."""
    settings = state.get("settings") if isinstance(state.get("settings"), dict) else {}
    return {"settings": settings}


def load_state():
    with _lock:
        global _runtime_state
        if _runtime_state is not None:
            return dict(_runtime_state)

        default = _default_state()

        if not STATE_FILE.exists():
            _runtime_state = dict(default)
            save_state(_runtime_state)
            return dict(_runtime_state)

        try:
            loaded = json.loads(STATE_FILE.read_text() or "{}")
        except json.JSONDecodeError:
            loaded = {}

        if not isinstance(loaded, dict):
            loaded = {}

        # Only settings are persisted between runs.
        settings = loaded.get("settings", {})
        if not isinstance(settings, dict):
            settings = {}
        state = dict(default)
        state["settings"] = {**default["settings"], **settings}
        _runtime_state = state

        if _persisted_state(state) != loaded:
            save_state(state)

        return dict(_runtime_state)


def save_state(state: dict):
    with _lock:
        STATE_FILE.write_text(json.dumps(_persisted_state(state), indent=2))


def update_state(patch: dict):
    with _lock:
        state = load_state()
        state.update(patch)
        global _runtime_state
        _runtime_state = dict(state)
        STATE_FILE.write_text(json.dumps(_persisted_state(state), indent=2))
        return dict(_runtime_state)


def append_event(
    message: str,
    *,
    event_type: str = "event",
    level: str = "info",
    details: dict | None = None
):
    with _lock:
        state = load_state()
        events = state.get("events", [])

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "level": level,
            "message": message
        }

        if details:
            entry["details"] = details

        events.append(entry)
        state["events"] = events[-300:]
        global _runtime_state
        _runtime_state = dict(state)
        STATE_FILE.write_text(json.dumps(_persisted_state(state), indent=2))
        return entry
