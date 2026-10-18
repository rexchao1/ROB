"""Mafia (D15 to D19), after the table has been gathered.

Roles: one Mafia and one Doctor with four to six players, two Mafia with seven or more,
the rest Villagers (D15), dealt through the private screen in seat order. Then rounds,
each a night and a day:

- Night: heads down, a heads-down check, the Mafia whisper a target, a check, the Doctor
  whispers a save, a check. Every whisper is called even when the role is dead or sitting
  out, so the calls give nothing away. The night resolves at morning: the target dies
  unless the Doctor saved them (D16, D17), and a role that is dead or sitting out by then
  (all the Mafia, or the Doctor) has no effect, whatever it whispered.
- Day: a timed discussion with the halfway call (D18), the vote (D12, D13), the role of
  whoever went out revealed.

After every elimination the win check (D19): no Mafia left, the village wins; the Mafia
as many as everyone else, the Mafia win. A new round clears the night's warnings and
lets the players who sat out back in (D11).

The big moments show on the host's screen while it says them (Table.reveal): the
night's kill or "nobody died", the role of whoever is voted out, and the win. The
role cards are needed only for the deal, so the screen's five slots then go to the
reveals, prepared while the host is still talking: the night's set as soon as the
whispers are in (the target is known; a Doctor or Mafia sitting out can only turn a
save into a kill or a kill into nobody, both in the set), the day's set as the day
begins (every role a vote can reveal, and both wins).
"""

from __future__ import annotations

import random
from typing import Any

from brain import ears, lines
from brain.games.common import Options, State, abandon, deal, decided, finish, hear, heads_down_check, vote, whisper
from brain.table import Card, Table

MAFIA, DOCTOR, VILLAGER = lines.MAFIA, lines.DOCTOR, lines.VILLAGER


# The reveals (Table.reveal), by what they mean.
MAFIA_WINS_CARD = Card("MAFIA", "win", "win")
VILLAGE_WINS_CARD = Card("VILLAGE", "wins", "win")
NOBODY_DIED_CARD = Card("NOBODY", "died last night", "safe")


def killed_card(seat: int) -> Card:
    return Card(f"PLAYER {seat}", "killed in the night", "out")


def out_card(role: str) -> Card:
    """The role of whoever the vote put out."""
    return Card(role, "voted out", "out")


DAY_CARDS = [out_card(MAFIA), out_card(DOCTOR), out_card(VILLAGER), VILLAGE_WINS_CARD, MAFIA_WINS_CARD]


def mafia_count(seats: int) -> int:
    """D15: one Mafia up to six players, two from seven."""
    return 2 if seats >= 7 else 1


def assign_roles(seats: int, rng: random.Random, rig: dict[str, Any]) -> dict[int, str]:
    """Seat -> role. A rig fixes some of it ({"mafia": [1], "doctor": 5}); rng the rest."""
    want = mafia_count(seats)
    mafia = [int(s) for s in rig.get("mafia", [])]
    doctor = rig.get("doctor")
    named = mafia + ([int(doctor)] if doctor is not None else [])
    if any(not 1 <= s <= seats for s in named) or len(set(named)) != len(named) or len(mafia) > want:
        raise ValueError(f"a rig that does not fit {seats} seats: {rig}")
    free = [s for s in range(1, seats + 1) if s not in named]
    rng.shuffle(free)
    while len(mafia) < want:
        mafia.append(free.pop())
    if doctor is None:
        doctor = free.pop()
    roles = {s: VILLAGER for s in range(1, seats + 1)}
    for s in mafia:
        roles[s] = MAFIA
    roles[int(doctor)] = DOCTOR
    return roles


def run(table: Table, rng: random.Random, seats: int, rig: dict[str, Any], options: Options, state: State) -> None:
    roles = assign_roles(seats, rng, rig)
    table.prepare([Card(MAFIA), Card(DOCTOR), Card(VILLAGER)])
    table.say(lines.mafia_intro(mafia_count(seats)))
    table.say(lines.DEAL_ROLES)
    table.say(lines.flavor("deal", rng))
    if not deal(table, {s: Card(r) for s, r in roles.items()}, state):
        abandon(table, state)
        return
    while True:
        if state.round >= options.max_rounds:
            table.say(lines.DRAW)
            finish(table, state, None, rng)
            return
        state.round += 1
        state.warnings.clear()
        state.sitting_out.clear()
        if _night(table, rng, roles, state, options):
            return
        if _day(table, rng, roles, state, options):
            return


