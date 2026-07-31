"""
GestureOS — Mouse Controller

Controls the system cursor and mouse buttons via PyAutoGUI.
"""

import pyautogui

import config

# PyAutoGUI safety: moving cursor to (0, 0) triggers FailSafeException
pyautogui.FAILSAFE = True
# Disable the default 0.1 s pause between calls for low-latency gesture control
pyautogui.PAUSE = 0.0


class MouseController:
    """Wraps PyAutoGUI mouse operations."""

    def move(self, x: int, y: int) -> None:
        """Move cursor to absolute screen coordinates."""
        pyautogui.moveTo(x, y, _pause=False)

    def click(self) -> None:
        """Left click at current position."""
        pyautogui.click(_pause=False)

    def double_click(self) -> None:
        """Double left click at current position."""
        pyautogui.doubleClick(_pause=False)

    def right_click(self) -> None:
        """Right click at current position."""
        pyautogui.rightClick(_pause=False)

    def scroll(self, amount: int) -> None:
        """Scroll. Positive = up, negative = down."""
        pyautogui.scroll(amount, _pause=False)

    def drag_start(self) -> None:
        """Press and hold the left mouse button."""
        pyautogui.mouseDown(_pause=False)

    def drag_end(self) -> None:
        """Release the left mouse button."""
        pyautogui.mouseUp(_pause=False)
