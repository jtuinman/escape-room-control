import re
from typing import List

from .cameras import load_camera_streams
from .config import (
    INPUTS,
    INPUT_UI,
    LANGUAGE_UI,
    RELAY_UI,
    RELAYS,
    STATE_UI,
    UI_TEXT,
    VALID_GAME_STATES,
)


def get_state_ui_config() -> List[dict]:
    return [
        {
            "id": state_id,
            "label": STATE_UI.get(state_id, {}).get("label", state_id),
            "selectable": True,
            "order": STATE_UI.get(state_id, {}).get("order", order),
        }
        for order, state_id in enumerate(VALID_GAME_STATES)
    ]


def get_relay_ui_config() -> List[dict]:
    return [
        {
            "id": relay_id,
            "label": RELAY_UI.get(relay_id, {}).get("label", relay_id),
            "order": RELAY_UI.get(relay_id, {}).get("order", order),
            "enabled": True,
        }
        for order, relay_id in enumerate(RELAYS)
    ]


def get_input_ui_config() -> List[dict]:
    inputs = []
    for order, (input_id, cfg) in enumerate(INPUTS.items()):
        role = str(cfg.get("role", ""))
        inputs.append({
            "id": input_id,
            "role": role,
            "label": INPUT_UI.get(role, {}).get("label", input_id),
            "order": order,
        })
    return inputs


def get_camera_ui_config() -> List[dict]:
    cameras = []
    for order, (camera_id, cfg) in enumerate(load_camera_streams().items()):
        label = ""
        url = ""

        if isinstance(cfg, dict):
            label = str(cfg.get("label", "")).strip()
            url = str(cfg.get("url", "")).strip()
            visible = bool(cfg.get("visible", True))
        elif isinstance(cfg, str):
            url = cfg.strip()
            visible = True
        else:
            visible = True

        cameras.append({
            "id": camera_id,
            "label": label or _camera_label_fallback(camera_id),
            "url": url,
            "order": order,
            "visible": visible,
        })

    return cameras


def get_ui_config() -> dict:
    return {
        "states": get_state_ui_config(),
        "relays": get_relay_ui_config(),
        "inputs": get_input_ui_config(),
        "cameras": get_camera_ui_config(),
        "languages": LANGUAGE_UI,
        "text": UI_TEXT,
    }


def _camera_label_fallback(camera_id: str) -> str:
    match = re.fullmatch(r"cam(\d+)", camera_id)
    if match:
        return f"Camera {match.group(1)}"
    return camera_id
