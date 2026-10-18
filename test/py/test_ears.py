"""Parsing what was heard: lower-cased Whisper output, punctuation and all. Every parser
answers None rather than guess."""

import pytest

from brain import ears


@pytest.mark.parametrize(
    "text, game",
    [
        ("let's play mafia.", "mafia"),
        ("Let's play Mafia!", "mafia"),
        ("can we play werewolf", "mafia"),
        ("let's play impostor", "imposter"),
        ("let's play in poster", "imposter"),
        ("wavelength please", "wavelength"),
        ("let's play wave length", "wavelength"),
        ("let's play a game", None),
        ("", None),
    ],
)
def test_game_named(text, game):
    assert ears.game_named(text) == game


@pytest.mark.parametrize(
    "text, n",
    [
        ("there are six of us", 6),
        ("there are six of us.", 6),
        ("six of us", 6),
        ("we're six", 6),
        ("we are six.", 6),
        ("6 players", 6),
        ("six people", 6),
        ("we have six", 6),
        ("let's play mafia, there are six of us", 6),
        ("let's play mafia", None),
        ("player four", None),
        ("there are two mafia", None),
        ("four", None),
        ("", None),
    ],
)
def test_count_said(text, n):
    assert ears.count_said(text) == n


@pytest.mark.parametrize(
    "text, seat",
    [
        ("player four", 4),
        ("player four.", 4),
        ("Player Four.", 4),
        ("four", 4),
        ("4", 4),
        ("4.", 4),
        ("number four", 4),
        ("i vote for four", 4),
        ("i vote for player two", 2),
        ("player for", 4),
        ("for.", 4),
        ("too", 2),
        ("won", 1),
        ("player-three", 3),
        ("i want to go home", None),  # "to" in a sentence is not a seat
        ("two or four", None),  # two seats named: ask again
        ("player six", None),  # no such seat at five
        ("no one", None),
        ("", None),
        ("um", None),
    ],
)
def test_seat_said_at_five_seats(text, seat):
    assert ears.seat_said(text, 5) == seat


@pytest.mark.parametrize(
    "text, n",
    [("six", 6), ("i think seven", 7), ("7", 7), ("ten", 10), ("one", 1), ("eleven", None), ("six or seven", None), ("", None)],
)
def test_number_said(text, n):
    assert ears.number_said(text) == n


def test_bare_number_is_only_a_number():
    assert ears.bare_number("six.") == 6
    assert ears.bare_number("uh, six") == 6
    assert ears.bare_number("player six") == 6
    assert ears.bare_number("i think there might be six") is None


def test_agreeing_stopping_and_voting_early():
    assert ears.agrees("okay")
    assert ears.agrees("yeah, fine, start")
    assert not ears.agrees("there are six of us")
    assert ears.wants_to_stop("let's stop the game")
    assert ears.wants_to_stop("can we start over")
    assert not ears.wants_to_stop("stop it, player two")
    assert ears.wants_to_vote("okay let's vote")
    assert not ears.wants_to_vote("i think it's player two")
