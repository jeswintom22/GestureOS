"""
Unit tests for the One Euro filter (app/gestures/smoother.py).
"""

import math

from app.gestures.detector import Landmark
from app.gestures.smoother import OneEuroFilter

FPS_DT = 1.0 / 30.0  # simulated ~30 fps frame interval


def _landmark(x: float, y: float) -> Landmark:
    return Landmark(x=x, y=y, z=0.0, px=int(x * 640), py=int(y * 480))


def _run(filt, values, dt=FPS_DT):
    """Feed a sequence of x values through the filter, return filtered xs."""
    out = []
    for x in values:
        lm = filt.smooth(_landmark(x, 0.5), 640, 480, dt=dt)
        out.append(lm.x)
    return out


def test_constant_input_converges():
    filt = OneEuroFilter(min_cutoff=10.0, beta=0.0, d_cutoff=1.0)
    out = _run(filt, [0.5] * 30)
    assert all(abs(v - 0.5) < 1e-6 for v in out[20:]), out


def test_jitter_attenuated_at_rest():
    """A jittery signal around a fixed point should be heavily smoothed."""
    filt = OneEuroFilter(min_cutoff=1.0, beta=0.0, d_cutoff=1.0)
    noisy = [0.5 + 0.02 * math.sin(i * 2.3) for i in range(60)]
    out = _run(filt, noisy)

    spread_in = max(noisy) - min(noisy)
    spread_out = max(out[10:]) - min(out[10:])
    assert spread_out < spread_in * 0.25, (spread_in, spread_out)


def test_fast_motion_less_smoothed():
    """
    With a positive beta, a fast step should track more aggressively than a
    low cutoff alone would allow (low latency on quick movements).
    """
    filt = OneEuroFilter(min_cutoff=0.1, beta=1.0, d_cutoff=1.0)
    step = [0.0] * 5 + [1.0] * 5
    out = _run(filt, step)
    # After 5 frames of a large step, the filter should have travelled most
    # of the way (adaptive cutoff opens up at speed).
    assert out[-1] > 0.5, out


def test_reset_clears_state():
    filt = OneEuroFilter(min_cutoff=1.0, beta=0.0, d_cutoff=1.0)
    _run(filt, [0.9] * 10)
    filt.reset()
    # After reset, the first call returns the raw position (no history).
    out = _run(filt, [0.1])
    assert out == [0.1]


def test_param_validation():
    try:
        OneEuroFilter(min_cutoff=0.0)
    except ValueError:
        pass
    else:
        raise AssertionError("min_cutoff=0 should raise")
