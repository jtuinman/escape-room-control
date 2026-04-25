import time
from dataclasses import dataclass
from typing import Optional

from gpiozero import Button

from .config import ACTIVE_WHEN_OPEN, INPUTS


@dataclass
class InputDevice:
    label: str
    pin: int
    bounce_time: float
    role: str
    button: Button


def logical_active_from_button(btn: Button) -> bool:
    pressed = bool(btn.is_pressed)
    return (not pressed) if ACTIVE_WHEN_OPEN else pressed


def set_input_state(ctx, label: str, is_active: bool) -> None:
    state = "ACTIVE" if is_active else "INACTIVE"
    with ctx.lock:
        prev = ctx.current_inputs.get(label)
        ctx.previous_inputs[label] = prev if prev is not None else state
        ctx.current_inputs[label] = state

    ctx.broadcaster.publish({
        "type": "input",
        "label": label,
        "state": state,
        "ts": time.time(),
    })


def get_label_by_role(role: str) -> Optional[str]:
    for label, cfg in INPUTS.items():
        if cfg.get("role") == role:
            return label
    return None


def evaluate_rules_on_change(ctx, changed_label: str) -> None:
    with ctx.lock:
        gs = ctx.game_state
        snapshot = dict(ctx.current_inputs)
        prev_snapshot = dict(ctx.previous_inputs)

    pb1 = get_label_by_role("pb1")
    pb2 = get_label_by_role("pb2")
    t1 = get_label_by_role("t1")
    t2 = get_label_by_role("t2")

    def is_active(label: Optional[str]) -> bool:
        if not label:
            return False
        return snapshot.get(label) == "ACTIVE"

    def was_inactive(label: Optional[str]) -> bool:
        if not label:
            return False
        return prev_snapshot.get(label) == "INACTIVE"

    if gs == "idle":
        return

    if gs == "scene_1":
        if is_active(pb1) and is_active(pb2):
            from .state import set_game_state

            set_game_state(ctx, "scene_2", reason="pb1+pb2_overlap")
        return

    if gs == "scene_2":
        if changed_label == t1 and was_inactive(t1) and is_active(t1):
            from .state import set_game_state

            set_game_state(ctx, "end_game", reason="toggle_1_edge")
        return

    if gs == "end_game":
        if changed_label == t2 and was_inactive(t2) and is_active(t2):
            from .timer import stop_timer

            stop_timer(ctx, reason="toggle_2_edge_stop_timer")
        return


def init_gpio(ctx) -> None:
    for label, cfg in INPUTS.items():
        pin = int(cfg["pin"])
        bounce_time = float(cfg.get("bounce_time", 0.05))
        role = str(cfg.get("role", ""))

        btn = Button(pin, pull_up=True, active_state=None, bounce_time=bounce_time)

        ctx.devices[label] = InputDevice(
            label=label,
            pin=pin,
            bounce_time=bounce_time,
            role=role,
            button=btn,
        )

        set_input_state(ctx, label, logical_active_from_button(btn))

        def on_change(lab=label):
            dev = ctx.devices[lab].button
            set_input_state(ctx, lab, logical_active_from_button(dev))
            evaluate_rules_on_change(ctx, lab)

        btn.when_pressed = on_change
        btn.when_released = on_change
