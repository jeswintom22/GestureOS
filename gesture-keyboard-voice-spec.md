# GestureOS — Gesture Keyboard & Voice Setup Spec

Status: **Draft — spec only, no code changes yet**
Author: Interview-driven spec (5 rounds with the user)
Target version: next iteration of `main`

---

## 1. Overview

The user wants two things:

1. **A virtual keyboard that can be opened with a hand gesture and used to type** —
   so GestureOS can fully replace the physical keyboard, not just the mouse.
2. **Voice setup guidance** — how to get the existing Vosk voice engine working
   (or verify it already works), plus new keyboard/dictation voice commands.

After five interview rounds the agreed design is:

- **Typing = hover (dwell) typing**: point the index finger (the existing cursor
  gesture) at a key and hold still; after ~500 ms the key presses automatically.
- **Keyboard = the built-in Windows on-screen keyboard (`osk.exe`)** launched by
  GestureOS. The hand cursor clicks its keys; OSK never steals focus, so typing
  goes straight into the focused app. The "compact layout + symbol layer" idea
  was **dropped** in Round 5 in favour of OSK's full QWERTY.
- **Open/close = two open palms** (both hands in the frame, all five fingers
  extended). Voice commands (`"show keyboard"` / `"hide keyboard"`) are also
  added as a fallback.
- **Voice**: full setup documentation + a standalone diagnostic script
  (`scripts/voice_check.py`) + new commands (`"show keyboard"`, `"hide keyboard"`,
  `"type <text>"` prefix, and `"start typing"` / `"stop typing"` dictation toggle).

Scope: **virtual keyboard via OSK + dwell typing, typing-mode gesture
suppression, two-hand open gesture, voice setup tooling and dictation.**
Everything else is out of scope (see §9).

---

## 2. Current Pipeline Analysis (from code)

### Relevant subsystems

1. **Gesture loop** (`main.py` `_run_gesture_loop`): reads camera frames →
   `HandDetector.detect()` returns up to `config.MP_MAX_HANDS` hands (default
   **1**) → `GestureClassifier.classify(hands[0], w, h)` classifies only the
   **first** hand → `GestureEvent` pushed to the `EventBus` → `ActionExecutor`
   dispatches to OS controllers (pyautogui etc.).
2. **Hand-loss state machine** (already in `main.py`): a `HAND_LOST_GRACE_MS`
   (200 ms) grace period, then emits `HAND_LOST`, releases drags, and calls
   `classifier.reset()`.
3. **Classifier** (`app/gestures/classifier.py`): gesture map includes
   index-only → `MOVE_CURSOR`, pinch → `LEFT_CLICK`, scroll (index+middle),
   volume (thumb), brightness (thumb+index+pinky), fist → drag, palm swipe →
   switch window. Already has One Euro smoothing, a pixel dead zone, and
   re-entry anchoring (from the previous gesture-feel iteration).
4. **HUD** (`app/hud/overlay.py`): a single transparent, always-on-top,
   **click-through** Tkinter window (bottom-right) that displays the last
   event's label with a source icon and a warning colour for `HAND_LOST`.
5. **Voice engine** (`app/voice/engine.py` + `parser.py`): Vosk offline
   recognition (16 kHz mono int16) in a daemon thread; `CommandParser` does
   keyword matching and a special `open <app>` regex; recognised commands are
   pushed as `GestureEvent(source="voice")`. **There is currently no dictation
   path — unrecognised text is discarded.**
6. **Config** (`config.py`): every knob is a `GESTUREOS_` env var backed by
   `.env`; `MP_MAX_HANDS` defaults to 1.

### Gaps this feature fills

