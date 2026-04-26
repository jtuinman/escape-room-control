import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from . import config


CAMERA_IDS_EXPECTED_BY_FRONTEND = {"cam1", "cam2", "cam3"}
REQUIRED_STATE_MACHINE_ROLES = {"rs1", "rs2", "rs3", "t2"}
URL_PREFIXES = ("http://", "https://", "rtsp://")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def extend(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


@dataclass(frozen=True)
class HintShape:
    states: Dict[str, Dict[str, Tuple[str, ...]]]
    global_hint_ids: Tuple[str, ...]
    hint_extensions: Dict[str, str]


def validate_startup_config() -> ValidationResult:
    result = ValidationResult()
    result.extend(validate_runtime_config())

    hint_shapes = {}
    for lang, path in config.HINTS_CONFIG_PATHS.items():
        hints_cfg = _load_json_object(path, f"hints_{lang}", result)
        if hints_cfg is not None:
            shape = validate_hints_config(hints_cfg, f"{path.name}", result)
            if shape is not None:
                hint_shapes[lang] = shape

    validate_hint_compatibility(hint_shapes, result)
    validate_camera_streams_config(config.CAMERA_STREAMS_FILE, result)
    validate_language_file(result)

    if result.errors:
        lines = ["Startup config validation failed:"]
        lines.extend(f"- {error}" for error in result.errors)
        if result.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in result.warnings)
        raise RuntimeError("\n".join(lines))

    for warning in result.warnings:
        print(f"[config warning] {warning}")

    return result


def validate_runtime_config() -> ValidationResult:
    result = ValidationResult()

    supported = config.SUPPORTED_LANGUAGES
    if not isinstance(supported, set) or not supported or not all(_non_empty_str(v) for v in supported):
        result.error("SUPPORTED_LANGUAGES must be a non-empty set of language strings")

    if config.DEFAULT_LANGUAGE not in supported:
        result.error("DEFAULT_LANGUAGE must be present in SUPPORTED_LANGUAGES")

    if set(config.HINTS_CONFIG_PATHS) != set(supported):
        result.error("HINTS_CONFIG_PATHS must contain exactly all SUPPORTED_LANGUAGES")

    for lang, path in config.HINTS_CONFIG_PATHS.items():
        if not isinstance(path, Path):
            result.error(f"HINTS_CONFIG_PATHS.{lang} must be a pathlib.Path")
        elif not path.exists():
            result.error(f"HINTS_CONFIG_PATHS.{lang} path does not exist: {path}")

    states = config.VALID_GAME_STATES
    if (
        not isinstance(states, tuple)
        or not states
        or not all(_non_empty_str(state) for state in states)
        or len(set(states)) != len(states)
    ):
        result.error("VALID_GAME_STATES must be a non-empty tuple of unique strings")

    input_pins = _validate_pin_map(
        config.INPUTS,
        "INPUTS",
        result,
        require_role=True,
        require_bounce_time=True,
    )
    relay_hardware_pins = _validate_pin_map(
        config.RELAY_HARDWARE,
        "RELAY_HARDWARE",
        result,
        require_role=False,
        require_bounce_time=False,
    )
    _validate_pin_map(
        config.RELAYS,
        "RELAYS",
        result,
        require_role=False,
        require_bounce_time=False,
    )

    if not set(config.RELAYS).issubset(set(config.RELAY_HARDWARE)):
        result.error("RELAYS must be a subset of RELAY_HARDWARE")

    roles = [str(cfg.get("role", "")) for cfg in config.INPUTS.values() if isinstance(cfg, dict)]
    missing_roles = REQUIRED_STATE_MACHINE_ROLES - set(roles)
    if missing_roles:
        result.error(f"INPUTS missing required state-machine roles: {sorted(missing_roles)}")

    overlap = input_pins & relay_hardware_pins
    if overlap:
        result.error(f"GPIO input pins and relay pins overlap: {sorted(overlap)}")

    validate_relay_patterns(result)
    return result


def validate_relay_patterns(result: ValidationResult) -> None:
    state_names = set(config.VALID_GAME_STATES)
    relay_names = set(config.RELAYS)

    if set(config.RELAY_PATTERNS) != state_names:
        result.error("RELAY_PATTERNS must contain exactly all VALID_GAME_STATES")

    for state_name, pattern in config.RELAY_PATTERNS.items():
        path = f"RELAY_PATTERNS.{state_name}"
        if not isinstance(pattern, dict):
            result.error(f"{path} must be an object")
            continue
        if set(pattern) != relay_names:
            result.error(f"{path} must contain exactly all relays: {sorted(relay_names)}")
        for relay_name, value in pattern.items():
            if not isinstance(value, bool):
                result.error(f"{path}.{relay_name} must be boolean")


