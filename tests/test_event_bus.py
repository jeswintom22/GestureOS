"""
Unit tests for EventBus.
"""

import threading
import time

from app.core.actions import ActionType
from app.core.events import EventBus, GestureEvent


def test_event_bus_push_pop():
    EventBus.reset()
    bus = EventBus()

    event = GestureEvent(action=ActionType.LEFT_CLICK, source="test")
    bus.push(event)

    popped = bus.pop(timeout=0.1)
    assert popped is not None
    assert popped.action == ActionType.LEFT_CLICK
    assert popped.source == "test"


def test_event_bus_last_event():
    EventBus.reset()
    bus = EventBus()

    e1 = GestureEvent(action=ActionType.MOVE_CURSOR, value=(100, 200))
    bus.push(e1)
    assert bus.last_event == e1

    e2 = GestureEvent(action=ActionType.VOLUME_UP)
    bus.push(e2)
    assert bus.last_event == e2


def test_event_bus_thread_safety():
    EventBus.reset()
    bus = EventBus()

    def producer():
        for _ in range(50):
            bus.push(GestureEvent(action=ActionType.SCROLL_UP))

    threads = [threading.Thread(target=producer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    count = 0
    while bus.pop(timeout=0.01) is not None:
        count += 1

    assert count == 200
