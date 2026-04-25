import time

from gpiozero import OutputDevice

from .config import RELAY_ACTIVE_HIGH, RELAY_PATTERNS, RELAYS


def init_relays(ctx) -> None:
    for name, cfg in RELAYS.items():
        pin = int(cfg["pin"])
        dev = OutputDevice(pin, active_high=RELAY_ACTIVE_HIGH, initial_value=False)
        ctx.relay_devices[name] = dev
        ctx.current_relays[name] = False


def relays_off(ctx, reason: str) -> None:
    for dev in ctx.relay_devices.values():
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

    for relay_name, on in pattern.items():
        dev = ctx.relay_devices.get(relay_name)
        if not dev:
            continue
        if on:
            dev.on()
        else:
            dev.off()
        ctx.current_relays[relay_name] = bool(on)

    ctx.broadcaster.publish({
        "type": "relays",
        "state": state_name,
        "pattern": pattern,
        "reason": reason,
        "ts": time.time(),
    })


def toggle_relay(ctx, name: str):
    with ctx.lock:
        cur = bool(ctx.current_relays.get(name, False))
        new = not cur
        ctx.current_relays[name] = new

    dev = ctx.relay_devices[name]
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
