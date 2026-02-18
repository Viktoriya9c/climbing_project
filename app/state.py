import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "state.json"

_lock = RLock()


def _default_state():
    return {
        "video": None,
        "converted": None,
        "protocol_csv": None,
        "processing": False,
        "phase": "idle",
        "progress": 0,
        "cancel_requested": False,
        "results_text": "",
        "playback": {
            "source": None,
            "position": 0
        },
        "bboxes": [],
        "timestamps": [],
        "events": [],
        "ui": {
            "sidebar_hidden": False,
            "right_panel_collapsed": False,
            "sidebar_pinned": False,
            "right_panel_pinned": False,
            "events_open": True,
            "state_open": False,
        }
    }


def load_state():
    with _lock:
        default = _default_state()

        if not STATE_FILE.exists():
            save_state(default)
            return default

        try:
            loaded = json.loads(STATE_FILE.read_text() or "{}")
        except json.JSONDecodeError:
            loaded = {}

        if not isinstance(loaded, dict):
            loaded = {}

        state = {**default, **loaded}
        loaded_ui = loaded.get("ui", {})
        if isinstance(loaded_ui, dict):
            state["ui"] = {**default["ui"], **loaded_ui}
        else:
            state["ui"] = dict(default["ui"])

        if state != loaded:
            save_state(state)

        return state


def save_state(state: dict):
    with _lock:
        STATE_FILE.write_text(json.dumps(state, indent=2))


def update_state(patch: dict):
    with _lock:
        state = load_state()
        state.update(patch)
        STATE_FILE.write_text(json.dumps(state, indent=2))
        return state


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
        STATE_FILE.write_text(json.dumps(state, indent=2))
        return entry
