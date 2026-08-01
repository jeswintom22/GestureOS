"""
Unit tests for VoiceEngine dictation mode (_handle_utterance).

These tests exercise the utterance → event mapping without any audio
hardware: _handle_utterance() is the pure-logic entry point used by the
audio loop, so it can be driven directly.
"""

from app.core.actions import ActionType
from app.core.events import EventBus
from app.voice.engine import VoiceEngine


def _make_engine() -> VoiceEngine:
    EventBus.reset()  # singleton — avoid cross-test leakage
    return VoiceEngine(event_bus=EventBus())


def test_commands_pass_through_when_dictation_off():
    engine = _make_engine()

    ev = engine._handle_utterance("volume up")
    assert ev is not None
    assert ev.action == ActionType.VOLUME_UP

    # Non-command speech with dictation off → nothing
    assert engine._handle_utterance("hello world how are you") is None


def test_start_stop_typing_toggles_dictation():
    engine = _make_engine()

    ev = engine._handle_utterance("start typing")
    assert ev is not None
    assert ev.action == ActionType.DICTATION_ON
    assert engine._dictation_on is True

    # While dictation is on, free speech becomes TYPED_TEXT
    ev2 = engine._handle_utterance("the quick brown fox")
    assert ev2 is not None
    assert ev2.action == ActionType.TYPED_TEXT
    assert ev2.value == "the quick brown fox"
    assert ev2.source == "voice"

    ev3 = engine._handle_utterance("stop typing")
    assert ev3 is not None
    assert ev3.action == ActionType.DICTATION_OFF
    assert engine._dictation_on is False

    # Dictation off again → free speech ignored
    assert engine._handle_utterance("nothing to see") is None


def test_dictation_commands_still_win():
    """Recognised commands must override dictation while it is active."""
    engine = _make_engine()
    engine._handle_utterance("start typing")

    # A known command is still parsed as a command, not typed out
    ev = engine._handle_utterance("show keyboard")
    assert ev is not None
    assert ev.action == ActionType.KEYBOARD_OPEN

    ev2 = engine._handle_utterance("type hello")
    assert ev2 is not None
    assert ev2.action == ActionType.TYPED_TEXT
    assert ev2.value == "hello"
