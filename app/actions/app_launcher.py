"""
GestureOS — App Launcher

Launches applications by name using the system shell.
Maps friendly names (e.g. "chrome") to executable commands
via the registry in ``config.APP_REGISTRY``.
"""

from __future__ import annotations

import subprocess
import logging

import config

log = logging.getLogger(__name__)


class AppLauncher:
    """Launches desktop applications by friendly name."""

    def __init__(self, registry: dict[str, str] | None = None):
        self._registry = registry or config.APP_REGISTRY

    def launch(self, app_name: str) -> bool:
        """
        Launch an application.

        Parameters
        ----------
        app_name : str
            Friendly name (case-insensitive). Must exist in the registry.

        Returns
        -------
        bool
            ``True`` if launched, ``False`` if unknown app.
        """
        key = app_name.strip().lower()
        exe = self._registry.get(key)

        if exe is None:
            log.warning("Unknown app: %r", app_name)
            return False

        try:
            # shell=True so we can use names like "chrome" or protocol URIs
            subprocess.Popen(exe, shell=True)
            log.info("Launched: %s → %s", app_name, exe)
            return True
        except Exception:
            log.exception("Failed to launch %s", app_name)
            return False

    @property
    def available_apps(self) -> list[str]:
        """Return list of registered app names."""
        return sorted(self._registry.keys())
