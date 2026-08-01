# GestureOS — Gesture Feel Polish Spec

Status: **Draft — spec only, no code changes yet**
Author: Interview-driven spec (4 rounds with the user)
Target version: next iteration of `main`

---

## 1. Overview

The user's verdict on the current build: *"little clunky and a little rudimentary but it works."* After
discussing the options, the agreed focus is **gesture feel** — the hand-tracked cursor currently feels
jittery when held still, lags when moved fast, and **teleports** when the hand leaves the camera frame
and returns. This spec captures the requirements, design decisions, and implementation plan to fix that.

Scope: **cursor movement and drag movement only.** Scroll thresholds, voice, HUD redesign beyond the
hand-lost indicator, and all other subsystems are explicitly out of scope (see §9).

---

## 2. Current Pipeline Analysis (from code)

### Movement path
1. `app/camera/camera.py` reads frames → `app/gestures/detector.py` (`HandDetector`, MediaPipe Tasks API) extracts 21 landmarks per hand → `HandResult`.
2. `app/gestures/classifier.py` (`GestureClassifier.classify`) decides the gesture and, for `MOVE_CURSOR`, maps the index tip to screen coordinates via `_map_to_screen()` (margin + x-flip for mirrored webcam).
3. `LandmarkSmoother` (`app/gestures/smoother.py`) applies a fixed **EMA** (`alpha = CURSOR_SMOOTHING_ALPHA`, default 0.4) to the index tip before mapping.
4. Events go through the `EventBus` → `ActionExecutor` → `MouseController` (pyautogui).

### Problems found
| # | Problem | Location | Why it feels clunky |
|---|---------|----------|---------------------|
| P1 | Static EMA smoothing | `smoother.py` | One alpha can't do both: high smoothing kills jitter but adds lag on fast moves; low alpha is responsive but jittery at rest. |
| P2 | No dead zone on cursor moves | `classifier.py` `MOVE_CURSOR` branch | `CURSOR_DEAD_ZONE` (0.02) is applied **only to scroll** (`_handle_scroll`). Hand tremor maps straight to sub-pixel→pixel jitter. |
| P3 | Cursor teleports on hand re-acquisition | `classifier.reset()` in `main.py` | When the hand leaves frame, `reset()` clears the smoother; when it reappears, the first `MOVE_CURSOR` maps the raw new hand position → cursor jumps to wherever the hand re-entered. |
| P4 | Mid-drag hand loss leaves the button stuck | `classifier.reset()` | If the hand is lost while `_dragging`, `reset()` clears `_dragging = False` but **never emits `DRAG_END`** → the OS mouse button stays held. |
| P5 | Drag movement is unsmoothed | `classifier.py` `_dragging` branch | The drag path maps the raw index tip (`_map_to_screen(index_tip, ...)`) with **no smoother** → jittery drags. |
| P6 | No visible feedback on hand loss | `overlay.py`, `main.py` | HUD keeps showing the last action while the cursor is frozen; no reason given. |

---

## 3. Interview Decisions (4 rounds)

### Round 1 — Core movement feel
| Question | Decision |
|---|---|
| Smoothing algorithm | **Switch to the One Euro filter** (adaptive: heavy smoothing at rest, near-zero lag in motion). |
| Dead zone | **Screen pixels (3–6px)** — hold the last position within the dead zone. |
| Hand re-acquisition | **Instant resume, no jump** — control resumes immediately, but the cursor holds still until the hand moves. |

### Round 2 — Hand loss & drag edge cases
| Question | Decision |
|---|---|
| Loss timing | **Grace period (~200ms)** before declaring the hand "lost" — tolerates brief detection blips. |
| Drag safety | **Release after grace** — emit `DRAG_END` only once the grace period expires, not on the first missed frame. |
| HUD feedback | **HUD state + color change** — a distinct "🙈 Hand lost" state with a subtle color change on the label. |

### Round 3 — Scope, tuning, config
| Question | Decision |
|---|---|
| Drag feel | **Smooth drags too** — apply the same One Euro filter + dead zone during drags. |
| Config exposure | **Env vars + `.env.example` + README** — every new knob gets a `GESTUREOS_` var, consistent with existing pattern. |
| Hardware setup | **Laptop built-in webcam, hand 20–40cm** — the hand fills more of the frame; fast normalized velocities. Tune One Euro defaults accordingly. |

### Round 4 — Validation & constraints
| Question | Decision |
|---|---|
| Resume anchor | **Re-entry anchor** — on re-acquisition the hand's re-entry position becomes the reference; cursor movement is relative to it (no surprise motion). |
| Validation | **Unit tests + live tuning by user** (`python main.py --debug` + `.env` knobs). |
| Scroll scope | **Cursor + drag only** — leave scroll thresholds untouched. |
| Constraints | **No hard constraints** — new dependencies allowed if genuinely useful (One Euro is pure Python, so none needed). |

