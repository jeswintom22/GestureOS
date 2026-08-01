"""
Unit tests for ToggleGate (two-open-palms keyboard toggle debounce).
"""

from app.core.toggle import ToggleGate


class _FakeClock:
    """Deterministic monotonic clock for driving ToggleGate in tests."""

    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_first_presentation_fires():
    clock = _FakeClock()
    gate = ToggleGate(cooldown_ms=1500, clock=clock)

    assert gate.trigger(True) is True


def test_held_pose_does_not_refire():
    """Holding the pose must not fire again until released."""
    clock = _FakeClock()
    gate = ToggleGate(cooldown_ms=1500, clock=clock)

    assert gate.trigger(True) is True
    clock.advance(10.0)  # cooldown long passed, but pose still held
    assert gate.trigger(True) is False
    assert gate.trigger(True) is False


def test_requires_release_before_retrigger():
    """Releasing the pose re-arms the gate."""
    clock = _FakeClock()
    gate = ToggleGate(cooldown_ms=1500, clock=clock)

    assert gate.trigger(True) is True
    assert gate.trigger(False) is False  # released
    clock.advance(2.0)  # past cooldown
    assert gate.trigger(True) is True


def test_rapid_representation_blocked_by_cooldown():
    """Re-presenting within the cooldown must not double-toggle."""
    clock = _FakeClock()
    gate = ToggleGate(cooldown_ms=1500, clock=clock)

    assert gate.trigger(True) is True
    assert gate.trigger(False) is False
    clock.advance(0.5)  # too soon
    assert gate.trigger(True) is False  # blocked by cooldown
    # Still held — must release again before it can fire
    clock.advance(2.0)
    assert gate.trigger(True) is False
    assert gate.trigger(False) is False
    assert gate.trigger(True) is True
