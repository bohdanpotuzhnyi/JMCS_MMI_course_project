"""Voice modality types used by the voice module.

This file is intentionally tiny:
- `VoiceEvent` is imported from the shared `contracts` package (the real event schema)
- `VoiceIntent` is a small set of strings this module can output
"""

from typing import Literal

from contracts.events import VoiceEvent

# The intent labels the voice module can emit.
VoiceIntent = Literal["left", "right", "up", "down", "rotate-left", "rotate-right"]

__all__ = ["VoiceEvent", "VoiceIntent"]