---

## 4. Design

### 4.1 One Euro filter (`app/gestures/smoother.py`)

Replace the EMA `LandmarkSmoother` with a One Euro filter (Casiez et al., 2012) — the standard for
hand/pointer HCI filtering.

- Per-axis low-pass filter with a **speed-adaptive cutoff**: `fc = min_cutoff + beta * |velocity|`.
- Filter x and y independently (z is depth and not used for cursor mapping).
- Keep the same public surface so callers barely change:
  - `smooth(landmark, frame_w, frame_h) -> Landmark` (accepts the timestamp internally or via arg)
  - `reset()` — clears per-axis state.
- Inputs use `time.perf_counter()` for `dt` (the loop's fixed `time.sleep(0.005)` is not a reliable frame clock).
- Params (tunable, §4.5):
  - `min_cutoff` (Hz) — smoothing at rest. Lower = less jitter but slower to start moving.
  - `beta` — responsiveness to speed. Higher = less lag on fast moves.
  - `d_cutoff` (Hz) — smoothing of the velocity estimate itself (usually left at ~1.0).

Suggested starting defaults for the laptop-cam close-up case (hand fills frame → fast normalized moves):

| Param | Default | Rationale |
|---|---|---|
| `min_cutoff` | `1.0` Hz | Solid tremor suppression at rest. |
| `beta` | `0.05` | Moderate; near-zero lag on quick flicks without letting noise through. |
| `d_cutoff` | `1.0` Hz | Standard value for velocity estimation. |

These are starting points — the user tunes live via `.env`.

### 4.2 Cursor dead zone (screen pixels)

- New constant `CURSOR_DEAD_ZONE_PX` (default **4**, range 3–6).
- In `classifier.py`, track the **last emitted screen position** (`_last_cursor_screen`).
- When a new target is computed:
  - If it is within `CURSOR_DEAD_ZONE_PX` of the last emitted position → emit **no movement** (return `NONE` for normal moves; for drags, re-report the held position so the HUD stays in the dragging state).
  - Once it exceeds the dead zone → update `_last_cursor_screen` and emit `MOVE_CURSOR`.
- Dead zone is evaluated **after** filtering, in **screen-pixel** space (matches how the user perceives precision).

### 4.3 Hand loss: grace period & re-entry anchor

This is a state machine in the gesture loop (`main.py`) + classifier:

```
HAND_TRACKED --(no detection)--> GRACE (≈200ms, cursor frozen, filter state kept)
GRACE --(hand returns)----------> HAND_TRACKED (seamless — no anchor reset)
GRACE --(timer expires)---------> HAND_LOST (emit HAND_LOST event; release drag; classifier.reset())
HAND_LOST --(hand detected)-----> RE-ENTERING (capture re-entry anchor; cursor stays put)
RE-ENTERING --(hand moves > dead zone)--> HAND_TRACKED
```

- **Grace period** (`HAND_LOST_GRACE_MS`, default 200): `main.py` tracks the time since the last
  detection. If the hand returns during grace, nothing is reset — no flicker, no jump.
- **On grace expiry** (declared lost):
  - Push a `GestureEvent(action=ActionType.HAND_LOST)` (new enum, §4.4).
  - If `classifier._dragging` was true → push `GestureEvent(action=ActionType.DRAG_END)` to release the button (fixes P4).
  - Call `classifier.reset()` (clears smoother, drag, swipe, scroll state).
- **Re-entry anchor** (fixes P3): the classifier keeps a persistent screen offset between the raw
  mapped position and the last cursor position.
  - On re-entry, capture `anchor = current mapped position` and `offset = last_cursor_screen - anchor`.
  - While `|mapped - anchor|` stays within the dead zone → hold (no movement).
  - Beyond the dead zone → target = `mapped + offset` (relative movement from the anchor), so there is
    **no jump** and no requirement to "re-center" the hand in the frame (user explicitly rejected the
    re-centering gate).

### 4.4 New `ActionType.HAND_LOST`

- Add to `ActionType` in `app/core/actions.py`.
- `ActionExecutor` dispatch: no-op handler (consume it, do nothing).
- `HUD` (`app/hud/overlay.py`):
  - Label: `"🙈 Hand Lost"` (icon + text).
  - **Color change**: when the event is `HAND_LOST`, set the label `fg` to an amber/warning tone
    (e.g. `#ffcc66` or similar); restore the normal `HUD_TEXT_COLOR` on the next non-`HAND_LOST` event.

### 4.5 New / changed config knobs (`config.py` + `.env.example` + README)

| Env var | Default | Description |
|---|---|---|
| `GESTUREOS_ONE_EURO_MIN_CUTOFF` | `1.0` | One Euro min cutoff (Hz) — smoothing at rest |
| `GESTUREOS_ONE_EURO_BETA` | `0.05` | One Euro speed coefficient — responsiveness |
| `GESTUREOS_ONE_EURO_D_CUTOFF` | `1.0` | One Euro derivative cutoff (Hz) |
| `GESTUREOS_CURSOR_DEAD_ZONE_PX` | `4` | Cursor dead zone in screen pixels (3–6 recommended) |
| `GESTUREOS_HAND_LOST_GRACE_MS` | `200` | Frames of grace before declaring the hand lost |
| `GESTUREOS_CURSOR_SMOOTHING_ALPHA` | *(kept)* | Retained for compatibility; no longer used once One Euro is active (or removed — see open question §10) |

---

## 5. Files to Change

| File | Change |
|---|---|
| `app/gestures/smoother.py` | Replace EMA with One Euro filter (same class/interface, or new `OneEuroFilter` class; classifier updated to match). |
| `app/gestures/classifier.py` | Use One Euro; dead-zone cursor moves; smooth drag moves; re-entry anchor offset; track `_last_cursor_screen`. |
| `app/core/actions.py` | Add `HAND_LOST` enum value. |
| `app/actions/executor.py` | No-op handler for `HAND_LOST`. |
| `app/hud/overlay.py` | `HAND_LOST` label + warning color. |
| `main.py` | Grace-period state machine; emit `HAND_LOST` and post-grace `DRAG_END`; wire re-entry anchor. |
| `config.py` | New constants (§4.5). |
| `.env.example`, `README.md` | Document new knobs (README config table + brief gesture-feel section). |
| `tests/test_gesture_classifier.py` (+ new `tests/test_smoother.py`) | Tests per §6. |

---

## 6. Test Plan

Unit tests (no hardware needed):

1. **One Euro filter** (`tests/test_smoother.py`):
   - Constant input converges to the input value.
   - Jittery input at rest is attenuated (variance of output < variance of input).
   - `reset()` clears state (output resumes from raw after reset).
2. **Dead zone** (`test_gesture_classifier.py`):
   - Same hand position across consecutive frames → first emits `MOVE_CURSOR`, subsequent emit `NONE` (held).
   - Movement beyond the dead zone emits `MOVE_CURSOR` again.
3. **Re-entry anchor**:
   - After `reset()`, first frame emits no movement; cursor target has no jump (offset math holds).
4. **Drag**:
   - Drag movement is emitted with smoothed coordinates.
   - `reset()` while dragging → caller (main loop) emits `DRAG_END` (classifier exposes dragging state; main loop pushes the event).

Manual validation: `python main.py --debug`, tune via `.env`, check:
- Cursor is still when hand is still (no tremor jitter).
- Cursor keeps up on fast flicks (no rubber-band lag).
- Taking the hand out of frame and re-entering causes **no teleport**.
- Mid-drag hand loss releases the mouse button after ~200ms.

---

## 7. Out of Scope (explicit)

- Scroll feel / scroll dead zone / scroll sensitivity (kept as-is this pass).
- Voice engine feel or wake-word latency.
- Full HUD redesign (only the hand-lost indicator + color is in scope).
- Gesture map changes, new gestures, calibration/re-centering gestures (user chose re-entry anchor over a re-centering gate).
- Camera capture / inference performance tuning.

---

## 8. Risks & Notes

- **Latency vs smoothness**: One Euro's whole point is avoiding the tradeoff, but badly-tuned `beta`
  can either reintroduce jitter (too high) or lag (too low). Defaults in §4.1 are starting points.
- **pyautogui failsafe**: `MouseController` enables `pyautogui.FAILSAFE` — cursor moves must never
  target (0,0) unintentionally; the re-entry offset math must clamp to the visible screen area.
- **`time.sleep(0.005)` loop**: dt should come from a monotonic clock, not assumed constant, or the
  One Euro filter will misbehave under load.
- **Laptop webcam close-up**: hand fills more of the frame, so normalized velocities are higher —
  the `beta` default may need upward tuning if the user feels lag on flicks.

---

## 9. Open Questions — RESOLVED

1. **`CURSOR_SMOOTHING_ALPHA`** → **Removed** (dead config once One Euro is active; pre-1.0 project, clean break). Removed from `config.py`, `.env.example`, README.
2. **Class naming** → New `OneEuroFilter` class in `smoother.py`; `LandmarkSmoother` removed; imports/exports updated (`app/gestures/__init__.py`).
3. **Warning color** → Amber `#ffcc66` (`_HAND_LOST_COLOR` in `overlay.py`).
