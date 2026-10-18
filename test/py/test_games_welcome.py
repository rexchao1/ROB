"""The welcome's conversation on a fake table (D38 to D43, D94): a game's name inside
other talk gets a confirm, not a start."""

import random

from fake_table import FakeTable

from brain import lines
from brain.games.common import Options
from brain.games.welcome import Choice, Welcome


def welcome(seats: int = 5) -> tuple[Welcome, FakeTable]:
    t = FakeTable(seats)
    w = Welcome(t, random.Random(1), Options(), listen_window=4.0)
    w.greet()
    return w, t


def test_d94_a_games_name_inside_other_talk_asks_instead_of_starting():
    w, t = welcome()
    assert w.suggestion == "mafia"
    answer = w._hear("that was a hot seat yesterday", t.now())
    assert answer is None  # keep talking: no Choice
    assert t.said[-1] == "Hot Seat? Say yes to play it."
    assert w.suggestion == "hotseat"


def test_d94_a_yes_after_the_confirm_starts_that_game():
    w, t = welcome()
    w._hear("i have twenty questions about this", t.now())
    assert t.said[-1] == lines.confirm_game("twenty")
    answer = w._hear("yes", t.now())
    assert isinstance(answer, Choice) and answer.game == "twenty"


def test_d94_a_plain_request_still_starts_at_once():
    w, t = welcome()
    answer = w._hear("let's play hot seat", t.now())
    assert isinstance(answer, Choice) and answer.game == "hotseat" and answer.counted == 5
