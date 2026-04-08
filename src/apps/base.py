from __future__ import annotations

from dataclasses import dataclass, field

from contracts.actions import ActionPayload


@dataclass
class LoggingDemoApp:
    """
    Minimal app stub for early integration.

    Real apps can replace this with their own scene logic, but the interface stays
    the same: the collaboration core emits ActionPayload objects, the app consumes them.
    """

    app_id: str
    received_actions: list[ActionPayload] = field(default_factory=list)

    def handle_action(self, action: ActionPayload) -> None:
        self.received_actions.append(action)
