"""
GestureOS — Gesture Classifier

Analyses a ``HandResult`` and emits a ``GestureEvent`` representing the
user's intended OS action.  Handles finger-state detection, pinch
detection, swipe velocity tracking, and cursor coordinate mapping.
"""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Optional

import config
from app.core.actions import ActionType
from app.core.events import GestureEvent
from app.gestures.detector import HandResult, Landmark
from app.gestures.smoother import OneEuroFilter


def _distance(a: Landmark, b: Landmark) -> float:
    """Euclidean distance between two landmarks (normalised space)."""
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


class GestureClassifier:
    """
    Classifies a ``HandResult`` into a ``GestureEvent``.

    Gesture map
    -----------
    ☝️  Index only           → MOVE_CURSOR
    ✌️  Index + Middle       → SCROLL (vertical motion)
    🤏 Pinch (thumb↔index)  → LEFT_CLICK
    🤞 Thumb↔middle close   → RIGHT_CLICK
    ✋ All five up           → NONE (pause)
    👍 Thumb only            → VOLUME control
    🤟 Thumb+Index+Pinky    → BRIGHTNESS control
    ✊ Fist                  → DRAG
    👋 Open-palm swipe      → SWITCH_WINDOW
    """

    def __init__(self):
        self._smoother = OneEuroFilter()

        # Swipe detection — track palm centre over last N frames
        self._palm_history: deque[tuple[float, float, float]] = deque(maxlen=8)

        # Drag state
        self._fist_frames: int = 0
        self._dragging: bool = False

        # Scroll tracking
        self._prev_scroll_y: Optional[float] = None

        # Cursor feel — dead zone + re-entry anchoring
        self._last_cursor_screen: Optional[tuple[int, int]] = None
        self._reentry_offset: tuple[int, int] = (0, 0)
        self._reentering: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(
        self,
        hand: HandResult,
        frame_w: int,
        frame_h: int,
        typing_mode: bool = False,
    ) -> GestureEvent:
        """
        Classify one hand detection into a GestureEvent.

        Parameters
        ----------
        hand : HandResult
            The detected hand.
        frame_w, frame_h : int
            Camera frame dimensions (pixels).
        typing_mode : bool
            When True (virtual keyboard open), only cursor movement, pinch
            clicks and dwell presses are emitted; scroll / volume /
            brightness / swipe / drag are suppressed so aiming at keys
            cannot trigger unrelated actions.

        Returns
        -------
        GestureEvent
        """
        lms = hand.landmarks
        fingers = self._fingers_up(lms)
        index_tip = lms[8]
        thumb_tip = lms[4]
        middle_tip = lms[12]

        # --- Typing mode: cursor + pinch only (dwell hooks in later) ---
        if typing_mode:
            # If a drag was in progress, release it — drags are suppressed
            # while typing.
            if self._dragging:
                self._dragging = False
                self._fist_frames = 0
                return GestureEvent(action=ActionType.DRAG_END)
            # Pinch → LEFT_CLICK (tap a key on the on-screen keyboard)
            if _distance(thumb_tip, index_tip) < config.PINCH_THRESHOLD:
                return GestureEvent(action=ActionType.LEFT_CLICK)
            # Index only → MOVE_CURSOR (aim at keys)
            if fingers == [0, 1, 0, 0, 0]:
                target = self._cursor_target(index_tip, frame_w, frame_h)
                if target is None:
                    return GestureEvent(action=ActionType.NONE)
                return GestureEvent(action=ActionType.MOVE_CURSOR, value=target)
            # Everything else is suppressed while typing
            return GestureEvent(action=ActionType.NONE)

        # --- Swipe detection (must check before individual gestures) ---
        swipe = self._detect_swipe(lms)
        if swipe is not None:
            return swipe

        # --- Pinch → LEFT_CLICK ---
        if _distance(thumb_tip, index_tip) < config.PINCH_THRESHOLD:
            return GestureEvent(action=ActionType.LEFT_CLICK)

        # --- Thumb↔Middle close → RIGHT_CLICK ---
        if _distance(thumb_tip, middle_tip) < config.RIGHT_CLICK_THRESHOLD:
            return GestureEvent(action=ActionType.RIGHT_CLICK)

        # --- Fist → DRAG ---
        if fingers == [0, 0, 0, 0, 0]:
            self._fist_frames += 1
            if self._fist_frames >= config.DRAG_HOLD_FRAMES and not self._dragging:
                self._dragging = True
                return GestureEvent(action=ActionType.DRAG_START)
            # While dragging, still report cursor position (smoothed + dead zone)
            if self._dragging:
                target = self._cursor_target(index_tip, frame_w, frame_h)
                if target is not None:
                    return GestureEvent(action=ActionType.MOVE_CURSOR, value=target)
                # Held within the dead zone — keep re-reporting the held
                # position so the HUD stays in the dragging state.
                if self._last_cursor_screen is not None:
                    return GestureEvent(
                        action=ActionType.MOVE_CURSOR,
                        value=self._last_cursor_screen,
                    )
                return GestureEvent(action=ActionType.NONE)
            return GestureEvent(action=ActionType.NONE)

        # --- If we leave fist, end drag ---
        if self._dragging and fingers != [0, 0, 0, 0, 0]:
            self._dragging = False
            self._fist_frames = 0
            return GestureEvent(action=ActionType.DRAG_END)
        self._fist_frames = 0

        # --- Open palm (all 5) → NONE / STOP ---
        if fingers == [1, 1, 1, 1, 1]:
            self._palm_history.append((lms[9].x, lms[9].y, time.time()))
            return GestureEvent(action=ActionType.NONE)

        # --- Index only → MOVE_CURSOR ---
        if fingers == [0, 1, 0, 0, 0]:
            target = self._cursor_target(index_tip, frame_w, frame_h)
            if target is None:
                return GestureEvent(action=ActionType.NONE)
            return GestureEvent(action=ActionType.MOVE_CURSOR, value=target)

        # --- Index + Middle → SCROLL ---
        if fingers == [0, 1, 1, 0, 0]:
            return self._handle_scroll(index_tip)

        # --- Thumb only → VOLUME ---
        if fingers == [1, 0, 0, 0, 0]:
            # Thumb above wrist → volume up; below → volume down
            if thumb_tip.y < lms[0].y:  # normalised y: lower value = higher on screen
                return GestureEvent(action=ActionType.VOLUME_UP)
            return GestureEvent(action=ActionType.VOLUME_DOWN)

        # --- Thumb + Index + Pinky → BRIGHTNESS ---
        if fingers == [1, 1, 0, 0, 1]:
            if index_tip.y < lms[0].y:
                return GestureEvent(action=ActionType.BRIGHTNESS_UP)
            return GestureEvent(action=ActionType.BRIGHTNESS_DOWN)

        # --- Fallback ---
        return GestureEvent(action=ActionType.NONE)

    def reset(self) -> None:
        """Reset all internal state (call when hand is lost)."""
        self._smoother.reset()
        self._palm_history.clear()
        self._fist_frames = 0
        self._dragging = False
        self._prev_scroll_y = None
        # The next hand that appears must re-anchor so the cursor doesn't
        # teleport to wherever the hand re-enters the frame.
        self._reentering = True
        # NOTE: _last_cursor_screen is intentionally kept, so the cursor
        # holds its position while the hand is away.

    @property
    def dragging(self) -> bool:
        """True while a drag is in progress (for the caller to release on loss)."""
        return self._dragging

    # ------------------------------------------------------------------
    # Multi-hand helpers (virtual keyboard open/close gesture)
    # ------------------------------------------------------------------

    def is_open_palm(self, hand: HandResult) -> bool:
        """True if the hand is an open palm (all five fingers extended)."""
        return self._fingers_up(hand.landmarks) == [1, 1, 1, 1, 1]

    def two_open_palms(self, hands: list[HandResult]) -> bool:
        """
        True if at least two hands are detected and the first two are both
        open palms — the gesture that opens/closes the virtual keyboard.
        """
        return len(hands) >= 2 and all(self.is_open_palm(h) for h in hands[:2])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fingers_up(lms: list[Landmark]) -> list[int]:
        """
        Return ``[thumb, index, middle, ring, pinky]`` as 0/1.

        A finger is "up" if its tip is above (lower y) its PIP joint.
        The thumb uses x-axis comparison (tip further from palm centre).
        """
        fingers = []

        # Thumb — compare tip.x vs IP joint.x
        # For right hand: tip.x > ip.x means "out" = up
        # MediaPipe mirrors the image, so this heuristic works for both hands.
        fingers.append(1 if lms[4].x < lms[3].x else 0)

        # Index  (tip=8,  pip=6)
        fingers.append(1 if lms[8].y < lms[6].y else 0)
        # Middle (tip=12, pip=10)
        fingers.append(1 if lms[12].y < lms[10].y else 0)
        # Ring   (tip=16, pip=14)
        fingers.append(1 if lms[16].y < lms[14].y else 0)
        # Pinky  (tip=20, pip=18)
        fingers.append(1 if lms[20].y < lms[18].y else 0)

        return fingers

    def _cursor_target(
        self,
        landmark: Landmark,
        frame_w: int,
        frame_h: int,
    ) -> Optional[tuple[int, int]]:
        """
        Map a landmark to the next cursor screen position.

        Applies One Euro smoothing, re-entry anchoring (so a returning hand
        does not teleport the cursor), and a screen-pixel dead zone (so a
        still hand does not jitter). Returns ``None`` when the cursor should
        hold its current position.
        """
        smoothed = self._smoother.smooth(landmark, frame_w, frame_h)
        sx, sy = self._map_to_screen(smoothed, frame_w, frame_h)

        # Re-entry: anchor the mapping so a returning hand resumes control
        # relative to where the cursor already is, not wherever it appears.
        if self._reentering:
            if self._last_cursor_screen is not None:
                self._reentry_offset = (
                    self._last_cursor_screen[0] - sx,
                    self._last_cursor_screen[1] - sy,
                )
            else:
                self._reentry_offset = (0, 0)
            self._reentering = False
            return None

        tx = sx + self._reentry_offset[0]
        ty = sy + self._reentry_offset[1]
        # Clamp into the visible screen area (never (0,0) — pyautogui failsafe)
        tx = max(1, min(tx, config.SCREEN_WIDTH - 1))
        ty = max(1, min(ty, config.SCREEN_HEIGHT - 1))

        # Dead zone: suppress micro-movement while the hand is held still.
        if self._last_cursor_screen is not None:
            lx, ly = self._last_cursor_screen
            if (
                abs(tx - lx) <= config.CURSOR_DEAD_ZONE_PX
                and abs(ty - ly) <= config.CURSOR_DEAD_ZONE_PX
            ):
                return None

        self._last_cursor_screen = (tx, ty)
        return (tx, ty)

    def _map_to_screen(
        self,
        landmark: Landmark,
        frame_w: int,
        frame_h: int,
    ) -> tuple[int, int]:
        """
        Map a normalised landmark position to screen pixel coordinates.

        Applies a margin so the user doesn't have to reach the very edge
        of the camera frame to reach the screen edge.
        """
        margin = config.CURSOR_FRAME_MARGIN

        # Clamp to [margin, 1-margin] then scale to [0, 1]
        nx = max(0.0, min(1.0, (landmark.x - margin) / (1 - 2 * margin)))
        ny = max(0.0, min(1.0, (landmark.y - margin) / (1 - 2 * margin)))

        # Flip x because the webcam is mirrored
        nx = 1.0 - nx

        sx = int(nx * config.SCREEN_WIDTH)
        sy = int(ny * config.SCREEN_HEIGHT)

        return sx, sy

    def _handle_scroll(self, index_tip: Landmark) -> GestureEvent:
        """Track vertical motion of the index finger for scrolling."""
        if self._prev_scroll_y is None:
            self._prev_scroll_y = index_tip.y
            return GestureEvent(action=ActionType.NONE)

        delta = index_tip.y - self._prev_scroll_y
        self._prev_scroll_y = index_tip.y

        if abs(delta) < config.CURSOR_DEAD_ZONE:
            return GestureEvent(action=ActionType.NONE)

        if delta > 0:
            return GestureEvent(
                action=ActionType.SCROLL_DOWN,
                value=config.SCROLL_SENSITIVITY,
            )
        return GestureEvent(
            action=ActionType.SCROLL_UP,
            value=config.SCROLL_SENSITIVITY,
        )

    def _detect_swipe(self, lms: list[Landmark]) -> Optional[GestureEvent]:
        """
        Detect a horizontal swipe gesture (open palm moving left/right).

        Only fires if ALL five fingers are up AND the palm centre has
        moved fast enough horizontally over the last few frames.
        """
        fingers = self._fingers_up(lms)
        if fingers != [1, 1, 1, 1, 1]:
            return None

        palm_x = lms[9].x  # Middle-finger MCP as palm centre proxy
        palm_y = lms[9].y
        now = time.time()
        self._palm_history.append((palm_x, palm_y, now))

        if len(self._palm_history) < 4:
            return None

        oldest = self._palm_history[0]
        dt = now - oldest[2]
        if dt < 0.01:
            return None

        dx = palm_x - oldest[0]
        velocity = abs(dx) / dt

        if velocity > config.SWIPE_VELOCITY_THRESHOLD:
            self._palm_history.clear()
            return GestureEvent(action=ActionType.SWITCH_WINDOW)

        return None
