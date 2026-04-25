import json

from .config import (
    DEFAULT_LANGUAGE,
    HINTS_CONFIG_PATHS,
    SUPPORTED_LANGUAGES,
    VALID_GAME_STATES,
)


def load_hints_config(lang: str) -> dict:
    lang = (lang or DEFAULT_LANGUAGE).lower()
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    path = HINTS_CONFIG_PATHS[lang]
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_hint_index(hints_cfg: dict) -> dict:
    index = {}

    for hint in hints_cfg.get("global", {}).get("hints", []):
        hint_id = hint.get("id")
        if hint_id:
            index[hint_id] = hint

    for state_name in VALID_GAME_STATES:
        scene_data = hints_cfg.get(state_name, {})
        for puzzle in scene_data.get("puzzles", []):
            for hint in puzzle.get("hints", []):
                hint_id = hint.get("id")
                if hint_id:
                    index[hint_id] = hint

    return index


def load_all_hints():
    hints_by_lang = {}
    hint_index_by_lang = {}

    for lang in SUPPORTED_LANGUAGES:
        cfg = load_hints_config(lang)
        hints_by_lang[lang] = cfg
        hint_index_by_lang[lang] = build_hint_index(cfg)

    return hints_by_lang, hint_index_by_lang


def get_hints_for_language(ctx, lang: str) -> dict:
    lang = (lang or DEFAULT_LANGUAGE).lower()
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    return ctx.hints_by_lang[lang]


def get_current_hints(ctx) -> dict:
    return get_hints_for_language(ctx, ctx.current_language)


def get_hints_payload_for_state(ctx, state_name: str) -> dict:
    hints_cfg = get_current_hints(ctx)
    scene_data = hints_cfg.get(state_name, {})

    global_cfg = hints_cfg.get("global", {})

    return {
        "global": {
            "label": global_cfg.get("label", ""),
            "hints": global_cfg.get("hints", []),
        },
        "puzzles": scene_data.get("puzzles", []),
    }


def find_hint_by_id(ctx, hint_id: str):
    return ctx.hint_index_by_lang[ctx.current_language].get(hint_id)
