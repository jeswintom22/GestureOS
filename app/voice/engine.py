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
from app.core.events import EventBus
from app.voice.parser import CommandParser

log = logging.getLogger(__name__)


class VoiceEngine:
    """
    Offline voice command engine using Vosk.

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

                    event = self._parser.parse(text)
                    if event:
                        self._bus.push(event)
                        log.info("Voice command: %s", event.action.name)

        except Exception:
            log.exception("VoiceEngine error")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
