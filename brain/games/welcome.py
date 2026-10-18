"""The welcome (D38 to D43): when the host starts, and whenever someone says "reset",
"start over" or "restart", it greets the table, counts it with the full sweep, turns
to each seat in order and says hello by number, suggests a game for the headcount
(two Wavelength, three or four Imposter, five or more Mafia, D38; one player Twenty
Questions or Wordle) and talks with the group until they pick one. The suggestion and
the list of games read lines.MINIMUM, so a game shows up here once it is built.

What the group says is read in this order (brain/ears.py):

  reset                         the welcome again
  a question about a game       its rules, from the script, and "Want to play it?"
  a game's name                 that game, on this count (a count said with it still
                                has to agree: "imposter with six people", D39); the
                                name inside other talk ("that was a hot seat") gets
                                "Hot Seat? Say yes to play it." and a yes starts it (D94)
  "not now", "stop"             a line, then the host waits quietly
  a headcount                   "I only see five. Who's hiding?", a pause, a second look
  "what games?", "you pick"     the games, or the suggestion again
  "nah", "something else"       the other games the count can play
  "sure", "yeah"                the suggestion, right after the host asked (D39)
  small talk                    a short reply (Table.chat, the host's talk model) or a
                                scripted one; capped and rate-limited (D39, D42)
  anything else                 noise: nothing (D39)

Silence gets at most two nudges; then the conversation ends without a word and the
host waits for a game's name (D39). The rules, the count and the suggestion are code
(D14, D42): the talk model only writes the small-talk lines, and a line it writes that
does not fit is replaced by a scripted one.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any

from brain import ears, lines
from brain.games.common import Options, State
from brain.table import Table

RESTART = "restart"  # converse(): someone said "reset"
_MAX_REPLY = 240  # characters: a model line longer than this is not one or two short sentences


@dataclass
class Choice:
    """The group picked a game: what was heard, and the welcome's count if it still stands."""

    game: str
    heard: str
    counted: int | None


