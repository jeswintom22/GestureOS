"""
Unit tests for GestureClassifier.
"""

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
