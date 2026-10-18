"""Wavelength on a fake table (D21): Player two is the psychic, the spectrum "cold -
hot", the target 7."""

import random

import pytest
from fake_table import FakeTable

from brain import games, lines
from brain.games import wavelength
from brain.table import Card

ROUNDS = [{"spectrum": "cold - hot", "target": 7}, {"spectrum": "bad - good", "target": 3}, {"spectrum": "quiet - loud", "target": 9}]


def play(t: FakeTable, psychic: int = 2, rounds=ROUNDS) -> FakeTable:
    games.play("wavelength", t, random.Random(2), rig={"psychic": psychic, "rounds": rounds})
    return t


def test_the_psychic_alone_sees_the_target():
    t = play(FakeTable(5))
    seat, card = t.shown[0]
    assert seat == 2 and card == Card("7", "cold - hot")
    assert t.said[t.said.index(lines.round_line(1)) + 1] == "Player two, lean in."
    assert Card("7", "cold - hot") in t.prepared and len(t.prepared) == 3


@pytest.mark.parametrize("guess, score", [("six", "Nine points."), ("seven", "Ten points."), ("one", "Four points."), ("ten", "Seven points.")])
def test_a_spoken_guess_scores_by_distance_from_the_target(guess, score):
    t = FakeTable(5)
    t.reply(lines.WAVELENGTH_TALK, guess)
    play(t)
    assert t.said[t.said.index(lines.WAVELENGTH_TALK) + 1] == score


def test_a_guess_out_of_range_or_unclear_is_ignored():
    t = FakeTable(5)
    t.reply(lines.count_line(5), "")
    t.reply(lines.psychic_clue(2), "fire")
    t.reply(lines.WAVELENGTH_TALK, "eleven")
    t.hear("six or seven", "six")
    play(t)
    first = t.said.index(lines.WAVELENGTH_TALK)
    assert t.said[first + 1] == "Nine points."


def test_no_guess_scores_zero():
    t = play(FakeTable(5))
    assert t.said.count(lines.NO_GUESS) == 3
    assert t.said.count(lines.WAVELENGTH_AGAIN) == 3
    assert "Zero points. Nice work." in t.said


def test_the_psychic_rotates_and_the_total_is_announced_after_three_rounds():
    # Player two leads the third round ("Player two is the psychic this round"), so the
    # rounds were led by five, one and two, and the next round would be Player three's.
    t = FakeTable(5)
    t.reply(lines.WAVELENGTH_TALK, "six", "three", "three")  # targets 7, 3, 9: nine, ten, four
    play(t, psychic=5)
    assert [seat for seat, _ in t.shown] == [5, 1, 2]
    assert [line for line in t.said if line.endswith("points.")][:3] == ["Nine points.", "Ten points.", "Four points."]
    assert t.said.count("Twenty-three points. Nice work.") == 1
    assert t.state["next_psychic"] == 3 and t.state["scores"] == [9, 10, 4] and t.state["total"] == 23
    assert t.state["over"] is True and t.state["winner"] is None


def test_rotation_from_player_two():
    t = play(FakeTable(5))
    assert [seat for seat, _ in t.shown] == [2, 3, 4]
    assert t.state["next_psychic"] == 5
    during = [r for r in t.reports if r["round"] == 1 and r["phase"] == "deal"][0]
    assert during["psychic"] == 2 and during["next_psychic"] == 3


def test_random_rounds_have_distinct_cards_and_a_target_in_range():
    rounds = wavelength.plan_rounds(random.Random(4), {"rounds": ROUNDS[:1]}, 3)
    assert rounds[0] == ROUNDS[0] and len({r["spectrum"] for r in rounds}) == 3
    assert all(1 <= r["target"] <= 10 for r in rounds)
    with pytest.raises(ValueError):
        wavelength.plan_rounds(random.Random(4), {"rounds": [{"spectrum": "a - b", "target": 11}]}, 3)


def test_score_is_ten_minus_the_distance():
    assert [wavelength.score(7, g) for g in (6, 7, 1, 10)] == [9, 10, 4, 7]


def test_a_psychic_who_never_leans_in_ends_the_game_on_its_own_line_without_the_ceremony():
    t = play(FakeTable(3, no_lean={2}))
    assert t.said[-1] == lines.CANT_DEAL and lines.GOOD_GAME not in t.said
    assert not set(lines.FLAVOR["win"]) & set(t.said) and lines.WAVELENGTH_TALK not in t.said
    assert t.state["over"] is True and t.state["winner"] is None
