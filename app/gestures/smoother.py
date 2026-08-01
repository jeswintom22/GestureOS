"""
GestureOS — Landmark Smoother

One Euro filter (Casiez, Roussel & Vogel, 2012) for hand landmark positions.

Unlike a fixed EMA, the One Euro filter is speed-adaptive: its cutoff
frequency scales with the estimated velocity of the signal. When the hand
is still it applies heavy smoothing (killing physiological tremor and
model jitter); when the hand moves fast the cutoff rises and lag
effectively disappears.

Three tunable parameters:

- ``min_cutoff`` (Hz): smoothing at rest. Lower = less jitter but slower to
  start moving.
- ``beta``: responsiveness to speed. Higher = less lag on fast movements.
- ``d_cutoff`` (Hz): smoothing of the velocity estimate itself. Usually left
  at ~1.0.

Usage::

    smoother = OneEuroFilter()
    smoothed = smoother.smooth(raw_landmark, frame_w, frame_h)
    smoother.reset()  # clear history (e.g. when the hand is lost)
"""

from __future__ import annotations

import math
import time

import config
from app.gestures.detector import Landmark


class OneEuroFilter:
    """
    Adaptive low-pass filter for a stream of hand landmarks.

    Filters the normalised ``x`` / ``y`` coordinates independently; ``z``
    is passed through unchanged (not used for cursor mapping).

    Parameters
    ----------
    min_cutoff : float
        Minimum cutoff frequency (Hz), used at low / zero speed.
    beta : float
        Speed coefficient — how strongly cutoff rises with velocity.
    d_cutoff : float
        Cutoff (Hz) applied to the derivative (velocity) estimate.
    """

    def __init__(
        self,
        min_cutoff: float = config.ONE_EURO_MIN_CUTOFF,
        beta: float = config.ONE_EURO_BETA,
        d_cutoff: float = config.ONE_EURO_D_CUTOFF,
    ):
        if not (0.0 < min_cutoff <= 1000.0):
            raise ValueError(f"min_cutoff must be in (0, 1000], got {min_cutoff}")
        if beta < 0.0:
            raise ValueError(f"beta must be >= 0, got {beta}")
        if not (0.0 < d_cutoff <= 1000.0):
            raise ValueError(f"d_cutoff must be in (0, 1000], got {d_cutoff}")

        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff

        # Per-axis low-pass state
        self._prev_x: float | None = None
        self._prev_y: float | None = None
        # Filtered velocity estimates (per axis)
        self._dx_hat: float = 0.0
        self._dy_hat: float = 0.0
        self._last_time: float | None = None

    def smooth(
        self,
        landmark: Landmark,
        frame_w: int,
        frame_h: int,
        dt: float | None = None,
    ) -> Landmark:
        """
        Return a new Landmark with One Euro filtered coordinates.

        ``dt`` (seconds) may be passed explicitly — useful for deterministic
        tests. When omitted it is measured from wall-clock time between calls.

        The first call has no previous state and returns the raw landmark.
        """
        now = time.perf_counter()

        if self._last_time is None or self._prev_x is None or self._prev_y is None:
            self._prev_x = landmark.x
            self._prev_y = landmark.y
            self._last_time = now
            return landmark

        dt = max(dt if dt is not None else now - self._last_time, 1e-6)
        self._last_time = now

        # --- Filtered velocity estimate (derivative) -----------------------
        # Low-pass the raw derivative before using it to adapt the cutoff.
        alpha_d = self._alpha(self.d_cutoff, dt)
        raw_dx = (landmark.x - self._prev_x) / dt
        raw_dy = (landmark.y - self._prev_y) / dt
        self._dx_hat = alpha_d * raw_dx + (1.0 - alpha_d) * self._dx_hat
        self._dy_hat = alpha_d * raw_dy + (1.0 - alpha_d) * self._dy_hat

        # --- Speed-adaptive cutoff -----------------------------------------
        cutoff_x = self.min_cutoff + self.beta * abs(self._dx_hat)
        cutoff_y = self.min_cutoff + self.beta * abs(self._dy_hat)

        # --- Low-pass the position -----------------------------------------
        alpha_x = self._alpha(cutoff_x, dt)
        alpha_y = self._alpha(cutoff_y, dt)

        sx = alpha_x * landmark.x + (1.0 - alpha_x) * self._prev_x
        sy = alpha_y * landmark.y + (1.0 - alpha_y) * self._prev_y

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
        """Clear filtering history (e.g. when the hand is lost)."""
        self._prev_x = None
        self._prev_y = None
        self._dx_hat = 0.0
        self._dy_hat = 0.0
        self._last_time = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        """Smoothing factor for a given cutoff frequency and timestep."""
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)
