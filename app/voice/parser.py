"""
GestureOS — Command Parser

Maps recognised voice text to ``GestureEvent`` objects using
keyword matching with fuzzy tolerance.
"""

from __future__ import annotations

import re
from typing import Optional

from app.core.actions import ActionType
from app.core.events import GestureEvent


# ---------------------------------------------------------------------------
# Command patterns — order matters (first match wins)
# ---------------------------------------------------------------------------
# Each entry: (list of keyword patterns, ActionType, optional value extractor)

_COMMAND_TABLE: list[tuple[list[str], ActionType, Optional[str]]] = [
    # --- App launching (must be before shorter matches) ---
    # Handled specially: "open <app_name>"

    # --- Window management ---
    (["close window", "close this", "close it"], ActionType.CLOSE_WINDOW, None),
    (["minimize", "minimise"], ActionType.MINIMIZE_WINDOW, None),
    (["maximize", "maximise", "full screen"], ActionType.MAXIMIZE_WINDOW, None),
    (["switch window", "alt tab", "next window"], ActionType.SWITCH_WINDOW, None),

    # --- Volume ---
    (["volume up", "louder", "turn up"], ActionType.VOLUME_UP, None),
    (["volume down", "softer", "turn down", "quieter"], ActionType.VOLUME_DOWN, None),
    (["mute", "silence", "shut up"], ActionType.MUTE, None),

    # --- Brightness ---
    (["brightness up", "brighter", "screen up"], ActionType.BRIGHTNESS_UP, None),
    (["brightness down", "dimmer", "screen down", "darker"], ActionType.BRIGHTNESS_DOWN, None),

    # --- Media ---
    (["play", "pause", "play pause"], ActionType.MEDIA_PLAY_PAUSE, None),
    (["next track", "next song", "skip", "next"], ActionType.MEDIA_NEXT, None),
    (["previous track", "previous song", "go back", "previous"], ActionType.MEDIA_PREV, None),

    # --- Mouse / scroll ---
    (["scroll up", "page up"], ActionType.SCROLL_UP, None),
    (["scroll down", "page down"], ActionType.SCROLL_DOWN, None),
    (["click", "left click"], ActionType.LEFT_CLICK, None),
    (["right click"], ActionType.RIGHT_CLICK, None),
    (["double click"], ActionType.DOUBLE_CLICK, None),

    # --- Screenshot ---
    (["screenshot", "screen capture", "take a screenshot"], ActionType.SCREENSHOT, None),

    # --- Gesture toggle ---
    (["gesture off", "gestures off", "stop gestures", "disable gestures"], ActionType.GESTURE_OFF, None),
    (["gesture on", "gestures on", "start gestures", "enable gestures"], ActionType.GESTURE_ON, None),

    # --- System ---
    (["shut down", "exit", "quit", "stop"], ActionType.STOP, None),
]

# Pre-compile the "open <app>" pattern
_OPEN_APP_RE = re.compile(r"^(?:open|launch|start|run)\s+(.+)$", re.IGNORECASE)


class CommandParser:
    """
    Parses recognised speech text into a ``GestureEvent``.

    Usage::

        parser = CommandParser()
        event = parser.parse("open chrome")
        # → GestureEvent(action=ActionType.OPEN_APP, value="chrome", source="voice")
    """

    def parse(self, text: str) -> Optional[GestureEvent]:
        """
        Parse a text command.

        Returns ``None`` if the text doesn't match any known command.
        """
        text = text.strip().lower()
        if not text:
            return None

        # --- Check "open <app>" first ---
        m = _OPEN_APP_RE.match(text)
        if m:
            app_name = m.group(1).strip()
            return GestureEvent(
                action=ActionType.OPEN_APP,
                value=app_name,
                source="voice",
            )

        # --- Keyword table scan ---
        for patterns, action, _ in _COMMAND_TABLE:
            for pattern in patterns:
                if pattern in text:
                    return GestureEvent(action=action, source="voice")

        return None
