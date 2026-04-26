from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from mqtt_sound import bg_start, bg_switch, panic

from .config import INPUTS, VALID_GAME_STATES


INPUT_CHANGE = "input_change"
ADMIN_OVERRIDE_TARGETS = VALID_GAME_STATES


@dataclass(frozen=True)
class InputChangeEvent:
    changed_label: str
    game_state: str
    inputs: dict
    previous_inputs: dict


@dataclass(frozen=True)
class TransitionRule:
    trigger: str
    guard: Callable[[InputChangeEvent], bool]
    target_state: str
    reason: str


@dataclass(frozen=True)
class ActionRule:
    trigger: str
    guard: Callable[[InputChangeEvent], bool]
    action: str
    reason: str


@dataclass(frozen=True)
class StateDefinition:
    name: str
    entry_actions: Tuple[str, ...]
    rules: Tuple[object, ...] = ()


def get_label_by_role(role: str) -> Optional[str]:
    for label, cfg in INPUTS.items():
        if cfg.get("role") == role:
            return label
    return None


def is_active(label: Optional[str], inputs: dict) -> bool:
    if not label:
        return False
    return inputs.get(label) == "ACTIVE"


def is_inactive(label: Optional[str], inputs: dict) -> bool:
    if not label:
        return False
    return inputs.get(label) == "INACTIVE"


def was_active(label: Optional[str], previous_inputs: dict) -> bool:
    if not label:
        return False
    return previous_inputs.get(label) == "ACTIVE"


def was_inactive(label: Optional[str], previous_inputs: dict) -> bool:
    if not label:
        return False
    return previous_inputs.get(label) == "INACTIVE"


def reed_switch_1_and_2_inactive(event: InputChangeEvent) -> bool:
    return (
        is_inactive(get_label_by_role("rs1"), event.inputs)
        and is_inactive(get_label_by_role("rs2"), event.inputs)
    )


def inactive_to_active_edge(event: InputChangeEvent, role: str) -> bool:
    label = get_label_by_role(role)
    return (
        event.changed_label == label
        and was_inactive(label, event.previous_inputs)
        and is_active(label, event.inputs)
    )


def active_to_inactive_edge(event: InputChangeEvent, role: str) -> bool:
    label = get_label_by_role(role)
    return (
        event.changed_label == label
        and was_active(label, event.previous_inputs)
        and is_inactive(label, event.inputs)
    )


def reed_switch_3_active_to_inactive(event: InputChangeEvent) -> bool:
    return active_to_inactive_edge(event, "rs3")


def toggle_2_inactive_to_active(event: InputChangeEvent) -> bool:
    return inactive_to_active_edge(event, "t2")


STATE_DEFINITIONS = {
    "idle": StateDefinition(
        name="idle",
        entry_actions=("reset_timer", "panic", "apply_relay_pattern"),
    ),
    "scene_1": StateDefinition(
        name="scene_1",
        entry_actions=("start_timer_if_fresh", "bg_start_state1", "apply_relay_pattern"),
        rules=(
            TransitionRule(
                trigger=INPUT_CHANGE,
                guard=reed_switch_1_and_2_inactive,
                target_state="scene_2",
                reason="reed_switch_1_2_inactive",
            ),
        ),
    ),
    "scene_2": StateDefinition(
        name="scene_2",
        entry_actions=("bg_switch_state2", "apply_relay_pattern"),
        rules=(
            TransitionRule(
                trigger=INPUT_CHANGE,
                guard=reed_switch_3_active_to_inactive,
                target_state="end_game",
                reason="reed_switch_3_edge",
            ),
        ),
    ),
    "end_game": StateDefinition(
        name="end_game",
        entry_actions=("bg_switch_state3", "apply_relay_pattern"),
        rules=(
            ActionRule(
                trigger=INPUT_CHANGE,
                guard=toggle_2_inactive_to_active,
                action="stop_timer",
                reason="toggle_2_edge_stop_timer",
            ),
        ),
    ),
}


class StateMachine:
    def __init__(self, ctx) -> None:
        self.ctx = ctx

    def transition_to(self, new_state: str, reason: str, source: str = "runtime") -> None:
        if new_state not in ADMIN_OVERRIDE_TARGETS:
            return

        state = STATE_DEFINITIONS[new_state]
        self.ctx.prepare_state_entry(new_state, state.entry_actions)
        self.enter_state(state, reason)

        from .state import publish_full_state

        publish_full_state(self.ctx, reason=f"state_change:{reason}")

    def enter_state(self, state: StateDefinition, reason: str) -> None:
        for action in state.entry_actions:
            self.run_entry_action(action, state.name, reason)

    def handle_input_change(self, changed_label: str) -> None:
        snapshot = self.ctx.snapshot_rule_inputs()
        event = InputChangeEvent(
            changed_label=changed_label,
            game_state=snapshot["game_state"],
            inputs=snapshot["inputs"],
            previous_inputs=snapshot["previous_inputs"],
        )
        self.evaluate_rules(event)

    def evaluate_rules(self, event: InputChangeEvent) -> None:
        state = STATE_DEFINITIONS[event.game_state]
        for rule in state.rules:
            if rule.trigger != INPUT_CHANGE or not rule.guard(event):
                continue

            if isinstance(rule, TransitionRule):
                self.transition_to(rule.target_state, reason=rule.reason, source=INPUT_CHANGE)
                return

            if isinstance(rule, ActionRule):
                self.run_action_rule(rule)
                return

    def run_entry_action(self, action: str, state_name: str, reason: str) -> None:
        if action == "reset_timer":
            return
        elif action == "start_timer_if_fresh":
            return
        elif action == "panic":
            panic()
        elif action == "bg_start_state1":
            bg_start("state1.mp3")
        elif action == "bg_switch_state2":
            bg_switch("state2.mp3")
        elif action == "bg_switch_state3":
            bg_switch("state3.mp3")
        elif action == "apply_relay_pattern":
            from .relays import apply_relay_pattern

            apply_relay_pattern(self.ctx, state_name, reason=f"state:{reason}")
        else:
            raise ValueError(f"unknown_entry_action:{action}")

    def run_action_rule(self, rule: ActionRule) -> None:
        if rule.action == "stop_timer":
            from .timer import stop_timer

            stop_timer(self.ctx, reason=rule.reason)
            return

        raise ValueError(f"unknown_action_rule:{rule.action}")
