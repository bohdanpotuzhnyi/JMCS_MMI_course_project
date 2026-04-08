"""Voice modality aliases backed by the shared contracts package."""

from typing import Literal

from contracts.events import VoiceEvent

VoiceIntent = Literal["left", "right", "up", "down", "rotate-left", "rotate-right"]

__all__ = ["VoiceEvent", "VoiceIntent"]
