#!/usr/bin/env python3
import json
import os 
import queue
import threading
import time
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional
from mqtt_sound import bg_start, bg_switch, bg_stop, hint_play, panic

import re
from flask import Flask, Response, jsonify, render_template, request, abort
from gpiozero import Button, OutputDevice



# =========================
# Escape room config 
# =========================
HOST = "0.0.0.0"
PORT = 8000

# GPIO inputs (BCM numbering)
# IMPORTANT: You did NOT provide toggle_2 pin. Defaulting to 23. Change if needed.
INPUTS = {
    "pushbutton 1": {"pin": 17, "bounce_time": 0.05, "role": "pb1"},
    "pushbutton 2": {"pin": 27, "bounce_time": 0.05, "role": "pb2"},
    "toggle 1": {"pin": 22, "bounce_time": 0.05, "role": "t1"},
    "toggle 2": {"pin": 5, "bounce_time": 0.05, "role": "t2"},
    "reed switch": {"pin": 6, "bounce_time": 0.05, "role": "rs1"}

}
# =========================
# Relay outputs
# =========================
RELAY_ACTIVE_HIGH = False  # True: HIGH=ON, False: LOW=ON (veel relay boards zijn active-low)

RELAYS = {
    "relay_1": {"pin": 16},
    "relay_2": {"pin": 20},
    "relay_3": {"pin": 21},
    "relay_4": {"pin": 26},
}
# Relay patterns per game state (True=ON, False=OFF)
RELAY_PATTERNS = {
    "idle":     {"relay_1": False, "relay_2": False, "relay_3": False, "relay_4": False},
    "scene_1":  {"relay_1": True,  "relay_2": False, "relay_3": True,  "relay_4": False},
    "scene_2":  {"relay_1": True,  "relay_2": True,  "relay_3": False, "relay_4": True},
    "end_game": {"relay_1": False, "relay_2": False, "relay_3": True,  "relay_4": True},
}

# Semantics you requested:
# ACTIVE = open circuit (NOT connected to GND)
# INACTIVE = circuit to GND
# Hardware is active-low with pull-up, so gpiozero Button.is_pressed is True when connected to GND.
# Therefore: logical_active = NOT is_pressed
ACTIVE_WHEN_OPEN = True


# =========================
# State machine
# =========================
VALID_GAME_STATES = ("idle", "scene_1", "scene_2", "end_game")


@dataclass
class InputDevice:
    label: str
    pin: int
    bounce_time: float
    role: str
    button: Button


class Broadcaster:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: List["queue.Queue[dict]"] = []

    def register(self) -> "queue.Queue[dict]":
        q: "queue.Queue[dict]" = queue.Queue(maxsize=200)
        with self._lock:
            self._clients.append(q)
        return q

    def unregister(self, q: "queue.Queue[dict]") -> None:
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    def publish(self, event: dict) -> None:
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass


app = Flask(__name__)
broadcaster = Broadcaster()

devices: Dict[str, InputDevice] = {}
relay_devices: Dict[str, OutputDevice] = {}
current_relays: Dict[str, bool] = {}  # relay_name -> True(on)/False(off)

lock = threading.Lock()
current_inputs: Dict[str, str] = {}       # label -> "ACTIVE"/"INACTIVE"
previous_inputs: Dict[str, str] = {}      # label -> "ACTIVE"/"INACTIVE"
game_state: str = "idle"

# Timer model:
# - starts at scene_1
# - runs continuously (through scene_2 and end_game)
# - stops only when in end_game and toggle_2 edges INACTIVE->ACTIVE
timer_running: bool = False
timer_started_at: Optional[float] = None  # time.monotonic()
timer_elapsed_base: float = 0.0           # seconds accumulated when stopped


def now_mono() -> float:
    return time.monotonic()


def get_timer_elapsed() -> float:
    global timer_elapsed_base, timer_started_at, timer_running
    if not timer_running or timer_started_at is None:
        return float(timer_elapsed_base)
    return float(timer_elapsed_base + (now_mono() - timer_started_at))


def publish_full_state(reason: str) -> None:
    evt = {
        "type": "full_state",
        "reason": reason,
        "game_state": game_state,
        "inputs": dict(current_inputs),
        "timer": {
            "running": timer_running,
            "elapsed": get_timer_elapsed(),
        },
        "ts": time.time(),
    }
    broadcaster.publish(evt)

def init_relays() -> None:
    # OutputDevice(active_high=...) bepaalt of "on()" HIGH of LOW schrijft.
    for name, cfg in RELAYS.items():
        pin = int(cfg["pin"])
        dev = OutputDevice(pin, active_high=RELAY_ACTIVE_HIGH, initial_value=False)
        relay_devices[name] = dev
        current_relays[name] = False


def relays_off(reason: str) -> None:
    for dev in relay_devices.values():
        dev.off()
    broadcaster.publish({
        "type": "relays",
        "state": "all_off",
        "reason": reason,
        "ts": time.time(),
    })
