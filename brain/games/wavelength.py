"""Wavelength (D21, reworked by D117), after the table has been gathered.

Three rounds. Each round one player is the guesser (rotating in seat order) and
everyone else leans in, one at a time, and sees the secret number from one to ten on
the private screen. Then the guesser goes round the table: for each player who saw the
number, the guesser names a category ("animals", "movies") and that player names
something in it whose size, strength or worth is about the number (one the least, ten
the most). Then the guesser says the number. The round scores ten minus the distance
("Nine points."); after the last round the host says the total ("Twenty-three points.
Nice work."). Cooperative: nobody wins or loses, so the winner stays None.

The host does not judge the categories or the answers; it gives each one its listen,
prompts the next player, and only reads the guesser's number.

next_guesser in the report is who would guess in the round after the current one, and
after the last round, the next game's first round.

Each round's number card goes up again, for everyone, as the host says what it was.
The total is known only once the last guess is in, so its card is prepared then (with
that round's number, still to be revealed): the upload runs while the host says the
round's points, and the number's reveal waits only for what is left of it.
"""

from __future__ import annotations

import random
from typing import Any

from brain import ears, lines
from brain.games.common import Options, State, abandon, decided, finish, hear
from brain.table import Card, Table

SCALE = "out of ten"  # the small line under the number on the private screen


def guesser_for(start: int, round_index: int, seats: int) -> int:
    """The guesser of round round_index (0-based), rotating in seat order from `start`."""
    return (start - 1 + round_index) % seats + 1


def plan_rounds(rng: random.Random, rig: dict[str, Any], rounds: int) -> list[dict[str, Any]]:
    """The rig's rounds' numbers, then random ones."""
    planned = [{"target": int(r["target"])} for r in rig.get("rounds", [])][:rounds]
    for r in planned:
        if not 1 <= r["target"] <= 10:
            raise ValueError(f"a Wavelength number is one to ten, not {r['target']}")
    while len(planned) < rounds:
        planned.append({"target": rng.randint(1, 10)})
    return planned


def number_card(target: int) -> Card:
    return Card(str(target), SCALE, "target")


def total_card(points: int) -> Card:
    return Card(str(points), "points" if points != 1 else "point", "score")


def score(target: int, guess: int) -> int:
    """D21: ten minus the distance."""
    return 10 - abs(target - guess)


def knowers(guesser: int, seats: int) -> list[int]:
    """Everyone but the guesser, in seat order from the guesser's left."""
    return [guesser_for(guesser, i, seats) for i in range(1, seats)]


def _guess(table: Table, options: Options) -> int | None:
    for i in range(options.guess_listens):
        guess = ears.number_said(hear(table, options.guess_seconds), 1, 10)
        if guess is not None:
            return guess
        if i == options.guess_listens // 2 - 1:
            table.say(lines.WAVELENGTH_AGAIN)
    return None


def _deal(table: Table, guesser: int, seats: int, card: Card) -> list[int]:
    """The number to everyone but the guesser; a player who does not lean in is called
    again after the others. Those who saw it."""
    seen, missed = [], []
    for seat in knowers(guesser, seats):
        if table.show_private(seat, card):
            seen.append(seat)
        else:
            table.say(lines.come_back(seat))
            missed.append(seat)
    for seat in missed:
        if table.show_private(seat, card):
            seen.append(seat)
    return sorted(seen, key=knowers(guesser, seats).index)


def run(table: Table, rng: random.Random, seats: int, rig: dict[str, Any], options: Options, state: State) -> None:
    start = int(rig.get("guesser") or rig.get("psychic") or 1)
    if not 1 <= start <= seats:
        raise ValueError(f"a rig that does not fit {seats} seats: {rig}")
    rounds = plan_rounds(rng, rig, options.wavelength_rounds)
    cards = [number_card(r["target"]) for r in rounds]
    table.prepare(list(dict.fromkeys(cards)))
    table.say(lines.WAVELENGTH_INTRO)
    table.say(lines.flavor("wavelength", rng))

    scores: list[int] = []
    for i, (r, card) in enumerate(zip(rounds, cards)):
        guesser = guesser_for(start, i, seats)
        state.round = i + 1
        state.phase = "deal"
        state.extra = {"guesser": guesser, "next_guesser": guesser_for(start, i + 1, seats), "scores": list(scores), "total": sum(scores)}
        state.report(table)
        table.say(lines.round_line(i + 1))
        table.look(guesser)
        table.say(lines.guesser_turn(guesser))
        seen = _deal(table, guesser, seats, card)
        if not seen:
            table.say(lines.CANT_DEAL)
            table.look(None)
            abandon(table, state)
            return

        state.phase = "clue"
        state.report(table)
        for seat in seen:
            table.look(guesser)
            table.say(lines.ask_category(guesser, seat))
            hear(table, options.clue_seconds)
            table.look(seat)
            table.say(lines.category_answer(seat))
            hear(table, options.clue_seconds)

        state.phase = "guess"
        state.report(table)
        table.look(guesser)
        table.say(lines.guesser_number(guesser))
        guess = _guess(table, options)
        table.look(None)
        points = 0 if guess is None else score(r["target"], guess)
        scores.append(points)
        if i == len(rounds) - 1:
            table.prepare([card, total_card(sum(scores))])
        table.say(lines.NO_GUESS if guess is None else lines.points(points))
        table.reveal(card, lines.target_was(r["target"]))
        state.extra = {**state.extra, "scores": list(scores), "total": sum(scores)}
        state.report(table)

    decided(table, state, None)
    table.reveal(total_card(sum(scores)), lines.total(sum(scores)))
    finish(table, state, None, rng)
