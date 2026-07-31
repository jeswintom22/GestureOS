"""
GestureOS — Landmark Smoother

Exponential Moving Average (EMA) filter for hand landmark positions.
Reduces jitter in cursor movement without adding perceptible lag.
"""

from __future__ import annotations

from app.gestures.detector import Landmark

import config


class LandmarkSmoother:
    """
    Apply EMA smoothing to a sequence of Landmark positions.

    Lower alpha → heavier smoothing (more lag, less jitter).
    Higher alpha → lighter smoothing (less lag, more jitter).

    Usage::

        smoother = LandmarkSmoother(alpha=0.4)
        smoothed = smoother.smooth(raw_landmark, frame_w, frame_h)
    """

    def __init__(self, alpha: float = config.CURSOR_SMOOTHING_ALPHA):
        if not 0.0 < alpha <= 1.0:
            raise ValueError(f"alpha must be in (0, 1], got {alpha}")
        self.alpha = alpha
        self._prev_x: float | None = None
        self._prev_y: float | None = None

    def smooth(self, landmark: Landmark, frame_w: int, frame_h: int) -> Landmark:
        """
        Return a new Landmark with smoothed normalised coordinates.

        The first call has no previous data and returns the raw position.
        """
        if self._prev_x is None:
            self._prev_x = landmark.x
            self._prev_y = landmark.y
            return landmark

        sx = self.alpha * landmark.x + (1 - self.alpha) * self._prev_x
        sy = self.alpha * landmark.y + (1 - self.alpha) * self._prev_y

        self._prev_x = sx
        self._prev_y = sy

        return Landmark(
            x=sx,
            y=sy,
            z=landmark.z,
            px=int(sx * frame_w),
            py=int(sy * frame_h),
        )

    def reset(self) -> None:
        """Clear smoothing history (e.g. when hand is lost)."""
        self._prev_x = None
        self._prev_y = None
