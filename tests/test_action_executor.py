"""
Unit tests for ActionExecutor.
"""

from unittest.mock import MagicMock

from app.actions.executor import ActionExecutor
from app.core.actions import ActionType
from app.core.events import EventBus, GestureEvent


def test_action_executor_dispatch():
    EventBus.reset()
    bus = EventBus()

    executor = ActionExecutor(event_bus=bus)

    # Mock controllers
    executor._mouse = MagicMock()
    executor._app = MagicMock()

    # Test click event
    bus.push(GestureEvent(action=ActionType.LEFT_CLICK))
    executor._run_loop_single_pass() if hasattr(executor, "_run_loop_single_pass") else executor._handle(bus.pop())

    executor._mouse.click.assert_called_once()

    # Test move cursor event
    bus.push(GestureEvent(action=ActionType.MOVE_CURSOR, value=(500, 300)))
    executor._handle(bus.pop())

    executor._mouse.move.assert_called_once_with(500, 300)

    # Test open app event
    bus.push(GestureEvent(action=ActionType.OPEN_APP, value="chrome"))
    executor._handle(bus.pop())

    executor._app.launch.assert_called_once_with("chrome")