def apply_relay_pattern(state_name: str, reason: str) -> None:
    pattern = RELAY_PATTERNS.get(state_name)
    if not pattern:
        return

    for relay_name, on in pattern.items():
        dev = relay_devices.get(relay_name)
        if not dev:
            continue
        if on:
            dev.on()
        else:
            dev.off()
        current_relays[relay_name] = bool(on)

    broadcaster.publish({
        "type": "relays",
        "state": state_name,
        "pattern": pattern,
        "reason": reason,
        "ts": time.time(),
    })


def set_game_state(new_state: str, reason: str) -> None:
    global game_state, timer_running, timer_started_at, timer_elapsed_base

    if new_state not in VALID_GAME_STATES:
        return

    with lock:
        game_state = new_state

        # TIMER RULES:
        # - Timer can only be STOPPED/RESET by going to idle (admin) OR by toggle_2 edge in end_game.
        # - Timer should keep running through all other state changes.
        # - Starting scene_1 starts the timer ONLY if it is not running AND has not started before.

        if new_state == "idle":
            panic()  # stop all sounds immediately when going idle
            timer_running = False
            timer_started_at = None
            timer_elapsed_base = 0.0
            apply_relay_pattern("idle", reason="entered_idle")
        
        elif new_state == "scene_1":
            # Start timer ONLY if it has never started and is not running.
            # If it's already running, do nothing (no reset).
            # If it was stopped by toggle_2 (end_game) and you DON'T want it to restart unless idle happened,
            # then also do nothing here when elapsed_base > 0.
            bg_start("state1.mp3") # Start state1 music when entering scene_1
            if (not timer_running) and (timer_started_at is None) and (timer_elapsed_base == 0.0):
                timer_started_at = now_mono()
                timer_running = True
        elif new_state == "scene_2":
            bg_switch("state2.mp3") # Switch to state2 music when entering scene_2
        elif new_state == "end_game":
            bg_switch("state3.mp3") # Switch to state3 music when entering end_game
        # scene_2 and end_game: timer continues unchanged (no stop/reset here)

    apply_relay_pattern(new_state, reason=f"state:{reason}")

    broadcaster.publish({
        "type": "game_state",
        "game_state": new_state,
        "reason": reason,
        "ts": time.time(),
    })
    broadcaster.publish({
        "type": "timer",
        "timer": {"running": timer_running, "elapsed": get_timer_elapsed()},
        "reason": reason,
        "ts": time.time(),
    })
    publish_full_state(reason=f"state_change:{reason}")


def stop_timer(reason: str) -> None:
    global timer_running, timer_started_at, timer_elapsed_base
    with lock:
        if not timer_running:
            return
        timer_elapsed_base = get_timer_elapsed()
        timer_running = False
        timer_started_at = None

    broadcaster.publish({
        "type": "timer",
        "timer": {"running": False, "elapsed": get_timer_elapsed()},
        "reason": reason,
        "ts": time.time(),
    })


def logical_active_from_button(btn: Button) -> bool:
    # gpiozero: is_pressed True when active_low circuit is closed (to GND)
    # You want ACTIVE when open => logical_active = not is_pressed
    pressed = bool(btn.is_pressed)
    return (not pressed) if ACTIVE_WHEN_OPEN else pressed


def set_input_state(label: str, is_active: bool) -> None:
    state = "ACTIVE" if is_active else "INACTIVE"
    with lock:
        prev = current_inputs.get(label)
        previous_inputs[label] = prev if prev is not None else state
        current_inputs[label] = state

    broadcaster.publish({
        "type": "input",
        "label": label,
        "state": state,
        "ts": time.time(),
    })


def get_label_by_role(role: str) -> Optional[str]:
    for label, cfg in INPUTS.items():
        if cfg.get("role") == role:
            return label
    return None


def evaluate_rules_on_change(changed_label: str) -> None:
    """Called after any input change. Enforces your game rules."""
    global game_state

    with lock:
        gs = game_state
        snapshot = dict(current_inputs)
        prev_snapshot = dict(previous_inputs)

    pb1 = get_label_by_role("pb1")
    pb2 = get_label_by_role("pb2")
    t1 = get_label_by_role("t1")
    t2 = get_label_by_role("t2")

    # Helper
    def is_active(label: Optional[str]) -> bool:
        if not label:
            return False
        return snapshot.get(label) == "ACTIVE"

    def was_inactive(label: Optional[str]) -> bool:
        if not label:
            return False
        return prev_snapshot.get(label) == "INACTIVE"

    # idle: physical inputs do nothing
    if gs == "idle":
        return

    # scene_1: if pb1 and pb2 are both ACTIVE at any moment => scene_2
    if gs == "scene_1":
        if is_active(pb1) and is_active(pb2):
            set_game_state("scene_2", reason="pb1+pb2_overlap")
        return

    # scene_2: toggle_1 edge INACTIVE->ACTIVE => end_game
    if gs == "scene_2":
        if changed_label == t1 and was_inactive(t1) and is_active(t1):
            set_game_state("end_game", reason="toggle_1_edge")
        return

    # end_game: toggle_2 edge INACTIVE->ACTIVE => stop timer
    if gs == "end_game":
        if changed_label == t2 and was_inactive(t2) and is_active(t2):
            stop_timer(reason="toggle_2_edge_stop_timer")
        return


