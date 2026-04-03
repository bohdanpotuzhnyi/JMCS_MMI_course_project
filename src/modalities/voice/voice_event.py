"""
Shapes of data the voice modality *outputs* for the rest of the toolkit.

The collaboration core (fusion, context, apps) should not care *how* you got speech;
it only cares that events look like this. TypedDict = "a dict with these keys and types."

Later, the team may unify this with src/contracts/events.ts (TypeScript). Until then,
Python code uses these definitions locally.
"""

from typing import Literal, NotRequired, TypedDict

# Currently supported discrete commands (movement-only).
# The collaboration core can later map these to canonical actions.
VoiceIntent = Literal["left", "right", "up", "down", "rotate-left", "rotate-right"]


class VoiceEvent(TypedDict):
    """One utterance, packaged for the event bus / fusion layer."""

    type: Literal["voice"]  # Lets the core distinguish voice from GestureEvent, etc.
    timestamp: float  # Milliseconds since epoch (same idea as JS Date.now()).
    transcript: str  # Raw text from the speech recognizer.
    confidence: float  # 1.0 = intent matched; 0.3 = heard speech, no intent; 0.0 = empty.
    intent: NotRequired[VoiceIntent]  # Omitted if no supported intent matched.
    slots: NotRequired[dict[str, str | int]]  # Reserved for future use.
