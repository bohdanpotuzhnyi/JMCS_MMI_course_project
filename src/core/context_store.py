from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from contracts.events import GestureEvent, VoiceEvent


@dataclass
class InteractionContext:
    selected_target_id: Optional[str] = None
    last_point_position: Optional[tuple[float, float]] = None
    last_gesture: Optional[GestureEvent] = None
    last_voice: Optional[VoiceEvent] = None
    pending_clarification: Optional[str] = None
    recent_event_ids: deque[str] = field(default_factory=lambda: deque(maxlen=20))


class InteractionContextStore:
    """Tracks short-lived multimodal state for the fusion engine."""

    def __init__(self) -> None:
        self._state = InteractionContext()

    @property
    def state(self) -> InteractionContext:
        return self._state

    def remember_gesture(self, event: GestureEvent) -> None:
        self._state.last_gesture = event
        self._state.recent_event_ids.append(event.id)
        if event.gesture.value == "point":
            self._state.last_point_position = (event.position.x, event.position.y)

    def remember_voice(self, event: VoiceEvent) -> None:
        self._state.last_voice = event
        self._state.recent_event_ids.append(event.id)

    def set_selected_target(self, target_id: Optional[str]) -> None:
        self._state.selected_target_id = target_id

    def set_pending_clarification(self, reason: Optional[str]) -> None:
        self._state.pending_clarification = reason
