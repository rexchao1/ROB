"""What a game asks of the host: the one contract between the rules (brain/games/,
pure code that decides everything, D14) and the host's body (brain/host.py: the head,
the camera, the screen, the voice, the ears and the clock).

Seats are numbered 1..N from the host's left to its right, in the order the last
count() found them (D5). Every method blocks until it is done. Time is the table's
clock (virtual in test mode, so nothing waits real time in a test), never the wall.

A game never touches the body, the camera or the clock directly, and the host never
decides a rule. Tests for the rules drive a fake Table; tests for the host drive the
real one against the fake gateway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

MOODS = ("idle", "listening", "night", "day", "tense", "win")


@dataclass(frozen=True)
class Card:
    """Something on the host's screen: private, for one player's eyes (D7: a role, a
    word, a target number), or a reveal the whole table sees while the host says it
    ("VILLAGE" / "wins")."""

    text: str  # the big line: "MAFIA", "beach", "7"
    sub: str | None = None  # an optional small line under it: "cold - hot"
    kind: str | None = None  # what a reveal means: one of REVEALS; None for a role or a word dealt
    # How the card looks: a key of brain.cards.STYLES ("villain", "helper", "town",
    # "number", "win", "out", ...), its accent color. None lets brain/cards.py pick
    # from the kind, then the text (the role cards, a number) or the default. Looks only: two cards
    # with the same text, sub and kind are the same card whatever their style.
    style: str | None = field(default=None, compare=False)


# What a reveal card means (Card.kind), so the screen can give each its own look.
REVEALS = ("win", "out", "safe", "word", "target", "score")


class Table(Protocol):
    def now(self) -> float:
        """Seconds on the table's clock."""
        ...

    def wait(self, seconds: float) -> None:
        """Let `seconds` pass on the table's clock, saying and hearing nothing."""
        ...

    def say(self, line: str) -> None:
        """Speak one line, exactly as written (the feature files assert the text).
        Returns once it has been said."""
        ...

    def look(self, seat: int | None) -> None:
        """Turn the head to a seat; None faces straight ahead."""
        ...

    def count(self) -> int:
        """Sweep the head across its whole range, find the faces, number the seats 1..N
        from left to right (replacing any earlier seating) and return N. Says nothing."""
        ...

    def seated(self, n: int) -> None:
        """Take the group's word that `n` players are at the table, with no sweep: number
        the seats 1..n spread evenly from the host's left to its right (replacing any
        earlier seating), so look(seat) has somewhere to turn. Says nothing."""
        ...

    def prepare(self, cards: list[Card]) -> None:
        """The cards this game will show (at most five, all distinct), so the host can
        put them on its screen ahead of time; may take a while on the real body, so it
        returns at once there and the upload runs while the host talks. Call it before
        the first show_private(), and again when the cards to come change (the reveals
        once the deal is done). Replaces the previous cards."""
        ...

    def show_private(self, seat: int, card: Card) -> bool:
        """D7 and D8, start to finish. Turn to the seat, say "Player N, lean in.", then
        show the card only while exactly one close face is in view and facing the host:
        when a second close face appears the screen goes blank within one second and the
        host says "One at a time."; the card returns when only one is left. Returns True
        once the player has seen it and leaned back (the screen blank again), or False
        when nobody leaned in within the host's time limit (the screen blank). `card` must
        be one of the prepared cards."""
        ...

    def reveal(self, card: Card, line: str) -> None:
        """A big moment for the whole table: `card` on the screen while the host says
        `line`, held a moment after, then the host's own face again. `card` must be one
        of the prepared cards; a game prepares its reveals with its private cards, or
        prepares them again once what it will reveal is known (an upload of a few
        seconds on the real body, done while the host talks). A card the screen cannot
        show leaves the line said without it. Never shown while a private card is owed."""
        ...

    def listen(self, seconds: float) -> str:
        """Everything heard over the next `seconds`, lower-cased, '' for silence."""
        ...

    def faces_up(self) -> list[int]:
        """One heads-down sweep across the seats (D9, D10): the seats where a face is up
        and facing the host, ascending; [] when every head is down. Says nothing."""
        ...

    def mood(self, name: str) -> None:
        """The host's look for a phase, one of MOODS (face and lights). Cosmetic only."""
        ...

    def report(self, state: dict[str, Any]) -> None:
        """Publish the game's state (what GET /test/state serves, see brain/games/
        __init__.py for the keys). Call it after every change the feature files name."""
        ...

    def quip(self, slot: str, **context: Any) -> None:
        """Banter at a slot the script marks (D14): may say one extra line or nothing.
        Never names a player and never changes anything."""
        ...

    def talk_settings(self) -> dict[str, Any]:
        """Current provider, model, effort and personality, without keys."""
        ...

    def chat(self, situation: str, heard: str = "", **facts: Any) -> str | None:
        """A line of talk for a moment the script leaves open (D42): the welcome's reply
        to small talk ("welcome", what was heard, and facts such as the player count and
        the suggested game). Written by the host's talk model, or None (no model, no
        internet, a slow answer, or a line that would not do); the caller then says a
        scripted line. Says nothing itself, and decides nothing (D14)."""
        ...

    def sleep(self, seconds: float) -> str | None:
        """Nap between games for at most `seconds`: hear nothing (the microphone off)
        until a tap on the host's head ('') or a line typed for it on the operator's
        pages (that line, lower-cased); None when the time ran out with neither, and the
        caller naps again. Says nothing."""
        ...
