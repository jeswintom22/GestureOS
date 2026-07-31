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


def test_parse_unknown():
    parser = CommandParser()
    assert parser.parse("foobar random noise") is None
    assert parser.parse("") is None
