from __future__ import annotations

import math

from collections.abc import Iterable

from contracts.actions import ActionPayload, ActionType, Delta, Position
from contracts.events import GestureEvent, GestureType, NormalizedPosition, VoiceEvent
from infra.config.fusion_config import FusionActionRule, FusionConfig

from .context_store import InteractionContextStore


def _default_config() -> FusionConfig:
    return FusionConfig(
        voice_actions={
            "left": FusionActionRule("move_object", dx=-0.1, dy=0.0),
            "right": FusionActionRule("move_object", dx=0.1, dy=0.0),
            "up": FusionActionRule("move_object", dx=0.0, dy=-0.1),
            "down": FusionActionRule("move_object", dx=0.0, dy=0.1),
            "rotate-left": FusionActionRule("rotate_object", rotation=-15.0),
            "rotate-right": FusionActionRule("rotate_object", rotation=15.0),
            "create-sphere": FusionActionRule("create_object", object_type="sphere", use_position=True),
            "create-cube": FusionActionRule("create_object", object_type="cube", use_position=True),
            "create-cuboid": FusionActionRule("create_object", object_type="cuboid", use_position=True),
            "create-diamond": FusionActionRule("create_object", object_type="diamond", use_position=True),
            "select": FusionActionRule("select_object", use_position=True),
            "move-here": FusionActionRule("move_object", use_position=True),
            "drag": FusionActionRule("set_interaction_mode", mode="dragging"),
            "rotate": FusionActionRule("set_interaction_mode", mode="rotating"),
            "resize": FusionActionRule("set_interaction_mode", mode="resizing"),
            "done": FusionActionRule("set_interaction_mode", mode="idle"),
            "delete": FusionActionRule("delete_object"),
            "insert": FusionActionRule("insert_object"),
            "restart": FusionActionRule("reset_app"),
        },
        gesture_actions={
            "swipe_left": FusionActionRule("move_object", dx=-0.1, dy=0.0, use_position=True),
            "swipe_right": FusionActionRule("move_object", dx=0.1, dy=0.0, use_position=True),
            "swipe_up": FusionActionRule("move_object", dx=0.0, dy=-0.1, use_position=True),
            "swipe_down": FusionActionRule("move_object", dx=0.0, dy=0.1, use_position=True),
            "point": FusionActionRule("select_object", use_position=True),
            "pinch": FusionActionRule("select_object", use_position=True),
            "grab": FusionActionRule("select_object", use_position=True),
            "release": FusionActionRule("deselect_object"),
            "open_palm": FusionActionRule("open_menu", use_position=True),
            "fist": FusionActionRule("close_menu", use_position=True),
        },
    )


