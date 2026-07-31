"""
GestureOS — HUD Overlay

A minimal, transparent, always-on-top, click-through Tkinter window
that displays the current gesture / voice command status in the
bottom-right corner of the screen.

Uses ``win32gui`` to make the window click-through on Windows.
"""

from __future__ import annotations

import logging
import time
import tkinter as tk
from typing import Optional

import config
from app.core.actions import ActionType
from app.core.events import EventBus

log = logging.getLogger(__name__)

# Gesture → emoji / label for display
_ACTION_LABELS: dict[ActionType, str] = {
    ActionType.MOVE_CURSOR: "☝️ Moving",
    ActionType.LEFT_CLICK: "🤏 Click",
    ActionType.RIGHT_CLICK: "🤞 Right Click",
    ActionType.DOUBLE_CLICK: "👆 Double Click",
    ActionType.SCROLL_UP: "⬆️ Scroll Up",
    ActionType.SCROLL_DOWN: "⬇️ Scroll Down",
    ActionType.DRAG_START: "✊ Dragging…",
    ActionType.DRAG_END: "✋ Drag End",
    ActionType.VOLUME_UP: "🔊 Vol +",
    ActionType.VOLUME_DOWN: "🔉 Vol −",
    ActionType.MUTE: "🔇 Mute",
    ActionType.BRIGHTNESS_UP: "☀️ Bright +",
    ActionType.BRIGHTNESS_DOWN: "🌙 Bright −",
    ActionType.MEDIA_PLAY_PAUSE: "⏯ Play/Pause",
    ActionType.MEDIA_NEXT: "⏭ Next",
    ActionType.MEDIA_PREV: "⏮ Previous",
    ActionType.CLOSE_WINDOW: "❌ Close",
    ActionType.MINIMIZE_WINDOW: "🔽 Minimize",
    ActionType.MAXIMIZE_WINDOW: "🔼 Maximize",
    ActionType.SWITCH_WINDOW: "🔄 Switch",
    ActionType.SCREENSHOT: "📸 Screenshot",
    ActionType.OPEN_APP: "🚀 Launch",
    ActionType.GESTURE_ON: "✅ Gestures ON",
    ActionType.GESTURE_OFF: "⛔ Gestures OFF",
    ActionType.NONE: "✋ Idle",
}


class HUD:
    """
    Transparent always-on-top HUD overlay.

    Must be created and run on the **main thread** (Tkinter requirement).

    Usage::

        hud = HUD()
        hud.run()      # blocks (runs Tkinter mainloop)
        # OR
        hud.stop()     # call from another thread to shut down
    """

    def __init__(self, event_bus: EventBus | None = None):
        self._bus = event_bus or EventBus()
        self._last_action_time: float = 0.0

        # --- Tkinter setup ---
        self._root = tk.Tk()
        self._root.title("GestureOS HUD")
        self._root.overrideredirect(True)            # No title bar / borders
        self._root.attributes("-topmost", True)       # Always on top
        self._root.attributes("-alpha", 0.85)         # Slight transparency
        self._root.configure(bg=config.HUD_BG_COLOR)

        # Position: bottom-right corner
        x = config.SCREEN_WIDTH - config.HUD_WIDTH - config.HUD_PADDING
        y = config.SCREEN_HEIGHT - config.HUD_HEIGHT - config.HUD_PADDING - 40  # taskbar offset
        self._root.geometry(
            f"{config.HUD_WIDTH}x{config.HUD_HEIGHT}+{x}+{y}"
        )

        # --- Widgets ---
        self._title = tk.Label(
            self._root,
            text="GestureOS",
            font=("Segoe UI", 9),
            fg="#888888",
            bg=config.HUD_BG_COLOR,
            anchor="w",
        )
        self._title.pack(fill="x", padx=12, pady=(8, 0))

        self._label = tk.Label(
            self._root,
            text="✋ Ready",
            font=config.HUD_FONT,
            fg=config.HUD_TEXT_COLOR,
            bg=config.HUD_BG_COLOR,
            anchor="w",
        )
        self._label.pack(fill="x", padx=12, pady=(2, 8))

        # --- Make click-through (Windows only) ---
        self._setup_clickthrough()

        # --- Start polling ---
        self._root.after(config.HUD_POLL_MS, self._poll)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Block on Tkinter mainloop (call on main thread)."""
        log.info("HUD started")
        self._root.mainloop()

    def stop(self) -> None:
        """Destroy the HUD window (can be called from any thread)."""
        try:
            self._root.after(0, self._root.destroy)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        """Periodically check the event bus for the latest action."""
        event = self._bus.last_event
        now = time.time()

        if event and event.timestamp > self._last_action_time:
            self._last_action_time = event.timestamp
            label = _ACTION_LABELS.get(event.action, f"❓ {event.action.name}")

            # For app launching, append the app name
            if event.action == ActionType.OPEN_APP and event.value:
                label = f"🚀 {event.value}"

            # Source indicator
            source_icon = "🎤" if event.source == "voice" else "👋"
            self._label.config(text=f"{source_icon}  {label}")

            # Reset opacity when active
            self._root.attributes("-alpha", 0.9)

        elif now - self._last_action_time > config.HUD_FADE_MS / 1000:
            # Fade to low opacity after idle period
            self._root.attributes("-alpha", 0.4)

        # Reschedule
        self._root.after(config.HUD_POLL_MS, self._poll)

    def _setup_clickthrough(self) -> None:
        """Make the window click-through on Windows using win32gui."""
        try:
            import win32gui
            import win32con

            # We need the HWND — on Windows, Tkinter exposes it via winfo_id
            self._root.update_idletasks()
            hwnd = self._root.winfo_id()

            # Set extended window style: layered + transparent (click-through)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                hwnd,
                win32con.GWL_EXSTYLE,
                ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT,
            )
            log.info("HUD click-through enabled")
        except ImportError:
            log.warning("pywin32 not available — HUD will capture clicks")
        except Exception:
            log.exception("Failed to set HUD click-through")
