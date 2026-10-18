"""The hosting rules every game shares: gathering the table (D5, D6), dealing
through the private screen in seat order (D7, D15), the heads-down watch (D9 to D11),
votes by voice (D12, D13), and the state the host reports (brain/games/__init__.py
lists its keys).

Everything here acts through the Table and decides in code; what was heard only
ever arrives as a parsed seat or number (brain/ears.py), and a vote or a whisper the
host cannot make out is asked for once more, never guessed (OUT-OF-SCOPE.md).
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

from brain import ears, lines
from brain.table import Card, Table


class GameStopped(Exception):
    """The group asked to stop or restart (D27); the game ends where it is. reset: they
    said "reset", "start over" or "restart", and the welcome comes next (D38)."""

    def __init__(self, reset: bool = False) -> None:
        super().__init__("reset" if reset else "stop")
        self.reset = reset


@dataclass
class Options:
    """Timings and limits. Seconds are on the table's clock."""

    day_seconds: float = 120.0  # D18: the day's discussion; the halfway call comes at half
    settle_seconds: float = 3.0  # after a "heads down" line, before a sweep
    confirm_seconds: float = 4.0  # a listen after the count line, for a spoken count
    whisper_seconds: float = 5.0  # a night whisper (D16)
    vote_seconds: float = 4.0  # one player's vote (D12)
    clue_seconds: float = 6.0  # one clue (Imposter, Wavelength)
    guess_seconds: float = 6.0  # one listen for Wavelength's guess
    guess_listens: int = 8  # listens for a guess before the round scores zero
    talk_chunk_seconds: float = 10.0  # the day is heard in pieces this long, for an early "let's vote"
    count_tries: int = 3  # disagreements over the count before the host gives up (D6)
    wavelength_rounds: int = 3  # D21
    max_rounds: int = 10  # Mafia rounds before the host calls a draw
    # The welcome's conversation (brain/games/welcome.py, D40 to D43):
    answer_seconds: float = 20.0  # a short answer ("sure", "nah") counts this long after the host asks something
    nudge_seconds: float = 25.0  # this long with nothing said to the host gets a nudge
    nudges: int = 2  # nudges before the host waits quietly
    reply_gap_seconds: float = 8.0  # at most one small-talk reply this often
    max_chats: int = 6  # small-talk replies in one welcome
    count_fresh_seconds: float = 120.0  # a game named this soon after the welcome's count starts on it


@dataclass
class State:
    """The game's state as the feature files name it; snapshot() is what report() publishes."""

    game: str | None = None  # None until the count is agreed (D6: "no game has started")
    phase: str = "count"
    seats: int = 0
    living: list[int] = field(default_factory=list)
    out: list[int] = field(default_factory=list)  # in the order they went out
    warnings: dict[int, int] = field(default_factory=dict)  # this night only
    sitting_out: set[int] = field(default_factory=set)  # until the next round begins (D11)
    round: int = 0
    over: bool = False
    winner: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)  # Wavelength's psychic, scores, total
    stalled: str | None = None  # not reported: why gather() started no game, "too few" or "no count"

    def snapshot(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "phase": self.phase,
            "seats": self.seats,
            "living": sorted(self.living),
            "out": list(self.out),
            "warnings": {str(seat): n for seat, n in sorted(self.warnings.items())},
            "sitting_out": sorted(self.sitting_out),
            "round": self.round,
            "over": self.over,
            "winner": self.winner,
            **self.extra,
        }

    def report(self, table: Table) -> None:
        table.report(self.snapshot())

    def eliminate(self, seat: int) -> None:
        self.living.remove(seat)
        self.out.append(seat)
        self.sitting_out.discard(seat)


def hear(table: Table, seconds: float) -> str:
    """table.listen, except that a request to stop ends the game (GameStopped)."""
    heard = table.listen(seconds)
    if ears.wants_to_stop(heard):
        raise GameStopped(reset=ears.wants_to_reset(heard))
    return heard