class FusionEngine:
    """
    Rule-based fusion layer for the current modality vocabulary.

    It accepts raw modality events, updates short-lived context, and emits
    app-facing actions that applications can execute without knowing where
    the input came from.
    """

    def __init__(
        self,
        context: InteractionContextStore | None = None,
        config: FusionConfig | None = None,
    ) -> None:
        self._context = context or InteractionContextStore()
        self._config = config or _default_config()
        self._last_pointer_position: NormalizedPosition | None = None
        self._last_palm_position: NormalizedPosition | None = None
        self._last_pinch_distance: float | None = None

    @property
    def context(self) -> InteractionContextStore:
        return self._context

    def handle_gesture_event(self, event: GestureEvent) -> ActionPayload | Iterable[ActionPayload] | None:
        if not self._config.enabled or event.confidence < self._config.gesture_min_confidence:
            return None
        gesture_name = event.gesture.value
        if self._config.gesture_include and gesture_name not in self._config.gesture_include:
            return None
        if gesture_name in self._config.gesture_exclude:
            return None

        self._context.remember_gesture(event)

        pointer_position = self._pointer_position(event)
        pointer_delta = self._normalized_delta(pointer_position, self._last_pointer_position)
        palm_delta = self._normalized_delta(event.position, self._last_palm_position)
        pinch_distance = self._pinch_distance(event)
        pinch_delta = (
            None
            if pinch_distance is None or self._last_pinch_distance is None
            else pinch_distance - self._last_pinch_distance
        )

        self._last_pointer_position = pointer_position
        self._last_palm_position = event.position
        self._last_pinch_distance = pinch_distance

        pointer_action = None
        if (
            self._config.pointer.emit_update_pointer
            and (pointer_delta is not None or palm_delta is not None or pinch_delta is not None)
        ):
            pointer_action = ActionPayload(
                type=ActionType.UPDATE_POINTER,
                position=Position(x=pointer_position.x, y=pointer_position.y),
                delta=(
                    Delta(dx=pointer_delta[0], dy=pointer_delta[1])
                    if pointer_delta is not None and self._config.pointer.emit_pointer_delta
                    else None
                ),
                metadata={
                    "modality": "gesture",
                    "gesture": event.gesture.value,
                    "hand": event.hand,
                    "palm_delta": (
                        {"dx": palm_delta[0], "dy": palm_delta[1]}
                        if palm_delta is not None and self._config.pointer.emit_palm_delta
                        else None
                    ),
                    "pinch_distance": pinch_distance,
                    "pinch_delta": pinch_delta if self._config.pointer.emit_pinch_delta else None,
                },
                source_events=[event.id],
            )

        rule = self._config.gesture_actions.get(gesture_name)
        if rule is not None:
            return self._actions(
                pointer_action,
                self._action_from_rule(
                    rule,
                    position=Position(x=pointer_position.x, y=pointer_position.y),
                    metadata={"modality": "gesture", "gesture": event.gesture.value},
                    source_events=[event.id],
                ),
            )

        return pointer_action

    def handle_voice_event(self, event: VoiceEvent) -> ActionPayload | None:
        if not self._config.enabled or event.confidence < self._config.voice_min_confidence:
            return None
        self._context.remember_voice(event)
        if not event.intent:
            return None
        if self._config.voice_include and event.intent not in self._config.voice_include:
            return None
        if event.intent in self._config.voice_exclude:
            return None

        source_events = [event.id]
        if self._should_fuse_with_last_gesture(event):
            source_events.append(self._context.state.last_gesture.id)

        rule = self._config.voice_actions.get(event.intent)
        if rule is None:
            return None
        return self._action_from_rule(
            rule,
            position=self._current_position(),
            metadata={"modality": "voice", "intent": event.intent},
            source_events=source_events,
        )

    def _action_from_rule(
        self,
        rule: FusionActionRule,
        *,
        position: Position | None,
        metadata: dict[str, object],
        source_events: list[str],
    ) -> ActionPayload | None:
        if not rule.enabled:
            return None
        return ActionPayload(
            type=ActionType(rule.action),
            delta=(
                Delta(dx=rule.dx, dy=rule.dy, dz=rule.dz)
                if rule.dx is not None and rule.dy is not None
                else None
            ),
            position=position if rule.use_position else None,
            rotation=rule.rotation,
            scale=rule.scale,
            object_type=rule.object_type,
            mode=rule.mode,
            metadata={
                **metadata,
                "requires_confirmation": rule.requires_confirmation,
            },
            source_events=source_events,
            )

    def _should_fuse_with_last_gesture(self, voice_event: VoiceEvent) -> bool:
        last_gesture = self._context.state.last_gesture
        if last_gesture is None:
            return False
        return abs(voice_event.timestamp - last_gesture.timestamp) <= self._config.temporal_window_seconds

    def _current_position(self) -> Position | None:
        if self._last_pointer_position is not None:
            return Position(x=self._last_pointer_position.x, y=self._last_pointer_position.y)

        last_gesture = self._context.state.last_gesture
        if last_gesture is not None:
            pointer_position = self._pointer_position(last_gesture)
            return Position(x=pointer_position.x, y=pointer_position.y)

        last_point = self._context.state.last_point_position
        if last_point is not None:
            return Position(x=last_point[0], y=last_point[1])
        return None

    def _pointer_position(self, event: GestureEvent) -> NormalizedPosition:
        if self._config.pointer.source == "index-finger" and event.landmarks and len(event.landmarks) > 8:
            return event.landmarks[8]
        return event.position

    def _normalized_delta(
        self,
        current: NormalizedPosition,
        previous: NormalizedPosition | None,
    ) -> tuple[float, float] | None:
        if previous is None:
            return None
        return current.x - previous.x, current.y - previous.y

    def _pinch_distance(self, event: GestureEvent) -> float | None:
        if not event.landmarks or len(event.landmarks) <= 8:
            return None
        thumb = event.landmarks[4]
        index = event.landmarks[8]
        return math.hypot(thumb.x - index.x, thumb.y - index.y)

    def _actions(
        self,
        *actions: ActionPayload | None,
    ) -> ActionPayload | list[ActionPayload] | None:
        present_actions = [action for action in actions if action is not None]
        if not present_actions:
            return None
        if len(present_actions) == 1:
            return present_actions[0]
        return present_actions
