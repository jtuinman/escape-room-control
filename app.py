#!/usr/bin/env python3
from flask import Flask

from escape_room import EscapeRoomContext
from escape_room.config import HOST, PORT
from escape_room.gpio_io import init_gpio
from escape_room.relays import init_relays
from escape_room.routes import register_routes
from escape_room.state import set_game_state
from mqtt_sound import set_language as mqtt_set_language


app = Flask(__name__)
context = EscapeRoomContext.create()
register_routes(app, context)


def main() -> None:
    init_relays(context)
    init_gpio(context)
    set_game_state(context, "idle", reason="boot_to_idle")
    mqtt_set_language(context.current_language)
    app.run(host=HOST, port=PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
