"""The welcome (D38 to D43): when the host starts, and whenever someone says "reset",
"start over" or "restart", it greets the table and asks what they want to play or how
many they are, and starts listening right away. The greeting, and the line after a tap
wakes the host, are the talk model's when it wrote one ahead (Table.chat
"welcome.greeting" and "welcome.woke"), else scripted. It does not sweep the table on its
own: a headcount said out loud is taken at its word and gets a suggestion for it (two
Wavelength, three or four Imposter, five or more Mafia, D38; one player Twenty
Questions or Wordle), and "count us" or "look around" gets the full sweep, a hello to
each seat by number and the suggestion. The talk goes on until they pick a game. The
suggestion and the list of games read lines.MINIMUM, so a game shows up here once it
is built.

What the group says is read in this order (brain/ears.py):

  reset                         the welcome again
  a question about a game       its rules, from the script, and "Want to play it?"
  a game's name                 that game, on the count so far (none yet: the game
                                asks for one; a count said with it: that count, or,
                                after a sweep, it has to agree: "imposter with six
                                people", D39)
  "not now", "stop"             a line, then the host naps until a tap on its head
  "count us", "look around"     the sweep, a hello to each seat, the suggestion
  a headcount                   taken at its word, and the suggestion for it; after a
                                sweep that saw fewer, "I only see five. Who's hiding?",
                                a pause, a second look
  "what games?", "you pick"     the games, or the suggestion again
  "nah", "something else"       the other games the count can play
  "sure", "yeah"                the suggestion, right after the host offered it (D39);
                                after the model asked something else ("how was the
                                beach?") a yes is talk, not a pick
  small talk                    a reply (Table.chat, the host's talk model) or a
                                scripted one: a hello, "how are you" or "who are you"
                                is answered even when the host asked nothing (D39, D42)
  anything else                 noise: nothing (D39), and so is transcription junk

Silence gets at most two nudges; then the host says it is taking a nap and stops
listening until a tap on its head wakes it (D39). Woken, it says it is up and asks
what they want to play, and the talk goes on as before. The rules, the count and the suggestion are code
(D14, D42): the talk model only writes the small-talk lines, and a line it writes that
does not fit is replaced by a scripted one.

The talk is remembered: the last MEMORY lines, both what the group said and what the
host said (scripted lines too), go to the model with each reply, so it holds a
conversation and never says the same thing twice. The memory belongs to the table: a
nap keeps it, and a greeting (the start, "reset") clears it. Game end clears it too,
so the next lobby cannot carry dialogue or game context forward. Nothing is persisted;
process exit drops all dialogue. Only selected facts and public totals can be durable.
"""

from __future__ import annotations

import random
import re
import weakref
from collections import deque
from dataclasses import dataclass
from typing import Any

from brain import ears, facts, lines
from brain.games.common import Options, State
from brain.table import Table

RESTART = "restart"  # converse(): someone said "reset"
_MAX_REPLY = 320  # characters: a model line longer than this is not about three short sentences
MEMORY = 12  # lines of the talk, both sides, the model sees with each reply
_memories: weakref.WeakKeyDictionary[Any, deque[tuple[str, str]]] = weakref.WeakKeyDictionary()


def _memory(table: Table) -> deque[tuple[str, str]]:
    """The talk so far at this table, ("ROB" or "them", the line), kept across a nap."""
    try:
        return _memories.setdefault(table, deque(maxlen=MEMORY))
    except TypeError:  # a table that cannot be weakly referenced remembers one welcome only
        return deque(maxlen=MEMORY)


def clear_memory(table: Table) -> None:
    """Drop dialogue on reset, game end or lobby teardown; RAM vanishes on exit."""
    _memory(table).clear()


@dataclass
class Choice:
    """The group picked a game: what was heard, and the welcome's count if it still stands."""

    game: str
    heard: str
    counted: int | None
    seen: bool = True  # the count came from a sweep, not the group's word


