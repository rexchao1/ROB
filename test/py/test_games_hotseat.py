"""Hot Seat on a fake table: an answer on no list is judged by code, and a model's
"no" only makes the host ask the table (D104, D106)."""

import random

from fake_table import FakeTable

from brain import games, lines
from brain.games import hotseat
from brain.games.common import Options

RIG = {"categories": ["fruits", "colors"]}


def play(t: FakeTable, chats: list[str] | None = None) -> FakeTable:
    t.chats = list(chats or [])
    t.reply(lines.count_line(2), "")  # the confirm listen after the count hears nothing
    games.play("hotseat", t, random.Random(2), rig=RIG, options=Options())
    return t


def test_d106_a_models_no_makes_the_host_ask_the_table_and_a_yes_keeps_the_player_in():
    t = FakeTable(2)
    t.reply("Player one, go!", "apple")
    t.reply("Player two, go!", "rambutan")
    t.reply("Rambutan? Does that count?", "yes")
    play(t, chats=["no"])
    assert "Rambutan? Does that count?" in t.said
    first_round = next(r for r in t.reports if r["round"] == 2)
    assert first_round["living"] == [1, 2]


def test_d106_a_no_from_the_table_puts_the_player_out():
    t = FakeTable(2)
    t.reply("Player one, go!", "apple")
    t.reply("Player two, go!", "rambutan")
    t.reply("Rambutan? Does that count?", "no")
    play(t, chats=["no"])
    assert t.state["winner"] == "1" and t.state["out"] == [2]


def test_d106_silence_after_the_question_puts_the_player_out():
    t = FakeTable(2)
    t.reply("Player one, go!", "apple")
    t.reply("Player two, go!", "rambutan")
    play(t, chats=["no"])
    assert "Rambutan? Does that count?" in t.said and t.state["out"] == [2]


def test_judge_offline_an_unlisted_answer_counts_unless_it_is_on_another_list():
    t = FakeTable(2)
    assert hotseat.judge(t, "fruits", "rambutan", set()) == ("ok", "rambutan")
    assert hotseat.judge(t, "fruits", "purple", set()) == ("wrong", None)


def test_judge_a_models_no_is_an_ask_and_its_yes_counts():
    t = FakeTable(2)
    t.chats = ["no"]
    assert hotseat.judge(t, "fruits", "rambutan", set()) == ("ask", "rambutan")
    t.chats = ["yes"]
    assert hotseat.judge(t, "fruits", "rambutan", set()) == ("ok", "rambutan")
