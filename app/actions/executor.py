"""
GestureOS — Action Executor

Consumes ``GestureEvent`` objects from the ``EventBus`` and dispatches
them to the appropriate OS controller (mouse, volume, brightness, etc.).
Runs as a daemon thread.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

from app.core.actions import ActionType
from app.core.events import EventBus, GestureEvent
from app.actions.mouse import MouseController
from app.actions.volume import VolumeController
from app.actions.brightness import BrightnessController
from app.actions.media import MediaController
from app.actions.window_manager import WindowManager
from app.actions.app_launcher import AppLauncher

log = logging.getLogger(__name__)


class ActionExecutor:
    """
    Dispatch loop that maps ``ActionType`` → OS controller method.

    Usage::

        executor = ActionExecutor(event_bus)
        executor.start()   # starts daemon thread
        ...
        executor.stop()
    """

    def __init__(self, event_bus: EventBus | None = None):
        self._bus = event_bus or EventBus()
        self._stop_event = threading.Event()

        # Lazily initialise controllers (some may fail on non-Windows)
        self._mouse = MouseController()
        self._media = MediaController()
        self._window = WindowManager()
        self._app = AppLauncher()

        # Volume and brightness may fail if hardware is unavailable
        try:
            self._volume = VolumeController()
        except Exception:
            log.warning("Volume control unavailable")
            self._volume = None

        try:
            self._brightness = BrightnessController()
        except Exception:
            log.warning("Brightness control unavailable")
            self._brightness = None

        # Build dispatch table
        self._dispatch: dict[ActionType, Callable[[GestureEvent], None]] = {
            ActionType.MOVE_CURSOR: self._on_move,
            ActionType.LEFT_CLICK: lambda _: self._mouse.click(),
            ActionType.DOUBLE_CLICK: lambda _: self._mouse.double_click(),
            ActionType.RIGHT_CLICK: lambda _: self._mouse.right_click(),
            ActionType.SCROLL_UP: self._on_scroll_up,
            ActionType.SCROLL_DOWN: self._on_scroll_down,
            ActionType.DRAG_START: lambda _: self._mouse.drag_start(),
            ActionType.DRAG_END: lambda _: self._mouse.drag_end(),
            ActionType.VOLUME_UP: lambda _: self._volume.volume_up() if self._volume else None,
            ActionType.VOLUME_DOWN: lambda _: self._volume.volume_down() if self._volume else None,
            ActionType.MUTE: lambda _: self._volume.toggle_mute() if self._volume else None,
            ActionType.BRIGHTNESS_UP: lambda _: self._brightness.brightness_up() if self._brightness else None,
            ActionType.BRIGHTNESS_DOWN: lambda _: self._brightness.brightness_down() if self._brightness else None,
            ActionType.MEDIA_PLAY_PAUSE: lambda _: self._media.play_pause(),
            ActionType.MEDIA_NEXT: lambda _: self._media.next_track(),
            ActionType.MEDIA_PREV: lambda _: self._media.prev_track(),
            ActionType.CLOSE_WINDOW: lambda _: self._window.close_window(),
            ActionType.MINIMIZE_WINDOW: lambda _: self._window.minimize(),
            ActionType.MAXIMIZE_WINDOW: lambda _: self._window.maximize(),
            ActionType.SWITCH_WINDOW: lambda _: self._window.switch_window(),
            ActionType.SCREENSHOT: lambda _: self._window.screenshot(),
            ActionType.OPEN_APP: self._on_open_app,
            ActionType.NONE: lambda _: None,
        }

        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the executor in a daemon thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="ActionExecutor",
            daemon=True,
        )
        self._thread.start()
        log.info("ActionExecutor started")

    def stop(self) -> None:
        """Signal the executor to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        log.info("ActionExecutor stopped")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            event = self._bus.pop(timeout=0.05)
            if event is None:
                continue
            self._handle(event)

    def _handle(self, event: GestureEvent) -> None:
        handler = self._dispatch.get(event.action)
        if handler:
            try:
                handler(event)
            except Exception:
                log.exception("Error handling %s", event.action)
        elif event.action == ActionType.STOP:
            self._stop_event.set()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_move(self, event: GestureEvent) -> None:
        if event.value and isinstance(event.value, tuple):
            x, y = event.value
            self._mouse.move(x, y)

    def _on_scroll_up(self, event: GestureEvent) -> None:
        amount = event.value if isinstance(event.value, int) else 3
        self._mouse.scroll(amount)

    def _on_scroll_down(self, event: GestureEvent) -> None:
        amount = event.value if isinstance(event.value, int) else 3
        self._mouse.scroll(-amount)

    def _on_open_app(self, event: GestureEvent) -> None:
        if event.value and isinstance(event.value, str):
            self._app.launch(event.value)