| # | Gap | Location |
|---|-----|----------|
| G1 | No keyboard input path at all | — |
| G2 | Only 1 hand tracked; two-hand gesture impossible | `config.MP_MAX_HANDS`, `main.py` (`hands[0]` only) |
| G3 | No typing/dictation mode; voice text is dropped if not a command | `voice/engine.py` |
| G4 | No OSK lifecycle management | — |
| G5 | No dwell (hover-hold) detection | `classifier.py` |
| G6 | No cursor-following progress indicator | `hud/` |

---

## 3. Interview Decisions (5 rounds)

### Round 1 — Core interaction design
| Question | Decision |
|---|---|
| How to press a key | **Hover to type (dwell)** — point index finger at a key, hold ~500 ms to press. |
| Keyboard layout | **Compact + symbol layer** *(later superseded — see Round 5)*. |
| Open/close mechanism | **Two-hand gesture** (new multi-hand path). |

### Round 2 — Keyboard window & typing target
| Question | Decision |
|---|---|
| Where typed text goes | **Type into the focused app** — like a normal keyboard. |
| How the keyboard is displayed | **Use the built-in Windows OSK (`osk.exe`)** — zero custom UI, launched via subprocess, clicked by the hand cursor. |
| Feedback cues (multi-select) | **All four**: sound on keypress, HUD status line, visual press effect, dwell progress indicator. |

### Round 3 — Voice scope & dwell behaviour
| Question | Decision |
|---|---|
| Voice scope | **Setup docs + full dictation** — document setup AND add `"show keyboard"`, `"hide keyboard"`, and dictation. |
| Diagnostic tool | **Add a standalone voice check script** (`scripts/voice_check.py`) that lists mic devices, checks the model, and live-transcribes test speech. |
| Dwell timing | **Configurable + repeat guard** — default ~500 ms with a cooldown so holding past the timer doesn't auto-repeat the key. |

### Round 4 — Edge cases & constraints
| Question | Decision |
|---|---|
| Two-hand tracking cost | **Bump to 2 hands always** (`MP_MAX_HANDS` default 1 → 2); accept the FPS cost. |
| Hand lost while keyboard open | **Close only if idle long** — keep open through blips; auto-close after a longer timeout (e.g. 10 s). |
| Other gestures while keyboard open | **Typing mode: cursor + dwell only** — scroll/volume/brightness/swipe suspended while open; predictable aiming. |
| Dwell progress ring location | **Tiny cursor-following overlay** — a small always-on-top circle that tracks the system cursor and fills as the timer counts down. |

### Round 5 — Conflict resolution & final details
| Question | Decision |
|---|---|
| OSK vs compact layout (conflict) | **Keep OSK, drop the compact layout** — OSK's full QWERTY wins; symbols via Shift. |
| Dictation trigger | **Both** — `"type <text>"` prefix for one-shot input AND `"start typing"` / `"stop typing"` toggle for continuous dictation. |
| Exact open gesture shape | **Both hands open palms** (all five fingers extended on each). |

---

## 4. Design

### 4.1 Two-hand tracking & the open gesture

- `config.MP_MAX_HANDS` default changes **1 → 2** (already env-configurable;
  README warns about the FPS tradeoff — user accepted).
- `main.py` gesture loop: before single-hand classification, run a
  **two-hand toggle check**:
  - If `len(hands) == 2` and **both** hands are open palms
    (each `_fingers_up == [1,1,1,1,1]`) → toggle keyboard.
  - **Re-arm cooldown** (`GESTUREOS_KEYBOARD_TOGGLE_COOLDOWN_MS`, default
    ~1500): the pose must be *released* (fewer than two open palms) before it
    can trigger again, so the same pose can't instantly re-close the keyboard.
- If the keyboard is already open, the two-palms pose closes it
  (toggle semantics). Voice commands are an independent fallback
  (§4.5).
- Implementation note: the two-hand check happens in the gesture loop
  (a small helper in the classifier, e.g. `GestureClassifier.classify_pair()`
  or a standalone `_is_two_open_palms(hands)`), then single-hand
  classification continues for cursor control.

