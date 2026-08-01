"""
GestureOS — Main Entry Point & Orchestrator

Initializes all pipelines:
1. Camera + Gesture recognition loop (daemon thread)
2. Voice recognition engine (daemon thread)
3. Action executor dispatcher (daemon thread)
4. HUD Overlay (main thread - Tkinter event loop)

Supports CLI flags:
  --debug       Show OpenCV preview window with hand landmarks
  --no-voice    Disable voice command engine
  --no-gesture  Disable camera gesture tracking
"""

import argparse
import logging
import signal
import sys
import threading
import time

import config
from app.actions.executor import ActionExecutor
from app.camera.camera import Camera
from app.core.actions import ActionType
from app.core.events import EventBus, GestureEvent
from app.gestures.classifier import GestureClassifier
from app.gestures.detector import HandDetector
from app.hud.overlay import HUD
from app.utils.fps import FPSCounter
from app.voice.engine import VoiceEngine

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("GestureOS")

# Silence noisy third-party loggers (e.g. screen-brightness-control EDID
# warnings) unless the user opts out.
if config.QUIET_THIRD_PARTY_WARNINGS:
    # Setting the parent level also silences the .windows child logger.
    logging.getLogger("screen_brightness_control").setLevel(logging.ERROR)


class GestureOSController:
    """Orchestrates all GestureOS subsystems."""

    def __init__(
        self,
        debug: bool = False,
        enable_voice: bool = True,
        enable_gesture: bool = True,
    ):
        self.debug = debug
        self.enable_voice = enable_voice
        self.enable_gesture = enable_gesture

        self.bus = EventBus()
        self.executor = ActionExecutor(event_bus=self.bus)

        self.voice_engine = VoiceEngine(event_bus=self.bus) if enable_voice else None

        self.camera = None
        self.detector = None
        self.classifier = None
        self.gesture_thread = None

        self.gesture_enabled = True
        self.stop_event = threading.Event()

        # Hand-loss tracking: timestamp of the last frame where a hand was
        # seen, and whether the hand is currently declared "lost" (past the
        # grace period).
        self._last_hand_time = 0.0
        self._hand_lost = True

    def start(self) -> None:
        """Start background threads and HUD."""
        log.info("Starting GestureOS...")

        # 1. Start action executor thread
        self.executor.start()

        # 2. Start voice engine if enabled
        if self.voice_engine:
            self.voice_engine.start()

        # 3. Start gesture processing thread if enabled
        if self.enable_gesture:
            self.gesture_thread = threading.Thread(
                target=self._run_gesture_loop,
                name="GestureLoop",
                daemon=True,
            )
            self.gesture_thread.start()

        log.info("GestureOS operational. Launching HUD...")

    def _run_gesture_loop(self) -> None:
        try:
            self.camera = Camera()
            self.detector = HandDetector()
            self.classifier = GestureClassifier()
            fps_counter = FPSCounter()
        except Exception:
            log.exception("Failed to initialize camera / gesture pipeline")
            return

        log.info("Gesture processing loop active")

        try:
            while not self.stop_event.is_set():
                fps = fps_counter.update()

                rgb_frame = self.camera.read_rgb()
                if rgb_frame is None:
                    time.sleep(0.01)
                    continue

                h, w = rgb_frame.shape[:2]
                hands = self.detector.detect(rgb_frame, w, h)

                if hands and self.gesture_enabled:
                    # Hand is present — reset the loss timer
                    self._last_hand_time = time.monotonic()
                    if self._hand_lost:
                        self._hand_lost = False
                        log.debug("Hand re-acquired")

                    # Classify first hand
                    event = self.classifier.classify(hands[0], w, h)

                    # Handle system-level toggles directly or push to bus
                    if event.action == ActionType.GESTURE_OFF:
                        self.gesture_enabled = False
                        log.info("Gestures disabled")
                    elif event.action == ActionType.GESTURE_ON:
                        self.gesture_enabled = True
                        log.info("Gestures enabled")
                    elif event.action != ActionType.NONE:
                        self.bus.push(event)

                elif not hands and self.gesture_enabled:
                    # Grace period: only declare the hand "lost" after it has
                    # been absent for HAND_LOST_GRACE_MS. This tolerates brief
                    # tracking blips without freezing the cursor — the
                    # classifier is NOT reset during grace, so a returning
                    # hand resumes seamlessly.
                    if not self._hand_lost and (
                        (time.monotonic() - self._last_hand_time) * 1000
                        >= config.HAND_LOST_GRACE_MS
                    ):
                        self._hand_lost = True
                        log.info("Hand lost")
                        self.bus.push(GestureEvent(action=ActionType.HAND_LOST))
                        # If we were dragging, release the mouse button so it
                        # doesn't stay stuck. (Check dragging BEFORE reset —
                        # reset() clears the drag state.)
                        if self.classifier.dragging:
                            log.info("Releasing drag after hand loss")
                            self.bus.push(GestureEvent(action=ActionType.DRAG_END))
                        self.classifier.reset()

                # Optional debug window
                if self.debug or config.DEBUG_SHOW_CAMERA:
                    bgr_frame = self.camera.read()
                    if bgr_frame is not None:
                        annotated = self.detector.draw(bgr_frame, rgb_frame)
                        key = self.camera.show(annotated)
                        if key == 27 or key == ord("q"):  # ESC or q
                            log.info("Quit requested via debug window")
                            self.stop()
                            break

                time.sleep(0.005)  # Yield CPU slightly

        except Exception:
            log.exception("Error in gesture loop")
        finally:
            if self.detector:
                self.detector.close()
            if self.camera:
                self.camera.release()
            log.info("Gesture loop stopped")

    def stop(self) -> None:
        """Gracefully stop all components."""
        log.info("Stopping GestureOS...")
        self.stop_event.set()

        if self.voice_engine:
            self.voice_engine.stop()

        self.executor.stop()
        log.info("GestureOS stopped")


def parse_args():
    parser = argparse.ArgumentParser(description="GestureOS - Hand & Voice Control Overlay")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show webcam preview with hand landmarks",
    )
    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="Disable voice recognition engine",
    )
    parser.add_argument(
        "--no-gesture",
        action="store_true",
        help="Disable camera gesture recognition",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    controller = GestureOSController(
        debug=args.debug,
        enable_voice=not args.no_voice,
        enable_gesture=not args.no_gesture,
    )

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        log.info("Interrupt received, shutting down...")
        controller.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    controller.start()

    # Launch HUD on main thread (Tkinter loop blocks here)
    try:
        hud = HUD(event_bus=controller.bus)
        hud.run()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()


if __name__ == "__main__":
    main()