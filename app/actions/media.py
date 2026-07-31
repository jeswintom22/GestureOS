"""
GestureOS — Media Controller

Controls media playback by sending virtual media key presses.
"""

import pyautogui


class MediaController:
    """Sends media key events (play/pause, next, previous)."""

    def play_pause(self) -> None:
        pyautogui.press("playpause", _pause=False)

    def next_track(self) -> None:
        pyautogui.press("nexttrack", _pause=False)

    def prev_track(self) -> None:
        pyautogui.press("prevtrack", _pause=False)
