import time

from mqtt_sound import bg_start, bg_switch, panic

from .config import DEFAULT_LANGUAGE, LANGUAGE_FILE, SUPPORTED_LANGUAGES, VALID_GAME_STATES


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
    snapshot = ctx.snapshot_state()

    evt = {
        "type": "full_state",
        "reason": reason,
        "game_state": snapshot["game_state"],
        "inputs": snapshot["inputs"],
        "relays": snapshot["relays"],
        "language": snapshot["language"],
        "hints": snapshot["hints"],
        "timer": snapshot["timer"],
        "ts": time.time(),
    }
    ctx.broadcaster.publish(evt)


def set_game_state(ctx, new_state: str, reason: str) -> None:
    if new_state not in VALID_GAME_STATES:
        return

    side_effect = ctx.transition_game_state(new_state)

    if side_effect == ("panic", None):
        panic()
    elif side_effect and side_effect[0] == "bg_start":
        bg_start(side_effect[1])
    elif side_effect and side_effect[0] == "bg_switch":
        bg_switch(side_effect[1])

    from .relays import apply_relay_pattern

    apply_relay_pattern(ctx, new_state, reason=f"state:{reason}")
    publish_full_state(ctx, reason=f"state_change:{reason}")
