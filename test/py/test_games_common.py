"""The hosting rules every game shares, on a fake table: gathering (D5, D6), heads
down (D9 to D11), votes by voice (D12, D13)."""

import random

import pytest
from fake_table import FakeTable

from brain import games, lines
from brain.games.common import GameStopped, Options, State, gather, heads_down_check, vote


def started(seats: int, living: list[int] | None = None) -> State:
    s = State(game="mafia", phase="night", seats=seats, living=list(living or range(1, seats + 1)))
    return s


# --- D5, D6 --------------------------------------------------------------------------


def test_d5_the_host_counts_the_table_and_numbers_the_seats():
    t = FakeTable(5)
    n = gather(t, "mafia", "let's play mafia", State(), Options())
    assert n == 5
    assert t.said[0] == "Five of you. Player one is on my left, then two, three, four, five going clockwise."
    assert t.state["game"] == "mafia" and t.state["living"] == [1, 2, 3, 4, 5]


def test_d6_a_spoken_count_that_disagrees_stops_the_start():
    t = FakeTable(5)
    t.reply(lines.count_line(5), "there are six of us")
    state = State()
    n = gather(t, "mafia", "", state, Options())
    assert n is None
    assert t.said[:2] == [lines.count_line(5), "I only see five. Who's hiding?"]
    assert [e[2] for e in t.log if e[1] == "count"][:2] == [5, 5]  # the mismatch line, then a second sweep
    assert all(r["game"] is None for r in t.reports)  # no game has started, ever
    assert not any(line.startswith("Let's play") for line in t.said)


def test_d89_a_disagreement_without_a_number_gets_a_second_sweep_not_a_start():
    t = FakeTable(5)
    t.reply(lines.count_line(5), "there are six of us")
    t.reply(lines.only_see(5), "no, that's not right")
    state = State()
    assert gather(t, "mafia", "", state, Options()) is None
    counts = [e[2] for e in t.log if e[1] == "count"]
    assert len(counts) >= 2 and t.said.count(lines.only_see(5)) >= 2
    assert all(r["game"] is None for r in t.reports)


def test_d89_silence_after_the_mismatch_line_is_not_agreement():
    t = FakeTable(5)
    t.reply(lines.count_line(5), "there are six of us")
    t.reply(lines.only_see(5), "")
    state = State()
    assert gather(t, "mafia", "", state, Options()) is None
    assert len([e for e in t.log if e[1] == "count"]) >= 2
    assert t.said[-1] == lines.COUNT_GIVE_UP and state.stalled == "no count"


def test_d89_after_three_disagreements_the_host_gives_up():
    t = FakeTable(5)
    t.reply(lines.count_line(5), "there are six of us")
    t.reply(lines.only_see(5), "there are six of us", "there are six of us", "there are six of us")
    state = State()
    assert gather(t, "mafia", "", state, Options()) is None
    assert t.said.count(lines.only_see(5)) == 2  # D89: the third disagreement is the give-up
    assert t.said[-1] == "Let's try again when everyone's ready."
    assert all(r["game"] is None for r in t.reports)


def test_d90_a_count_below_the_hosts_gets_the_watching_line_and_a_second_sweep():
    t = FakeTable(counts=[5, 4])
    t.reply(lines.count_line(5), "we're four")
    n = gather(t, "mafia", "", State(), Options())
    assert t.said[:3] == [lines.count_line(5), "I see five. Is someone just watching?", lines.count_line(4)]
    assert n == 4


def test_d6_said_with_the_request_and_resolved_by_a_recount():
    t = FakeTable(counts=[5, 6])
    n = gather(t, "mafia", "let's play mafia, there are six of us", State(), Options())
    assert n == 6
    assert t.said[:3] == [lines.count_line(5), lines.only_see(5), lines.count_line(6)]
    assert t.state["game"] == "mafia" and t.state["seats"] == 6


def test_d6_the_group_can_accept_the_hosts_count():
    t = FakeTable(5)
    t.reply(lines.count_line(5), "there are six of us")
    t.reply(lines.only_see(5), "okay fine")
    assert gather(t, "mafia", "", State(), Options()) == 5


