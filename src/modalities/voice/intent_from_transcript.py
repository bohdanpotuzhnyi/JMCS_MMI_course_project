"""
Intent extraction: transcript string → (intent, confidence).

This file intentionally contains *only* pure text logic:
- no microphone
- no Vosk / SpeechRecognition imports
- no networking

That keeps it easy to test and easy to monkey-patch from demo apps.

Important: some apps mutate `_RULES` and `COMMAND_GRAMMAR` at runtime to extend the
vocabulary. Keep those names stable and module-level.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from difflib import SequenceMatcher
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

    # What command we think the user said (or None if unknown).
    intent: Optional[VoiceIntent] = None
    # 1.0 = at least one keyword phrase matched; 0.0 = no match (unrecognized command).
    confidence: float = 0.0
    # The exact phrase we matched (helpful for debugging).
    matched_phrase: Optional[str] = None
    # Cleaned-up transcript used for matching (lowercase, etc.).
    normalized_transcript: str = ""


@dataclass(frozen=True)
class _Rule:
    """One intent label plus phrases that trigger it (all lowercase substrings)."""

    # The intent label this rule produces.
    intent: VoiceIntent
    # Phrases that should trigger this intent.
    phrases: tuple[str, ...]


# We walk this list top → bottom. First phrase that appears *anywhere* in the text wins.
# More specific phrases must come before their broader matches.
_RULES: tuple[_Rule, ...] = (
    _Rule("rotate-left", ("rotate left", "turn left", "counterclockwise", "counter-clockwise")),
    _Rule("rotate-right", ("rotate right", "turn right", "clockwise")),
    _Rule("left", ("move left", "go left", "left")),
    _Rule("right", ("move right", "go right", "right")),
    _Rule("up", ("move up", "go up", "up")),
    _Rule("down", ("move down", "go down", "down")),
)

# This list is fed into Vosk as a "limited vocabulary" to improve command recognition.
COMMAND_GRAMMAR: tuple[str, ...] = tuple(
    phrase
    for rule in _RULES
    for phrase in rule.phrases
)

# Common STT quirks / homophones we want to normalize before rule matching.
# Keep this as a tuple so apps can easily extend/replace it if they want.
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

# Precompiled regex for speed + readability.
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s-]")


def _normalize_transcript(raw: str) -> str:
    """Lowercase, strip punctuation, and normalize common STT quirks."""
    # Example: "Rotate, write!!" -> "rotate right"
    text = raw.lower().strip()
    text = _NON_ALNUM_RE.sub(" ", text)
    text = " ".join(text.split())
    for src, dst in _PHRASE_REPLACEMENTS:
        text = text.replace(src, dst)
    return " ".join(text.split())


def _first_substring_rule_match(text: str) -> IntentFromTranscriptResult | None:
    """Return a 1.0-confidence match based on substring rules, or None."""
    # Fast path: plain substring matching.
    for rule in _RULES:
        for phrase in rule.phrases:
            if phrase in text:
                return IntentFromTranscriptResult(
                    intent=rule.intent,
                    confidence=1.0,
                    matched_phrase=phrase,
                    normalized_transcript=text,
                )
    return None


def _fuzzy_match(text: str) -> IntentFromTranscriptResult:
    """
    Fall back to a fuzzy comparison against each known phrase.

    This intentionally stays simple (SequenceMatcher). The output is not used as a
    probability; it’s just a "close enough" heuristic.
    """
    best_intent: VoiceIntent | None = None
    best_phrase: str | None = None
    best_score: float = 0.0

    for rule in _RULES:
        for phrase in rule.phrases:
            # Compare "how similar" the transcript is to a known phrase.
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

    # 1) Exact / rule-based match.
    exact = _first_substring_rule_match(text)
    if exact is not None:
        return exact
    # 2) Fuzzy fallback match.
    return _fuzzy_match(text)
