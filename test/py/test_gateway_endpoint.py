"""scripts/gateway.py's end-of-speech check: a listen closes once someone has spoken and
gone quiet, and never on silence, a chime or a single click."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("gateway", Path(__file__).parents[2] / "scripts" / "gateway.py")
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)

QUIET, LOUD = 80.0, 3000.0


def run(levels, **kw):
    e = gateway.Endpointer(end_silence_ms=720, **kw)
    return next((i for i, rms in enumerate(levels) if e.feed(rms)), None)


def test_ends_after_speech_then_silence():
    levels = [QUIET] * 14 + [LOUD] * 10 + [QUIET] * 20
    assert run(levels) == 14 + 10 + 12 - 1  # 12 quiet frames of 60 ms after the last word


def test_silence_alone_never_ends():
    assert run([QUIET] * 200) is None


def test_the_opening_chime_is_not_speech():
    assert run([QUIET] * 3 + [LOUD] * 5 + [QUIET] * 50) is None  # as logged: loud in frames 3 to 7


def test_a_click_is_not_speech():
    assert run([QUIET] * 10 + [LOUD] + [QUIET] * 50) is None


def test_a_short_pause_inside_a_sentence_keeps_listening():
    levels = [QUIET] * 8 + [LOUD] * 6 + [QUIET] * 6 + [LOUD] * 6 + [QUIET] * 20
    assert run(levels) == 8 + 6 + 6 + 6 + 12 - 1


def test_a_noisy_room_raises_the_bar():
    room = 900.0  # above the fixed minimum, but steady from the start
    assert run([room] * 60) is None
    levels = [room] * 25 + [room * 5] * 8 + [room] * 20
    assert run(levels) == 25 + 8 + 12 - 1
