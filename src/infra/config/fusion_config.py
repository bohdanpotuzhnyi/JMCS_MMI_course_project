from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FusionActionRule:
    action: str
    dx: float | None = None
    dy: float | None = None
    dz: float | None = None
    rotation: float | None = None
    scale: float | None = None
    object_type: str | None = None
    mode: str | None = None
    use_position: bool = False
    requires_confirmation: bool = False
    enabled: bool = True


@dataclass(frozen=True)
class FusionPointerConfig:
    source: str = "index-finger"
    emit_update_pointer: bool = True
    emit_pointer_delta: bool = True
    emit_palm_delta: bool = True
    emit_pinch_delta: bool = True


@dataclass(frozen=True)
class FusionConfig:
    enabled: bool = True
    engine: str = "3d"
    strategy: str = "rule-based"
    temporal_window_seconds: float = 1.5
    voice_min_confidence: float = 0.0
    gesture_min_confidence: float = 0.0
    pointer: FusionPointerConfig = field(default_factory=FusionPointerConfig)
    voice_include: set[str] = field(default_factory=set)
    voice_exclude: set[str] = field(default_factory=set)
    gesture_include: set[str] = field(default_factory=set)
    gesture_exclude: set[str] = field(default_factory=set)
    voice_phrases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    voice_actions: dict[str, FusionActionRule] = field(default_factory=dict)
    gesture_actions: dict[str, FusionActionRule] = field(default_factory=dict)


def load_fusion_config(path: str | Path) -> FusionConfig:
    parser = ConfigParser()
    parser.optionxform = str
    loaded = parser.read(path)
    if not loaded:
        raise FileNotFoundError(f"Fusion config not found: {path}")

    return FusionConfig(
        enabled=_get_bool(parser, "fusion-core", "ENABLED", True),
        engine=_get(parser, "fusion-core", "ENGINE", "3d"),
        strategy=_get(parser, "fusion-core", "STRATEGY", "rule-based"),
        temporal_window_seconds=_get_duration(parser, "fusion-timing", "TEMPORAL_WINDOW", 1.5),
        voice_min_confidence=_get_float(parser, "fusion-confidence", "VOICE_MIN_CONFIDENCE", 0.0),
        gesture_min_confidence=_get_float(parser, "fusion-confidence", "GESTURE_MIN_CONFIDENCE", 0.0),
        pointer=FusionPointerConfig(
            source=_get(parser, "fusion-pointer", "SOURCE", "index-finger"),
            emit_update_pointer=_get_bool(parser, "fusion-pointer", "EMIT_UPDATE_POINTER", True),
            emit_pointer_delta=_get_bool(parser, "fusion-pointer", "EMIT_POINTER_DELTA", True),
            emit_palm_delta=_get_bool(parser, "fusion-pointer", "EMIT_PALM_DELTA", True),
            emit_pinch_delta=_get_bool(parser, "fusion-pointer", "EMIT_PINCH_DELTA", True),
        ),
        voice_include=set(_get_list(parser, "fusion-voice-include", "INTENTS")),
        voice_exclude=set(_get_list(parser, "fusion-voice-exclude", "INTENTS")),
        gesture_include=set(_get_list(parser, "fusion-gesture-include", "GESTURES")),
        gesture_exclude=set(_get_list(parser, "fusion-gesture-exclude", "GESTURES")),
        voice_phrases=_load_voice_phrases(parser),
        voice_actions=_load_action_rules(parser, "fusion-action.voice."),
        gesture_actions=_load_action_rules(parser, "fusion-action.gesture."),
    )


def _load_voice_phrases(parser: ConfigParser) -> dict[str, tuple[str, ...]]:
    prefix = "fusion-voice.intent."
    phrases: dict[str, tuple[str, ...]] = {}
    for section in parser.sections():
        if section.startswith(prefix):
            intent = section.removeprefix(prefix)
            if _get_bool(parser, section, "ENABLED", True):
                phrases[intent] = tuple(_get_list(parser, section, "PHRASES"))
    return phrases


def _load_action_rules(parser: ConfigParser, prefix: str) -> dict[str, FusionActionRule]:
    rules: dict[str, FusionActionRule] = {}
    for section in parser.sections():
        if section.startswith(prefix):
            key = section.removeprefix(prefix)
            action = _get(parser, section, "ACTION", "")
            if not action:
                continue
            rules[key] = FusionActionRule(
                action=action,
                dx=_get_optional_float(parser, section, "DX"),
                dy=_get_optional_float(parser, section, "DY"),
                dz=_get_optional_float(parser, section, "DZ"),
                rotation=_get_optional_float(parser, section, "ROTATION"),
                scale=_get_optional_float(parser, section, "SCALE"),
                object_type=_get_optional(parser, section, "OBJECT_TYPE"),
                mode=_get_optional(parser, section, "MODE"),
                use_position=_get_bool(parser, section, "USE_POSITION", False),
                requires_confirmation=_get_bool(parser, section, "REQUIRES_CONFIRMATION", False),
                enabled=_get_bool(parser, section, "ENABLED", True),
            )
    return rules


def _get(parser: ConfigParser, section: str, key: str, default: str) -> str:
    if not parser.has_section(section) or not parser.has_option(section, key):
        return default
    return parser.get(section, key).strip()


def _get_optional(parser: ConfigParser, section: str, key: str) -> str | None:
    value = _get(parser, section, key, "")
    return value or None


def _get_bool(parser: ConfigParser, section: str, key: str, default: bool) -> bool:
    value = _get(parser, section, key, "YES" if default else "NO").upper()
    return value in {"YES", "TRUE", "1", "ON"}


def _get_float(parser: ConfigParser, section: str, key: str, default: float) -> float:
    value = _get(parser, section, key, "")
    return float(value) if value else default


def _get_optional_float(parser: ConfigParser, section: str, key: str) -> float | None:
    value = _get(parser, section, key, "")
    return float(value) if value else None


def _get_duration(parser: ConfigParser, section: str, key: str, default: float) -> float:
    raw = _get(parser, section, key, "")
    if not raw:
        return default
    value = raw.strip().lower()
    if value.endswith("ms"):
        return float(value[:-2]) / 1000.0
    if value.endswith("s"):
        return float(value[:-1])
    if value.endswith("m"):
        return float(value[:-1]) * 60.0
    return float(value)


def _get_list(parser: ConfigParser, section: str, key: str) -> list[str]:
    raw = _get(parser, section, key, "")
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]
