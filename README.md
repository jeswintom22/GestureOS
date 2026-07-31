# GestureOS

GestureOS is a full desktop overlay application that replaces traditional mouse and keyboard interaction with hand gestures and voice commands on Windows.

## Features

- **Hand Gestures**: Use your webcam to control the mouse, click, scroll, adjust volume, change brightness, and more.
- **Voice Commands**: Offline speech recognition to launch apps, manage windows, and control media.
- **HUD Overlay**: A transparent, click-through Heads-Up Display showing your current gesture and voice command status.

## Default Gesture Map

| Gesture | Action |
|---|---|
| ☝️ Index only | Move cursor |
| ✌️ Index + Middle | Scroll mode (move hand up/down) |
| 🤏 Pinch (thumb + index) | Left click |
| 🤞 Middle + Thumb close | Right click |
| ✋ Open palm (all 5) | Pause / "stop" mode |
| 👍 Thumb only | Volume up/down |
| 🤟 Thumb + Index + Pinky | Brightness control mode |
| ✊ Fist | Drag mode (hold to drag) |
| 👋 Swipe left/right (open palm) | Switch window (Alt+Tab) |

## Default Voice Commands

| Command | Action |
|---|---|
| "open chrome" / "open notepad" / "open [app]" | Launch application |
| "close window" | Close current window (Alt+F4) |
| "minimize" / "maximize" | Window management |
| "volume up" / "volume down" / "mute" | Volume control |
| "brightness up" / "brightness down" | Brightness control |
| "play" / "pause" / "next" / "previous" | Media keys |
| "screenshot" | Take screenshot |
| "scroll up" / "scroll down" | Scroll |
| "switch window" | Alt+Tab |
| "gesture off" / "gesture on" | Toggle gesture control |
| "stop" / "exit" | Quit GestureOS |

## Requirements

- Python 3.10+
- Windows OS
- Webcam
- Microphone

## Installation

1. Clone the repository and navigate to the project directory:
   ```bash
   git clone <repo-url>
   cd GestureOS
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Download the models into the `models/` folder at the project root:
   - **MediaPipe hand landmarker**: download `hand_landmarker.task` from
     [hand_landmarker (float16)](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task)
     and save it as `models/hand_landmarker.task`.
   - **Vosk speech model**: download `vosk-model-small-en-us-0.15.zip` from
     [Vosk Models](https://alphacephei.com/vosk/models) and extract it so the
     folder `models/vosk-model-small-en-us-0.15` exists.

## Configuration

GestureOS can be configured with environment variables. Copy the template to
create your own config file (it is git-ignored):

```bash
cp .env.example .env
```

Edit `.env` to suit your setup — every line is optional and falls back to the
built-in default. Real environment variables always take precedence over the
`.env` file.

Key variables:

| Variable | Default | Description |
|---|---|---|
| `GESTUREOS_LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `GESTUREOS_QUIET_THIRD_PARTY_WARNINGS` | `true` | Silence noisy library warnings (e.g. brightness EDID) |
| `GESTUREOS_CAMERA_INDEX` | `0` | Webcam device index |
| `GESTUREOS_CAMERA_WIDTH` / `GESTUREOS_CAMERA_HEIGHT` | `640` / `480` | Capture resolution |
| `GESTUREOS_MP_MAX_HANDS` | `1` | Hands tracked simultaneously |
| `GESTUREOS_PINCH_THRESHOLD` | `0.05` | Pinch distance for click |
| `GESTUREOS_RIGHT_CLICK_THRESHOLD` | `0.05` | Middle–thumb distance for right-click |
| `GESTUREOS_SCROLL_SENSITIVITY` | `3` | Scroll clicks per frame |
| `GESTUREOS_DRAG_HOLD_FRAMES` | `5` | Frames to hold fist before drag |
| `GESTUREOS_CURSOR_SMOOTHING_ALPHA` | `0.4` | Cursor EMA smoothing (0 = none) |
| `GESTUREOS_VOLUME_STEP` | `0.05` | Volume change per tick |
| `GESTUREOS_BRIGHTNESS_STEP` | `5` | Brightness change per tick |
| `GESTUREOS_HAND_LANDMARKER_MODEL` | `models/hand_landmarker.task` | MediaPipe model path |
| `GESTUREOS_VOSK_MODEL_PATH` | `models/vosk-model-small-en-us-0.15` | Vosk model path |
| `GESTUREOS_HUD_BG_COLOR` / `GESTUREOS_HUD_TEXT_COLOR` | `#1a1a2e` / `#00ff88` | HUD colours (hex) |
| `GESTUREOS_DEBUG_SHOW_CAMERA` | `false` | Always show the debug preview window |

See `.env.example` for the complete list of all supported variables.

## Usage

Run GestureOS with the following command:

```bash
python main.py
```

### CLI Options

- `--debug`: Show webcam preview with hand landmarks.
- `--no-voice`: Disable voice recognition engine.
- `--no-gesture`: Disable camera gesture recognition.

## Troubleshooting

**`Volume control unavailable`** — The `pycaw` audio library could not
initialise Core Audio (no active playback device, or the process lacks the
needed permissions). GestureOS keeps running; only volume gestures/commands
are disabled.

**Repeated `screen_brightness_control ... EDIDParseError` warnings** — The
brightness library fails to parse the EDID of one of your displays (common on
some laptops and external monitors). These warnings are harmless and are
silenced by default via `GESTUREOS_QUIET_THIRD_PARTY_WARNINGS=true`. If you
need to debug brightness control, set it to `false`.

**`TypeError: cannot unpack non-iterable Connection object` (older builds)** —
This was a bug in the debug-drawing path and is fixed in the current code.
Update your checkout to the latest commit.

## Testing

Run the test suite using pytest:

```bash
pytest tests/ -v
```