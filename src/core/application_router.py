from __future__ import annotations

from typing import Protocol

from contracts.actions import ActionPayload


class ApplicationController(Protocol):
    """Application boundary used by the collaboration core."""

    app_id: str

    def handle_action(self, action: ActionPayload) -> None:
        ...


class ApplicationRouter:
    """Routes fused actions to the currently active application."""

    def __init__(self) -> None:
        self._apps: dict[str, ApplicationController] = {}
        self._active_app_id: str | None = None

    def register(self, app: ApplicationController) -> None:
        self._apps[app.app_id] = app
        if self._active_app_id is None:
            self._active_app_id = app.app_id

    def set_active_app(self, app_id: str) -> None:
        if app_id not in self._apps:
            raise KeyError(f"Unknown app: {app_id}")
        self._active_app_id = app_id

    def route(self, action: ActionPayload) -> None:
        if self._active_app_id is None:
            return
        self._apps[self._active_app_id].handle_action(action)
