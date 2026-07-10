from __future__ import annotations

from dataclasses import dataclass

from events.base import Event, EventBus


@dataclass
class TestEvent(Event):
    value: str = ""


class TestEventBus:
    def test_publish_subscribe(self) -> None:
        bus = EventBus()
        received = []

        bus.on(TestEvent, lambda e: received.append(e.value))
        bus.emit(TestEvent(value="hello"))

        assert len(received) == 1
        assert received[0] == "hello"

    def test_multiple_listeners(self) -> None:
        bus = EventBus()
        results = []

        bus.on(TestEvent, lambda e: results.append("a"))
        bus.on(TestEvent, lambda e: results.append("b"))
        bus.emit(TestEvent())

        assert results == ["a", "b"]

    def test_unsubscribe(self) -> None:
        bus = EventBus()
        results = []

        def handler(e: TestEvent) -> None:
            results.append("called")

        bus.on(TestEvent, handler)
        bus.off(TestEvent, handler)
        bus.emit(TestEvent())

        assert len(results) == 0

    def test_no_listeners(self) -> None:
        bus = EventBus()
        bus.emit(TestEvent(value="no crash"))

    def test_different_event_types(self) -> None:
        bus = EventBus()
        results = []

        @dataclass
        class EventA(Event):
            pass

        @dataclass
        class EventB(Event):
            pass

        bus.on(EventA, lambda e: results.append("a"))
        bus.on(EventB, lambda e: results.append("b"))
        bus.emit(EventA())
        bus.emit(EventB())

        assert results == ["a", "b"]