def test_d6_the_group_can_correct_itself_with_the_hosts_number():
    t = FakeTable(5)
    t.reply(lines.count_line(5), "there are six of us")
    t.reply(lines.only_see(5), "five")
    assert gather(t, "mafia", "", State(), Options()) == 5


def test_too_few_players_says_so_and_starts_nothing():
    t = FakeTable(3)
    assert gather(t, "mafia", "", State(), Options()) is None
    assert t.said[-2:] == ["Mafia needs at least four players.", "Want to try Imposter instead?"]  # D98
    assert t.state["game"] is None


def test_play_with_too_few_returns_to_idle():
    t = FakeTable(1)
    games.play("wavelength", t, random.Random(0))
    assert t.said[-2:] == ["Wavelength needs at least two players.", "Want to try Twenty Questions instead?"]  # D98
    assert t.log[-1][1:] == ("mood", "idle")


def test_stopping_the_game_mid_count():
    t = FakeTable(5)
    t.reply(lines.count_line(5), "stop the game")
    games.play("mafia", t, random.Random(0))
    assert t.said[-1] == lines.STOPPING and t.state["over"] is True


def test_play_refuses_an_unknown_game():
    with pytest.raises(ValueError):
        games.play("poker", FakeTable(5), random.Random(0))


# --- D9, D10, D11 ----------------------------------------------------------------------


def test_d9_a_face_up_during_heads_down_is_warned_by_seat():
    t = FakeTable(5).sweep([3])
    state = started(5)
    heads_down_check(t, state)
    assert t.said == ["Player three, heads down means heads DOWN."]
    assert t.state["warnings"] == {"3": 1}


def test_d10_every_head_down_means_no_warning():
    t = FakeTable(5).sweep([])
    state = started(5)
    heads_down_check(t, state)
    assert not any(line.startswith("Player") for line in t.said)
    assert state.warnings == {} and state.snapshot()["warnings"] == {}


def test_d11_a_second_peek_in_the_same_night_sits_the_player_out():
    t = FakeTable(5).sweep([3], [3])
    state = started(5)
    heads_down_check(t, state)
    heads_down_check(t, state)
    assert t.said == [lines.warn(3), "Player three, you're sitting this round out."]
    assert t.state["sitting_out"] == [3]


def test_heads_down_names_neither_the_dead_nor_those_already_sitting_out():
    t = FakeTable(5).sweep([2, 3])
    state = started(5, living=[1, 3, 4, 5])
    state.sitting_out = {3}
    heads_down_check(t, state)
    assert t.said == []


def test_two_faces_up_in_one_sweep_are_both_warned():
    t = FakeTable(5).sweep([4, 2])
    heads_down_check(t, started(5))
    assert t.said == [lines.warn(2), lines.warn(4)]


# --- D12, D13 ------------------------------------------------------------------------------


def voters(t: FakeTable, answers: dict[int, str]) -> None:
    for seat, answer in answers.items():
        t.reply(lines.who(seat), answer)


def test_d12_a_majority_vote_by_voice_eliminates_a_seat():
    t = FakeTable(5)
    voters(t, {1: "four", 2: "four", 3: "four", 4: "one", 5: "one"})
    out = vote(t, started(5), Options(), random.Random(0))
    assert out == 4
    assert [line for line in t.said if line.endswith("who?")] == [lines.who(s) for s in range(1, 6)]
    assert [t.log[i - 1][2] for i, e in enumerate(t.log) if e[1] == "say" and e[2].endswith("who?")] == [1, 2, 3, 4, 5]
    i = t.said.index("Three for Player four, two for Player one.")
    assert t.said[i + 1] == "Player four, you're out."


def test_d13_a_tied_vote_eliminates_nobody():
    t = FakeTable(4)
    voters(t, {1: "two", 2: "four", 3: "two", 4: "four"})
    state = started(4)
    out = vote(t, state, Options(), random.Random(0))
    assert out is None
    assert "Two for Player two, two for Player four. It's a tie. Nobody leaves." in t.said
    assert not any(line.endswith("you're out.") for line in t.said)
    assert state.living == [1, 2, 3, 4]


