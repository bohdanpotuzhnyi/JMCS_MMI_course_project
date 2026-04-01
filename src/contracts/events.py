# contracts/events.py
# Normalized event contracts shared across all modalities.
# Gesture, voice, and the fusion engine all speak this language.

from __future__ import annotations
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field
import uuid
import time


class ModalitySource(str, Enum):
    GESTURE = "gesture"
    VOICE   = "voice"
    FUSED   = "fused"


class GestureType(str, Enum):
    GRAB        = "grab"
    RELEASE     = "release"
    PINCH       = "pinch"
    POINT       = "point"
    SWIPE_LEFT  = "swipe_left"
    SWIPE_RIGHT = "swipe_right"
    SWIPE_UP    = "swipe_up"
    SWIPE_DOWN  = "swipe_down"
    OPEN_PALM   = "open_palm"
    FIST        = "fist"
    UNKNOWN     = "unknown"


class NormalizedPosition(BaseModel):
    x: float  # 0 = left edge, 1 = right edge
    y: float  # 0 = top edge,  1 = bottom edge
    z: Optional[float] = None  # relative depth when available


class BaseEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: ModalitySource
    timestamp: float = Field(default_factory=time.monotonic)
    confidence: float  # 0.0 – 1.0


class GestureEvent(BaseEvent):
    source: Literal[ModalitySource.GESTURE] = ModalitySource.GESTURE
    gesture: GestureType
    position: NormalizedPosition
    landmarks: Optional[list[NormalizedPosition]] = None
    hand: Optional[Literal["left", "right", "unknown"]] = None


class VoiceEvent(BaseEvent):
    source: Literal[ModalitySource.VOICE] = ModalitySource.VOICE
    transcript: str
    is_final: bool
    intent: Optional[str] = None  # filled in by intent-resolver


class FusedEvent(BaseEvent):
    source: Literal[ModalitySource.FUSED] = ModalitySource.FUSED
    gesture: GestureEvent
    voice: VoiceEvent
    resolved_action: str  # e.g. "move_object", "resize_object"