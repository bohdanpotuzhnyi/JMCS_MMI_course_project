"""
Intent extraction: transcript string → optional VoiceIntent + confidence.

This module has *no* microphone and *no* network. It is pure text logic, so you can
test it in Python without hardware ("rotate left" → intent rotate-left).

Flow in the full voice pipeline:
    speech_recognition_adapter  →  transcript string  →  intent_from_transcript (here)
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Optional

from .voice_event import VoiceIntent

__all__ = [
    "COMMAND_GRAMMAR",
    "IntentFromTranscriptResult",
    "intent_from_transcript",
]


@dataclass
class IntentFromTranscriptResult:
    """Outcome of matching a single transcript against the keyword rules."""

    intent: Optional[VoiceIntent] = None
    # 1.0 = at least one keyword phrase matched; 0.0 = no match (unrecognized command).
    confidence: float = 0.0
    matched_phrase: Optional[str] = None
    normalized_transcript: str = ""


@dataclass(frozen=True)
class _Rule:
    """One intent label plus phrases that trigger it (all lowercase substrings)."""

    intent: VoiceIntent
    phrases: tuple[str, ...]


# We walk this list top to bottom. First phrase that appears *anywhere* in the text wins.
# More specific phrases must come *before* their broader matches.
_RULES: tuple[_Rule, ...] = (
    _Rule("rotate-left", ("rotate left", "turn left", "counterclockwise", "counter-clockwise")),
    _Rule("rotate-right", ("rotate right", "turn right", "clockwise")),
    _Rule("left", ("move left", "go left", "left")),
    _Rule("right", ("move right", "go right", "right")),
    _Rule("up", ("move up", "go up", "up")),
    _Rule("down", ("move down", "go down", "down")),
)

COMMAND_GRAMMAR: tuple[str, ...] = tuple(
    phrase
    for rule in _RULES
    for phrase in rule.phrases
)

_PHRASE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("write", "right"),
    ("wright", "right"),
    ("rite", "right"),
    ("lift", "left"),
    ("let", "left"),
    ("laugh", "left"),
    ("go to left", "go left"),
    ("go to right", "go right"),
    ("go to up", "go up"),
    ("go to down", "go down"),
    ("counter clockwise", "counterclockwise"),
    ("count the clockwise", "counterclockwise"),
    ("turn life", "turn left"),
    ("turn lift", "turn left"),
    ("turn write", "turn right"),
    ("rotate life", "rotate left"),
    ("rotate write", "rotate right"),
)


def _normalize_transcript(raw: str) -> str:
    """Lowercase, strip punctuation, and normalize common STT quirks."""
    text = raw.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = " ".join(text.split())
    for src, dst in _PHRASE_REPLACEMENTS:
        text = text.replace(src, dst)
    return " ".join(text.split())


def _fuzzy_match(text: str) -> IntentFromTranscriptResult:
    best_intent: Optional[VoiceIntent] = None
    best_phrase: Optional[str] = None
    best_score = 0.0

    for rule in _RULES:
        for phrase in rule.phrases:
            score = SequenceMatcher(None, text, phrase).ratio()
            if phrase in text:
                score = max(score, 0.96)
            if score > best_score:
                best_score = score
                best_intent = rule.intent
                best_phrase = phrase

    if best_score >= 0.74:
        return IntentFromTranscriptResult(
            intent=best_intent,
            confidence=min(0.95, best_score),
            matched_phrase=best_phrase,
            normalized_transcript=text,
        )
    return IntentFromTranscriptResult(confidence=0.0, normalized_transcript=text)


def intent_from_transcript(transcript: str) -> IntentFromTranscriptResult:
    """
    Map speech text to a discrete intent using simple substring rules.

    Called by speech_recognition_adapter when building a VoiceEvent from recognized text.
    """
    text = _normalize_transcript(transcript)
    if not text:
        return IntentFromTranscriptResult(confidence=0.0, normalized_transcript=text)

    for rule in _RULES:
        for phrase in rule.phrases:
            if phrase in text:
                return IntentFromTranscriptResult(
                    intent=rule.intent,
                    confidence=1.0,
                    matched_phrase=phrase,
                    normalized_transcript=text,
                )

    return _fuzzy_match(text)
