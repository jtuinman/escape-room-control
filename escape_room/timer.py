import time


def get_timer_elapsed(ctx) -> float:
    return ctx.snapshot_timer()["elapsed"]


def stop_timer(ctx, reason: str) -> None:
    timer = ctx.stop_timer()
    if timer is None:
        return

    ctx.broadcaster.publish({
        "type": "timer",
        "timer": timer,
        "reason": reason,
        "ts": time.time(),
    })


def toggle_timer(ctx):
    action, timer = ctx.toggle_timer()

    ctx.broadcaster.publish({
        "type": "timer",
        "timer": timer,
        "reason": f"admin_{action}",
        "ts": time.time(),
    })

    return action
