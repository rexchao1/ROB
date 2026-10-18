"""Imposter (D20), after the table has been gathered.

Everyone sees the same word on the private screen except one player, who sees
IMPOSTER. Then one clue each in seat order, the host turning to each player and
addressing each exactly once (no second ask: a missed clue is just missed), a vote,
and the reveal: "Player three was the Imposter." when they are voted out, otherwise
"The Imposter survives. It was Player three." (a tie or no majority included).

Both endings and the word are known before the deal, so their reveal cards go up with
the words in the one set the game prepares: the screen shows the Imposter's seat as
the host names them, then the word.
"""

from __future__ import annotations

import random
from typing import Any

from brain import lines
from brain.games.common import Options, State, abandon, deal, decided, finish, hear, vote
from brain.table import Card, Table


def run(table: Table, rng: random.Random, seats: int, rig: dict[str, Any], options: Options, state: State) -> None:
    word = str(rig.get("word") or rng.choice(lines.IMPOSTER_WORDS))
    imposter = int(rig.get("imposter") or rng.randint(1, seats))
    if not 1 <= imposter <= seats or word.upper() == lines.IMPOSTER:
        raise ValueError(f"a rig that does not fit {seats} seats: {rig}")
    caught = Card(f"PLAYER {imposter}", "was the Imposter", "out")
    survived = Card(f"PLAYER {imposter}", "Imposter survives", "win")
    the_word = Card(word, "was the word", "word")
    table.prepare([Card(word), Card(lines.IMPOSTER), caught, survived, the_word])
    table.say(lines.IMPOSTER_INTRO)
    table.say(lines.DEAL_WORDS)
    table.say(lines.flavor("imposter", rng))
    cards = {s: Card(lines.IMPOSTER) if s == imposter else Card(word) for s in range(1, seats + 1)}
    if not deal(table, cards, state):
        abandon(table, state)
        return

    state.phase = "clues"
    state.report(table)
    table.say(lines.CLUES)
    for seat in range(1, seats + 1):
        table.look(seat)
        table.say(lines.clue(seat))
        hear(table, options.clue_seconds)
    table.look(None)

    table.say(lines.IMPOSTER_VOTE)
    out = vote(table, state, options, rng)
    winner = "players" if out == imposter else "imposter"
    decided(table, state, winner)
    if out == imposter:
        table.reveal(caught, lines.was_imposter(imposter))
    else:
        table.reveal(survived, lines.imposter_survives(imposter))
    table.reveal(the_word, lines.word_was(word))
    finish(table, state, winner, rng)
