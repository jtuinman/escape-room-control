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
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{CAMERA_STREAMS_FILE} contains invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"{CAMERA_STREAMS_FILE} could not be read: {exc}") from exc

    if not isinstance(loaded, dict):
        raise RuntimeError(f"{CAMERA_STREAMS_FILE} root must be a JSON object")

    for key, value in loaded.items():
        if key not in streams:
            streams[key] = {"url": ""}

        if isinstance(value, dict):
            streams[key]["url"] = str(value.get("url", "")).strip()
            if "label" in value:
                streams[key]["label"] = str(value.get("label", "")).strip()
        elif isinstance(value, str):
            streams[key]["url"] = value.strip()

    return streams
