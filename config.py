"""
GestureOS — Central Configuration

All tunable constants live here. Adjust thresholds, sensitivity,
and feature flags without touching application logic.

Every setting can be overridden with an environment variable (prefixed
``GESTUREOS_``) or a ``.env`` file placed in the project root. A
``.env.example`` file documenting all variables is committed to the repo;
copy it to ``.env`` and edit as needed. Real environment variables always
take precedence over the ``.env`` file.
"""

import ctypes
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

# ---------------------------------------------------------------------------
# .env support (zero-dependency KEY=VALUE loader)
# ---------------------------------------------------------------------------


def _load_dotenv(path: Path | None = None) -> None:
    """Load ``KEY=VALUE`` pairs from ``path`` (default: project ``.env``).

    Existing environment variables take precedence and are never
    overwritten. Blank lines and ``#`` comments are skipped; surrounding
    quotes on values are stripped.
    """
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    return raw if raw is not None and raw.strip() != "" else default


def _env_path(name: str, default: str) -> str:
    """Return an env var as a path, resolving relative paths to the project root."""
    value = _env_str(name, default)
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Screen
# ---------------------------------------------------------------------------
_user32 = ctypes.windll.user32
SCREEN_WIDTH: int = _user32.GetSystemMetrics(0)
SCREEN_HEIGHT: int = _user32.GetSystemMetrics(1)

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
CAMERA_INDEX: int = _env_int("GESTUREOS_CAMERA_INDEX", 0)
CAMERA_WIDTH: int = _env_int("GESTUREOS_CAMERA_WIDTH", 640)
CAMERA_HEIGHT: int = _env_int("GESTUREOS_CAMERA_HEIGHT", 480)
CAMERA_FPS: int = _env_int("GESTUREOS_CAMERA_FPS", 30)

# ---------------------------------------------------------------------------
# MediaPipe Hands
# ---------------------------------------------------------------------------
# Default is 2 so the two-open-palms "show keyboard" gesture is detectable.
# Tracking a second hand costs some FPS on laptop webcams; set back to 1 if
# performance matters more than the two-hand gesture.
MP_MAX_HANDS: int = _env_int("GESTUREOS_MP_MAX_HANDS", 2)
MP_MIN_DETECTION_CONFIDENCE: float = _env_float("GESTUREOS_MP_MIN_DETECTION_CONFIDENCE", 0.7)
MP_MIN_TRACKING_CONFIDENCE: float = _env_float("GESTUREOS_MP_MIN_TRACKING_CONFIDENCE", 0.7)

# ---------------------------------------------------------------------------
# Gesture thresholds
# ---------------------------------------------------------------------------
PINCH_THRESHOLD: float = _env_float("GESTUREOS_PINCH_THRESHOLD", 0.05)
RIGHT_CLICK_THRESHOLD: float = _env_float("GESTUREOS_RIGHT_CLICK_THRESHOLD", 0.05)
SWIPE_VELOCITY_THRESHOLD: float = _env_float("GESTUREOS_SWIPE_VELOCITY_THRESHOLD", 0.15)
SCROLL_SENSITIVITY: int = _env_int("GESTUREOS_SCROLL_SENSITIVITY", 3)
DRAG_HOLD_FRAMES: int = _env_int("GESTUREOS_DRAG_HOLD_FRAMES", 5)
# How long the hand may be absent (ms) before it is declared "lost". Tolerates
# brief tracking blips without freezing/releasing the cursor.
HAND_LOST_GRACE_MS: int = _env_int("GESTUREOS_HAND_LOST_GRACE_MS", 200)

# ---------------------------------------------------------------------------
# Cursor mapping
# ---------------------------------------------------------------------------
# One Euro filter — adaptive cursor smoothing. Heavy smoothing when the hand
# is still (kills tremor jitter), near-zero lag in fast motion.
ONE_EURO_MIN_CUTOFF: float = _env_float("GESTUREOS_ONE_EURO_MIN_CUTOFF", 1.0)
ONE_EURO_BETA: float = _env_float("GESTUREOS_ONE_EURO_BETA", 0.05)
ONE_EURO_D_CUTOFF: float = _env_float("GESTUREOS_ONE_EURO_D_CUTOFF", 1.0)
# Cursor dead zone in screen pixels — suppresses micro-jitter while the hand
# is held still. 3–6 recommended; larger feels sticky.
CURSOR_DEAD_ZONE_PX: int = _env_int("GESTUREOS_CURSOR_DEAD_ZONE_PX", 4)
CURSOR_DEAD_ZONE: float = _env_float("GESTUREOS_CURSOR_DEAD_ZONE", 0.02)
CURSOR_FRAME_MARGIN: float = _env_float("GESTUREOS_CURSOR_FRAME_MARGIN", 0.1)

