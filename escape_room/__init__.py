import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

from gpiozero import OutputDevice

from .broadcaster import Broadcaster
from .hints import load_all_hints
from .state import load_language


@dataclass
class EscapeRoomContext:
    broadcaster: Broadcaster = field(default_factory=Broadcaster)
    devices: Dict[str, object] = field(default_factory=dict)
    relay_devices: Dict[str, OutputDevice] = field(default_factory=dict)
    current_relays: Dict[str, bool] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)
    current_inputs: Dict[str, str] = field(default_factory=dict)
    previous_inputs: Dict[str, str] = field(default_factory=dict)
    game_state: str = "idle"
    timer_running: bool = False
    timer_started_at: Optional[float] = None
    timer_elapsed_base: float = 0.0
    hints_by_lang: dict = field(default_factory=dict)
    hint_index_by_lang: dict = field(default_factory=dict)
    current_language: str = "nl"

    @classmethod
    def create(cls) -> "EscapeRoomContext":
        hints_by_lang, hint_index_by_lang = load_all_hints()
        return cls(
            hints_by_lang=hints_by_lang,
            hint_index_by_lang=hint_index_by_lang,
            current_language=load_language(),
        )
