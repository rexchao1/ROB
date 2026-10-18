"""Wordle on a fake table: the last guess is confirmed, never scored on silence (C9)."""

import random

from fake_table import FakeTable

from brain import games, lines
from brain.games.common import Options

FIVE = ("crisp", "brick", "ghost", "plumb", "stork")


def play(t: FakeTable) -> FakeTable:
    t.reply(lines.count_line(1), "")  # the confirm listen after the count hears nothing
    games.play("wordle", t, random.Random(5), rig={"word": "crane"}, options=Options())
    return t


def test_c9_silence_after_final_answer_asks_once_more_then_keeps_the_guess_unscored():
    t = play(FakeTable(1).hear(*FIVE, "slate", "", "", "yes"))
    assert "Slate, final answer?" in t.said
    assert "Final answer? Yes or no." in t.said
    i = t.said.index("Final answer? Yes or no.")
    assert not any("Out of guesses" in line for line in t.said[: i + 1])
    assert "Out of guesses. The word was crane. Tough one." in t.said[i + 1 :]  # the later yes scored it


def test_c9_a_yes_to_final_answer_scores_the_guess():
    t = play(FakeTable(1).hear(*FIVE, "slate", "yes"))
    assert t.said.count("Slate, final answer?") == 1 and "Final answer? Yes or no." not in t.said
    assert any(line.startswith("Out of guesses") for line in t.said)


def test_c9_a_no_to_final_answer_asks_for_the_word_again():
    t = play(FakeTable(1).hear(*FIVE, "slate", "no", "crane", "yes"))
    assert "Okay, say it again." in t.said
    assert t.state["winner"] == "players"
