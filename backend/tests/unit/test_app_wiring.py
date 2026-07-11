"""Tests that platform services are wired into the application."""

from __future__ import annotations

from app.platform.events import InProcessEventBus
from fastapi import FastAPI


def test_event_bus_is_available_on_app_state(app: FastAPI) -> None:
    assert isinstance(app.state.event_bus, InProcessEventBus)
