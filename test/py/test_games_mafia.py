"""Mafia on a fake table (D15 to D19). The roles are rigged as the feature file's
Background has them: Player one is the Mafia and Player five is the Doctor."""

import random

import pytest
from fake_table import FakeTable

from brain import games, lines
from brain.games import mafia
from brain.games.common import Options
from brain.table import Card

RIG = {"mafia": [1], "doctor": 5}


def play(t: FakeTable, rig=RIG, **options) -> FakeTable:
    games.play("mafia", t, random.Random(7), rig=rig, options=Options(**options))
    return t


def night(t: FakeTable, target: str, save: str) -> FakeTable:
    t.reply(lines.MAFIA_WHISPER, target)
    t.reply(lines.DOCTOR_WHISPER, save)
    return t


def votes(t: FakeTable, answers: dict[int, str]) -> FakeTable:
    for seat, answer in answers.items():
        t.reply(lines.who(seat), answer)
    return t


def test_d15_roles_are_dealt_one_at_a_time_in_seat_order():
    t = play(FakeTable(5), max_rounds=0)
    assert [seat for seat, _ in t.shown] == [1, 2, 3, 4, 5]
    assert dict(t.shown) == {1: Card("MAFIA"), 2: Card("VILLAGER"), 3: Card("VILLAGER"), 4: Card("VILLAGER"), 5: Card("DOCTOR")}
    prepare = next(i for i, e in enumerate(t.log) if e[1] == "prepare")
    first_show = next(i for i, e in enumerate(t.log) if e[1] == "show")
    assert prepare < first_show
    assert set(t.prepared) == {Card("MAFIA"), Card("DOCTOR"), Card("VILLAGER")}


@pytest.mark.parametrize("seats, mafia_n", [(4, 1), (5, 1), (6, 1), (7, 2), (10, 2)])
def test_d15_role_counts(seats, mafia_n):
    roles = mafia.assign_roles(seats, random.Random(seats), {})
    assert list(roles.values()).count("MAFIA") == mafia_n
    assert list(roles.values()).count("DOCTOR") == 1
    assert sorted(roles) == list(range(1, seats + 1))


def test_seven_players_two_mafia_a_partial_rig_is_filled_in():
    roles = mafia.assign_roles(7, random.Random(1), {"mafia": [1], "doctor": 5})
    assert roles[1] == "MAFIA" and roles[5] == "DOCTOR"
    assert list(roles.values()).count("MAFIA") == 2
    with pytest.raises(ValueError):
        mafia.assign_roles(5, random.Random(1), {"mafia": [1, 2]})
    with pytest.raises(ValueError):
        mafia.assign_roles(5, random.Random(1), {"mafia": [1], "doctor": 1})


def test_a_player_who_does_not_lean_in_is_dealt_again_then_the_deal_gives_up():
    t = play(FakeTable(5, no_lean={3}), max_rounds=1)
    assert lines.come_back(3) in t.said and t.said.index(lines.come_back(3)) < t.said.index(lines.lean_in(4))
    assert lines.CANT_DEAL in t.said
    assert lines.HEADS_DOWN not in t.said and t.state["over"] is True


def test_a_deal_that_cannot_finish_ends_on_its_own_line_without_the_ceremony():
    t = play(FakeTable(5, no_lean={3}), max_rounds=1)
    assert t.said[-1] == lines.CANT_DEAL
    assert lines.GOOD_GAME not in t.said and not set(lines.FLAVOR["win"]) & set(t.said)
    assert ("mood", "win") not in [(kind, value) for _, kind, value in t.log] and "quip" not in [kind for _, kind, _ in t.log]
    assert t.state["over"] is True and t.state["winner"] is None and t.state["phase"] == "over"


def test_d16_the_mafias_target_dies_when_the_doctor_saves_someone_else():
    t = play(night(FakeTable(5), "player four", "player two"), max_rounds=1)
    assert "Player four was killed in the night." in t.said
    assert t.said.index(lines.MORNING) < t.said.index(lines.killed(4))
    assert t.state["out"] == [4] and 4 not in t.state["living"]


def test_d17_the_doctor_saves_the_mafias_target():
    t = play(night(FakeTable(5), "player four", "player four"), max_rounds=1)
    assert "Nobody died last night." in t.said
    assert lines.killed(4) not in t.said
    morning = next(r for r in t.reports if r["phase"] == "morning")
    assert morning["living"] == [1, 2, 3, 4, 5] and morning["out"] == []


def test_the_night_checks_heads_three_times_and_whispers_are_asked_again_once():
    t = FakeTable(5)
    t.reply(lines.MAFIA_WHISPER, "")
    t.reply(lines.MAFIA_AGAIN, "four")
    t.reply(lines.DOCTOR_WHISPER, "two")
    play(t, max_rounds=1)
    assert [e for e in t.log if e[1] == "faces_up"].__len__() == 3
    assert t.said.count(lines.MAFIA_AGAIN) == 1
    assert lines.killed(4) in t.said