### 4.2 Typing mode state machine

```
NORMAL
  │  two open palms (re-armed) │ "show keyboard" (voice)
  ▼
TYPING (OSK launched, topmost)
  │  two open palms (re-armed) │ "hide keyboard" (voice)
  │  hand lost for KEYBOARD_IDLE_CLOSE_MS
  ▼
NORMAL (OSK closed, typing mode off)
```

- **TYPING mode rules**:
  - Only `MOVE_CURSOR`, pinch `LEFT_CLICK`, and **dwell presses** are emitted.
  - Scroll (`SCROLL_*`), volume, brightness, swipe (`SWITCH_WINDOW`), drag,
    and `GESTURE_OFF` are **suppressed** (return `NONE`) so aiming at keys
    can't trigger unrelated actions.
  - Cursor movement keeps using the existing One Euro + dead zone + re-entry
    anchor pipeline — no changes needed there.
- **Opening** (`KEYBOARD_OPEN`): `KeyboardController.open()` →
  `subprocess.Popen(config.OSK_PATH)` (default `osk.exe`, resolved via
  `C:\Windows\System32\osk.exe`). Set typing mode.
- **Closing** (`KEYBOARD_CLOSE`): `KeyboardController.close()` →
  terminate the OSK process (`taskkill /IM osk.exe /F` or process handle
  tracking). Clear typing mode.
- **Idle close**: extend the existing hand-loss logic — if the hand has been
  lost for `GESTUREOS_KEYBOARD_IDLE_CLOSE_MS` (default 10 000) while the
  keyboard is open, close it (but do **not** disturb the normal 200 ms
  hand-lost grace/cursor-freeze behaviour).

### 4.3 Dwell (hover-hold) typing

New dwell logic (recommended: a `DwellController` in
`app/gestures/dwell.py`, or folded into the classifier — decide at
implementation; spec favours a small dedicated class for testability).

- **Trigger**: while in TYPING mode, a `MOVE_CURSOR` target that stays within
  the existing dead zone (i.e. the hand is still) starts a dwell timer.
  If the target stays still for `GESTUREOS_DWELL_MS` (default **500**),
  emit a press.
- **Press action**: reuse `ActionType.LEFT_CLICK` — the executor clicks at the
  current cursor position, the OSK receives the click and sends the key to
  the focused app. (OSK is designed never to steal focus, so focus stays in
  the target app.) Reusing `LEFT_CLICK` means no new executor handler is
  needed for the press itself.
- **Repeat guard** (`GESTUREOS_DWELL_REPEAT_GUARD_MS`, default ~400):
  after a dwell press, ignore further dwell triggers until the hand has
  *moved beyond the dead zone* (and optionally a minimum time has passed),
  so holding still doesn't machine-gun a character.
- **Cancellation**: moving the hand (target beyond dead zone) resets the
  dwell timer immediately.
- The dwell ring overlay (§4.4) reads the same progress so visual feedback
  matches reality — share state via a single `DwellController` instance.

### 4.4 Dwell progress ring overlay (cursor-following)

- A second, very small Tkinter window (`app/hud/dwell_ring.py`):
  - Always-on-top, **click-through** (same `WS_EX_LAYERED |
    WS_EX_TRANSPARENT` trick as the HUD) so clicks pass through to OSK.
  - Tracks the **system cursor** (poll via pyautogui `position()`, or
    `win32gui.GetCursorPos()` — pick at implementation) on a short timer
    (e.g. every 15–30 ms).
  - Draws a circular progress ring around the cursor position that fills
    as the dwell timer counts down (canvas arc). When the dwell fires, flash
    and hide; hidden entirely when the keyboard is closed.
  - Only rendered while the keyboard is open (typing mode).

### 4.5 Voice setup, verification & dictation

#### New commands (`app/voice/parser.py`)

Add to `_COMMAND_TABLE` / a new dictation branch (order matters — before
shorter matches):