def abandon(table: Table, state: State) -> None:
    """The game cannot go on (a deal that could not finish): over, with no winner and no
    ceremony; the line saying why has been said."""
    state.over = True
    state.winner = None
    state.phase = "over"
    state.report(table)


def decided(table: Table, state: State, winner: str | None) -> None:
    """The game is over, reported before the host reveals how (Table.reveal holds the
    card a moment), so the state does not lag the line; finish() follows."""
    state.over = True
    state.winner = winner
    state.phase = "over"
    state.report(table)


def finish(table: Table, state: State, winner: str | None, rng: random.Random) -> None:
    """The game is over: report it, then a little ceremony."""
    decided(table, state, winner)
    table.mood("win")
    table.say(lines.flavor("win", rng))
    table.quip("win", game=state.game)
    table.say(lines.GOOD_GAME)


# --- D5, D6: gathering the table -------------------------------------------------------


def _count(table: Table, state: State) -> int:
    n = table.count()
    state.seats = n
    state.report(table)
    table.say(lines.count_line(n))
    return n


def _spoken(heard: str) -> int | None:
    return ears.count_said(heard) or ears.bare_number(heard)


def gather(
    table: Table, game: str, heard: str, state: State, options: Options, counted: int | None = None, seen: bool = True
) -> int | None:
    """Agree on how many are playing (D5, D6) and start the game. A count said with the
    game's name ("imposter with six people") is taken at its word, with no sweep: the
    group knows who is there. With no number said, the host counts the table, says the
    count and agrees on it with the group: a spoken count that disagrees stops the start,
    the host says so, listens and counts again until the spoken number and its count
    agree, a go-ahead ("okay") accepts the host's count, and after options.count_tries
    disagreements it gives up. Returns the number of seats, with the game started in
    `state`, or None when no game starts (why, in state.stalled).

    counted: the welcome already knows the count (D40), so there is no sweep and no count
    line. seen: that count came from a sweep, so a different number said with the game's
    name still has to agree with it (D41); else the group's word, which a new number
    replaces."""
    state.game, state.phase, state.stalled = None, "count", None
    spoken = ears.count_said(heard)
    told = counted if not seen else None  # the group's word, from the welcome
    if told is not None or (counted is None and spoken is not None):
        n = spoken if spoken is not None else told
        assert n is not None
        table.seated(n)
        state.seats = n
        state.report(table)
        return _start(table, game, n, state)
    if counted is None:
        n = _count(table, state)
        if n == 0:  # the camera saw nobody: ask once, never sweep again
            if spoken is None:
                table.say(lines.HOW_MANY)
                spoken = _spoken(hear(table, options.confirm_seconds))
            if spoken is None:
                state.stalled = "no count"
                return None
            table.seated(spoken)
            return _start(table, game, spoken, state)
    else:
        n = state.seats = counted
        state.report(table)
        if spoken is None:
            spoken = n
    tries = 0
    while True:
        if spoken is None:
            spoken = _spoken(hear(table, options.confirm_seconds))
            if spoken is None:
                break  # silence, or anything but a count: the host's count stands
        if spoken == n:
            break
        tries += 1
        if tries > options.count_tries:
            table.say(lines.COUNT_GIVE_UP)
            state.stalled = "no count"
            return None
        table.say(lines.only_see(n) if spoken > n else lines.see_more(n))
        reply = hear(table, options.confirm_seconds)
        said = _spoken(reply)
        if said is not None:
            spoken = said
            continue
        if ears.agrees(reply):
            break
        n = _count(table, state)  # somebody may have come out of hiding
    return _start(table, game, n, state)


def _start(table: Table, game: str, n: int, state: State) -> int | None:
    """The count is settled: the game starts, or "Mafia needs at least four players.\""""
    minimum = lines.MINIMUM[game]
    if n < minimum:
        table.say(lines.too_few(game, minimum))
        state.seats = n
        state.stalled = "too few"
        return None
    state.game = game
    state.seats = n
    state.living = list(range(1, n + 1))
    state.phase = "deal"
    state.report(table)
    return n


