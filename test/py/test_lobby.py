"""The lobby's naps (brain/lobby.py): after a game or once the talk is over the host
stops listening until a tap on the head or a typed line wakes it."""

import random

from fake_table import FakeTable

from brain import games, lines
from brain.lobby import Lobby


def _lobby(table, *, naps=1):
    """A lobby that stops once the host has taken `naps` nap calls."""
    return Lobby(
        table, random.Random(7), options=games.Options(), listen_window=4.0, recovery="Lost.",
        stopped=lambda: table.sleeps >= naps,
    )


def _played(monkeypatch, outcome="played", seats=0):
    played = []

    def play(name, table, rng, **kw):
        played.append(name)
        kw["state"].seats = seats
        return outcome

    monkeypatch.setattr(games, "play", play)
    return played


def _kinds(table):
    return [kind for _, kind, _ in table.log]


def test_after_a_game_the_host_says_it_naps_and_stops_listening(monkeypatch):
    played = _played(monkeypatch)
    table = FakeTable().hear("let's play imposter")
    _lobby(table).run()
    assert played == ["imposter"]
    assert table.said == [lines.NAP]
    assert _kinds(table)[-1] == "sleep"


def test_a_tap_wakes_it_to_say_it_is_up_and_ask_with_no_sweep(monkeypatch):
    _played(monkeypatch)
    table = FakeTable().hear("let's play imposter")
    table.wakes.extend(["", None])
    _lobby(table, naps=2).run()
    woke = table.said.index(next(line for line in table.said if line in lines.WOKE))
    assert table.said[woke - 1] == lines.NAP
    assert "count" not in _kinds(table)


def test_a_nap_call_that_runs_out_naps_again_without_a_word(monkeypatch):
    _played(monkeypatch)
    table = FakeTable().hear("let's play imposter")
    table.wakes.extend([None, None])
    _lobby(table, naps=3).run()
    assert table.said == [lines.NAP]
    assert _kinds(table).count("listen") == 1


def test_a_game_typed_while_napping_starts_it_even_after_lets_go(monkeypatch):
    played = _played(monkeypatch)
    table = FakeTable().hear("let's play imposter")
    table.wakes.append("let's go play wavelength")
    _lobby(table, naps=2).run()
    assert played == ["imposter", "wavelength"]


def test_a_rules_question_typed_while_napping_gets_the_rules_not_the_game(monkeypatch):
    played = _played(monkeypatch)
    table = FakeTable().hear("let's play imposter")
    table.wakes.append("how do you play mafia")
    _lobby(table, naps=2).run()
    assert played == ["imposter"]
    assert lines.rules("mafia") in table.said


def test_shut_up_in_the_talk_gets_a_line_and_a_nap():
    table = FakeTable().hear("shut up")
    _lobby(table).run(welcome=True)
    assert table.said[-1] in lines.LATER
    assert _kinds(table)[-1] == "sleep"


def test_too_few_for_a_game_named_outside_the_talk_offers_one_that_fits(monkeypatch):
    _played(monkeypatch, outcome="too few", seats=3)
    table = FakeTable(seats=3).hear("let's play mafia")
    _lobby(table).run()
    assert lines.NAP not in table.said[:1]
    assert any("Imposter" in line for line in table.said)


def test_a_referee_picking_up_a_table_naps_first():
    table = FakeTable()
    _lobby(table).run(nap=True)
    assert _kinds(table) == ["sleep"]
