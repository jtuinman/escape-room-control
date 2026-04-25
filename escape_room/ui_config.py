import re
from typing import List

from .cameras import load_camera_streams
from .config import RELAY_LABELS, RELAYS, STATE_LABELS, VALID_GAME_STATES


def get_state_ui_config() -> List[dict]:
    return [
        {
            "id": state_id,
            "label": STATE_LABELS.get(state_id, state_id),
            "selectable": True,
            "order": order,
        }
        for order, state_id in enumerate(VALID_GAME_STATES)
    ]


def get_relay_ui_config() -> List[dict]:
    return [
        {
            "id": relay_id,
            "label": RELAY_LABELS.get(relay_id, relay_id),
            "order": order,
            "enabled": True,
        }
        for order, relay_id in enumerate(RELAYS)
    ]


def get_camera_ui_config() -> List[dict]:
    cameras = []
    for order, (camera_id, cfg) in enumerate(load_camera_streams().items()):
        label = ""
        url = ""

        if isinstance(cfg, dict):
            label = str(cfg.get("label", "")).strip()
            url = str(cfg.get("url", "")).strip()
        elif isinstance(cfg, str):
            url = cfg.strip()

        cameras.append({
            "id": camera_id,
            "label": label or _camera_label_fallback(camera_id),
            "url": url,
            "order": order,
            "visible": True,
        })

    return cameras


def get_ui_config() -> dict:
    return {
        "states": get_state_ui_config(),
        "relays": get_relay_ui_config(),
        "cameras": get_camera_ui_config(),
    }


def _camera_label_fallback(camera_id: str) -> str:
    match = re.fullmatch(r"cam(\d+)", camera_id)
    if match:
        return f"Camera {match.group(1)}"
    return camera_id