# --- D7, D15: dealing ---------------------------------------------------------------------


def deal(table: Table, cards: dict[int, Card], state: State) -> bool:
    """Each seat its card through the private screen, one at a time, in seat order. A
    player who does not lean in is dealt again after the others; a second miss ends the
    deal (False)."""
    state.phase = "deal"
    state.report(table)
    missed = []
    for seat in sorted(cards):
        if not table.show_private(seat, cards[seat]):
            table.say(lines.come_back(seat))
            missed.append(seat)
    for seat in missed:
        if not table.show_private(seat, cards[seat]):
            table.say(lines.CANT_DEAL)
            table.look(None)
            return False
    table.look(None)
    return True


# --- D9 to D11: heads down ------------------------------------------------------------------


def heads_down_check(table: Table, state: State) -> None:
    """One sweep: a living player found with a face up is warned by seat (D9); a second
    time in the same night they sit out the rest of the round (D11). Nobody up, nothing
    said (D10). The dead and those already sitting out are not named."""
    for seat in table.faces_up():
        if seat not in state.living or seat in state.sitting_out:
            continue
        state.warnings[seat] = state.warnings.get(seat, 0) + 1
        if state.warnings[seat] == 1:
            table.say(lines.warn(seat))
        else:
            state.sitting_out.add(seat)
            table.say(lines.sit_out(seat))
        state.report(table)


def whisper(table: Table, prompt: str, again: str, seats: int, valid: Callable[[int], bool], options: Options) -> int | None:
    """A night whisper (D16): the prompt, a listen, and if no valid seat was made out,
    once more, quietly (D26). None when still nothing."""
    table.say(prompt)
    seat = ears.seat_said(hear(table, options.whisper_seconds), seats)
    if seat is not None and valid(seat):
        return seat
    table.say(again)
    seat = ears.seat_said(hear(table, options.whisper_seconds), seats)
    return seat if seat is not None and valid(seat) else None


# --- D12, D13: votes -----------------------------------------------------------------------------


def _ask_vote(table: Table, state: State, voter: int, options: Options) -> int | None:
    seat = ears.seat_said(hear(table, options.vote_seconds), state.seats)
    if seat is not None and seat in state.living:
        return seat
    table.say(lines.PICK_LIVING if seat is not None else lines.who_again(voter))
    seat = ears.seat_said(hear(table, options.vote_seconds), state.seats)
    return seat if seat is not None and seat in state.living else None


def vote(table: Table, state: State, options: Options, rng: random.Random) -> int | None:
    """The host turns to each living player not sitting out, in seat order, and asks
    "Player one, who?" (D12); a vote not made out is asked for again, once. The tally is
    said with the most votes first (ties in count by seat). A seat named by a majority of
    the living players is out ("Player four, you're out."), and the seat is returned; a
    tie at the top eliminates nobody (D13), and neither does a top seat short of a
    majority. The game reveals the role."""
    state.phase = "vote"
    state.report(table)
    table.mood("tense")
    table.say(lines.flavor("vote", rng))
    votes: dict[int, int] = {}
    for voter in [s for s in sorted(state.living) if s not in state.sitting_out]:
        table.look(voter)
        table.say(lines.who(voter))
        target = _ask_vote(table, state, voter, options)
        if target is not None:
            votes[voter] = target
    table.look(None)
    ordered = sorted(Counter(votes.values()).items(), key=lambda kv: (-kv[1], kv[0]))
    if not ordered:
        table.say(lines.NO_VOTES)
        return None
    top_seat, top = ordered[0]
    if len(ordered) > 1 and ordered[1][1] == top:
        table.say(lines.tie(ordered))
        table.say(lines.flavor("tie", rng))
        table.quip("tie", game=state.game)
        return None
    if top * 2 <= len(state.living):
        table.say(lines.no_majority(ordered))
        return None
    table.say(lines.tally(ordered))
    table.say(lines.voted_out(top_seat))
    return top_seat
