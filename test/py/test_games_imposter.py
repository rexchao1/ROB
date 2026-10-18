"""Imposter on a fake table (D20): the word is "beach" and Player three is the Imposter."""

import random

from fake_table import FakeTable

from brain import games, lines
from brain.table import Card

RIG = {"word": "beach", "imposter": 3}


def play(t: FakeTable, rig=RIG) -> FakeTable:
    games.play("imposter", t, random.Random(5), rig=rig)
    return t


def votes(t: FakeTable, answer: str) -> FakeTable:
    for seat in range(1, 6):
        t.reply(lines.who(seat), answer)
    return t


def test_words_are_dealt_and_one_player_sees_imposter():
    t = play(FakeTable(5))
    assert [seat for seat, _ in t.shown] == [1, 2, 3, 4, 5]
    assert dict(t.shown) == {1: Card("beach"), 2: Card("beach"), 3: Card("IMPOSTER"), 4: Card("beach"), 5: Card("beach")}
    assert set(t.prepared) == {Card("beach"), Card("IMPOSTER")}


def test_each_player_gives_one_clue_in_seat_order():
    t = play(FakeTable(5))
    start, end = t.said.index(lines.CLUES), t.said.index(lines.IMPOSTER_VOTE)
    addressed = [line for line in t.said[start:end] if line.startswith("Player")]
    assert addressed == ["Player one, one word.", "Player two, one word.", "Player three, one word.", "Player four, one word.", "Player five, one word."]
    looks = [e[2] for e in t.log if e[1] == "look"]
    assert [1, 2, 3, 4, 5, None] == looks[looks.index(1, 6) : looks.index(1, 6) + 6]  # after the deal's looks


def test_voting_out_the_imposter_ends_the_round_with_a_reveal():
    t = play(votes(FakeTable(5), "three"))
    assert "Player three was the Imposter." in t.said
    assert lines.word_was("beach") in t.said
    assert t.state["over"] is True and t.state["winner"] == "players"


def test_voting_out_anyone_else_lets_the_imposter_survive():
    t = play(votes(FakeTable(5), "two"))
    assert "The Imposter survives. It was Player three." in t.said
    assert lines.was_imposter(3) not in t.said
    assert t.state["winner"] == "imposter"


def test_a_tie_lets_the_imposter_survive():
    t = FakeTable(4)
    for seat, answer in {1: "two", 2: "three", 3: "two", 4: "three"}.items():
        t.reply(lines.who(seat), answer)
    play(t)
    assert lines.tie([(2, 2), (3, 2)]) in t.said
    assert lines.imposter_survives(3) in t.said


def test_a_random_word_comes_from_the_list():
    t = FakeTable(5)
    games.play("imposter", t, random.Random(11))
    words = {card.text for _, card in t.shown} - {"IMPOSTER"}
    assert len(words) == 1 and words.pop() in lines.IMPOSTER_WORDS
    assert sum(1 for _, card in t.shown if card.text == "IMPOSTER") == 1


def test_a_deal_that_cannot_finish_ends_on_its_own_line_without_the_ceremony():
    t = play(FakeTable(4, no_lean={2}))
    assert t.said[-1] == lines.CANT_DEAL and lines.GOOD_GAME not in t.said and lines.CLUES not in t.said
    assert t.state["over"] is True and t.state["winner"] is None
