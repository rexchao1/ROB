"""The welcome (brain/games/welcome.py): it greets and listens straight away, takes a
headcount at its word, and sweeps the table only when asked."""

import random

from fake_table import FakeTable

from brain import lines
from brain.games.common import Options
from brain.games.welcome import Choice, Welcome


def _welcome(table):
    return Welcome(table, random.Random(3), Options(), listen_window=4.0)


def _kinds(table):
    return [kind for _, kind, _ in table.log]


def test_the_greeting_asks_and_listens_with_no_sweep():
    table = FakeTable().hear("let's play imposter")
    w = _welcome(table)
    w.greet()
    choice = w.converse()
    assert table.said[0] in lines.GREETINGS
    assert "count" not in _kinds(table)
    assert choice == Choice("imposter", "let's play imposter", None, False)


def test_a_headcount_is_taken_at_its_word_and_gets_a_suggestion():
    table = FakeTable().hear("there are three of us", "sure")
    w = _welcome(table)
    w.greet()
    choice = w.converse()
    assert "count" not in _kinds(table)
    assert ("seated", 3) in [(k, v) for _, k, v in table.log]
    assert "Imposter" in table.said[1]
    assert choice == Choice("imposter", "sure", 3, False)


def test_just_me_is_one_player():
    table = FakeTable().hear("just me")
    w = _welcome(table)
    w.greet()
    assert w.converse() is None  # silence after: nudges, then a nap
    assert w.seats == 1 and lines.suggested(1) == w.suggestion


def test_count_us_sweeps_says_hello_and_suggests():
    table = FakeTable(seats=5).hear("count us", "let's play mafia")
    w = _welcome(table)
    w.greet()
    choice = w.converse()
    assert table.said[1] in lines.LOOKING
    assert "count" in _kinds(table)
    assert any(line.startswith(("Hi,", "You're")) for line in table.said)
    assert choice == Choice("mafia", "let's play mafia", 5, True)


def test_what_should_we_play_with_no_count_asks_how_many():
    table = FakeTable().hear("what should we play", "four of us")
    w = _welcome(table)
    w.greet()
    assert w.converse() is None
    assert lines.HOW_MANY in table.said
    assert w.seats == 4