| Phrase | Action |
|---|---|
| `"show keyboard"` / `"open keyboard"` / `"keyboard"` | `KEYBOARD_OPEN` |
| `"hide keyboard"` / `"close keyboard"` | `KEYBOARD_CLOSE` |
| `"start typing"` / `"start dictation"` | `DICTATION_ON` |
| `"stop typing"` / `"stop dictation"` | `DICTATION_OFF` |
| `"type <text>"` (regex prefix, like `_OPEN_APP_RE`) | `TYPED_TEXT`, value = text after "type" |

#### Dictation mode (`app/voice/engine.py`)

- The engine already has the recognised `text` string. Currently non-command
  text is dropped. New behaviour:
  - When **dictation is on** (`DICTATION_ON` received), every recognised
    utterance is first checked against the command table (so `"stop typing"`,
    `"show keyboard"`, etc. still work), and **otherwise pushed as
    `TYPED_TEXT`** with the raw text.
  - `"type <text>"` is a one-shot: parser returns `TYPED_TEXT` immediately
    (no mode change).
- The executor (`app/actions/executor.py`) handles `TYPED_TEXT` by typing the
  value into the focused app via `pyautogui.typewrite()` (with a safe
  char-filter fallback — OSK/pyautogui may choke on non-ASCII; see §8).

#### Voice setup guide (README + `.env.example`)

Documented steps (verify-don't-assume; based on Vosk/PyAudio common issues):

1. **Install audio + speech deps**: `pip install vosk pyaudio` — on Windows,
   `pyaudio` ships a prebuilt wheel; if pip tries to compile and fails with
   "Microsoft Visual C++ 14.0 is required", upgrade pip first
   (`python -m pip install --upgrade pip`) and retry.
2. **Model download**: download `vosk-model-small-en-us-0.15.zip` from
   <https://alphacephei.com/vosk/models>, extract **the folder**
   `vosk-model-small-en-us-0.15` into `models/`
   (config default: `models/vosk-model-small-en-us-0.15`). The engine already
   logs a clear error if the path is missing.
3. **Windows microphone privacy**: Settings → Privacy & security →
   Microphone → enable **Microphone access**, **"Let apps access your
   microphone"**, and **"Let desktop apps access your microphone"** (this is
   the classic silent-failure cause: PyAudio opens but no audio).
4. **Verify**: run `python scripts/voice_check.py` (§4.6).
5. **Run the app** and confirm logs: `VoiceEngine started` →
   `Listening for voice commands…` → `Voice command: <ACTION>` when a
   command is spoken. Set `GESTUREOS_DEBUG_LOG_VOICE=true` to see raw
   transcriptions.

### 4.6 Voice diagnostic script (`scripts/voice_check.py`)

A standalone, dependency-light script that reports, step by step:

1. **PyAudio availability** + list of input devices with `maxInputChannels > 0`
   (name, index, channels) — so the user can find the right
   `GESTUREOS_CAMERA_INDEX`-style mic index if the default is wrong.
2. **Model check**: prints the resolved `VOSK_MODEL_PATH` and whether the
   directory exists; downloads are not automated, just a helpful message.
3. **Live test**: opens the 16 kHz mono int16 stream exactly as the engine
   does, prints **partial** recognitions live and final `Recognized: <text>`
   lines, and exits on Ctrl+C.
4. Clear pass/fail messaging for each stage (mic opened? model loaded?
   speech recognised?), so "is it working?" is answered in one run.

### 4.7 Feedback wiring (all four chosen)

| Cue | Implementation |
|---|---|
| Sound on keypress | `winsound.Beep(1000, 40)` on dwell press (Windows-only app; configurable on/off via `GESTUREOS_KEYBOARD_SOUND`, default on). |
| HUD status line | New labels: `"⌨ Typing"` (TYPING), `"⌨ Keyboard"` for open/close events, and `"🎤 Typing…"` when dictation is on; keep the source icon + warning-colour pattern. |
| Visual press effect | Provided natively by OSK (it highlights the hovered key and animates presses). We cannot restyle OSK. |
| Dwell progress indicator | Cursor-following ring overlay (§4.4). |