class Welcome:
    def __init__(self, table: Table, rng: random.Random, options: Options, listen_window: float) -> None:
        self.table = table
        self.rng = rng
        self.options = options
        self.listen_window = listen_window
        self.seats = 0
        self.suggestion: str | None = None

    # --- the greeting -------------------------------------------------------------

    def greet(self) -> None:
        """Hello, the count, a hello to each seat, the suggestion."""
        t = self.table
        t.mood("idle")
        self._say(lines.greeting(self.rng))
        self._count()
        self._hellos()
        self._suggest()
        self.nudged = 0
        self.chats = 0
        self.recounts = 0
        self.replied_at = float("-inf")

    def _count(self) -> None:
        self.seats = self.table.count()
        self.counted_at = self.table.now()
        State(phase="welcome", seats=self.seats).report(self.table)

    def _hellos(self) -> None:
        for seat in range(1, self.seats + 1):
            self.table.look(seat)
            self._say(lines.hello(seat, self.seats, self.rng))
        self.table.look(None)

    def _suggest(self) -> None:
        self.suggestion = lines.suggested(self.seats)
        self._ask(lines.suggestion(self.seats, self.rng))
        self.later = lines.nudges(self.suggestion, self.rng)

    def _say(self, line: str) -> None:
        self.table.say(line)
        self.quiet_since = self.table.now()

    def _ask(self, line: str) -> None:
        """A line the group may answer with a word ("sure", "nah")."""
        self._say(line)
        self.asked_at = self.table.now()

    # --- the conversation -----------------------------------------------------------

    def converse(self) -> Choice | str | None:
        """Listen and answer until the group picks a game (a Choice), says "reset"
        (RESTART), or goes quiet or asks to wait (None)."""
        while True:
            heard = self.table.listen(self.listen_window)
            now = self.table.now()
            if heard.strip():
                answer = self._hear(heard, now)
                if answer is not None:
                    return None if answer == "" else answer
            if now - self.quiet_since >= self.options.nudge_seconds:
                if self.nudged >= min(self.options.nudges, len(self.later)):
                    return None  # waits quietly, for a game's name
                self._ask(self.later[self.nudged])
                self.nudged += 1

    def _hear(self, heard: str, now: float) -> Choice | str | None:
        """What to do with one listen's words: a Choice, RESTART, "" (wait quietly), or
        None (keep talking)."""
        if ears.wants_to_reset(heard):
            return RESTART
        rules = ears.asks_rules(heard)
        if rules is not None:
            self.suggestion = rules
            self._ask(lines.rules(rules))
            return None
        game = ears.game_named(heard)
        if game is not None:
            fresh = self.seats > 0 and now - self.counted_at <= self.options.count_fresh_seconds
            return Choice(game, heard, self.seats if fresh else None)
        mentioned = ears.game_mentioned(heard)
        if mentioned is not None:  # D94: a doubtful hearing is confirmed, never started
            self.suggestion = mentioned
            self._ask(lines.confirm_game(mentioned))
            return None
        if ears.wants_later(heard) or ears.wants_to_stop(heard):
            self._say(lines.later(self.rng))
            return ""
        answering = now - self.asked_at <= self.options.answer_seconds
        spoken = ears.count_said(heard) or (ears.bare_number(heard) if answering else None)
        if spoken is not None:
            self._spoken(spoken)
            return None
        if ears.asks_games(heard):
            self._ask(lines.games_list(self.seats))
            return None
        if ears.asks_pick(heard) and self.suggestion is not None:
            self._ask(lines.suggestion(self.seats, self.rng))
            return None
        if answering and ears.says_no(heard) and len(heard.split()) <= 6:
            self._ask(lines.declined(self.seats, self.suggestion, self.rng))
            if lines.fits(self.seats) != [self.suggestion]:
                self.suggestion = None  # a "yes" now would be to nothing in particular
            return None
        if answering and self.suggestion is not None and ears.says_yes(heard):
            fresh = now - self.counted_at <= self.options.count_fresh_seconds
            return Choice(self.suggestion, heard, self.seats if fresh else None)
        if ears.meaningful(heard, answering):
            self.quiet_since = now
            self._chat(heard, answering, now)
        return None  # noise

    def _spoken(self, spoken: int) -> None:
        """A headcount said in the welcome: agreed, or a second look (D39, D6)."""
        n = self.seats
        if spoken == n:
            self._ask(lines.count_agreed(n, self.suggestion))
            return
        if spoken < n or self.recounts >= self.options.count_tries:
            self._ask(lines.see_more(n) if spoken < n else lines.only_see(n))
            return
        self.recounts += 1
        self._say(lines.only_see(n))  # "I only see five. Who's hiding?"
        self.table.wait(self.options.settle_seconds)
        self._count()
        self._say(lines.recounted(n, self.seats))
        if self.seats != n:
            self._hellos()
        self._suggest()

    def _chat(self, heard: str, answering: bool, now: float) -> None:
        """Small talk: a short reply, rate-limited and capped (D39, D42)."""
        if self.chats >= self.options.max_chats or now - self.replied_at < self.options.reply_gap_seconds:
            return
        facts: dict[str, Any] = {"players": self.seats, "answering": answering}
        if self.suggestion is not None:
            facts["suggestion"] = lines.game_name(self.suggestion)
        line = _fit(self.table.chat("welcome", heard, **facts))
        line = line or lines.chat_fallback(self.suggestion, self.rng)
        self.chats += 1
        if line.endswith("?"):
            self._ask(line)
        else:
            self._say(line)
        self.replied_at = self.table.now()

    def too_few(self, game: str) -> None:
        """After "Mafia needs at least four players." and gather()'s "Want to try X
        instead?" (D98): a yes now starts X; when nothing else fits, suggest again."""
        pick = lines.suggested(self.seats)
        if pick is not None and pick != game:
            self.suggestion = pick
            self.asked_at = self.table.now()
        else:
            self._ask(lines.suggestion(self.seats, self.rng))


_SEAT = re.compile(r"\b(?:player|players|seat|seats)\b|\d", re.IGNORECASE)


def _fit(line: Any) -> str | None:
    """A talk-model line the welcome can say: short, and naming no seat or number (the
    seats and the count are the code's). The host's talk client cleans it first."""
    if not isinstance(line, str):
        return None
    line = line.strip()
    if not line or len(line) > _MAX_REPLY or _SEAT.search(line):
        return None
    return line