def validate_hints_config(data: Any, root_path: str, result: ValidationResult) -> Optional[HintShape]:
    if not isinstance(data, dict):
        result.error(f"{root_path} must be a JSON object")
        return None

    seen_hint_ids: set[str] = set()
    hint_extensions: Dict[str, str] = {}

    global_data = data.get("global")
    if not isinstance(global_data, dict):
        result.error(f"{root_path}.global must exist and be an object")
        global_hint_ids: Tuple[str, ...] = ()
    else:
        label = global_data.get("label")
        if not _non_empty_str(label):
            result.error(f"{root_path}.global.label must be a non-empty string")
        hints = global_data.get("hints")
        if not isinstance(hints, list):
            result.error(f"{root_path}.global.hints must be a list")
            global_hint_ids = ()
        else:
            global_hint_ids = tuple(
                _validate_hint_list(hints, f"{root_path}.global.hints", seen_hint_ids, hint_extensions, result)
            )

    state_shapes: Dict[str, Dict[str, Tuple[str, ...]]] = {}
    for state_name in config.VALID_GAME_STATES:
        state_path = f"{root_path}.{state_name}"
        state_data = data.get(state_name)
        if not isinstance(state_data, dict):
            result.error(f"{state_path} must exist and be an object")
            continue

        puzzles = state_data.get("puzzles")
        if not isinstance(puzzles, list):
            result.error(f"{state_path}.puzzles must be a list")
            continue

        puzzle_ids: set[str] = set()
        puzzle_shapes: Dict[str, Tuple[str, ...]] = {}
        for idx, puzzle in enumerate(puzzles):
            puzzle_path = f"{state_path}.puzzles[{idx}]"
            if not isinstance(puzzle, dict):
                result.error(f"{puzzle_path} must be an object")
                continue

            puzzle_id = puzzle.get("id")
            if not _non_empty_str(puzzle_id):
                result.error(f"{puzzle_path}.id must be a non-empty string")
            elif puzzle_id in puzzle_ids:
                result.error(f"{puzzle_path}.id duplicates puzzle id {puzzle_id!r} in {state_path}")
            else:
                puzzle_ids.add(puzzle_id)

            if not _non_empty_str(puzzle.get("label")):
                result.error(f"{puzzle_path}.label must be a non-empty string")

            hints = puzzle.get("hints")
            if not isinstance(hints, list):
                result.error(f"{puzzle_path}.hints must be a list")
                hint_ids: Tuple[str, ...] = ()
            else:
                hint_ids = tuple(
                    _validate_hint_list(hints, f"{puzzle_path}.hints", seen_hint_ids, hint_extensions, result)
                )

            if _non_empty_str(puzzle_id):
                puzzle_shapes[puzzle_id] = hint_ids

        state_shapes[state_name] = puzzle_shapes

    extra_states = set(data) - {"global"} - set(config.VALID_GAME_STATES)
    if extra_states:
        result.warn(f"{root_path} contains unknown top-level sections: {sorted(extra_states)}")

    return HintShape(
        states=state_shapes,
        global_hint_ids=global_hint_ids,
        hint_extensions=hint_extensions,
    )


def validate_hint_compatibility(shapes: Dict[str, HintShape], result: ValidationResult) -> None:
    if len(shapes) < 2:
        return

    reference_lang = sorted(shapes)[0]
    reference = shapes[reference_lang]
    extension_mismatches = []

    for lang, shape in sorted(shapes.items()):
        if lang == reference_lang:
            continue

        if set(shape.states) != set(reference.states):
            result.error(f"hints_{lang} states differ from hints_{reference_lang}")

        if set(shape.global_hint_ids) != set(reference.global_hint_ids):
            result.error(f"hints_{lang}.global.hints IDs differ from hints_{reference_lang}")

        for state_name, reference_puzzles in reference.states.items():
            puzzles = shape.states.get(state_name, {})
            if set(puzzles) != set(reference_puzzles):
                result.error(
                    f"hints_{lang}.{state_name}.puzzles IDs differ from hints_{reference_lang}.{state_name}"
                )
                continue
            for puzzle_id, reference_hint_ids in reference_puzzles.items():
                hint_ids = puzzles.get(puzzle_id, ())
                if set(hint_ids) != set(reference_hint_ids):
                    result.error(
                        f"hints_{lang}.{state_name}.{puzzle_id}.hints IDs differ from "
                        f"hints_{reference_lang}.{state_name}.{puzzle_id}"
                    )

        for hint_id, reference_ext in reference.hint_extensions.items():
            ext = shape.hint_extensions.get(hint_id)
            if ext and ext != reference_ext:
                extension_mismatches.append(f"{hint_id}:{reference_ext}->{ext}")

    if extension_mismatches:
        result.warn(
            "Matching hint IDs use different audio extensions between languages: "
            + ", ".join(extension_mismatches)
        )


