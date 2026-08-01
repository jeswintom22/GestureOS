"""
Unit tests for GestureClassifier.
"""

import time

import config
from app.core.actions import ActionType
from app.gestures.classifier import GestureClassifier
from app.gestures.detector import HandResult, Landmark


def _make_dummy_hand(fingers_up_pattern: list[int]) -> HandResult:
    """
    Construct a dummy HandResult with 21 landmarks such that
    fingers_up matches the requested pattern [thumb, index, middle, ring, pinky].
    """
    landmarks = []
    # Wrist
    landmarks.append(Landmark(0.5, 0.9, 0.0, 500, 900))

    # Thumb: 1=4, 2=3, 3=2, 4=1 (tip)
    thumb_x = 0.3 if fingers_up_pattern[0] else 0.6
    landmarks.extend([
        Landmark(0.5, 0.8, 0, 0, 0),
        Landmark(0.5, 0.7, 0, 0, 0),
        Landmark(0.5, 0.6, 0, 0, 0),
        Landmark(thumb_x, 0.5, 0, 0, 0),  # tip (idx 4)
    ])

    # Index: 5..8 (pip=6, tip=8)
    idx_y = 0.2 if fingers_up_pattern[1] else 0.7
    landmarks.extend([
        Landmark(0.5, 0.6, 0, 0, 0),
        Landmark(0.5, 0.5, 0, 0, 0),  # pip (idx 6)
        Landmark(0.5, 0.4, 0, 0, 0),
        Landmark(0.5, idx_y, 0, 0, 0),  # tip (idx 8)
    ])

    # Middle: 9..12 (pip=10, tip=12)
    mid_y = 0.2 if fingers_up_pattern[2] else 0.7
    landmarks.extend([
        Landmark(0.5, 0.6, 0, 0, 0),
        Landmark(0.5, 0.5, 0, 0, 0),  # pip (idx 10)
        Landmark(0.5, 0.4, 0, 0, 0),
        Landmark(0.5, mid_y, 0, 0, 0),  # tip (idx 12)
    ])

    # Ring: 13..16 (pip=14, tip=16)
    ring_y = 0.2 if fingers_up_pattern[3] else 0.7
    landmarks.extend([
        Landmark(0.5, 0.6, 0, 0, 0),
        Landmark(0.5, 0.5, 0, 0, 0),  # pip (idx 14)
        Landmark(0.5, 0.4, 0, 0, 0),
        Landmark(0.5, ring_y, 0, 0, 0),  # tip (idx 16)
    ])

    # Pinky: 17..20 (pip=18, tip=20)
    pinky_y = 0.2 if fingers_up_pattern[4] else 0.7
    landmarks.extend([
        Landmark(0.5, 0.6, 0, 0, 0),
        Landmark(0.5, 0.5, 0, 0, 0),  # pip (idx 18)
        Landmark(0.5, 0.4, 0, 0, 0),
        Landmark(0.5, pinky_y, 0, 0, 0),  # tip (idx 20)
    ])

    return HandResult(landmarks=landmarks, handedness="Right", confidence=0.9)


def test_fingers_up_detector():
    hand = _make_dummy_hand([0, 1, 0, 0, 0])
    fingers = GestureClassifier._fingers_up(hand.landmarks)
    assert fingers == [0, 1, 0, 0, 0]


def test_index_only_move_cursor():
    classifier = GestureClassifier()
    hand = _make_dummy_hand([0, 1, 0, 0, 0])

    event = classifier.classify(hand, 640, 480)
    assert event.action == ActionType.MOVE_CURSOR
    assert event.value is not None
    assert len(event.value) == 2


def test_pinch_left_click():
    classifier = GestureClassifier()
    hand = _make_dummy_hand([1, 1, 0, 0, 0])
    # Place thumb tip (idx 4) and index tip (idx 8) very close
    hand.landmarks[4] = Landmark(0.5, 0.5, 0, 0, 0)
    hand.landmarks[8] = Landmark(0.51, 0.5, 0, 0, 0)

    event = classifier.classify(hand, 640, 480)
    assert event.action == ActionType.LEFT_CLICK


def test_cursor_dead_zone_suppresses_hold():
    """Holding the hand still must not emit further cursor moves."""
    classifier = GestureClassifier()
    hand = _make_dummy_hand([0, 1, 0, 0, 0])

    first = classifier.classify(hand, 640, 480)
    assert first.action == ActionType.MOVE_CURSOR

    # Same position again → within the dead zone → no move
    second = classifier.classify(hand, 640, 480)
    assert second.action == ActionType.NONE


def test_reentry_anchor_no_jump():
    """
    After hand loss, re-entering at a different spot must not teleport the
    cursor; it holds, then resumes relative to the anchor.
    """
    classifier = GestureClassifier()
    hand = _make_dummy_hand([0, 1, 0, 0, 0])

    first = classifier.classify(hand, 640, 480)
    assert first.action == ActionType.MOVE_CURSOR
    original = first.value

    # Hand lost
    classifier.reset()

    # Hand re-enters far to the right → cursor must hold (no jump)
    hand.landmarks[8] = Landmark(0.7, 0.2, 0, 0, 0)
    reentry = classifier.classify(hand, 640, 480)
    assert reentry.action == ActionType.NONE

    # Simulate a realistic frame interval so the One Euro filter has time to
    # track, then move the hand clearly beyond the dead zone.
    time.sleep(1 / 30)
    hand.landmarks[8] = Landmark(0.78, 0.2, 0, 0, 0)
    moved = classifier.classify(hand, 640, 480)
    assert moved.action == ActionType.MOVE_CURSOR

    # The resumed position is near the held cursor, NOT the raw mapped
    # position of the re-entered hand.
    margin = config.CURSOR_FRAME_MARGIN
    raw_mapped_x = int(
        (1.0 - (0.78 - margin) / (1 - 2 * margin)) * config.SCREEN_WIDTH
    )
    assert abs(moved.value[0] - original[0]) < abs(raw_mapped_x - original[0]), moved.value