def test_d102_both_asks_are_said_every_night_whether_or_not_a_whisper_was_heard():
    t = play(night(FakeTable(5), "player four", "player two"), max_rounds=1)
    assert t.said.count(lines.MAFIA_AGAIN) == 1 and t.said.count(lines.DOCTOR_AGAIN) == 1
    assert lines.killed(4) in t.said  # the first valid whisper stands


def test_d102_the_first_valid_whisper_wins_over_the_second():
    t = FakeTable(5)
    t.reply(lines.MAFIA_WHISPER, "player four")
    t.reply(lines.MAFIA_AGAIN, "player three")
    t.reply(lines.DOCTOR_WHISPER, "player two")
    play(t, max_rounds=1)
    assert lines.killed(4) in t.said and lines.killed(3) not in t.said


def test_d102_the_doctor_is_asked_twice_on_the_night_after_dying():
    t = FakeTable(5)
    t.reply(lines.MAFIA_WHISPER, "player five", "")
    t.reply(lines.DOCTOR_WHISPER, "player two", "")
    votes(t, {1: "two", 2: "three", 3: "four", 4: "one"})
    play(t, max_rounds=2)
    assert t.state["out"][:1] == [5]
    assert t.said.count(lines.DOCTOR_AGAIN) == 2 and t.said.count(lines.MAFIA_AGAIN) == 2


def test_the_mafia_cannot_target_themselves():
    t = FakeTable(5)
    t.reply(lines.MAFIA_WHISPER, "player one")
    t.reply(lines.MAFIA_AGAIN, "player one")
    t.reply(lines.DOCTOR_WHISPER, "two")
    play(t, max_rounds=1)
    assert lines.NOBODY_DIED in t.said


def test_a_mafia_sitting_out_by_morning_kills_nobody_that_night():
    t = night(FakeTable(5), "player four", "player two").sweep([1], [1])
    play(t, max_rounds=1)
    assert lines.sit_out(1) in t.said
    assert lines.NOBODY_DIED in t.said and lines.killed(4) not in t.said
    assert t.said.index(lines.sit_out(1)) > t.said.index(lines.MAFIA_WHISPER)


def test_a_mafia_warned_once_still_kills():
    t = night(FakeTable(5), "player four", "player two").sweep([1])
    play(t, max_rounds=1)
    assert lines.warn(1) in t.said and lines.killed(4) in t.said


def test_a_doctor_sitting_out_saves_nobody():
    t = night(FakeTable(5), "player four", "player four").sweep([5], [5])
    play(t, max_rounds=1)
    assert lines.sit_out(5) in t.said
    assert lines.killed(4) in t.said


def test_sitting_out_lasts_until_the_next_round_begins():
    t = night(FakeTable(5), "player four", "player two").sweep([3], [3])
    t.reply(lines.MAFIA_WHISPER, "player two")
    play(t, max_rounds=2)
    first_vote = t.said.index(lines.TIME_VOTE)
    second_vote = t.said.index(lines.TIME_VOTE, first_vote + 1)
    assert lines.who(3) not in t.said[first_vote:second_vote]
    assert lines.who(3) in t.said[second_vote:]
    second_night = [r for r in t.reports if r["round"] == 2]
    assert second_night[0]["sitting_out"] == [] and second_night[0]["warnings"] == {}


def day_start(t: FakeTable) -> float:
    return t.said_at(lines.discussion(120))[0]


def test_d18_discussion_time_runs_by_the_clock():
    t = play(night(FakeTable(5), "player four", "player four"), max_rounds=1)
    start = day_start(t)
    assert t.said_at("One minute left.") == [start + 60]
    assert t.said_at("Time. Let's vote.") == [start + 120]


def test_d18_with_a_shorter_day_the_halfway_call_follows_it():
    t = play(night(FakeTable(5), "player four", "player four"), max_rounds=1, day_seconds=30)
    start = t.said_at(lines.discussion(30))[0]
    assert t.said_at("Fifteen seconds left.") == [start + 15]
    assert t.said_at(lines.TIME_VOTE) == [start + 30]


def test_the_group_can_vote_early():
    t = night(FakeTable(5), "player four", "player four")
    t.reply(lines.discussion(120), "okay we're ready, let's vote")
    play(t, max_rounds=1)
    assert lines.EARLY_VOTE in t.said and lines.TIME_VOTE not in t.said


def test_d92_an_early_vote_after_the_half_still_gets_the_halfway_call():
    t = night(FakeTable(5), "player four", "player four")
    t.reply(lines.time_left(60), "let's vote")
    play(t, max_rounds=1)
    start = day_start(t)
    assert t.said_at("One minute left.") == [start + 60]
    assert t.said_at(lines.EARLY_VOTE) == [start + 70]
    assert t.said.index("One minute left.") < t.said.index("Okay, let's vote.")
    assert lines.TIME_VOTE not in t.said


