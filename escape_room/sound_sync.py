import time

from mqtt_sound import bg_start, bg_stop, bg_switch, set_language


BACKGROUND_AUDIO_BY_STATE = {
    "scene_1": ("start", "state1.mp3"),
    "scene_2": ("switch", "state2.mp3"),
    "end_game": ("switch", "state3.mp3"),
}


def resync_sound_state(ctx, reason: str = "resync") -> None:
    snapshot = ctx.snapshot_state()
    state_name = snapshot["game_state"]

    set_language(snapshot["language"])

    bg = BACKGROUND_AUDIO_BY_STATE.get(state_name)
    if bg is None:
        bg_stop()
    else:
        action, filename = bg
        if action == "start":
            bg_start(filename)
        else:
            bg_switch(filename)

    ctx.broadcaster.publish({
        "type": "sound_resync",
        "reason": reason,
        "game_state": state_name,
        "ts": time.time(),
    })


def publish_sound_status(ctx, status: dict) -> None:
    ctx.broadcaster.publish({
        "type": "sound_status",
        "sound": status,
        "ts": time.time(),
    })
