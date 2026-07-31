"""
GestureOS — Brightness Controller

Controls monitor brightness via screen-brightness-control.
Works on both laptops (WMI) and external monitors (DDC/CI).
"""

import screen_brightness_control as sbc

import config


class BrightnessController:
    """Controls system display brightness."""

    def get_brightness(self) -> int:
        """Return current brightness percentage (0–100)."""
        levels = sbc.get_brightness()
        # sbc.get_brightness() returns a list (one per monitor)
        return levels[0] if isinstance(levels, list) else levels

    def set_brightness(self, level: int) -> None:
        """Set absolute brightness (clamped to 0–100)."""
        level = max(0, min(100, level))
        sbc.set_brightness(level)

    def brightness_up(self, step: int = config.BRIGHTNESS_STEP) -> None:
        """Increase brightness by ``step`` percent."""
        current = self.get_brightness()
        self.set_brightness(current + step)

    def brightness_down(self, step: int = config.BRIGHTNESS_STEP) -> None:
        """Decrease brightness by ``step`` percent."""
        current = self.get_brightness()
        self.set_brightness(current - step)
