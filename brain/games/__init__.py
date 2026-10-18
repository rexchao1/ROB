"""The games: one entry point, play(), that runs a whole game on a Table and returns,
and the host goes back to listening for the next one.

play() gathers the table first (count, the count line, agreement on the count; D5,
D6), then runs the game. The group can stop at any listen by saying so ("stop the
game"; D27), or start over ("reset", "start over", "restart"), which ends the game
and sends the host back to the welcome (D38). It returns how the game went:

  "played"    the game ran to its end (a deal that could not finish included)
  "stopped"   the group stopped it
  "reset"     the group asked to start over: the welcome comes next
  "too few"   not enough players for this game (the host said so)
  "no count"  the host and the group never agreed on the count

A rig fixes the random choices, for the tests and the demo; anything it leaves out
comes from the rng:

  mafia       {"mafia": [1], "doctor": 5}
  imposter    {"word": "beach", "imposter": 3}
  wavelength  {"psychic": 2, "rounds": [{"spectrum": "cold - hot", "target": 7}, ...]}

The state each game reports (Table.report, served at GET /test/state):

  game         "mafia" | "imposter" | "wavelength", or None until the count is agreed
               (D6: "no game has started")
  phase        "count", "deal", "night", "morning", "day", "vote", "clues", "clue",
               "guess", "over"
  seats        how many seats the last count found
  living       seats still in, ascending (everyone, in Imposter and Wavelength)
  out          seats out, in the order they went out (Mafia)
  warnings     {"3": 1}: heads-down warnings by seat, this night only (D9, D11)
  sitting_out  seats sitting out until the next round begins (D11)
  round        the round number, from 1 (0 before the first)
  over         True once the game has ended
  winner       "mafia" | "village" | "players" | "imposter", or None (no winner, or
               Wavelength, or a stopped game)
  psychic, next_psychic, scores, total    Wavelength only
"""

from __future__ import annotations

import random
from typing import Any

from brain import lines
from brain.games import imposter, mafia, wavelength
from brain.games.common import GameStopped, Options, State, gather
from brain.table import Table

GAMES = ("mafia", "imposter", "wavelength")
_RUN = {"mafia": mafia.run, "imposter": imposter.run, "wavelength": wavelength.run}
from brain.games import hotseat  # noqa: E402  (Workstream X)
GAMES += ("hotseat",)
_RUN["hotseat"] = hotseat.run
from brain.games import wordle  # noqa: E402  (Workstream X)
GAMES += ("wordle",)
_RUN["wordle"] = wordle.run
from brain.games import twenty  # noqa: E402  (Workstream X)
GAMES += ("twenty",)
_RUN["twenty"] = twenty.run

__all__ = ["GAMES", "Options", "play"]


def play(
    name: str,
    table: Table,
    rng: random.Random,
    heard: str = "",
    rig: dict[str, Any] | None = None,
    options: Options | None = None,
    counted: int | None = None,
) -> str:
    """Run one whole game of `name` (one of GAMES) and say how it went (above). `heard`
    is what started it ("let's play mafia, there are six of us"), for a count said along
    with it; `counted`, the welcome's count when it has just counted the table."""
    if name not in GAMES:
        raise ValueError(f"no game named {name!r}; the games are {GAMES}")
    options = options or Options()
    state = State()
    outcome = "played"
    try:
        seats = gather(table, name, heard, state, options, counted)
        if seats is None:
            outcome = state.stalled or "no count"
        else:
            _RUN[name](table, rng, seats, rig or {}, options, state)
    except GameStopped as stop:
        table.look(None)
        table.say(lines.RESTARTING if stop.reset else lines.STOPPING)
        state.over = True
        state.phase = "over"
        state.report(table)
        outcome = "reset" if stop.reset else "stopped"
    table.mood("idle")
    return outcome
