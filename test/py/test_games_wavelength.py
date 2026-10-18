"""Wavelength on a fake table (D21, D117): Player two guesses first, the numbers 7, 3
and 9."""

import random

import pytest
from fake_table import FakeTable

from brain import games, lines
from brain.games import wavelength
from brain.table import Card

ROUNDS = [{"target": 7}, {"target": 3}, {"target": 9}]


def play(t: FakeTable, guesser: int = 2, rounds=ROUNDS) -> FakeTable:
    games.play("wavelength", t, random.Random(2), rig={"guesser": guesser, "rounds": rounds})
    return t


def test_everyone_but_the_guesser_sees_the_number():
    t = play(FakeTable(5))
    assert [seat for seat, _ in t.shown[:4]] == [3, 4, 5, 1]
    assert all(card == Card("7", "out of ten", "target") for _, card in t.shown[:4])
    assert lines.guesser_turn(2) in t.said


def test_the_guesser_gives_each_player_a_category_then_says_the_number():
    t = play(FakeTable(3))
    first_round = t.said[: t.said.index(lines.guesser_number(2)) + 1]
    asked = [line for line in first_round if line.endswith("a category.")]
    assert asked == [lines.ask_category(2, 3), lines.ask_category(2, 1)]
    assert first_round.index(lines.category_answer(3)) == first_round.index(lines.ask_category(2, 3)) + 1


@pytest.mark.parametrize("guess, score", [("six", "Nine points."), ("seven", "Ten points."), ("one", "Four points."), ("ten", "Seven points.")])
def test_the_guessers_number_scores_by_distance(guess, score):
    t = FakeTable(5)
    t.reply(lines.guesser_number(2), guess)
    play(t)
    assert t.said[t.said.index(lines.guesser_number(2)) + 1] == score


def test_no_guess_scores_zero():
    t = play(FakeTable(5))
    assert t.said.count(lines.NO_GUESS) == 3
    assert t.said.count(lines.WAVELENGTH_AGAIN) == 3
    assert "Zero points. Nice work." in t.said


def test_the_guesser_rotates_and_the_total_is_announced_after_three_rounds():
    t = FakeTable(5)
    t.reply(lines.guesser_number(5), "six")
    t.reply(lines.guesser_number(1), "three")
    t.reply(lines.guesser_number(2), "three")  # numbers 7, 3, 9: nine, ten, four
    play(t, guesser=5)
    assert [line for line in t.said if line.endswith("points.")][:3] == ["Nine points.", "Ten points.", "Four points."]
    assert t.said.count("Twenty-three points. Nice work.") == 1
    assert t.state["next_guesser"] == 3 and t.state["scores"] == [9, 10, 4] and t.state["total"] == 23
    assert t.state["over"] is True and t.state["winner"] is None


def test_two_players_one_sees_the_number_and_the_other_guesses():
    t = play(FakeTable(2), guesser=1)
    assert [seat for seat, _ in t.shown] == [2, 1, 2]


def test_random_rounds_have_a_number_in_range():
    rounds = wavelength.plan_rounds(random.Random(4), {"rounds": ROUNDS[:1]}, 3)
    assert rounds[0] == ROUNDS[0] and len(rounds) == 3
    assert all(1 <= r["target"] <= 10 for r in rounds)
    with pytest.raises(ValueError):
        wavelength.plan_rounds(random.Random(4), {"rounds": [{"target": 11}]}, 3)


def test_score_is_ten_minus_the_distance():
    assert [wavelength.score(7, g) for g in (6, 7, 1, 10)] == [9, 10, 4, 7]


def test_a_player_who_never_leans_in_is_skipped():
    t = play(FakeTable(3, no_lean={3}))
    first_round = t.said[: t.said.index(lines.guesser_number(2)) + 1]
    assert lines.come_back(3) in first_round and lines.ask_category(2, 3) not in first_round
    assert lines.ask_category(2, 1) in first_round


def test_nobody_leaning_in_ends_the_game_on_its_own_line_without_the_ceremony():
    t = play(FakeTable(2, no_lean={1}))
    assert t.said[-1] == lines.CANT_DEAL and lines.GOOD_GAME not in t.said
    assert t.state["over"] is True and t.state["winner"] is None
