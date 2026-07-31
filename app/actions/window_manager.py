"""
GestureOS — Window Manager

Controls window state (minimise, maximise, close, switch)
and takes screenshots using OS hotkeys.
"""

import pyautogui


class WindowManager:
    """Manages desktop windows via keyboard shortcuts."""

    def close_window(self) -> None:
        """Close the active window (Alt+F4)."""
        pyautogui.hotkey("alt", "F4", _pause=False)

    def minimize(self) -> None:
        """Minimise the active window (Win+Down)."""
        pyautogui.hotkey("win", "down", _pause=False)

    def maximize(self) -> None:
        """Maximise the active window (Win+Up)."""
        pyautogui.hotkey("win", "up", _pause=False)

    def switch_window(self) -> None:
        """Switch to the next window (Alt+Tab)."""
        pyautogui.hotkey("alt", "tab", _pause=False)

    def screenshot(self) -> None:
        """Open Windows Snipping Tool (Win+Shift+S)."""
        pyautogui.hotkey("win", "shift", "s", _pause=False)
