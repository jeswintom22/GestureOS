"""
GestureOS — FPS Counter

Tracks frames-per-second of the gesture processing loop using an
exponential moving average to smooth out frame-to-frame jitter.
"""

from __future__ import annotations

import time


class FPSCounter:
    """
    Simple smoothed frames-per-second counter.

    Call ``update()`` once per loop iteration; it returns the current
    smoothed FPS.

    Usage::

        counter = FPSCounter()
        fps = counter.update()   # call once per frame
        print(counter.fps)
    """

    def __init__(self, smoothing: float = 0.1) -> None:
        self._smoothing = smoothing
        self._fps: float = 0.0
        self._last_time: float | None = None

    def update(self) -> float:
        """
        Record one frame and return the smoothed FPS.

        The first call only seeds the start time (no meaningful interval
        has elapsed yet), so it returns ``0.0``.

        Returns
        -------
        float
            Exponential moving average of frames per second.
        """
        now = time.perf_counter()
        if self._last_time is None:
            self._last_time = now
            return self._fps

        dt = now - self._last_time
        self._last_time = now

        if dt > 0.0:
            instantaneous_fps = 1.0 / dt
            self._fps = (
                self._smoothing * instantaneous_fps
                + (1.0 - self._smoothing) * self._fps
            )
        return self._fps

    @property
    def fps(self) -> float:
        """Current smoothed FPS value."""
        return self._fps
