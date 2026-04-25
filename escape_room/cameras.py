import json

from .config import CAMERA_STREAMS_FILE


DEFAULT_CAMERA_STREAMS = {
    "cam1": {"url": ""},
    "cam2": {"url": ""},
    "cam3": {"url": ""},
}


def load_camera_streams() -> dict:
    streams = json.loads(json.dumps(DEFAULT_CAMERA_STREAMS))

    try:
        raw = CAMERA_STREAMS_FILE.read_text(encoding="utf-8")
        loaded = json.loads(raw)
    except FileNotFoundError:
        return streams
    except (json.JSONDecodeError, OSError):
        return streams

    if not isinstance(loaded, dict):
        return streams

    for key in streams:
        value = loaded.get(key, {})
        if isinstance(value, dict):
            streams[key]["url"] = str(value.get("url", "")).strip()
        elif isinstance(value, str):
            streams[key]["url"] = value.strip()

    return streams
