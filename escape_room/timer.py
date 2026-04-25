import time


def now_mono() -> float:
    return time.monotonic()


def get_timer_elapsed(ctx) -> float:
    if not ctx.timer_running or ctx.timer_started_at is None:
        return float(ctx.timer_elapsed_base)
    return float(ctx.timer_elapsed_base + (now_mono() - ctx.timer_started_at))


def stop_timer(ctx, reason: str) -> None:
    with ctx.lock:
        if not ctx.timer_running:
            return
        ctx.timer_elapsed_base = get_timer_elapsed(ctx)
        ctx.timer_running = False
        ctx.timer_started_at = None

    ctx.broadcaster.publish({
        "type": "timer",
        "timer": {"running": False, "elapsed": get_timer_elapsed(ctx)},
        "reason": reason,
        "ts": time.time(),
    })


def toggle_timer(ctx):
    with ctx.lock:
        if ctx.timer_running:
            ctx.timer_elapsed_base = get_timer_elapsed(ctx)
            ctx.timer_running = False
            ctx.timer_started_at = None
            action = "paused"
        else:
            ctx.timer_started_at = now_mono()
            ctx.timer_running = True
            action = "resumed"

    ctx.broadcaster.publish({
        "type": "timer",
        "timer": {"running": ctx.timer_running, "elapsed": get_timer_elapsed(ctx)},
        "reason": f"admin_{action}",
        "ts": time.time(),
    })

    return action
