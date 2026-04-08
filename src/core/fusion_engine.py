from __future__ import annotations

from contracts.actions import ActionPayload, ActionType, Delta, Position
from contracts.events import GestureEvent, GestureType, VoiceEvent

from .context_store import InteractionContextStore


_MOVE_DELTAS: dict[str, tuple[float, float]] = {
    "left": (-0.1, 0.0),
    "right": (0.1, 0.0),
    "up": (0.0, -0.1),
    "down": (0.0, 0.1),
}

_ROTATION_DEGREES: dict[str, float] = {
    "rotate-left": -15.0,
    "rotate-right": 15.0,
}

_GESTURE_MOVE_DELTAS: dict[GestureType, tuple[float, float]] = {
    GestureType.SWIPE_LEFT: (-0.1, 0.0),
    GestureType.SWIPE_RIGHT: (0.1, 0.0),
    GestureType.SWIPE_UP: (0.0, -0.1),
    GestureType.SWIPE_DOWN: (0.0, 0.1),
}


class FusionEngine:
    """
    Rule-based fusion layer for the current modality vocabulary.

    It accepts raw modality events, updates short-lived context, and emits
    app-facing actions that applications can execute without knowing where
    the input came from.
    """

    def __init__(self, context: InteractionContextStore | None = None) -> None:
        self._context = context or InteractionContextStore()

    @property
    def context(self) -> InteractionContextStore:
        return self._context

    def handle_gesture_event(self, event: GestureEvent) -> ActionPayload | None:
        self._context.remember_gesture(event)

        if event.gesture in _GESTURE_MOVE_DELTAS:
            dx, dy = _GESTURE_MOVE_DELTAS[event.gesture]
            return ActionPayload(
                type=ActionType.MOVE_OBJECT,
                delta=Delta(dx=dx, dy=dy),
                position=Position(x=event.position.x, y=event.position.y),
                source_events=[event.id],
            )

        if event.gesture in (GestureType.POINT, GestureType.PINCH, GestureType.GRAB):
            return ActionPayload(
                type=ActionType.SELECT_OBJECT,
                position=Position(x=event.position.x, y=event.position.y),
                source_events=[event.id],
            )

        if event.gesture == GestureType.RELEASE:
            return ActionPayload(
                type=ActionType.DESELECT_OBJECT,
                source_events=[event.id],
            )

        if event.gesture == GestureType.OPEN_PALM:
            return ActionPayload(
                type=ActionType.OPEN_MENU,
                position=Position(x=event.position.x, y=event.position.y),
                source_events=[event.id],
            )

        if event.gesture == GestureType.FIST:
            return ActionPayload(
                type=ActionType.CLOSE_MENU,
                position=Position(x=event.position.x, y=event.position.y),
                source_events=[event.id],
            )

        return None

    def handle_voice_event(self, event: VoiceEvent) -> ActionPayload | None:
        self._context.remember_voice(event)
        if not event.intent:
            return None

        source_events = [event.id]
        if self._should_fuse_with_last_gesture(event):
            source_events.append(self._context.state.last_gesture.id)

        if event.intent in _MOVE_DELTAS:
            dx, dy = _MOVE_DELTAS[event.intent]
            return ActionPayload(
                type=ActionType.MOVE_OBJECT,
                delta=Delta(dx=dx, dy=dy),
                position=self._current_position(),
                source_events=source_events,
            )

        if event.intent in _ROTATION_DEGREES:
            return ActionPayload(
                type=ActionType.ROTATE_OBJECT,
                rotation=_ROTATION_DEGREES[event.intent],
                position=self._current_position(),
                source_events=source_events,
            )

        return None

    def _should_fuse_with_last_gesture(self, voice_event: VoiceEvent) -> bool:
        last_gesture = self._context.state.last_gesture
        if last_gesture is None:
            return False
        return abs(voice_event.timestamp - last_gesture.timestamp) <= 1.5

    def _current_position(self) -> Position | None:
        last_gesture = self._context.state.last_gesture
        if last_gesture is not None:
            return Position(x=last_gesture.position.x, y=last_gesture.position.y)

        last_point = self._context.state.last_point_position
        if last_point is not None:
            return Position(x=last_point[0], y=last_point[1])
        return None
