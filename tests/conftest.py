from __future__ import annotations

from typing import Any, Dict, Generator, List

import pytest

from commands.base import CommandDispatcher
from events.base import EventBus
from store.base import Action, Store
from store.app_store import AppStore, AppState, app_reducer
from store.processing_store import ProcessingStore, ProcessingState, processing_reducer
from store.settings_store import SettingsStore, SettingsState, settings_reducer
from store.session_store import SessionStore, SessionState, session_reducer
from common.result import Result, Success, Failure


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def dispatcher(event_bus: EventBus) -> CommandDispatcher:
    return CommandDispatcher(event_bus)


@pytest.fixture
def app_store() -> AppStore:
    return AppStore()


@pytest.fixture
def processing_store() -> ProcessingStore:
    return ProcessingStore()


@pytest.fixture
def settings_store() -> SettingsStore:
    return SettingsStore()


@pytest.fixture
def session_store() -> SessionStore:
    return SessionStore()
