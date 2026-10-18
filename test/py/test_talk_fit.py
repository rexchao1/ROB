"""talk.fit: a model line fit to say out loud, or None (a seat named, too many words)."""

import pytest

from brain import talk


@pytest.mark.parametrize("line", [
    "Nice one, player three.", "Player number three, really?", "The third player looks nervous.",
    "Number three has a point.", "Seat two, your turn.", "Player 4 again.", "the first player is bluffing",
])
def test_fit_drops_a_line_that_names_a_seat(line):
    assert talk.fit(line) is None
    assert talk.fit(line, {"allow_seats": True}) is not None


def test_fit_keeps_an_ordinary_short_line():
    assert talk.fit("Somebody here is bluffing, and it shows.") == "Somebody here is bluffing, and it shows."
    assert talk.fit("One more round, then.") == "One more round, then."


def test_fit_caps_at_sixteen_words():
    assert talk.MAX_WORDS == 16
    assert talk.fit(" ".join(["word"] * 16) + ".") is not None
    assert talk.fit(" ".join(["word"] * 17) + ".") is None