def validate_camera_streams_config(path: Path, result: ValidationResult) -> None:
    if not path.exists():
        result.warn(f"{path} is missing; default empty camera streams will be used")
        return

    data = _load_json_object(path, path.name, result)
    if data is None:
        return

    camera_ids = set()
    for key, value in data.items():
        key_path = f"{path.name}.{key}"
        if not _non_empty_str(key):
            result.error(f"{path.name} camera keys must be non-empty strings")
            continue
        camera_ids.add(key)

        if isinstance(value, str):
            url = value.strip()
        elif isinstance(value, dict):
            url = str(value.get("url", "")).strip()
        else:
            result.error(f"{key_path} must be a string URL or an object with url")
            continue

        if url and not url.startswith(URL_PREFIXES):
            result.error(f"{key_path}.url must start with http://, https://, or rtsp://")

    if camera_ids != CAMERA_IDS_EXPECTED_BY_FRONTEND:
        result.warn(
            f"{path.name} camera IDs {sorted(camera_ids)} differ from frontend expectation "
            f"{sorted(CAMERA_IDS_EXPECTED_BY_FRONTEND)}"
        )
    if len(camera_ids) != 3:
        result.warn(f"{path.name} has {len(camera_ids)} cameras; current frontend expects 3")


def validate_language_file(result: ValidationResult) -> None:
    path = config.LANGUAGE_FILE
    if not path.exists():
        return

    try:
        lang = path.read_text(encoding="utf-8").strip().lower()
    except OSError as exc:
        result.warn(f"{path} could not be read; falling back to {config.DEFAULT_LANGUAGE}: {exc}")
        return

    if lang not in config.SUPPORTED_LANGUAGES:
        result.warn(
            f"{path} contains unsupported language {lang!r}; falling back to {config.DEFAULT_LANGUAGE}"
        )


def _validate_pin_map(
    mapping: dict,
    name: str,
    result: ValidationResult,
    *,
    require_role: bool,
    require_bounce_time: bool,
) -> set[int]:
    pins: set[int] = set()
    roles: set[str] = set()

    if not isinstance(mapping, dict) or not mapping:
        result.error(f"{name} must be a non-empty object")
        return pins

    for label, cfg in mapping.items():
        path = f"{name}.{label}"
        if not _non_empty_str(label):
            result.error(f"{name} labels must be non-empty strings")
        if not isinstance(cfg, dict):
            result.error(f"{path} must be an object")
            continue

        pin = cfg.get("pin")
        if not isinstance(pin, int):
            result.error(f"{path}.pin must be int")
        elif pin in pins:
            result.error(f"{path}.pin duplicates GPIO pin {pin}")
        else:
            pins.add(pin)

        if require_role:
            role = cfg.get("role")
            if not _non_empty_str(role):
                result.error(f"{path}.role must be a non-empty string")
            elif role in roles:
                result.error(f"{path}.role duplicates role {role!r}")
            else:
                roles.add(role)

        if require_bounce_time:
            bounce_time = cfg.get("bounce_time")
            if not isinstance(bounce_time, (int, float)) or isinstance(bounce_time, bool) or bounce_time <= 0:
                result.error(f"{path}.bounce_time must be a positive number")

    return pins


def _validate_hint_list(
    hints: list,
    path: str,
    seen_hint_ids: set[str],
    hint_extensions: Dict[str, str],
    result: ValidationResult,
) -> Iterable[str]:
    ids = []
    for idx, hint in enumerate(hints):
        hint_path = f"{path}[{idx}]"
        if not isinstance(hint, dict):
            result.error(f"{hint_path} must be an object")
            continue

        hint_id = hint.get("id")
        if not _non_empty_str(hint_id):
            result.error(f"{hint_path}.id must be a non-empty string")
        elif hint_id in seen_hint_ids:
            result.error(f"{hint_path}.id duplicates hint id {hint_id!r}")
        else:
            seen_hint_ids.add(hint_id)
            ids.append(hint_id)

        if not _non_empty_str(hint.get("label")):
            result.error(f"{hint_path}.label must be a non-empty string")

        filename = hint.get("file")
        if not _non_empty_str(filename):
            result.error(f"{hint_path}.file must be a non-empty string")
            continue

        if "/" in filename or "\\" in filename or ".." in filename:
            result.error(f"{hint_path}.file must be a filename without path components")

        ext = Path(filename).suffix.lower()
        if ext not in config.ALLOWED_HINT_AUDIO_EXTENSIONS:
            result.error(
                f"{hint_path}.file extension must be one of "
                f"{sorted(config.ALLOWED_HINT_AUDIO_EXTENSIONS)}"
            )
        elif _non_empty_str(hint_id):
            hint_extensions[hint_id] = ext

    return ids


def _load_json_object(path: Path, label: str, result: ValidationResult) -> Optional[Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        result.error(f"{label} file does not exist: {path}")
        return None
    except OSError as exc:
        result.error(f"{label} could not be read: {exc}")
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        result.error(f"{label} contains invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
        return None

    if not isinstance(data, dict):
        result.error(f"{label} root must be a JSON object")
        return None
    return data


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
