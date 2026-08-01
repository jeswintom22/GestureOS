"""
Unit tests for CommandParser.
"""

from app.core.actions import ActionType
from app.voice.parser import CommandParser


def test_parse_open_app():
    parser = CommandParser()

    ev = parser.parse("open chrome")
    assert ev is not None
    assert ev.action == ActionType.OPEN_APP
    assert ev.value == "chrome"
    assert ev.source == "voice"

    ev2 = parser.parse("launch notepad")
    assert ev2 is not None
    assert ev2.action == ActionType.OPEN_APP
    assert ev2.value == "notepad"


def test_parse_volume():
    parser = CommandParser()

    ev = parser.parse("volume up")
    assert ev is not None
    assert ev.action == ActionType.VOLUME_UP

    ev2 = parser.parse("make it louder")
    assert ev2 is not None
    assert ev2.action == ActionType.VOLUME_UP

    ev3 = parser.parse("mute")
    assert ev3 is not None
    assert ev3.action == ActionType.MUTE


def test_parse_window_controls():
    parser = CommandParser()

    ev = parser.parse("close window")
    assert ev is not None
    assert ev.action == ActionType.CLOSE_WINDOW

    ev2 = parser.parse("minimize")
    assert ev2 is not None
    assert ev2.action == ActionType.MINIMIZE_WINDOW


def test_parse_keyboard_open_close():
    parser = CommandParser()

    ev = parser.parse("show keyboard")
    assert ev is not None
    assert ev.action == ActionType.KEYBOARD_OPEN
    assert ev.source == "voice"

    ev2 = parser.parse("keyboard")
    assert ev2 is not None
    assert ev2.action == ActionType.KEYBOARD_OPEN

    ev3 = parser.parse("hide keyboard")
    assert ev3 is not None
    assert ev3.action == ActionType.KEYBOARD_CLOSE

    ev4 = parser.parse("close keyboard")
    assert ev4 is not None
    assert ev4.action == ActionType.KEYBOARD_CLOSE


def test_open_keyboard_is_not_open_app():
    """'open keyboard' must map to KEYBOARD_OPEN, not OPEN_APP."""
    parser = CommandParser()
    ev = parser.parse("open keyboard")
    assert ev is not None
    assert ev.action == ActionType.KEYBOARD_OPEN


def test_parse_dictation_toggle():
    parser = CommandParser()

    ev = parser.parse("start typing")
    assert ev is not None
    assert ev.action == ActionType.DICTATION_ON

    ev2 = parser.parse("start dictation")
    assert ev2 is not None
    assert ev2.action == ActionType.DICTATION_ON

    ev3 = parser.parse("stop typing")
    assert ev3 is not None
    assert ev3.action == ActionType.DICTATION_OFF

    ev4 = parser.parse("stop dictation")
    assert ev4 is not None
    assert ev4.action == ActionType.DICTATION_OFF


def test_start_typing_is_not_open_app():
    """'start typing' must map to DICTATION_ON, not OPEN_APP."""
    parser = CommandParser()
    ev = parser.parse("start typing")
    assert ev is not None
    assert ev.action == ActionType.DICTATION_ON


def test_parse_type_text():
    parser = CommandParser()

    ev = parser.parse("type hello world")
    assert ev is not None
    assert ev.action == ActionType.TYPED_TEXT
    assert ev.value == "hello world"

    ev2 = parser.parse("type next")
    assert ev2 is not None
    assert ev2.action == ActionType.TYPED_TEXT
    assert ev2.value == "next"


def test_type_next_does_not_trigger_media_next():
    """'type next' types the word, it must not skip to the next track."""
    parser = CommandParser()
    ev = parser.parse("type next")
    assert ev is not None
    assert ev.action == ActionType.TYPED_TEXT


def test_parse_unknown():
    parser = CommandParser()
    assert parser.parse("foobar random noise") is None
    assert parser.parse("") is None
    assert parser.parse("type") is None  # no text after "type"
    assert parser.parse("keyboard settings") is None  # not a bare toggle
