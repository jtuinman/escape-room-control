import time

from mqtt_sound import bg_start, bg_switch, panic

from .config import DEFAULT_LANGUAGE, LANGUAGE_FILE, SUPPORTED_LANGUAGES, VALID_GAME_STATES
from .hints import get_hints_payload_for_state
from .timer import get_timer_elapsed, now_mono


def load_language() -> str:
    try:
        lang = LANGUAGE_FILE.read_text(encoding="utf-8").strip().lower()
    except FileNotFoundError:
        lang = DEFAULT_LANGUAGE

    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    return lang


def save_language(lang: str) -> str:
    lang = (lang or DEFAULT_LANGUAGE).strip().lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError("invalid_language")
    LANGUAGE_FILE.write_text(lang + "\n", encoding="utf-8")
    return lang


def publish_full_state(ctx, reason: str) -> None:
    with ctx.lock:
        gs = ctx.game_state
        inputs = dict(ctx.current_inputs)
        lang = ctx.current_language
        relays = dict(ctx.current_relays)

    evt = {
        "type": "full_state",
        "reason": reason,
        "game_state": gs,
        "inputs": inputs,
        "relays": relays,
        "language": lang,
        "hints": get_hints_payload_for_state(ctx, gs),
        "timer": {
            "running": ctx.timer_running,
            "elapsed": get_timer_elapsed(ctx),
        },
        "ts": time.time(),
    }
    ctx.broadcaster.publish(evt)


def set_game_state(ctx, new_state: str, reason: str) -> None:
    if new_state not in VALID_GAME_STATES:
        return

    with ctx.lock:
        ctx.game_state = new_state

        if new_state == "idle":
            panic()
            ctx.timer_running = False
            ctx.timer_started_at = None
            ctx.timer_elapsed_base = 0.0

        elif new_state == "scene_1":
            bg_start("state1.mp3")
            if (
                (not ctx.timer_running)
                and (ctx.timer_started_at is None)
                and (ctx.timer_elapsed_base == 0.0)
            ):
                ctx.timer_started_at = now_mono()
                ctx.timer_running = True

        elif new_state == "scene_2":
            bg_switch("state2.mp3")

        elif new_state == "end_game":
            bg_switch("state3.mp3")

    from .relays import apply_relay_pattern

    apply_relay_pattern(ctx, new_state, reason=f"state:{reason}")
    publish_full_state(ctx, reason=f"state_change:{reason}")
