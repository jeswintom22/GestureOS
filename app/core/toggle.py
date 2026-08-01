"""
GestureOS — Debounced Toggle Gate

A tiny state machine that turns a sustained/held signal into a single
toggle trigger. Used for the two-open-palms virtual keyboard gesture:

- The pose must be *released* (signal drops to ``False``) before it can
  trigger again, so holding the pose doesn't re-trigger every frame.
- A cooldown prevents rapid re-presentation (e.g. releasing and raising
  both palms again within a fraction of a second) from double-toggling.

The clock is injectable so unit tests can drive time deterministically.
"""

from __future__ import annotations

import time
from typing import Callable


class ToggleGate:
    """
    Emits at most one trigger per signal presentation.

    Re-arming happens naturally when the signal drops to ``False`` (pose
    released). There is deliberately no ``reset()``: forcing a re-arm while
    the pose is still held would cause a double-toggle (e.g. a keyboard that
    instantly re-opens after closing). To re-arm on hand loss, feed
    ``trigger(False)`` from the loss path — that only runs when no hands are
    present, so it cannot cause a flicker.

    Parameters
    ----------
    cooldown_ms : int
        Minimum time (ms) between two triggers.
    clock : Callable[[], float]
        Monotonic-seconds source; default ``time.monotonic``.
    """

    def __init__(self, cooldown_ms: int, clock: Callable[[], float] = time.monotonic):
        if cooldown_ms < 0:
            raise ValueError(f"cooldown_ms must be >= 0, got {cooldown_ms}")
        self.cooldown_ms = cooldown_ms
        self._clock = clock
        self._armed = True
        # ``-inf`` so the first presentation always fires, regardless of
        # where the monotonic clock started (e.g. zero-origin fake clocks
        # in tests, or a freshly booted machine).
        self._last_trigger: float = float("-inf")

    def trigger(self, signal: bool) -> bool:
        """
        Feed the raw signal once per frame.

        Returns ``True`` exactly once per presentation: when the signal is
        held, the gate disarms after the first trigger and only re-arms once
        the signal drops to ``False``; the cooldown must also have elapsed
        since the last trigger.
        """
        now = self._clock()
        if not signal:
            # Pose released — re-arm for the next presentation.
            self._armed = True
            return False
        if self._armed and (now - self._last_trigger) * 1000 >= self.cooldown_ms:
            self._last_trigger = now
            self._armed = False
            return True
        # Held but already fired (or within cooldown) — disarm until release.
        self._armed = False
        return False
