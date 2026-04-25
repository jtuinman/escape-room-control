import time
from dataclasses import dataclass

from gpiozero import Button

from .config import ACTIVE_WHEN_OPEN, INPUTS
from .state_machine import StateMachine


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
    ctx.set_input_state(label, state)

    ctx.broadcaster.publish({
        "type": "input",
        "label": label,
        "state": state,
        "ts": time.time(),
    })


def evaluate_rules_on_change(ctx, changed_label: str) -> None:
    StateMachine(ctx).handle_input_change(changed_label)


def init_gpio(ctx) -> None:
    for label, cfg in INPUTS.items():
        pin = int(cfg["pin"])
        bounce_time = float(cfg.get("bounce_time", 0.05))
        role = str(cfg.get("role", ""))

        btn = Button(pin, pull_up=True, active_state=None, bounce_time=bounce_time)

        ctx.register_input_device(label, InputDevice(
            label=label,
            pin=pin,
            bounce_time=bounce_time,
            role=role,
            button=btn,
        ))

        set_input_state(ctx, label, logical_active_from_button(btn))

        def on_change(lab=label):
            btn = ctx.get_input_button(lab)
            set_input_state(ctx, lab, logical_active_from_button(btn))
            evaluate_rules_on_change(ctx, lab)

        btn.when_pressed = on_change
        btn.when_released = on_change
