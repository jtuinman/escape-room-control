from pathlib import Path

HOST = "0.0.0.0"
PORT = 8000

INPUTS = {
    "pushbutton 1": {"pin": 17, "bounce_time": 0.05, "role": "pb1"},
    "pushbutton 2": {"pin": 27, "bounce_time": 0.05, "role": "pb2"},
    "toggle 1": {"pin": 22, "bounce_time": 0.05, "role": "t1"},
    "toggle 2": {"pin": 5, "bounce_time": 0.05, "role": "t2"},
    "reed switch": {"pin": 6, "bounce_time": 0.05, "role": "rs1"},
}

RELAY_ACTIVE_HIGH = False

RELAYS = {
    "relay_1": {"pin": 16},
    "relay_2": {"pin": 20},
    "relay_3": {"pin": 21},
    "relay_4": {"pin": 26},
}

RELAY_PATTERNS = {
    "idle": {"relay_1": False, "relay_2": False, "relay_3": False, "relay_4": False},
    "scene_1": {"relay_1": True, "relay_2": False, "relay_3": False, "relay_4": True},
    "scene_2": {"relay_1": False, "relay_2": True, "relay_3": False, "relay_4": False},
    "end_game": {"relay_1": True, "relay_2": True, "relay_3": False, "relay_4": False},
}

ACTIVE_WHEN_OPEN = True

VALID_GAME_STATES = ("idle", "scene_1", "scene_2", "end_game")

STATE_LABELS = {
    "idle": "idle",
    "scene_1": "scene 1",
    "scene_2": "scene 2",
    "end_game": "end game",
}

RELAY_LABELS = {
    "relay_1": "lamp",
    "relay_2": "spot",
#    "relay_3": "niet beschikbaar",
    "relay_4": "magneet",
}

CONFIG_DIR = Path("config")
LANGUAGE_FILE = CONFIG_DIR / "language.txt"
CAMERA_STREAMS_FILE = CONFIG_DIR / "camera_streams.json"

SUPPORTED_LANGUAGES = {"nl", "en"}
DEFAULT_LANGUAGE = "nl"

HINTS_CONFIG_PATHS = {
    "nl": CONFIG_DIR / "hints_nl.json",
    "en": CONFIG_DIR / "hints_en.json",
}
