from __future__ import annotations

from store.base import Action
from store.app_store import AppStore, AppState
from store.processing_store import ProcessingStore, ProcessingState
from store.settings_store import SettingsStore, SettingsState
from store.session_store import SessionStore, SessionState


class TestAppStore:
    def test_initial_state(self) -> None:
        store = AppStore()
        assert store.state.current_page == 0
        assert store.state.theme == "dark"

    def test_set_page(self) -> None:
        store = AppStore()
        store.dispatch(Action(type="SET_PAGE", payload={"page": 2}))
        assert store.state.current_page == 2

    def test_set_theme(self) -> None:
        store = AppStore()
        store.dispatch(Action(type="SET_THEME", payload={"theme": "light"}))
        assert store.state.theme == "light"

    def test_set_processing(self) -> None:
        store = AppStore()
        store.dispatch(Action(type="SET_PROCESSING", payload={"running": True}))
        assert store.state.is_processing

    def test_subscribe(self) -> None:
        store = AppStore()
        calls = []
        store.subscribe(lambda s: calls.append(s.current_page))
        store.dispatch(Action(type="SET_PAGE", payload={"page": 1}))
        assert len(calls) == 1
        assert calls[0] == 1

    def test_unsubscribe(self) -> None:
        store = AppStore()
        calls = []
        listener = lambda s: calls.append(s.current_page)
        store.subscribe(listener)
        store.unsubscribe(listener)
        store.dispatch(Action(type="SET_PAGE", payload={"page": 1}))
        assert len(calls) == 0

    def test_unknown_action_returns_same_state(self) -> None:
        store = AppStore()
        state_before = store.state
        store.dispatch(Action(type="UNKNOWN"))
        assert store.state.current_page == state_before.current_page


class TestProcessingStore:
    def test_initial_state(self) -> None:
        store = ProcessingStore()
        assert not store.state.is_running

    def test_start(self) -> None:
        store = ProcessingStore()
        store.dispatch(Action(type="PROCESSING_START", payload={"job_id": "j1", "total": 5}))
        assert store.state.is_running
        assert store.state.total == 5

    def test_progress(self) -> None:
        store = ProcessingStore()
        store.dispatch(Action(type="PROCESSING_START", payload={"job_id": "j1", "total": 5}))
        store.dispatch(Action(type="PROCESSING_PROGRESS", payload={"completed": 2, "percentage": 40.0}))
        assert store.state.completed == 2

    def test_pause_resume(self) -> None:
        store = ProcessingStore()
        store.dispatch(Action(type="PROCESSING_START", payload={"job_id": "j1", "total": 5}))
        store.dispatch(Action(type="PROCESSING_PAUSE"))
        assert store.state.is_paused
        store.dispatch(Action(type="PROCESSING_RESUME"))
        assert not store.state.is_paused

    def test_complete(self) -> None:
        store = ProcessingStore()
        store.dispatch(Action(type="PROCESSING_START", payload={"job_id": "j1", "total": 5}))
        store.dispatch(Action(type="PROCESSING_COMPLETE"))
        assert not store.state.is_running

    def test_reset(self) -> None:
        store = ProcessingStore()
        store.dispatch(Action(type="PROCESSING_START", payload={"job_id": "j1", "total": 5}))
        store.dispatch(Action(type="PROCESSING_RESET"))
        assert store.state.total == 0


class TestSettingsStore:
    def test_initial_state(self) -> None:
        store = SettingsStore()
        assert store.state.output_folder == "output/final"

    def test_load(self) -> None:
        store = SettingsStore()
        store.dispatch(Action(type="SETTINGS_LOAD", payload={"settings": {"output_folder": "/custom"}}))
        assert store.state.output_folder == "/custom"

    def test_update(self) -> None:
        store = SettingsStore()
        store.dispatch(Action(type="SETTINGS_UPDATE", payload={"settings": {"quality": 100}}))
        assert store.state.quality == 100


class TestSessionStore:
    def test_initial_state(self) -> None:
        store = SessionStore()
        assert store.state.window_width == 1180

    def test_update(self) -> None:
        store = SessionStore()
        store.dispatch(Action(type="SESSION_UPDATE", payload={"license": "licensed"}))
        assert store.state.license_status == "licensed"

    def test_add_recent(self) -> None:
        store = SessionStore()
        store.dispatch(Action(type="SESSION_ADD_RECENT", payload={"path": "/project1"}))
        assert "/project1" in store.state.recent_projects
