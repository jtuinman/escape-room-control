import threading
import time
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
    relay_hardware_devices: Dict[str, OutputDevice] = field(default_factory=dict)
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

    def get_timer_elapsed_locked(self) -> float:
        """Return timer elapsed seconds. Caller must hold self.lock."""
        if not self.timer_running or self.timer_started_at is None:
            return float(self.timer_elapsed_base)
        return float(self.timer_elapsed_base + (time.monotonic() - self.timer_started_at))

    def snapshot_timer_locked(self) -> dict:
        """Return timer payload. Caller must hold self.lock."""
        return {
            "running": self.timer_running,
            "elapsed": self.get_timer_elapsed_locked(),
        }

    def snapshot_timer(self) -> dict:
        with self.lock:
            return self.snapshot_timer_locked()

    def stop_timer(self):
        with self.lock:
            if not self.timer_running:
                return None
            self.timer_elapsed_base = self.get_timer_elapsed_locked()
            self.timer_running = False
            self.timer_started_at = None
            return self.snapshot_timer_locked()

    def toggle_timer(self):
        with self.lock:
            if self.timer_running:
                self.timer_elapsed_base = self.get_timer_elapsed_locked()
                self.timer_running = False
                self.timer_started_at = None
                action = "paused"
            else:
                self.timer_started_at = time.monotonic()
                self.timer_running = True
                action = "resumed"
            return action, self.snapshot_timer_locked()

    def get_hints_payload_for_state_locked(self, state_name: str) -> dict:
        """Return frontend hints payload. Caller must hold self.lock."""
        hints_cfg = self.hints_by_lang[self.current_language]
        scene_data = hints_cfg.get(state_name, {})
        global_cfg = hints_cfg.get("global", {})

        return {
            "global": {
                "label": global_cfg.get("label", ""),
                "hints": global_cfg.get("hints", []),
            },
            "puzzles": scene_data.get("puzzles", []),
        }

    def get_hints_for_language(self, language: str) -> dict:
        return self.hints_by_lang[language]

    def snapshot_state(self) -> dict:
        with self.lock:
            state_name = self.game_state
            return {
                "game_state": state_name,
                "language": self.current_language,
                "inputs": dict(self.current_inputs),
                "relays": dict(self.current_relays),
                "hints": self.get_hints_payload_for_state_locked(state_name),
                "timer": self.snapshot_timer_locked(),
            }

    def snapshot_index(self) -> dict:
        with self.lock:
            return {
                "game_state": self.game_state,
                "language": self.current_language,
            }

    def snapshot_inputs(self) -> dict:
        with self.lock:
            return dict(self.current_inputs)

    def snapshot_relays(self) -> dict:
        with self.lock:
            return dict(self.current_relays)

    def snapshot_rule_inputs(self) -> dict:
        with self.lock:
            return {
                "game_state": self.game_state,
                "inputs": dict(self.current_inputs),
                "previous_inputs": dict(self.previous_inputs),
            }

    def set_input_state(self, label: str, state: str) -> None:
        with self.lock:
            prev = self.current_inputs.get(label)
            self.previous_inputs[label] = prev if prev is not None else state
            self.current_inputs[label] = state

    def register_input_device(self, label: str, device: object) -> None:
        with self.lock:
            self.devices[label] = device

    def get_input_button(self, label: str):
        with self.lock:
            return self.devices[label].button

    def register_relay_device(self, name: str, device: OutputDevice, active: bool = True) -> None:
        with self.lock:
            self.relay_hardware_devices[name] = device
            if active:
                self.relay_devices[name] = device
                self.current_relays[name] = False

    def get_relay_devices(self) -> dict:
        with self.lock:
            return dict(self.relay_devices)

    def get_relay_hardware_devices(self) -> dict:
        with self.lock:
            return dict(self.relay_hardware_devices)

    def has_relay_device(self, name: str) -> bool:
        with self.lock:
            return name in self.relay_devices

    def decide_relay_toggle(self, name: str):
        with self.lock:
            dev = self.relay_devices[name]
            new = not bool(self.current_relays.get(name, False))
            self.current_relays[name] = new
            return dev, new

    def apply_relay_pattern_decision(self, pattern: dict):
        actions = []
        with self.lock:
            for relay_name, on in pattern.items():
                dev = self.relay_devices.get(relay_name)
                if not dev:
                    continue
                self.current_relays[relay_name] = bool(on)
                actions.append((dev, bool(on)))
        return actions

    def is_idle(self) -> bool:
        with self.lock:
            return self.game_state == "idle"

    def prepare_state_entry(self, new_state: str, entry_actions) -> None:
        with self.lock:
            self.game_state = new_state
            for action in entry_actions:
                if action == "reset_timer":
                    self.timer_running = False
                    self.timer_started_at = None
                    self.timer_elapsed_base = 0.0
                elif action == "start_timer_if_fresh":
                    if (
                        (not self.timer_running)
                        and (self.timer_started_at is None)
                        and (self.timer_elapsed_base == 0.0)
                    ):
                        self.timer_started_at = time.monotonic()
                        self.timer_running = True

    def set_language(self, language: str) -> dict:
        with self.lock:
            self.current_language = language
            return {
                "language": self.current_language,
                "game_state": self.game_state,
                "hints": self.get_hints_payload_for_state_locked(self.game_state),
            }

    def snapshot_language(self) -> str:
        with self.lock:
            return self.current_language

    def find_hint_by_id(self, hint_id: str):
        with self.lock:
            return self.hint_index_by_lang[self.current_language].get(hint_id)
