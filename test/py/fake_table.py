"""A fake Table (brain/table.py) for the rules' tests: no body, no camera, no voice, a
virtual clock, and everything the game did recorded in order.

What the table hears is scripted two ways, keyed answers first:

  table.reply("Mafia, whisper your target.", "player four")   # heard in the listen
                                                              # right after that line
  table.reply("Player one, who?", "four", "two")              # one answer per time asked
  table.hear("there are six of us")                           # the next listen with no
                                                              # keyed answer, in order

A listen with nothing scripted hears silence (''). faces_up() answers each sweep from
table.sweeps (a list of seat lists, consumed in order; [] once used up). count()
answers from table.counts the same way (the last value repeats). show_private returns
False for the seats in `no_lean`; like the real host it says "Player N, lean in." and
records the card, and it refuses a card that was not prepared.

Every action lands in table.log as (time, kind, value): "say", "look", "count",
"prepare", "show", "listen", "heard", "faces_up", "wait", "mood", "quip". table.said is
the lines alone; table.reports every report() in order; table.state the latest.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from brain import lines
from brain.table import MOODS, Card


class FakeTable:
    def __init__(self, seats: int = 5, counts: list[int] | None = None, no_lean: set[int] | None = None) -> None:
        self.clock = 0.0
        self.counts = deque(counts if counts is not None else [seats])
        self.no_lean = set(no_lean or ())
        self.sweeps: deque[list[int]] = deque()
        self.log: list[tuple[float, str, Any]] = []
        self.said: list[str] = []
        self.reports: list[dict[str, Any]] = []
        self.prepared: list[Card] = []
        self.shown: list[tuple[int, Card]] = []
        self.facing: int | None = None
        self._keyed: dict[str, deque[str]] = {}
        self._queue: deque[str] = deque()
        self._last_line: str | None = None
        self.listens = 0
        self.max_listens = 2000  # a runaway game fails the test instead of hanging it

    # --- scripting ---------------------------------------------------------------

    def reply(self, line: str, *answers: str) -> FakeTable:
        self._keyed.setdefault(line, deque()).extend(answers)
        return self

    def hear(self, *answers: str) -> FakeTable:
        self._queue.extend(answers)
        return self

    def sweep(self, *results: list[int]) -> FakeTable:
        self.sweeps.extend(results)
        return self

    # --- the Table ---------------------------------------------------------------

    def _note(self, kind: str, value: Any) -> None:
        self.log.append((self.clock, kind, value))

    def now(self) -> float:
        return self.clock

    def wait(self, seconds: float) -> None:
        assert seconds >= 0
        self.clock += seconds
        self._note("wait", seconds)

    def say(self, line: str) -> None:
        assert isinstance(line, str) and line, f"say({line!r})"
        self.said.append(line)
        self._last_line = line
        self._note("say", line)

    def look(self, seat: int | None) -> None:
        self.facing = seat
        self._note("look", seat)

    def count(self) -> int:
        n = self.counts.popleft() if len(self.counts) > 1 else self.counts[0]
        self._note("count", n)
        return n

    def prepare(self, cards: list[Card]) -> None:
        assert 0 < len(cards) <= 5 and len(set(cards)) == len(cards), f"prepare({cards})"
        self.prepared = list(cards)
        self._note("prepare", list(cards))

    def show_private(self, seat: int, card: Card) -> bool:
        assert card in self.prepared, f"{card} was not prepared ({self.prepared})"
        self.look(seat)
        self.say(lines.lean_in(seat))
        if seat in self.no_lean:
            self._note("show", (seat, None))
            return False
        self.shown.append((seat, card))
        self._note("show", (seat, card))
        return True

    def listen(self, seconds: float) -> str:
        assert seconds > 0
        self.listens += 1
        assert self.listens <= self.max_listens, "the game kept listening: a runaway loop"
        self.clock += seconds
        keyed = self._keyed.get(self._last_line or "")
        if keyed:
            heard = keyed.popleft()
        elif self._queue:
            heard = self._queue.popleft()
        else:
            heard = ""
        self._last_line = None  # a keyed answer belongs to the listen right after its line
        self._note("listen", seconds)
        if heard:
            self._note("heard", heard)
        return heard.lower()

    def faces_up(self) -> list[int]:
        up = sorted(self.sweeps.popleft()) if self.sweeps else []
        self._note("faces_up", up)
        return up

    def mood(self, name: str) -> None:
        assert name in MOODS, name
        self._note("mood", name)

    def report(self, state: dict[str, Any]) -> None:
        self.reports.append(state)

    def quip(self, slot: str, **context: Any) -> None:
        self._note("quip", slot)

    def chat(self, situation: str, heard: str = "", **facts: Any) -> str | None:
        """The talk model's line: the next of table.chats (a list), else None (no model)."""
        self._note("chat", situation)
        return self.chats.pop(0) if getattr(self, "chats", None) else None

    # --- reading the record ------------------------------------------------------

    @property
    def state(self) -> dict[str, Any]:
        return self.reports[-1] if self.reports else {"game": None}

    def said_at(self, line: str) -> list[float]:
        """The table times at which `line` was said."""
        return [t for t, kind, value in self.log if kind == "say" and value == line]

    def after(self, line: str) -> list[str]:
        """The lines said after the first time `line` was said."""
        i = self.said.index(line)
        return self.said[i + 1 :]
