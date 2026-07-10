from __future__ import annotations

from features.home.state import HomeState
from features.home.controller import HomeController
from features.home.commands import AddImagesCommand, RemoveImagesCommand, SelectImageCommand, ClearImagesCommand


class TestHomeState:
    def test_initial_state(self) -> None:
        state = HomeState()
        assert state.image_paths == []
        assert state.total_images == 0
        assert not state.has_images

    def test_with_images(self) -> None:
        state = HomeState(image_paths=["/img1.png", "/img2.png"], total_images=2, has_images=True)
        assert state.total_images == 2
        assert state.has_images


class TestAddImagesCommand:
    def test_execute(self, event_bus) -> None:
        cmd = AddImagesCommand(paths=["/test.png"], event_bus=event_bus)
        result = cmd.execute()
        assert result.success
        assert result.value == ["/test.png"]


class TestRemoveImagesCommand:
    def test_execute(self, event_bus) -> None:
        cmd = RemoveImagesCommand(paths=["/test.png"], event_bus=event_bus)
        result = cmd.execute()
        assert result.success


class TestSelectImageCommand:
    def test_execute(self, event_bus) -> None:
        cmd = SelectImageCommand(path="/test.png", index=0, event_bus=event_bus)
        result = cmd.execute()
        assert result.success


class TestClearImagesCommand:
    def test_execute(self, event_bus) -> None:
        cmd = ClearImagesCommand(event_bus=event_bus)
        result = cmd.execute()
        assert result.success
