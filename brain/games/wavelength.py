"""Wavelength (D21), after the table has been gathered.

Three rounds. Each round the psychic (rotating in seat order) leans in and sees a
target from one to ten on a spectrum ("7", "cold - hot"), gives a clue, and the group
talks it over and says a number. The round scores ten minus the distance ("Nine
points."); after the last round the host says the total ("Twenty-three points. Nice
work."). Cooperative: nobody wins or loses, so the winner stays None.

next_psychic in the report is who would lead the round after the current one, and
after the last round, the next game's first round.
"""

from __future__ import annotations

import random
from typing import Any

from brain import ears, lines
from brain.games.common import Options, State, abandon, finish, hear
from brain.table import Card, Table


def psychic_for(start: int, round_index: int, seats: int) -> int:
    """The psychic of round round_index (0-based), rotating in seat order from `start`."""
    return (start - 1 + round_index) % seats + 1


def plan_rounds(rng: random.Random, rig: dict[str, Any], rounds: int) -> list[dict[str, Any]]:
    """The rig's rounds, then random ones, every card distinct (spectra not repeated)."""
    planned = [{"spectrum": str(r["spectrum"]), "target": int(r["target"])} for r in rig.get("rounds", [])][:rounds]
    for r in planned:
        if not 1 <= r["target"] <= 10:
            raise ValueError(f"a Wavelength target is one to ten, not {r['target']}")
    spectra = [s for s in lines.SPECTRA if s not in {r["spectrum"] for r in planned}]
    rng.shuffle(spectra)
    while len(planned) < rounds:
        planned.append({"spectrum": spectra.pop(), "target": rng.randint(1, 10)})
    return planned


def score(target: int, guess: int) -> int:
    """D21: ten minus the distance."""
    return 10 - abs(target - guess)


def _guess(table: Table, options: Options) -> int | None:
    for i in range(options.guess_listens):
        guess = ears.number_said(hear(table, options.guess_seconds), 1, 10)
        if guess is not None:
            return guess
        if i == options.guess_listens // 2 - 1:
            table.say(lines.WAVELENGTH_AGAIN)
    return None


def run(table: Table, rng: random.Random, seats: int, rig: dict[str, Any], options: Options, state: State) -> None:
    start = int(rig.get("psychic") or 1)
    if not 1 <= start <= seats:
        raise ValueError(f"a rig that does not fit {seats} seats: {rig}")
    rounds = plan_rounds(rng, rig, options.wavelength_rounds)
    cards = [Card(str(r["target"]), r["spectrum"]) for r in rounds]
    table.prepare(list(dict.fromkeys(cards)))
    table.say(lines.WAVELENGTH_INTRO)
    table.say(lines.flavor("wavelength", rng))

    scores: list[int] = []
    for i, (r, card) in enumerate(zip(rounds, cards)):
        psychic = psychic_for(start, i, seats)
        state.round = i + 1
        state.phase = "deal"
        state.extra = {"psychic": psychic, "next_psychic": psychic_for(start, i + 1, seats), "scores": list(scores), "total": sum(scores)}
        state.report(table)
        table.say(lines.round_line(i + 1))
        if not table.show_private(psychic, card):
            table.say(lines.come_back(psychic))
            if not table.show_private(psychic, card):
                table.say(lines.CANT_DEAL)
                table.look(None)
                abandon(table, state)
                return

        state.phase = "clue"
        state.report(table)
        table.look(psychic)
        table.say(lines.psychic_clue(psychic))
        hear(table, options.clue_seconds)
        table.look(None)

        state.phase = "guess"
        state.report(table)
        table.say(lines.WAVELENGTH_TALK)
        guess = _guess(table, options)
        points = 0 if guess is None else score(r["target"], guess)
        table.say(lines.NO_GUESS if guess is None else lines.points(points))
        table.say(lines.target_was(r["target"]))
        scores.append(points)
        state.extra = {**state.extra, "scores": list(scores), "total": sum(scores)}
        state.report(table)

    table.say(lines.total(sum(scores)))
    finish(table, state, None, rng)