# ---------------------------------------------------------------------------
# Virtual Keyboard (dwell typing + Windows OSK)
# ---------------------------------------------------------------------------
# Hold the cursor still this long (ms) on a key before it presses.
DWELL_MS: int = _env_int("GESTUREOS_DWELL_MS", 500)
# After a dwell press, the hand must move beyond the dead zone (and this much
# time must pass) before another dwell press can fire — prevents auto-repeat.
DWELL_REPEAT_GUARD_MS: int = _env_int("GESTUREOS_DWELL_REPEAT_GUARD_MS", 400)
# The two-open-palms pose must be released for this long before it can toggle
# the keyboard again (prevents the same pose from instantly re-closing it).
KEYBOARD_TOGGLE_COOLDOWN_MS: int = _env_int("GESTUREOS_KEYBOARD_TOGGLE_COOLDOWN_MS", 1500)
# If the hand stays lost this long (ms) while the keyboard is open, close it.
KEYBOARD_IDLE_CLOSE_MS: int = _env_int("GESTUREOS_KEYBOARD_IDLE_CLOSE_MS", 10000)
# Windows On-Screen Keyboard executable (absolute path or on PATH).
OSK_PATH: str = _env_str("GESTUREOS_OSK_PATH", "osk.exe")
# Beep on each dwell keypress.
KEYBOARD_SOUND: bool = _env_bool("GESTUREOS_KEYBOARD_SOUND", True)

# ---------------------------------------------------------------------------
# Volume & Brightness
# ---------------------------------------------------------------------------
VOLUME_STEP: float = _env_float("GESTUREOS_VOLUME_STEP", 0.05)
BRIGHTNESS_STEP: int = _env_int("GESTUREOS_BRIGHTNESS_STEP", 5)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
MP_HAND_LANDMARKER_MODEL: str = _env_path(
    "GESTUREOS_HAND_LANDMARKER_MODEL",
    str(PROJECT_ROOT / "models" / "hand_landmarker.task"),
)

# ---------------------------------------------------------------------------
# Voice — Vosk
# ---------------------------------------------------------------------------
VOSK_MODEL_PATH: str = _env_path(
    "GESTUREOS_VOSK_MODEL_PATH",
    str(PROJECT_ROOT / "models" / "vosk-model-small-en-us-0.15"),
)
VOICE_SAMPLE_RATE: int = _env_int("GESTUREOS_VOICE_SAMPLE_RATE", 16000)
VOICE_CHUNK_SIZE: int = _env_int("GESTUREOS_VOICE_CHUNK_SIZE", 4096)

# ---------------------------------------------------------------------------
# App Launcher — name → executable mapping
# ---------------------------------------------------------------------------
APP_REGISTRY: dict[str, str] = {
    "chrome": "chrome",
    "notepad": "notepad",
    "calculator": "calc",
    "explorer": "explorer",
    "terminal": "wt",
    "settings": "ms-settings:",
    "task manager": "taskmgr",
    "paint": "mspaint",
    "word": "winword",
    "excel": "excel",
    "vscode": "code",
}

# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------
HUD_WIDTH: int = _env_int("GESTUREOS_HUD_WIDTH", 260)
HUD_HEIGHT: int = _env_int("GESTUREOS_HUD_HEIGHT", 80)
HUD_PADDING: int = _env_int("GESTUREOS_HUD_PADDING", 20)
HUD_FADE_MS: int = _env_int("GESTUREOS_HUD_FADE_MS", 2000)
HUD_POLL_MS: int = _env_int("GESTUREOS_HUD_POLL_MS", 50)
HUD_BG_COLOR: str = _env_str("GESTUREOS_HUD_BG_COLOR", "#1a1a2e")
HUD_TEXT_COLOR: str = _env_str("GESTUREOS_HUD_TEXT_COLOR", "#00ff88")
HUD_FONT: tuple = ("Segoe UI", 13, "bold")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = _env_str("GESTUREOS_LOG_LEVEL", "INFO")
QUIET_THIRD_PARTY_WARNINGS: bool = _env_bool(
    "GESTUREOS_QUIET_THIRD_PARTY_WARNINGS", True
)

# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------
DEBUG_SHOW_CAMERA: bool = _env_bool("GESTUREOS_DEBUG_SHOW_CAMERA", False)
DEBUG_LOG_GESTURES: bool = _env_bool("GESTUREOS_DEBUG_LOG_GESTURES", False)
DEBUG_LOG_VOICE: bool = _env_bool("GESTUREOS_DEBUG_LOG_VOICE", False)
