"""
GestureOS — Volume Controller

Controls system master volume via pycaw (Windows Core Audio API).
"""

from __future__ import annotations

from ctypes import POINTER, cast

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

import config


class VolumeController:
    """Controls Windows system master volume."""

    def __init__(self):
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_,
            CLSCTX_ALL,
            None,
        )
        self._volume = cast(interface, POINTER(IAudioEndpointVolume))

    def get_volume(self) -> float:
        """Return current volume as 0.0–1.0."""
        return self._volume.GetMasterVolumeLevelScalar()

    def set_volume(self, level: float) -> None:
        """Set absolute volume (clamped to 0.0–1.0)."""
        level = max(0.0, min(1.0, level))
        self._volume.SetMasterVolumeLevelScalar(level, None)

    def volume_up(self, step: float = config.VOLUME_STEP) -> None:
        """Increase volume by ``step``."""
        current = self.get_volume()
        self.set_volume(current + step)

    def volume_down(self, step: float = config.VOLUME_STEP) -> None:
        """Decrease volume by ``step``."""
        current = self.get_volume()
        self.set_volume(current - step)

    def toggle_mute(self) -> None:
        """Toggle mute on/off."""
        muted = self._volume.GetMute()
        self._volume.SetMute(not muted, None)
