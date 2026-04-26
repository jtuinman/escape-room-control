#!/usr/bin/env python3
from flask import Flask

from escape_room import EscapeRoomContext
from escape_room.config import HOST, PORT
from escape_room.config_validation import validate_startup_config
from escape_room.gpio_io import init_gpio
from escape_room.relays import init_relays
from escape_room.routes import register_routes
from escape_room.sound_sync import publish_sound_status, resync_sound_state
from escape_room.state import set_game_state
from mqtt_sound import set_language as mqtt_set_language, start_monitor


app = Flask(__name__)


def main() -> None:
    validate_startup_config()

    context = EscapeRoomContext.create()
    register_routes(app, context)

    start_monitor(
        on_ready=lambda: resync_sound_state(context, reason="sound_ready"),
        on_status=lambda status: publish_sound_status(context, status),
    )

    init_relays(context)
    init_gpio(context)
    set_game_state(context, "idle", reason="boot_to_idle")
    mqtt_set_language(context.snapshot_language())
    app.run(host=HOST, port=PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