def init_gpio() -> None:
    # Initialize gpiozero devices and register callbacks
    for label, cfg in INPUTS.items():
        pin = int(cfg["pin"])
        bounce_time = float(cfg.get("bounce_time", 0.05))
        role = str(cfg.get("role", ""))

        btn = Button(pin, pull_up=True, active_state=None, bounce_time=bounce_time)

        devices[label] = InputDevice(label=label, pin=pin, bounce_time=bounce_time, role=role, button=btn)

        # initial state
        set_input_state(label, logical_active_from_button(btn))

        def on_change(lab=label):
            dev = devices[lab].button
            set_input_state(lab, logical_active_from_button(dev))
            evaluate_rules_on_change(lab)

        # We trigger on both edges, then compute logical state
        btn.when_pressed = on_change
        btn.when_released = on_change

    # Push an initial full snapshot
    publish_full_state(reason="boot")

_BG_FILE_RE = re.compile(r"^state\d+\.mp3$", re.IGNORECASE)

def _validate_bg_file(filename: str) -> str:
    if not _BG_FILE_RE.match(filename):
        abort(400, "Invalid background file")
    return filename

HINTS_CONFIG_PATH = os.path.join("config", "hints.json")

def load_hints_config():
    with open(HINTS_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

HINTS = load_hints_config()


@app.route("/")
def index():
    labels = list(INPUTS.keys())
    return render_template("index.html", inputs=labels, states=list(VALID_GAME_STATES))


@app.route("/api/state")
def api_state():
    with lock:
        return jsonify({
            "game_state": game_state,
            "inputs": dict(current_inputs),
            "relays": dict(current_relays),
            "timer": {"running": timer_running, "elapsed": get_timer_elapsed()},
        })


@app.route("/api/set_state", methods=["POST"])
def api_set_state():
    data = request.get_json(silent=True) or {}
    new_state = str(data.get("state", "")).strip()
    if new_state not in VALID_GAME_STATES:
        return jsonify({"ok": False, "error": "invalid_state"}), 400

    set_game_state(new_state, reason="admin_override")
    return jsonify({"ok": True})

@app.route("/api/relay/toggle", methods=["POST"])
def api_relay_toggle():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if name not in relay_devices:
        return jsonify({"ok": False, "error": "unknown_relay"}), 400

    with lock:
        cur = bool(current_relays.get(name, False))
        new = not cur
        current_relays[name] = new

    dev = relay_devices[name]
    if new:
        dev.on()
    else:
        dev.off()

    broadcaster.publish({
        "type": "relay",
        "name": name,
        "on": new,
        "reason": "admin_toggle",
        "ts": time.time(),
    })

    return jsonify({"ok": True, "name": name, "on": new})

@app.route("/api/poweroff", methods=["POST"])
def api_poweroff():
    # Only allow shutdown when game is idle
    if game_state != "idle":
        return jsonify({"ok": False, "error": "not_idle"}), 403

    broadcaster.publish({
        "type": "system",
        "action": "poweroff",
        "reason": "admin_request",
        "ts": time.time(),
    })

    try:
        # Use sudo so we don't need to run the whole app as root
        subprocess.Popen(["sudo", "/usr/sbin/poweroff"])
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True})


@app.route("/events")
def events():
    q = broadcaster.register()

    def gen():
        try:
            yield "event: hello\ndata: {}\n\n"
            while True:
                evt = q.get()
                yield f"data: {json.dumps(evt, separators=(',', ':'))}\n\n"
        except GeneratorExit:
            pass
        finally:
            broadcaster.unregister(q)

    return Response(gen(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })

@app.route("/sound/bg/<action>/<filename>")
def sound_bg(action, filename):
    filename = _validate_bg_file(filename)
    action = action.lower()

    if action == "start":
        bg_start(filename)
        return "OK"
    if action == "switch":
        bg_switch(filename)
        return "OK"
    if action == "stop":
        bg_stop()
        return "OK"

    abort(400, "Invalid action")

@app.route("/sound/hint1")
def sound_hint1():
    hint_play("hint1.mp3")
    return "OK"

@app.route("/sound/panic")
def sound_panic():
    panic()
    return "OK"

def main() -> None:
    init_relays()
    init_gpio()
    set_game_state("idle", reason="boot_to_idle")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
