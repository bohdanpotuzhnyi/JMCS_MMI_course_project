from __future__ import annotations

from typing import Callable

from contracts.actions import ActionPayload
from contracts.events import BaseEvent

EventHandler = Callable[[BaseEvent], None]
ActionHandler = Callable[[ActionPayload], None]


class EventBus:
    """Simple in-process bus for modality events and fused actions."""

    def __init__(self) -> None:
        self._event_handlers: list[EventHandler] = []
        self._action_handlers: list[ActionHandler] = []

    def subscribe_events(self, handler: EventHandler) -> Callable[[], None]:
        self._event_handlers.append(handler)

        def unsubscribe() -> None:
            self._event_handlers = [h for h in self._event_handlers if h is not handler]

        return unsubscribe

    def subscribe_actions(self, handler: ActionHandler) -> Callable[[], None]:
        self._action_handlers.append(handler)

        def unsubscribe() -> None:
            self._action_handlers = [h for h in self._action_handlers if h is not handler]

        return unsubscribe

    def publish_event(self, event: BaseEvent) -> None:
        for handler in list(self._event_handlers):
            handler(event)

    def publish_action(self, action: ActionPayload) -> None:
        for handler in list(self._action_handlers):
            handler(action)