def test_a_top_seat_short_of_a_majority_eliminates_nobody():
    t = FakeTable(5)
    voters(t, {1: "two", 2: "three", 3: "two", 4: "four", 5: "five"})
    assert vote(t, started(5), Options(), random.Random(0)) is None
    assert lines.no_majority([(2, 2), (3, 1), (4, 1), (5, 1)]) in t.said


def test_d97_exactly_half_is_no_majority():
    t = FakeTable(4)
    voters(t, {1: "four", 2: "four", 3: "one", 4: "two"})
    state = started(4)
    assert vote(t, state, Options(), random.Random(0)) is None
    assert "Two for Player four, one for Player one, one for Player two. Nobody has a majority. Nobody leaves." in t.said
    assert state.living == [1, 2, 3, 4]


def test_d97_a_plurality_of_four_eliminates_nobody():
    t = FakeTable(4)
    voters(t, {1: "four", 2: "four", 3: "one", 4: "two"})
    assert vote(t, started(4), Options(), random.Random(0)) is None
    assert not any(line.endswith("you're out.") for line in t.said)


def test_d97_players_sitting_out_do_not_count_toward_the_majority():
    t = FakeTable(5)
    voters(t, {1: "three", 2: "three", 3: "one"})
    state = started(5)
    state.sitting_out = {4, 5}
    assert vote(t, state, Options(), random.Random(0)) == 3
    assert lines.who(4) not in t.said and lines.who(5) not in t.said
    i = t.said.index("Two for Player three, one for Player one.")
    assert t.said[i + 1] == "Player three, you're out."


def test_an_unheard_vote_is_asked_for_again_once():
    t = FakeTable(5)
    voters(t, {1: "", 2: "four", 3: "four", 4: "one", 5: "four"})
    t.reply(lines.who_again(1), "four")
    assert vote(t, started(5), Options(), random.Random(0)) == 4
    assert t.said.count(lines.who_again(1)) == 1
    assert lines.tally([(4, 4), (1, 1)]) in t.said


def test_a_vote_still_unheard_after_asking_again_counts_for_nobody():
    t = FakeTable(5)
    voters(t, {1: "mumble", 2: "four", 3: "four", 4: "one", 5: "four"})
    assert vote(t, started(5), Options(), random.Random(0)) == 4
    assert t.said.count(lines.who_again(1)) == 1
    assert lines.tally([(4, 3), (1, 1)]) in t.said


def test_a_seat_that_does_not_exist_or_is_out_is_asked_again():
    t = FakeTable(5)
    voters(t, {1: "player nine", 3: "player two", 4: "one", 5: "one"})
    t.reply(lines.who_again(1), "one")
    t.reply(lines.PICK_LIVING, "four")
    state = started(5, living=[1, 3, 4, 5])
    vote(t, state, Options(), random.Random(0))
    assert lines.who_again(1) in t.said  # nine is no seat at five: unheard
    assert lines.PICK_LIVING in t.said  # two is out
    assert lines.tally([(1, 3), (4, 1)]) in t.said


def test_players_sitting_out_do_not_vote():
    t = FakeTable(5)
    voters(t, {1: "four", 2: "four", 4: "one", 5: "four"})
    state = started(5)
    state.sitting_out = {3}
    assert vote(t, state, Options(), random.Random(0)) == 4
    assert lines.who(3) not in t.said


def test_d88_a_round_restart_in_another_game_is_a_plain_stop():
    t = FakeTable(5)
    t.reply(lines.count_line(5), "restart the round")
    assert games.play("imposter", t, random.Random(0)) == "stopped"
    assert t.said[-1] == lines.STOPPING


def test_a_stop_heard_during_a_vote_ends_the_game():
    t = FakeTable(5)
    voters(t, {1: "let's stop the game"})
    with pytest.raises(GameStopped):
        vote(t, started(5), Options(), random.Random(0))
