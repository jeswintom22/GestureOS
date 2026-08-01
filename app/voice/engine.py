"""
GestureOS — Voice Engine

Runs Vosk offline speech recognition in a background thread.
Continuously listens to the microphone and pushes recognised
commands through the ``EventBus``.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Optional

import config
from app.core.actions import ActionType
from app.core.events import EventBus, GestureEvent
from app.voice.parser import CommandParser

log = logging.getLogger(__name__)


class VoiceEngine:
    """
    Offline voice command engine using Vosk.

    In addition to parsed commands, supports a dictation mode: while enabled
    (via the "start typing" / "stop typing" commands), every recognised
    utterance that isn't a command is pushed as a ``TYPED_TEXT`` event so it
    can be typed into the focused app.

    Usage::

        engine = VoiceEngine()
        engine.start()
        ...
        engine.stop()
    """

    def __init__(self, event_bus: EventBus | None = None):
        self._bus = event_bus or EventBus()
        self._parser = CommandParser()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # Dictation mode: while True, non-command speech becomes TYPED_TEXT.
        self._dictation_on = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start listening in a daemon thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="VoiceEngine",
            daemon=True,
        )
        self._thread.start()
        log.info("VoiceEngine started")

    def stop(self) -> None:
        """Signal the engine to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        log.info("VoiceEngine stopped")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        try:
            import pyaudio
            from vosk import Model, KaldiRecognizer
        except ImportError as e:
            log.error(
                "Voice dependencies not installed (%s). "
                "Run: pip install vosk pyaudio",
                e,
            )
            return

        # Load model
        model_path = config.VOSK_MODEL_PATH
        if not os.path.isdir(model_path):
            log.error(
                "Vosk model not found at %s. "
                "Download from https://alphacephei.com/vosk/models "
                "and extract to that path.",
                model_path,
            )
            return

        model = Model(model_path)
        recognizer = KaldiRecognizer(model, config.VOICE_SAMPLE_RATE)

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=config.VOICE_SAMPLE_RATE,
            input=True,
            frames_per_buffer=config.VOICE_CHUNK_SIZE,
        )
        stream.start_stream()

        log.info("Listening for voice commands…")

        try:
            while not self._stop_event.is_set():
                data = stream.read(
                    config.VOICE_CHUNK_SIZE,
                    exception_on_overflow=False,
                )

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()

                    if not text:
                        continue

                    if config.DEBUG_LOG_VOICE:
                        log.info("Voice: %r", text)

                    event = self._handle_utterance(text)
                    if event is not None:
                        self._bus.push(event)

        except Exception:
            log.exception("VoiceEngine error")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

    # ------------------------------------------------------------------
    # Utterance handling (also used directly by tests)
    # ------------------------------------------------------------------

    def _handle_utterance(self, text: str) -> Optional[GestureEvent]:
        """
        Turn one recognised utterance into a ``GestureEvent`` (or ``None``).

        Commands are parsed normally. ``DICTATION_ON`` / ``DICTATION_OFF``
        toggle dictation mode (the events are still pushed to the bus so the
        HUD can show the state). While dictation is on, any utterance that
        is not a recognised command becomes a ``TYPED_TEXT`` event.

        Note: the returned event is pushed by the caller, not here.
        """
        event = self._parser.parse(text)
        if event is not None:
            if event.action == ActionType.DICTATION_ON:
                self._dictation_on = True
                log.info("Dictation ON")
            elif event.action == ActionType.DICTATION_OFF:
                self._dictation_on = False
                log.info("Dictation OFF")
            if event.action == ActionType.TYPED_TEXT:
                log.info("Dictation text: %r", event.value)
            else:
                log.info("Voice command: %s", event.action.name)
            return event

        if self._dictation_on:
            return GestureEvent(
                action=ActionType.TYPED_TEXT,
                value=text,
                source="voice",
            )
        return None
