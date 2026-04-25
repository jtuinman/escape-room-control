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

RELAY_HARDWARE = {
    "relay_1": {"pin": 16},
    "relay_2": {"pin": 20},
    # relay_3 is physically present on the board, but not part of game/UI control.
    "relay_3": {"pin": 21},
    "relay_4": {"pin": 26},
}

RELAYS = {
    "relay_1": RELAY_HARDWARE["relay_1"],
    "relay_2": RELAY_HARDWARE["relay_2"],
    "relay_4": RELAY_HARDWARE["relay_4"],
}

RELAY_PATTERNS = {
    "idle": {"relay_1": False, "relay_2": False, "relay_4": False},
    "scene_1": {"relay_1": True, "relay_2": False, "relay_4": True},
    "scene_2": {"relay_1": False, "relay_2": True, "relay_4": False},
    "end_game": {"relay_1": True, "relay_2": True, "relay_4": False},
}

ACTIVE_WHEN_OPEN = True

VALID_GAME_STATES = ("idle", "scene_1", "scene_2", "end_game")

STATE_UI = {
    "idle": {"label": "idle", "order": 0},
    "scene_1": {"label": "scene 1", "order": 1},
    "scene_2": {"label": "scene 2", "order": 2},
    "end_game": {"label": "end game", "order": 3},
}

RELAY_UI = {
    "relay_1": {"label": "lamp", "order": 0},
    "relay_2": {"label": "spot", "order": 1},
    "relay_4": {"label": "magneet", "order": 2},
}

INPUT_UI = {
    "pb1": {"label": "pushbutton 1"},
    "pb2": {"label": "pushbutton 2"},
    "t1": {"label": "toggle 1"},
    "t2": {"label": "toggle 2"},
    "rs1": {"label": "reed switch"},
}

CONFIG_DIR = Path("config")
LANGUAGE_FILE = CONFIG_DIR / "language.txt"
CAMERA_STREAMS_FILE = CONFIG_DIR / "camera_streams.json"

SUPPORTED_LANGUAGES = {"nl", "en"}
DEFAULT_LANGUAGE = "nl"

LANGUAGE_UI = {
    "nl": {"label": "Nederlands", "short_label": "NL"},
    "en": {"label": "English", "short_label": "EN"},
}

UI_TEXT = {
    "nl": {
        "global_hints_label": "Algemeen",
        "no_hints": "Geen hints voor deze scene.",
    },
    "en": {
        "global_hints_label": "Global",
        "no_hints": "No hints for this scene.",
    },
}

# Hint audio intentionally accepts both formats: NL currently uses .mp3, EN uses .ogg.
ALLOWED_HINT_AUDIO_EXTENSIONS = {".mp3", ".ogg"}
BACKGROUND_AUDIO_EXTENSIONS = {".mp3"}

HINTS_CONFIG_PATHS = {
    "nl": CONFIG_DIR / "hints_nl.json",
    "en": CONFIG_DIR / "hints_en.json",
}
