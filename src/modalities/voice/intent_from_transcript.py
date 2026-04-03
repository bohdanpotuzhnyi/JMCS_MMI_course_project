"""
Intent extraction: transcript string → optional VoiceIntent + confidence.

This module has *no* microphone and *no* network. It is pure text logic, so you can
test it in Python without hardware ("rotate left" → intent rotate-left).

Flow in the full voice pipeline:
    speech_recognition_adapter  →  transcript string  →  intent_from_transcript (here)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .voice_event import VoiceIntent

__all__ = ["IntentFromTranscriptResult", "intent_from_transcript"]


@dataclass
class IntentFromTranscriptResult:
    """Outcome of matching a single transcript against the keyword rules."""

    intent: Optional[VoiceIntent] = None
    # 1.0 = at least one keyword phrase matched; 0.0 = no match (unrecognized command).
    confidence: float = 0.0


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


def _normalize_transcript(raw: str) -> str:
    """Lowercase, trim, collapse spaces so matching is stable across STT quirks."""
    return " ".join(raw.lower().strip().split())


def intent_from_transcript(transcript: str) -> IntentFromTranscriptResult:
    """
    Map speech text to a discrete intent using simple substring rules.

    Called by speech_recognition_adapter when building a VoiceEvent from recognized text.
    """
    text = _normalize_transcript(transcript)
    if not text:
        return IntentFromTranscriptResult(confidence=0.0)

    for rule in _RULES:
        for phrase in rule.phrases:
            if phrase in text:
                return IntentFromTranscriptResult(intent=rule.intent, confidence=1.0)

    return IntentFromTranscriptResult(confidence=0.0)
