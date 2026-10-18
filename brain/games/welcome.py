"""The welcome (D38 to D43, and docs/CHAT-PLAN.md): when the host starts, and whenever
someone says "reset", "start over" or "restart", it greets the table and starts
listening right away. The greeting is always scripted (lines.GREETINGS, recorded once);
then, with the talk on, an open question (lines.OPENERS) and the games come up in the
talk; offline, the games menu. The line after a tap wakes the host is the talk model's
when it wrote one ahead (Table.chat "welcome.woke"), else scripted. It does not sweep
the table on its own: a headcount said out loud is taken at its word (two Wavelength,
three or four Imposter, five or more Mafia, D38; one player Twenty Questions or
Wordle), and "count us" or "look around" gets the sweep. The talk goes on until they
pick a game. The suggestion and the list of games read lines.MINIMUM, so a game shows
up here once it is built.

What the group says is read in this order (brain/ears.py):

  "remember that ...", "forget"  the facts, with scripted confirmations
  reset                         the welcome again
  a game's name, no question    that game, on the count so far, at once
  "not now", "stop", "pause"    a line, then the host naps until a tap on its head
  noise                         nothing (D39), and so is transcription junk
  anything else                 the talk model's turn (brain/agent.py, run_turn): the
                                line it says plus the tools it picked, each checked in
                                code (start a game, nap, count the table, the rules,
                                look, a face, remember); a headcount said is still
                                taken at its word first

When the model gives nothing (offline, no key, too slow, a provider without tools),
the scripted router answers instead, as before the talk had tools:

  a question about a game       its rules, from the script, and "Want to play it?"
  a game's name                 that game, on the count so far (none yet: the game
                                asks for one; a count said with it: that count, or,
                                after a sweep, it has to agree: "imposter with six
                                people", D39)
  "count us", "look around"     the sweep, a hello to each seat, the suggestion
  a headcount                   taken at its word, and the suggestion for it; after a
                                sweep that saw fewer, "I only see five. Who's hiding?",
                                a pause, a second look
  "what games?", "you pick"     the games, or the suggestion again
  "nah", "something else"       the other games the count can play
  "sure", "yeah"                the suggestion, right after the host offered it (D39);
                                after the model asked something else ("how was the
                                beach?") a yes is talk, not a pick
  small talk                    a reply (Table.chat) or a scripted one

Silence gets at most two nudges, the model's own words when it gives some, else
scripted; then the host says it is taking a nap and stops listening until a tap on its
head wakes it (D39). Woken, it says it is up and asks what they want to play, and the
talk goes on as before. The rules, the count and the suggestion are code (D14, D42):
the model picks words and checked tools, never a rule or a count.

The talk is remembered: the last MEMORY lines, both what the group said and what the
host said (scripted lines too), go to the model with each turn, so it holds a
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

from brain import agent, ears, facts, lines
from brain.games.common import Options, State
from brain.table import Table

RESTART = "restart"  # converse(): someone said "reset"
_MAX_REPLY = 320  # characters: a model line longer than this is not about three short sentences
MEMORY = 40  # lines of the talk, both sides, the model sees with each turn
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
        self.started_at = table.now()  # the talk's start, so the model knows when to nudge toward a game
        self.quiet_since = self.asked_at = float("-inf")
        self.offered_at = float("-inf")  # the last question offered the suggestion, so a yes takes it
        self.memory = _memory(table)
        self.facts = remembered if remembered is not None else facts.for_table(table)
        self.later: list[str] = []
        self.suggestion: str | None = None
        self.nudged = 0
        self.recounts = 0
        self.replied_at = float("-inf")

    # --- the greeting -------------------------------------------------------------

    def greet(self) -> None:
        """Hello, and what are we playing? No sweep: the host listens straight away. The
        talk starts afresh."""
        self.table.mood("idle")
        State(phase="welcome", seats=0).report(self.table)
        self.memory.clear()
        self._say(lines.greeting(self.rng))
        if self._talking():
            self._ask(lines.opener(self.rng), offer=False)  # the games come up in the talk
        else:
            self._ask(lines.games_menu())  # offline, the table still hears what there is
        self.later = lines.nudges(None, self.rng)

    def wake(self) -> None:
        """A tap woke the host: "I'm up, I'm up! What are we playing?\""""
        self.table.mood("idle")
        State(phase="welcome", seats=0).report(self.table)
        self._ask(self._opening("welcome.woke") or lines.woke(self.rng))
        self.later = lines.nudges(None, self.rng)

    def _opening(self, situation: str) -> str | None:
        """The talk model's wake-up line, written ahead, if it fits (it asks what they
        want to play); else None."""
        line = _fit(self.table.chat(situation, games=lines.game_names(), remembered=self.facts.remembered()))
        return line if line is not None and "?" in line else None

    def _talking(self) -> bool:
        """The host's talk can pick his moves now (Table.talk_settings "tools"; a table
        that does not say, "talk" not "off")."""
        try:
            choices = self.table.talk_settings() or {}
        except Exception:  # a table with no talk settings is offline
            return False
        if "tools" in choices:
            return choices["tools"] is True
        talk = choices.get("talk")
        return isinstance(talk, str) and talk != "off"

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
                self.nudged += 1
                turned, answer = self._turn("", now, list(self.memory), answering=False, quiet=True)
                if not turned:
                    self._ask(self.later[self.nudged - 1])
                elif answer is not None:
                    return None if answer == "" else answer

    def _hear(self, heard: str, now: float) -> Choice | str | None:
        """What to do with one listen's words: a Choice, RESTART, "" (wait quietly), or
        None (keep talking). The commands and a game named outright are the code's and
        instant; any other line worth answering is the talk model's turn, and the
        scripted router when the model gives nothing."""
        command = ears.memory_command(heard)
        if command is not None:
            self._remember(*command)
            return None
        if ears.wants_to_reset(heard):
            self.memory.clear()
            return RESTART
        game = ears.game_named(heard)
        if game is not None and ears.asks_rules(heard) is None and "?" not in heard:
            return Choice(game, heard, self._counted(now), self.seen)
        if ears.wants_later(heard) or ears.wants_to_stop(heard) or ears.wants_pause(heard) or ears.wants_sleep(heard):
            self._say(lines.later(self.rng))  # "shut up", "not now": a line, then a nap
            return ""
        before = list(self.memory)
        if ears.meaningful(heard, answering=True):
            self.memory.append(("them", heard.strip()))
        rules = ears.asks_rules(heard)
        if rules is not None:  # the rules are the script's, said as written, never the model's (D42)
            self.suggestion = rules
            self._ask(lines.rules(rules))
            return None
        answering = now - self.asked_at <= self.options.answer_seconds
        if ears.meaningful(heard, answering):
            turned, answer = self._turn(heard, now, before, answering)
            if turned:
                return answer
        return self._scripted(heard, now, before, answering)

    def _turn(self, heard: str, now: float, before: list[tuple[str, str]], answering: bool, quiet: bool = False) -> tuple[bool, Choice | str | None]:
        """The talk model's turn (brain/agent.py): it says its line and runs its tools.
        (False, None) when it gave nothing or failed, and the scripted line is said
        instead; else (True, what _hear answers). A headcount said is still taken at
        its word, and a sweep's count kept, as the scripted router does."""
        spoken = ears.count_said(heard) or (ears.bare_number(heard) if answering else None)
        seats = spoken if spoken is not None else self.seats
        suggestion = lines.suggested(seats) if spoken is not None else self.suggestion
        facts: dict[str, Any] = {
            "transcript": [list(e) for e in before], "remembered": self.facts.remembered(), "memory": self.facts,
            "games": lines.game_names(), "minimum": dict(lines.MINIMUM), "seats": seats, "answering": answering,
            "minutes": max(0.0, now - self.started_at) / 60,
        }
        if suggestion is not None:
            facts["suggestion"] = lines.game_name(suggestion)
        if quiet:
            facts["quiet"] = True
        table = _Counting(self.table)
        try:
            outcome = agent.run_turn(table, "lobby", heard, facts, agent.LOBBY)
        except Exception:  # the talk is decoration: a failure is the scripted line
            outcome = None
        if outcome is None:
            return False, None
        if spoken is not None:
            self._settled(spoken)
            self.table.seated(spoken)
            self.suggestion = suggestion
        if table.counted is not None:  # count_table: as _count, and the suggestion for it
            self.seats, self.seen, self.counted_at = table.counted, True, self.table.now()
            State(phase="welcome", seats=self.seats).report(self.table)
            self.suggestion = lines.suggested(self.seats)
        if spoken is not None or table.counted is not None:
            self.later = lines.nudges(self.suggestion, self.rng)
        if "forget" in outcome.ran:
            self.memory.clear()  # a forgotten fact must not survive in recent dialogue
        if outcome.said:
            self.memory.append(("ROB", outcome.said))
            self.quiet_since = self.replied_at = self.table.now()
            if outcome.said.rstrip().endswith("?"):
                named = ears.game_named(outcome.said)
                if named is not None:
                    self.suggestion = named  # "So, Imposter?": a yes takes it
                self.asked_at = self.replied_at
                self.offered_at = self.asked_at if named is not None else float("-inf")
        else:
            self.quiet_since = max(self.quiet_since, now)
        if outcome.game is not None:
            return True, Choice(outcome.game, heard, self._counted(self.table.now()), self.seen)
        if outcome.nap:
            if not outcome.said:
                self._say(lines.later(self.rng))  # the way to wake him
            return True, ""
        return True, None

    def _scripted(self, heard: str, now: float, before: list[tuple[str, str]], answering: bool) -> Choice | str | None:
        """The scripted router, offline or when the talk model gave nothing (D39)."""
        rules = ears.asks_rules(heard)
        if rules is not None:
            self.suggestion = rules
            self._ask(lines.rules(rules))
            return None
        game = ears.game_named(heard)
        if game is not None:
            return Choice(game, heard, self._counted(now), self.seen)
        if ears.wants_count(heard):
            self._say(lines.looking(self.rng))
            self._count()
            self._hellos()
            self._suggest()
            return None
        offered = now - self.offered_at <= self.options.answer_seconds
        spoken = ears.count_said(heard) or (ears.bare_number(heard) if answering else None)
        if spoken is not None:
            if self.seen and spoken == self.seats:
                self._spoken(spoken)
            else:
                self._told(spoken)  # their number wins over the sweep
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
        """A headcount said in the welcome that matches the sweep: agreed (D39)."""
        self._ask(lines.count_agreed(spoken, self.suggestion))

    def _chat(self, heard: str, answering: bool, now: float, before: list[tuple[str, str]]) -> None:
        """Small talk: a reply that knows the talk so far (`before`, what was said before
        `heard`), the model's or a scripted one, never a line just said (D39, D42). A
        question back offers the suggestion only when it names it."""
        facts: dict[str, Any] = {"remembered": self.facts.remembered(), "answering": answering, "games": lines.game_names(), "transcript": [list(e) for e in before]}
        if self.seats > 0:
            facts["players"] = self.seats
        if self.suggestion is not None:
            facts["suggestion"] = lines.game_name(self.suggestion)
        said = [line for who, line in self.memory if who == "ROB"]
        line = _fit(self.table.chat("welcome", heard, **facts))
        if line is None or line in said:
            line = lines.chat_fallback(self.suggestion, self.rng, ears.small_talk(heard), said)
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


class _Counting:
    """The table as a talk turn sees it, keeping what a count_table sweep found."""

    def __init__(self, table: Table) -> None:
        self._table = table
        self.counted: int | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._table, name)

    def count(self) -> int:
        self.counted = self._table.count()
        return self.counted


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