def test_d92_a_sentence_about_not_being_ready_does_not_end_the_day():
    t = night(FakeTable(5), "player four", "player four")
    t.reply(lines.discussion(120), "i'm not ready to vote")
    t.hear("we're ready to hear from player two")
    play(t, max_rounds=1)
    assert lines.EARLY_VOTE not in t.said and lines.TIME_VOTE in t.said


def test_d87_a_sentence_that_mentions_starting_over_is_talk():
    t = night(FakeTable(5), "player four", "player four")
    t.reply(lines.discussion(120), "i think we should start over with the accusations")
    play(t, max_rounds=1)
    assert lines.RESTARTING not in t.said and "One minute left." in t.said


def test_d88_restart_the_round_starts_the_night_again_with_nothing_undone():
    t = FakeTable(5)
    t.reply(lines.MAFIA_WHISPER, "player four", "player two")
    t.reply(lines.DOCTOR_WHISPER, "player three", "player three")
    t.reply(lines.discussion(120), "restart the round")
    t.sweep([3], [3])  # night one: three sits out
    votes(t, {1: "two", 2: "one", 3: "two", 5: "two"})
    outcome = games.play("mafia", t, random.Random(7), rig=RIG, options=Options(max_rounds=1))
    assert outcome == "played"
    assert "Okay, this round again." in t.said
    i = t.said.index(lines.ROUND_AGAIN)
    assert lines.HEADS_DOWN in t.said[i + 1 : i + 3]  # the night's flavor line may come between
    assert t.said.count(lines.HEADS_DOWN) == 2 and t.said.count(lines.discussion(120)) == 2
    assert lines.RESTARTING not in t.said and lines.STOPPING not in t.said
    assert t.state["out"] == [4, 2] and t.state["round"] == 1  # four stays dead; the roles are the same
    restarted = next(r for r in t.reports[t.reports.index(next(r for r in t.reports if r["out"] == [4])):] if r["phase"] == "night" and r["sitting_out"] == [])
    assert restarted["warnings"] == {}


def test_d18_the_eliminated_players_role_is_revealed():
    t = night(FakeTable(5), "player two", "player five")
    votes(t, {1: "four", 3: "four", 4: "one", 5: "four"})
    play(t, max_rounds=1)
    assert lines.voted_out(4) in t.said
    assert t.said[t.said.index(lines.voted_out(4)) + 1] == "Player four was a Villager."


def test_d19_the_village_wins_when_no_mafia_is_left():
    t = FakeTable(5)
    # Night one: two dies. Day one: three is voted out. Night two: the Doctor saves four.
    # Day two: one is voted out, the only Mafia.
    t.reply(lines.MAFIA_WHISPER, "player two", "player four")
    t.reply(lines.DOCTOR_WHISPER, "player five", "player four")
    votes(t, {1: "three", 3: "one", 4: "three", 5: "three"})
    t.reply(lines.who(1), "four")
    t.reply(lines.who(4), "one")
    t.reply(lines.who(5), "one")
    play(t)
    assert "Player one was the Mafia. The village wins." in t.said
    assert t.state["over"] is True and t.state["winner"] == "village"
    assert t.state["out"] == [2, 3, 1]


def test_d19_the_mafia_win_when_they_equal_the_rest():
    t = FakeTable(5)
    t.reply(lines.MAFIA_WHISPER, "player two", "player four")
    t.reply(lines.DOCTOR_WHISPER, "player five", "player five")
    votes(t, {1: "three", 3: "one", 4: "three", 5: "three"})
    play(t)
    assert t.state["living"] == [1, 5] and t.state["out"] == [2, 3, 4]
    assert "The Mafia win." in t.said
    assert t.said[t.said.index(lines.MAFIA_WIN) + 1] == "The Mafia was Player one."
    assert t.state["over"] is True and t.state["winner"] == "mafia"


def test_two_mafia_one_voted_out_the_game_goes_on():
    t = FakeTable(7)
    t.reply(lines.MAFIA_WHISPER, "player three")
    t.reply(lines.DOCTOR_WHISPER, "player five")
    votes(t, {s: "two" for s in (1, 2, 4, 5, 6, 7)})
    play(t, rig={"mafia": [1, 2], "doctor": 5}, max_rounds=1)
    assert lines.was(2, "MAFIA") in t.said
    assert lines.VILLAGE_WINS not in " ".join(t.said)
    assert t.state["winner"] is None  # the draw at max_rounds, not a win


def test_a_runaway_game_ends_in_a_draw():
    t = play(FakeTable(5), max_rounds=2)
    assert lines.DRAW in t.said and t.state["round"] == 2 and t.state["over"] is True
