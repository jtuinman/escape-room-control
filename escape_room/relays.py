import time

from gpiozero import OutputDevice

from .config import RELAY_ACTIVE_HIGH, RELAY_HARDWARE, RELAY_PATTERNS, RELAYS


def init_relays(ctx) -> None:
    for name, cfg in RELAY_HARDWARE.items():
        pin = int(cfg["pin"])
        dev = OutputDevice(pin, active_high=RELAY_ACTIVE_HIGH, initial_value=False)
        dev.off()
        ctx.register_relay_device(name, dev, active=(name in RELAYS))


def relays_off(ctx, reason: str) -> None:
    for dev in ctx.get_relay_hardware_devices().values():
        dev.off()
    ctx.broadcaster.publish({
        "type": "relays",
        "state": "all_off",
        "reason": reason,
        "ts": time.time(),
    })


def apply_relay_pattern(ctx, state_name: str, reason: str) -> None:
    pattern = RELAY_PATTERNS.get(state_name)
    if not pattern:
        return

    actions = ctx.apply_relay_pattern_decision(pattern)
    for dev, on in actions:
        if on:
            dev.on()
        else:
            dev.off()

    ctx.broadcaster.publish({
        "type": "relays",
        "state": state_name,
        "pattern": pattern,
        "reason": reason,
        "ts": time.time(),
    })


def toggle_relay(ctx, name: str):
    dev, new = ctx.decide_relay_toggle(name)
    if new:
        dev.on()
    else:
        dev.off()

    ctx.broadcaster.publish({
        "type": "relay",
        "name": name,
        "on": new,
        "reason": "admin_toggle",
        "ts": time.time(),
    })

    return new
