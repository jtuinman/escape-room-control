import json
import re
import subprocess
import time

from flask import Response, abort, jsonify, render_template, request

from mqtt_sound import bg_start, bg_stop, bg_switch, hint_play, panic, set_language as mqtt_set_language

from .config import BACKGROUND_AUDIO_EXTENSIONS, SUPPORTED_LANGUAGES, VALID_GAME_STATES
from .hints import find_hint_by_id
from .relays import toggle_relay
from .state import save_language, set_game_state
from .timer import toggle_timer
from .ui_config import get_ui_config


_BG_FILE_RE = re.compile(r"^state\d+\.mp3$", re.IGNORECASE)


def _validate_bg_file(filename: str) -> str:
    if not _BG_FILE_RE.match(filename):
        abort(400, "Invalid background file")
    if not any(filename.lower().endswith(ext) for ext in BACKGROUND_AUDIO_EXTENSIONS):
        abort(400, "Invalid background file")
    return filename


def register_routes(app, ctx) -> None:
    @app.route("/")
    def index():
        snapshot = ctx.snapshot_index()
        ui_config = get_ui_config()

        return render_template(
            "index.html",
            inputs=ui_config["inputs"],
            game_state=snapshot["game_state"],
            language=snapshot["language"],
            supported_languages=sorted(SUPPORTED_LANGUAGES),
            ui_config=ui_config,
        )

    @app.route("/panel")
    def panel():
        return render_template("panel.html")

    @app.route("/api/state")
    def api_state():
        snapshot = ctx.snapshot_state()
        ui_config = get_ui_config()

        return jsonify({
            "game_state": snapshot["game_state"],
            "language": snapshot["language"],
            "inputs": snapshot["inputs"],
            "relays": snapshot["relays"],
            "hints": snapshot["hints"],
            "timer": snapshot["timer"],
            "sound": snapshot["sound"],
            "states": ui_config["states"],
            "relays_meta": ui_config["relays"],
            "inputs_meta": ui_config["inputs"],
            "cameras": ui_config["cameras"],
            "languages": ui_config["languages"],
            "text": ui_config["text"],
        })

    @app.route("/api/language", methods=["POST"])
    def api_language():
        data = request.get_json(silent=True) or {}
        new_lang = str(data.get("language", "")).strip().lower()

        if new_lang not in SUPPORTED_LANGUAGES:
            return jsonify({"ok": False, "error": "invalid_language"}), 400

        lang = save_language(new_lang)
        snapshot = ctx.set_language(lang)

        mqtt_set_language(snapshot["language"])

        ctx.broadcaster.publish({
            "type": "language",
            "language": snapshot["language"],
            "hints": snapshot["hints"],
            "ts": time.time(),
        })

        return jsonify({"ok": True, "language": snapshot["language"]})

    @app.route("/api/set_state", methods=["POST"])
    def api_set_state():
        data = request.get_json(silent=True) or {}
        new_state = str(data.get("state", "")).strip()
        if new_state not in VALID_GAME_STATES:
            return jsonify({"ok": False, "error": "invalid_state"}), 400

        set_game_state(ctx, new_state, reason="admin_override")
        return jsonify({"ok": True})

    @app.route("/api/timer/toggle", methods=["POST"])
    def api_timer_toggle():
        action = toggle_timer(ctx)
        timer = ctx.snapshot_timer()

        return jsonify({
            "ok": True,
            "action": action,
            "timer": timer,
        })

    @app.route("/api/relay/toggle", methods=["POST"])
    def api_relay_toggle():
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", "")).strip()
        if not ctx.has_relay_device(name):
            return jsonify({"ok": False, "error": "unknown_relay"}), 400

        new = toggle_relay(ctx, name)
        return jsonify({"ok": True, "name": name, "on": new})

    @app.route("/api/poweroff", methods=["POST"])
    def api_poweroff():
        if not ctx.is_idle():
            return jsonify({"ok": False, "error": "not_idle"}), 403

        ctx.broadcaster.publish({
            "type": "system",
            "action": "poweroff",
            "reason": "admin_request",
            "ts": time.time(),
        })

        try:
            subprocess.Popen(["sudo", "/usr/sbin/poweroff"])
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

        return jsonify({"ok": True})

    @app.route("/api/reboot", methods=["POST"])
    def api_reboot():
        if not ctx.is_idle():
            return jsonify({"ok": False, "error": "not_idle"}), 403

        ctx.broadcaster.publish({
            "type": "system",
            "action": "reboot",
            "reason": "admin_request",
            "ts": time.time(),
        })

        try:
            subprocess.Popen(["sudo", "/usr/sbin/reboot"])
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

        return jsonify({"ok": True})

    @app.route("/events")
    def events():
        q = ctx.broadcaster.register()

        def gen():
            try:
                yield "event: hello\ndata: {}\n\n"
                while True:
                    evt = q.get()
                    yield f"data: {json.dumps(evt, separators=(',', ':'))}\n\n"
            except GeneratorExit:
                pass
            finally:
                ctx.broadcaster.unregister(q)

        return Response(gen(), mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        })

    @app.route("/sound/bg/<action>", defaults={"filename": None})
    @app.route("/sound/bg/<action>/<filename>")
    def sound_bg(action, filename):
        action = action.lower()

        if action == "start":
            if not filename:
                abort(400, "Missing background file")
            filename = _validate_bg_file(filename)
            bg_start(filename)
            return "OK"

        if action == "switch":
            if not filename:
                abort(400, "Missing background file")
            filename = _validate_bg_file(filename)
            bg_switch(filename)
            return "OK"

        if action == "stop":
            bg_stop()
            return "OK"

        abort(400, "Invalid action")

    @app.route("/sound/hint/<hint_id>")
    def sound_hint_by_id(hint_id):
        h = find_hint_by_id(ctx, hint_id)
        if not h:
            return "Unknown hint", 404
        hint_play(h["file"])
        return "OK"

    @app.route("/sound/panic")
    def sound_panic():
        panic()
        return "OK"