class Welcome:
    def __init__(self, table: Table, rng: random.Random, options: Options, listen_window: float, remembered: facts.Facts | None = None) -> None:
        self.table = table
        self.rng = rng
        self.options = options
        self.listen_window = listen_window
        self.seats = 0  # 0: nobody has said, and no sweep has run
        self.seen = False  # self.seats came from a sweep
        self.counted_at = float("-inf")
        self.quiet_since = self.asked_at = float("-inf")
        self.offered_at = float("-inf")  # the last question offered the suggestion, so a yes takes it
        self.memory = _memory(table)
        self.facts = remembered if remembered is not None else facts.for_table(table)
        self.later: list[str] = []
        self.suggestion: str | None = None
        self.nudged = 0
        self.chats = 0
        self.recounts = 0
        self.replied_at = float("-inf")

    # --- the greeting -------------------------------------------------------------

    def greet(self) -> None:
        """Hello, and what are we playing? No sweep: the host listens straight away. The
        talk starts afresh."""
        self.table.mood("idle")
        State(phase="welcome", seats=0).report(self.table)
        self.memory.clear()
        self._say(self._opening("welcome.greeting", named=True) or lines.greeting(self.rng))
        self._ask(lines.games_menu())
        self.later = lines.nudges(None, self.rng)

    def wake(self) -> None:
        """A tap woke the host: "I'm up, I'm up! What are we playing?\""""
        self.table.mood("idle")
        State(phase="welcome", seats=0).report(self.table)
        self._ask(self._opening("welcome.woke") or lines.woke(self.rng))
        self.later = lines.nudges(None, self.rng)

    def _opening(self, situation: str, named: bool = False) -> str | None:
        """The talk model's greeting or wake-up line, written ahead, if it fits: the
        greeting (`named`) says it is ROB, the wake-up asks what they want to play;
        else None."""
        line = _fit(self.table.chat(situation, games=lines.game_names(), remembered=self.facts.remembered()))
        if line is None or (not named and "?" not in line) or (named and not re.search(r"\brob\b", line, re.IGNORECASE)):
            return None
        return line

    def instead_of(self, game: str, seats: int) -> None:
        """After "Mafia needs at least four players." outside the talk: a game the
        `seats` that game found can play."""
        self.table.mood("idle")
        self._settled(seats)
        self.later = lines.nudges(lines.suggested(self.seats), self.rng)
        self.too_few(game)

    def _count(self) -> None:
        self.seats = self.table.count()
        self.seen = True
        self.counted_at = self.table.now()
        State(phase="welcome", seats=self.seats).report(self.table)

    def _told(self, n: int) -> None:
        """The group said how many they are: taken at its word, and a game for it."""
        self._settled(n)
        self.table.seated(n)
        self._suggest()

    def _settled(self, n: int) -> None:
        """The count is `n` and the host's seating already matches it (said, or settled
        by a game that just ran), so a new number said replaces it."""
        self.seats = n
        self.seen = False
        self.counted_at = self.table.now()
        State(phase="welcome", seats=n).report(self.table)

    def _counted(self, now: float) -> int | None:
        """The count a game picked now starts on: the group's word, or a fresh sweep."""
        if self.seats < 1 or (self.seen and now - self.counted_at > self.options.count_fresh_seconds):
            return None
        return self.seats

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
        self.memory.append(("ROB", line))

    def _ask(self, line: str, offer: bool = True) -> None:
        """A line the group may answer with a word: a number, and, when it offers a game
        (`offer`, every scripted question), "sure" or "nah"."""
        self._say(line)
        self.asked_at = self.table.now()
        self.offered_at = self.asked_at if offer else float("-inf")

    # --- the conversation -----------------------------------------------------------

    def converse(self, first: str = "") -> Choice | str | None:
        """Listen and answer until the group picks a game (a Choice), says "reset"
        (RESTART), or goes quiet or asks to wait (None: the host naps until a tap).
        `first`: words already heard (typed on the dashboard to wake the host),
        answered before the first listen."""
        while True:
            heard, first = first or self.table.listen(self.listen_window), ""
            now = self.table.now()
            if heard.strip():
                answer = self._hear(heard, now)
                if answer is not None:
                    return None if answer == "" else answer
            if now - self.quiet_since >= self.options.nudge_seconds:
                if self.nudged >= min(self.options.nudges, len(self.later)):
                    self._say(lines.NAP)
                    return None  # sleeps until a tap
                self._ask(self.later[self.nudged])
                self.nudged += 1

    def _hear(self, heard: str, now: float) -> Choice | str | None:
        """What to do with one listen's words: a Choice, RESTART, "" (wait quietly), or
        None (keep talking)."""
        command = ears.memory_command(heard)
        if command is not None:
            self._remember(*command)
            return None
        if ears.wants_to_reset(heard):
            self.memory.clear()
            return RESTART
        before = list(self.memory)
        if ears.meaningful(heard, answering=True):
            self.memory.append(("them", heard.strip()))
        rules = ears.asks_rules(heard)
        if rules is not None:
            self.suggestion = rules
            self._ask(lines.rules(rules))
            return None
        game = ears.game_named(heard)
        if game is not None:
            return Choice(game, heard, self._counted(now), self.seen)
        if ears.wants_later(heard) or ears.wants_to_stop(heard) or ears.wants_pause(heard):
            self._say(lines.later(self.rng))  # "shut up", "not now": a line, then a nap
            return ""
        if ears.wants_count(heard):
            self._say(lines.looking(self.rng))
            self._count()
            self._hellos()
            self._suggest()
            return None
        answering = now - self.asked_at <= self.options.answer_seconds
        offered = now - self.offered_at <= self.options.answer_seconds
        spoken = ears.count_said(heard) or (ears.bare_number(heard) if answering else None)
        if spoken is not None:
            if self.seen and self.seats > 0 and self.recounts < 1:  # one second look, then their word
                self._spoken(spoken)
            else:
                self._told(spoken)
            return None
        if ears.asks_games(heard):
            self._ask(lines.games_list(self.seats) if self.seats > 0 else lines.games_any())
            return None
        if ears.asks_pick(heard):
            if self.suggestion is not None:
                self._ask(lines.suggestion(self.seats, self.rng))
                return None
            if self.seats < 1:
                self._ask(lines.HOW_MANY)
                return None
        if offered and self.seats > 0 and ears.says_no(heard) and len(heard.split()) <= 6:
            self._ask(lines.declined(self.seats, self.suggestion, self.rng))
            if lines.fits(self.seats) != [self.suggestion]:
                self.suggestion = None  # a "yes" now would be to nothing in particular
            return None
        if offered and self.suggestion is not None and ears.says_yes(heard):
            return Choice(self.suggestion, heard, self._counted(now), self.seen)
        if ears.meaningful(heard, answering):
            self.quiet_since = now
            self._chat(heard, answering, now, before)
        return None  # noise

    def _remember(self, command: str, text: str) -> None:
        """Scripted confirmations, never let a model decide what goes on disk."""
        try:
            if command == "remember":
                result = self.facts.remember(text)
                line = {"saved": lines.MEMORY_SAVED, "duplicate": lines.MEMORY_DUPLICATE,
                        "full": lines.MEMORY_FULL, "invalid": lines.MEMORY_INVALID}[result]
            elif command == "forget":
                line = lines.MEMORY_FORGOT if self.facts.forget_last() else lines.MEMORY_EMPTY
                self.memory.clear()  # a forgotten fact must not survive in recent dialogue
            elif command == "clear":
                self.facts.forget_all()
                self.memory.clear()
                line = lines.MEMORY_CLEARED
            else:
                line = lines.memories_remembered(self.facts.remembered())
        except OSError:
            line = lines.MEMORY_UNAVAILABLE
        # Recall may be long and carries facts: keep it out of the dialogue buffer.
        self.table.say(line)
        self.quiet_since = self.table.now()
        self.offered_at = float("-inf")

    def _spoken(self, spoken: int) -> None:
        """A headcount said in the welcome: agreed, or a second look (D39, D6)."""
        n = self.seats
        if spoken == n:
            self._ask(lines.count_agreed(n, self.suggestion))
            return
        self.recounts += 1  # after this, the group's word wins (see _hear)
        if spoken < n:
            self._ask(lines.see_more(n))
            return
        self._say(lines.only_see(n))  # "I only see five. Who's hiding?"
        self.table.wait(self.options.settle_seconds)
        self._count()
        self._say(lines.recounted(n, self.seats))
        if self.seats != n:
            self._hellos()
        self._suggest()

    def _chat(self, heard: str, answering: bool, now: float, before: list[tuple[str, str]]) -> None:
        """Small talk: a reply that knows the talk so far (`before`, what was said before
        `heard`), the model's or a scripted one, never a line just said (D39, D42). A
        question back offers the suggestion only when it names it."""
        if self.chats >= self.options.max_chats or now - self.replied_at < self.options.reply_gap_seconds:
            return
        facts: dict[str, Any] = {"remembered": self.facts.remembered(), "answering": answering, "games": lines.game_names(), "transcript": [list(e) for e in before]}
        if self.seats > 0:
            facts["players"] = self.seats
        if self.suggestion is not None:
            facts["suggestion"] = lines.game_name(self.suggestion)
        said = [line for who, line in self.memory if who == "ROB"]
        line = _fit(self.table.chat("welcome", heard, **facts))
        if line is None or line in said:
            line = lines.chat_fallback(self.suggestion, self.rng, ears.small_talk(heard), said)
        self.chats += 1
        if line.endswith("?"):
            self._ask(line, offer=self.suggestion is not None and ears.game_named(line) == self.suggestion)
        else:
            self._say(line)
        self.replied_at = self.table.now()

    def too_few(self, game: str, seats: int | None = None) -> None:
        """After "Mafia needs at least four players.": the game this count can play;
        `seats`, the count the game settled on."""
        if seats is not None and seats != self.seats:
            self._settled(seats)
        pick = lines.suggested(self.seats)
        if pick is not None and pick != game:
            self.suggestion = pick
            self._ask(lines.instead(pick))
        else:
            self._ask(lines.suggestion(self.seats, self.rng))


_SEAT = re.compile(r"\b(?:player|players|seat|seats)\b|\d", re.IGNORECASE)


def _fit(line: Any) -> str | None:
    """A talk-model line the welcome can say: short, and naming no seat or number (the
    seats and the count are the code's), so it ends before the first sentence that names
    one; None when that is the first. The host's talk client cleans it first."""
    if not isinstance(line, str):
        return None
    line = line.strip()
    if not line or len(line) > _MAX_REPLY:
        return None
    kept = []
    for sentence in re.findall(r"[^.!?]+[.!?]*", line):
        if _SEAT.search(sentence):
            break
        kept.append(sentence.strip())
    return " ".join(kept) or None
