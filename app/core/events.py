"""
GestureOS — Event Bus

Thread-safe communication channel between producers (gesture classifier,
voice engine) and the consumer (action executor).  Also exposes the last
event so the HUD can display the current state.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.actions import ActionType


@dataclass(frozen=True)
class GestureEvent:
    """Immutable event emitted by gesture or voice pipeline."""

    action: ActionType
    value: Any = None                   # e.g. (x, y) for MOVE_CURSOR, app name for OPEN_APP
    source: str = "gesture"             # "gesture" | "voice"
    timestamp: float = field(default_factory=time.time)


class EventBus:
    """
    Singleton thread-safe event bus.

    Producers call ``push(event)`` from any thread.
    The ActionExecutor calls ``pop()`` to consume events.
    The HUD reads ``last_event`` for display purposes.
    """

    _instance: Optional[EventBus] = None
    _lock = threading.Lock()

    def __new__(cls) -> EventBus:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._queue: queue.Queue[GestureEvent] = queue.Queue(maxsize=256)
                cls._instance._last_event: Optional[GestureEvent] = None
                cls._instance._last_event_lock = threading.Lock()
            return cls._instance

    # -- Producer API -------------------------------------------------------

    def push(self, event: GestureEvent) -> None:
        """Enqueue an event (non-blocking; drops oldest if full)."""
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            # Drop oldest, then push
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(event)

        with self._last_event_lock:
            self._last_event = event

    # -- Consumer API -------------------------------------------------------

    def pop(self, timeout: float = 0.1) -> Optional[GestureEvent]:
        """Blocking pop with timeout.  Returns ``None`` on timeout."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # -- HUD API ------------------------------------------------------------

    @property
    def last_event(self) -> Optional[GestureEvent]:
        with self._last_event_lock:
            return self._last_event

    # -- Utilities ----------------------------------------------------------

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    def clear(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for tests)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.clear()
            cls._instance = None
