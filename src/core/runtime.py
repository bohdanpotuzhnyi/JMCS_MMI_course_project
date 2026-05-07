from __future__ import annotations

from collections.abc import Iterable

from contracts.actions import ActionPayload
from contracts.events import GestureEvent, VoiceEvent
from infra.config.fusion_config import FusionConfig

from .application_router import ApplicationController, ApplicationRouter
from .event_bus import EventBus
from .fusion_engine import FusionEngine


class CollaborationRuntime:
    """
    Wires modalities, fusion, and applications together in one place.

    Modality adapters publish shared event objects here. The runtime forwards
    them through the bus, fuses them into app-facing actions, and routes those
    actions to the active application.
    """

    def __init__(self, fusion_config: FusionConfig | None = None) -> None:
        self.bus = EventBus()
        self.fusion = FusionEngine(config=fusion_config)
        self.router = ApplicationRouter()

    def register_app(self, app: ApplicationController) -> None:
        self.router.register(app)

    def set_active_app(self, app_id: str) -> None:
        self.router.set_active_app(app_id)

    def handle_gesture(self, event: GestureEvent) -> None:
        self.bus.publish_event(event)
        self._publish_actions(self.fusion.handle_gesture_event(event))

    def handle_voice(self, event: VoiceEvent) -> None:
        self.bus.publish_event(event)
        self._publish_actions(self.fusion.handle_voice_event(event))

    def _publish_actions(
        self,
        actions: ActionPayload | Iterable[ActionPayload] | None,
    ) -> None:
        if actions is None:
            return
        if isinstance(actions, ActionPayload):
            actions = [actions]
        for action in actions:
            self.bus.publish_action(action)
            self.router.route(action)
