"""Twenty Questions on a fake table, the player guessing: code decides a guess (D104,
D105), a question the table cannot answer is not a wrong guess (C8)."""

import random

from fake_table import FakeTable

from brain import games, lines
from brain.games.common import Options

RIG = {"mode": "player_guesses", "secret": "dog"}


def play(t: FakeTable, chats: list[str] | None = None) -> FakeTable:
    t.chats = list(chats or [])
    t.reply(lines.count_line(1), "")  # the confirm listen after the count hears nothing
    games.play("twenty", t, random.Random(3), rig=RIG, options=Options())
    return t


def used(t: FakeTable) -> int:
    return t.state["questions"]


def test_d105_a_guess_the_table_does_not_know_is_not_decided_by_the_models_yes():
    t = play(FakeTable(1).hear("is it a kazoo?", "i give up"), chats=["yes", "yes", "yes"])
    assert "Nope, not a kazoo." in t.said
    assert used(t) == 1 and t.state["winner"] == "robot"  # the give-up, not a win on the model's yes
    assert not any(line.startswith("Yes!") for line in t.said)


def test_d104_a_guess_that_names_the_secret_wins_by_code():
    t = play(FakeTable(1).hear("is it a puppy?"), chats=["no"])
    assert t.state["winner"] == "player" and t.state["over"] is True


def test_d104_a_guess_of_another_table_thing_is_a_wrong_guess_that_counts():
    t = play(FakeTable(1).hear("is it a cat?", "i give up"))
    assert any(line.startswith(("Nope", "No.", "Ooh, close")) for line in t.said)
    assert used(t) == 1 and t.state["winner"] == "robot"


def test_c8_an_unknown_guess_that_asks_about_a_trait_is_answered_from_the_table():
    t = play(FakeTable(1).hear("is it a plant?", "i give up"))  # "plant" is a trait, not a thing
    assert "No." in t.said or "Nope." in t.said or "Nah." in t.said
    assert used(t) == 1


def test_c8_offline_an_unknown_guess_with_no_trait_does_not_count():
    t = play(FakeTable(1).hear("is it purple?", "i give up"))
    assert "Can't answer that one. Try another way." in t.said
    assert used(t) == 0


def test_d105_a_models_no_to_an_unknown_guess_is_a_wrong_guess_never_a_loss():
    t = play(FakeTable(1).hear("is it a kazoo?", "i give up"), chats=["no"])
    assert "Nope, not a kazoo." in t.said and used(t) == 1 and t.state["winner"] == "robot"