Note on "which key was pressed" in the HUD: OSK doesn't expose its layout,
so we cannot reliably name the pressed key without a low-level keyboard hook
(pywin32 `WH_KEYBOARD_LL`). **Default**: show a generic `"⌨ Typing"` state.
Optional enhancement (not in scope unless requested): a keyboard hook to show
the last typed character.

### 4.8 New / changed config knobs (`config.py` + `.env.example` + README)

| Env var | Default | Description |
|---|---|---|
| `GESTUREOS_MP_MAX_HANDS` | `1` → **`2`** | Hands tracked simultaneously (needed for the two-palms gesture; FPS tradeoff). |
| `GESTUREOS_DWELL_MS` | `500` | Hold-still time before a key presses. |
| `GESTUREOS_DWELL_REPEAT_GUARD_MS` | `400` | Cooldown / must-move-before re-press. |
| `GESTUREOS_KEYBOARD_TOGGLE_COOLDOWN_MS` | `1500` | Min time the two-palms pose must be released before it can toggle again. |
| `GESTUREOS_KEYBOARD_IDLE_CLOSE_MS` | `10000` | Hand lost this long while keyboard open → auto-close. |
| `GESTUREOS_OSK_PATH` | `osk.exe` | Windows OSK executable (absolute or on PATH). |
| `GESTUREOS_KEYBOARD_SOUND` | `true` | Beep on dwell keypress. |

---

## 5. Files to Change

| File | Change |
|---|---|
| `config.py` | New knobs (§4.8); `MP_MAX_HANDS` default → 2. |
| `.env.example`, `README.md` | Document knobs; **Voice setup guide** (§4.5); two-hand FPS warning. |
| `app/core/actions.py` | Add `KEYBOARD_OPEN`, `KEYBOARD_CLOSE`, `TYPED_TEXT`, `DICTATION_ON`, `DICTATION_OFF`. |
| `app/actions/keyboard.py` *(new)* | `KeyboardController`: launch/close OSK. |
| `app/actions/executor.py` | Handlers for the new actions; `TYPED_TEXT` → `pyautogui.typewrite`; dictation state. |
| `app/gestures/dwell.py` *(new, or in classifier)* | `DwellController`: dwell timing + repeat guard, shared with the ring overlay. |
| `app/gestures/classifier.py` | Typing-mode suppression (only cursor/pinch/dwell while open); two-open-palms helper; dwell wiring. |
| `main.py` | Two-hand toggle check; typing-mode state; OSK open/close wiring; idle-close on prolonged hand loss. |
| `app/hud/dwell_ring.py` *(new)* | Cursor-following click-through progress ring. |
| `app/hud/overlay.py` | New labels: `⌨ Typing`, keyboard open/close, dictation state. |
| `app/voice/parser.py` | New command patterns + `"type <text>"` regex. |
| `app/voice/engine.py` | Dictation mode: push `TYPED_TEXT` for non-command speech when active. |
| `scripts/voice_check.py` *(new)* | Diagnostic script (§4.6). |
| `tests/` | New tests (§6). |

---

## 6. Test Plan

Unit tests (no hardware needed):

1. **Dwell** (`tests/test_dwell.py`):
   - Moving target never triggers a press.
   - Target held still for ≥ `DWELL_MS` triggers exactly one press.
   - Repeat guard: holding past the press does **not** re-trigger until the
     target moves beyond the dead zone.
   - Moving then holding again triggers again.
