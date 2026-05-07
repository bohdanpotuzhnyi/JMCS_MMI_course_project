"""Voice modality aliases backed by the shared contracts package."""

from typing import Literal

from contracts.events import VoiceEvent

VoiceIntent = Literal[
    "left",
    "right",
    "up",
    "down",
    "rotate-left",
    "rotate-right",
    "create-sphere",
    "create-cube",
    "create-cuboid",
    "create-diamond",
    "select",
    "move-here",
    "drag",
    "rotate",
    "resize",
    "done",
    "insert",
    "restart",
    "delete",
]

__all__ = ["VoiceEvent", "VoiceIntent"]
