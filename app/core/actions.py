"""
GestureOS — Action Types

Every OS-level action the system can perform is defined here as an enum.
Both the gesture classifier and voice parser emit these action types,
and the ActionExecutor dispatches based on them.
"""

from enum import Enum, auto


class ActionType(Enum):
    """All supported OS actions."""

    # --- Cursor / Mouse ---
    MOVE_CURSOR = auto()
    LEFT_CLICK = auto()
    RIGHT_CLICK = auto()
    DOUBLE_CLICK = auto()
    SCROLL_UP = auto()
    SCROLL_DOWN = auto()
    DRAG_START = auto()
    DRAG_END = auto()

    # --- Volume ---
    VOLUME_UP = auto()
    VOLUME_DOWN = auto()
    MUTE = auto()

    # --- Brightness ---
    BRIGHTNESS_UP = auto()
    BRIGHTNESS_DOWN = auto()

    # --- Media ---
    MEDIA_PLAY_PAUSE = auto()
    MEDIA_NEXT = auto()
    MEDIA_PREV = auto()

    # --- Window Management ---
    CLOSE_WINDOW = auto()
    MINIMIZE_WINDOW = auto()
    MAXIMIZE_WINDOW = auto()
    SWITCH_WINDOW = auto()

    # --- Apps ---
    OPEN_APP = auto()
    SCREENSHOT = auto()

    # --- System ---
    GESTURE_ON = auto()
    GESTURE_OFF = auto()
    STOP = auto()              # Graceful shutdown
    NONE = auto()              # No action (idle / open palm)