def _awake(roles: dict[int, str], role: str, state: State) -> bool:
    return any(r == role and s in state.living and s not in state.sitting_out for s, r in roles.items())


def _night(table: Table, rng: random.Random, roles: dict[int, str], state: State, options: Options) -> bool:
    """One night; True when the game ended."""
    state.phase = "night"
    state.report(table)
    table.mood("night")
    table.say(lines.flavor("night", rng))
    table.say(lines.HEADS_DOWN)
    table.wait(options.settle_seconds)
    heads_down_check(table, state)

    target = whisper(
        table, lines.MAFIA_WHISPER, lines.MAFIA_AGAIN, state.seats,
        lambda s: s in state.living and roles[s] != MAFIA, options,
    )
    table.say(lines.MAFIA_DOWN)
    table.wait(options.settle_seconds)
    heads_down_check(table, state)

    save = whisper(table, lines.DOCTOR_WHISPER, lines.DOCTOR_AGAIN, state.seats, lambda s: s in state.living, options)
    # The morning's reveals, uploaded while the night finishes: the target as whispered
    # (a role sitting out by morning can only make it nobody), nobody, and a Mafia win.
    table.prepare(([killed_card(target)] if target is not None else []) + [NOBODY_DIED_CARD, MAFIA_WINS_CARD])
    table.say(lines.DOCTOR_DOWN)
    table.wait(options.settle_seconds)
    heads_down_check(table, state)

    # The night resolves at morning: a role sitting out by then (D11, "the rest of this
    # round") or dead has no effect, whatever it whispered.
    if not _awake(roles, MAFIA, state):
        target = None
    if not _awake(roles, DOCTOR, state):
        save = None

    state.phase = "morning"
    table.mood("day")
    table.say(lines.MORNING)
    if target is not None and target != save:
        state.eliminate(target)
        state.report(table)
        table.reveal(killed_card(target), lines.killed(target))
        table.say(lines.flavor("death", rng))
        table.quip("death", game="mafia")
        return _mafia_win(table, rng, roles, state)
    state.report(table)
    table.reveal(NOBODY_DIED_CARD, lines.NOBODY_DIED)
    table.say(lines.flavor("saved", rng))
    table.quip("saved", game="mafia")
    return False


def _mafia_win(table: Table, rng: random.Random, roles: dict[int, str], state: State) -> bool:
    """D19, the Mafia's half: as many Mafia as everyone else still in."""
    mafia_left = [s for s in state.living if roles[s] == MAFIA]
    if mafia_left and len(mafia_left) >= len(state.living) - len(mafia_left):
        decided(table, state, "mafia")
        table.reveal(MAFIA_WINS_CARD, lines.MAFIA_WIN)
        table.say(lines.mafia_were(sorted(s for s, r in roles.items() if r == MAFIA)))
        finish(table, state, "mafia", rng)
        return True
    return False


def _discuss(table: Table, options: Options) -> None:
    """D18: the day's discussion on the table's clock, the halfway call at half time,
    then "Time. Let's vote."; heard in pieces so the group can vote early."""
    start = table.now()
    half, end = start + options.day_seconds / 2, start + options.day_seconds
    called = False
    while True:
        now = table.now()
        if not called and now >= half - 1e-6:
            table.say(lines.time_left(options.day_seconds / 2))
            called = True
        if now >= end - 1e-6:
            table.say(lines.TIME_VOTE)
            return
        mark = end if called else half
        if ears.wants_to_vote(hear(table, max(0.1, min(options.talk_chunk_seconds, mark - now)))):
            table.say(lines.EARLY_VOTE)
            return


def _day(table: Table, rng: random.Random, roles: dict[int, str], state: State, options: Options) -> bool:
    """One day; True when the game ended."""
    state.phase = "day"
    state.report(table)
    table.prepare(DAY_CARDS)  # uploaded during the discussion
    table.say(lines.discussion(options.day_seconds))
    _discuss(table, options)
    out = vote(table, state, options, rng)
    if out is None:
        state.phase = "day"
        state.report(table)
        return False
    role = roles[out]
    state.eliminate(out)
    state.report(table)
    if role == MAFIA and not any(roles[s] == MAFIA for s in state.living):
        decided(table, state, "village")
        table.reveal(VILLAGE_WINS_CARD, lines.village_wins(out))  # D19: "Player one was the Mafia. The village wins."
        finish(table, state, "village", rng)
        return True
    table.reveal(out_card(role), lines.was(out, role))
    table.quip("out", game="mafia")
    return _mafia_win(table, rng, roles, state)