2. **Parser** (`tests/test_voice_parser.py`):
   - `"show keyboard"` → `KEYBOARD_OPEN`; `"hide keyboard"` → `KEYBOARD_CLOSE`.
   - `"start typing"` → `DICTATION_ON`; `"stop typing"` → `DICTATION_OFF`.
   - `"type hello world"` → `TYPED_TEXT` value `"hello world"`.
3. **KeyboardController** (mocked `subprocess`):
   - `open()` launches `osk.exe`; `close()` terminates it.
   - Idempotent open/close (no double-launch).
4. **Typing-mode suppression** (`tests/test_gesture_classifier.py`):
   - With the keyboard open, scroll/volume/brightness/swipe gestures emit
     `NONE`; cursor + pinch still work.
5. **Two-hand toggle helper**:
   - Two open palms → toggle signal; single palm / mixed poses → none;
     cooldown re-arm requires release.

Manual validation:

- `python scripts/voice_check.py` — all stages pass; speech is recognised.
- `python main.py --debug`:
  - Show two open palms → OSK appears, HUD shows `⌨ Typing`.
  - Aim at a key, hold ~0.5 s → key types into Notepad, beep + ring fill.
  - Swipe/scroll/volume gestures do nothing while the keyboard is open.
  - Take the hand away → cursor freezes (existing behaviour); after ~10 s the
    keyboard closes.
  - Two open palms again → OSK closes.
  - Say `"show keyboard"`, `"type hello"`, `"start typing" … "stop typing"`,
    `"hide keyboard"` — all behave.

---

## 7. Out of Scope (explicit)

- Custom Tkinter keyboard UI / compact layout / symbol layer (dropped in Round 5).
- Reading the exact pressed key back into the HUD (low-level keyboard hook) —
  optional future enhancement only.
- Multi-language dictation (Vosk small English model only).
- Text-editing gestures inside the keyboard (selection, cursor keys via
  gesture) — OSK's built-in keys cover this.
- Scroll/volume/brightness feel — untouched outside typing-mode suppression.
- Performance tuning of two-hand tracking beyond the config knob.

---

## 8. Risks & Notes

- **Dwell accidental presses**: mitigated by dead zone + repeat guard +
  configurable `DWELL_MS`; if it feels twitchy, raise the dwell or tighten the
  dead zone.
- **OSK focus behaviour**: OSK is designed not to steal focus; verify on the
  user's Windows build that clicking it types into the focused app. If a build
  misbehaves, fallback is a click-through custom keyboard (out of scope now).
- **Dwell ring must be click-through** or it will block OSK clicks.
- **`pyautogui.typewrite` non-ASCII**: dictation text should be filtered to
  printable ASCII / characters OSK+pyautogui support; log-and-skip the rest.
- **Two-hand FPS cost**: accepted by the user; watch for detection drops on the
  laptop webcam and document tuning in README.
- **Vosk small model dictation accuracy** is rough — expected for the model;
  the `"type <text>"` prefix and toggle are still useful for short input.
- **Taskkill on close**: if the user opened OSK manually, we should only kill
  an OSK we launched (track the PID), not a pre-existing one.
- **pyautogui failsafe**: cursor moves must keep avoiding (0,0); existing
  clamping already covers this — dwell clicks reuse the same clamped target.

---

## 9. Open Questions — RESOLVED

1. **OSK vs custom keyboard** → OSK (`osk.exe`), launched and clicked; compact
   layout dropped.
2. **Dwell press mechanism** → reuse `LEFT_CLICK` (click at cursor position);
   no new executor handler needed for the press.
3. **Two-hand pose** → both open palms; toggle with release cooldown.
4. **Dictation** → both `"type …"` prefix and `"start/stop typing"` toggle.
5. **Hand-loss with keyboard open** → close after ~10 s idle, not on the
   200 ms grace.
6. **Gesture mode while typing** → cursor + pinch + dwell only.
7. **`MP_MAX_HANDS`** → default raised to 2.
8. **Voice verification** → standalone `scripts/voice_check.py` + README guide.