def test_drag_reports_position_and_release_on_reset():
    """
    Drags report (smoothed) cursor positions, and a reset while dragging
    clears the drag state so the caller can emit DRAG_END.
    """
    classifier = GestureClassifier()
    fist = _make_dummy_hand([0, 0, 0, 0, 0])

    # Hold the fist long enough to start a drag
    start = None
    for _ in range(config.DRAG_HOLD_FRAMES):
        start = classifier.classify(fist, 640, 480)
    assert start.action == ActionType.DRAG_START
    assert classifier.dragging is True

    # While dragging, movement is still reported
    move = classifier.classify(fist, 640, 480)
    assert move.action == ActionType.MOVE_CURSOR
    assert isinstance(move.value, tuple) and len(move.value) == 2

    # Hand loss → reset clears drag state (caller emits DRAG_END)
    classifier.reset()
    assert classifier.dragging is False


def test_two_open_palms_detected():
    """Two hands with all five fingers up → two_open_palms is True."""
    classifier = GestureClassifier()
    left = _make_dummy_hand([1, 1, 1, 1, 1])
    right = _make_dummy_hand([1, 1, 1, 1, 1])

    assert classifier.two_open_palms([left, right]) is True


def test_two_open_palms_single_hand_is_false():
    """A single open palm must not count as the two-hand gesture."""
    classifier = GestureClassifier()
    palm = _make_dummy_hand([1, 1, 1, 1, 1])

    assert classifier.two_open_palms([palm]) is False
    assert classifier.two_open_palms([]) is False


def test_two_open_palms_mixed_pose_is_false():
    """Palm + non-palm (e.g. fist) must not toggle the keyboard."""
    classifier = GestureClassifier()
    palm = _make_dummy_hand([1, 1, 1, 1, 1])
    fist = _make_dummy_hand([0, 0, 0, 0, 0])

    assert classifier.two_open_palms([palm, fist]) is False
    assert classifier.two_open_palms([fist, palm]) is False


def test_is_open_palm():
    """is_open_palm is True only for the all-fingers-up pose."""
    classifier = GestureClassifier()
    assert classifier.is_open_palm(_make_dummy_hand([1, 1, 1, 1, 1])) is True
    assert classifier.is_open_palm(_make_dummy_hand([0, 1, 0, 0, 0])) is False


def test_typing_mode_allows_cursor_and_pinch():
    """
    In typing mode only cursor movement and pinch clicks are allowed
    (dwell presses will hook in later).
    """
    classifier = GestureClassifier()

    # Index only → MOVE_CURSOR still works
    index = _make_dummy_hand([0, 1, 0, 0, 0])
    event = classifier.classify(index, 640, 480, typing_mode=True)
    assert event.action == ActionType.MOVE_CURSOR

    # Pinch → LEFT_CLICK still works
    pinch = _make_dummy_hand([1, 1, 0, 0, 0])
    pinch.landmarks[4] = Landmark(0.5, 0.5, 0, 0, 0)
    pinch.landmarks[8] = Landmark(0.51, 0.5, 0, 0, 0)
    event = classifier.classify(pinch, 640, 480, typing_mode=True)
    assert event.action == ActionType.LEFT_CLICK


def test_typing_mode_suppresses_non_cursor_gestures():
    """
    While the keyboard is open, scroll / volume / brightness / swipe / drag
    must be suppressed so aiming at keys doesn't trigger them.
    """
    classifier = GestureClassifier()

    # Index + Middle → normally SCROLL; suppressed in typing mode
    scroll = _make_dummy_hand([0, 1, 1, 0, 0])
    assert classifier.classify(scroll, 640, 480, typing_mode=True).action == ActionType.NONE

    # Thumb only → normally VOLUME; suppressed
    thumb = _make_dummy_hand([1, 0, 0, 0, 0])
    assert classifier.classify(thumb, 640, 480, typing_mode=True).action == ActionType.NONE

    # Thumb+Index+Pinky → normally BRIGHTNESS; suppressed
    bright = _make_dummy_hand([1, 1, 0, 0, 1])
    assert classifier.classify(bright, 640, 480, typing_mode=True).action == ActionType.NONE

    # Open palm swipe → normally SWITCH_WINDOW after enough frames; suppressed
    palm = _make_dummy_hand([1, 1, 1, 1, 1])
    for _ in range(6):
        event = classifier.classify(palm, 640, 480, typing_mode=True)
    assert event.action == ActionType.NONE

    # Fist → normally DRAG after hold frames; suppressed
    fist = _make_dummy_hand([0, 0, 0, 0, 0])
    for _ in range(config.DRAG_HOLD_FRAMES):
        event = classifier.classify(fist, 640, 480, typing_mode=True)
    assert event.action == ActionType.NONE
    assert classifier.dragging is False


def test_typing_mode_releases_drag_in_progress():
    """
    If a drag was active when typing mode starts, the classifier must emit
    DRAG_END so the mouse button doesn't stay held.
    """
    classifier = GestureClassifier()
    fist = _make_dummy_hand([0, 0, 0, 0, 0])

    for _ in range(config.DRAG_HOLD_FRAMES):
        classifier.classify(fist, 640, 480)
    assert classifier.dragging is True

    event = classifier.classify(fist, 640, 480, typing_mode=True)
    assert event.action == ActionType.DRAG_END
    assert classifier.dragging is False
