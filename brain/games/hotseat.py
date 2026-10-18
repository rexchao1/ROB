"""Hot Seat (Workstream X), after the table has been gathered.

The host names a category, then turns to each player still in, left to right, and says
"Player two, go!". The player names something in the category before the time runs
out: 5 s in the first round, a second less each round, never under 3 s. Silence, a
pass, a repeat or a wrong answer is out. The last player in wins. A new category comes
each round.

Judging is code: an answer on the category's list counts; anything else goes to the
talk model ("yes" or "no", Table.chat "hotseat.judge"), and with no model it counts
unless it is plainly from another category's list. Standard library only.

A rig fixes the categories for a demo: {"categories": ["fruits", "colors"]}.
"""

from __future__ import annotations

import random
import re
from typing import Any

from brain import lines
from brain.games.common import Options, State, finish, hear
from brain.games.hotseat_words import CATEGORIES, GIVE_UP, NOISE
from brain.table import Table

START_SECONDS = 5
FLOOR_SECONDS = 3
MAX_ROUNDS = 12  # after this many rounds with two or more still in, it's a tie

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_ARTICLES = {"a", "an", "the"}
# Words around an answer that are not the answer: "um, I'll say banana".
_LEAD_IN = NOISE | {"i", "i'll", "ill", "say", "let", "let's", "me", "it's", "its", "is", "my", "answer", "go",
                    "with", "how", "about", "maybe", "uhh", "gonna", "going", "to", "and", "of", "some", "uh"}

INTRO = "Hot Seat! I say a category, you name one, fast. Freeze, repeat or miss, and you're out."
_FIRST = ("First category: {}.", "Category one: {}.")
_NEXT = ("Next up: {}.", "New category: {}.", "{}. Here we go.")
_REACT = ("Nice.", "Yep.", "Good.", "Quick.", "Sure.", "Okay!", "Ooh.", "Smooth.")
_OUT = {
    "time": ("Time! {p}, you're out.", "Too slow. {p}, you're out.", "Nothing? {p}, you're out."),
    "pass": ("A pass is an out. {p}, you're out.", "No pass in Hot Seat. {p}, you're out."),
    "repeat": ("Already taken. {p}, you're out.", "Somebody said that. {p}, you're out."),
    "wrong": ("Nope, doesn't count. {p}, you're out.", "I can't give you that. {p}, you're out."),
}
_SEND_OFF = ("Tough break.", "Good run.", "Rest those brain cells.", "We'll miss you.")
_TIE = "You're all too good at this. I'm calling it a tie."


def _norm_word(w: str) -> str:
    """Simple plurals to one form, the same for the list and for what was heard."""
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 4 and w.endswith(("ches", "shes", "xes", "sses")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _tokens(text: str) -> list[str]:
    words = _WORD.findall(text.lower().replace("’", "'"))
    return [_norm_word(w) for w in words if w not in _ARTICLES]


def norm(text: str) -> str:
    """"The Bananas" -> "banana"."""
    return " ".join(_tokens(text))


_KEYS: dict[str, frozenset[str]] = {k: frozenset(norm(a) for a in answers) for k, (_, answers) in CATEGORIES.items()}


def _find(tokens: list[str], keys: frozenset[str]) -> str | None:
    """The first listed answer in what was heard, the longest at each place."""
    for i in range(len(tokens)):
        for n in (3, 2, 1):
            phrase = " ".join(tokens[i : i + n])
            if len(tokens) - i >= n and phrase in keys:
                return phrase
    return None


def _judge(table: Table, label: str, heard: str, answer: str) -> bool | None:
    """The talk model's ruling on an answer not on the list; None when there is none."""
    chat = getattr(table, "chat", None)
    if chat is None:
        return None
    reply = chat("hotseat.judge", heard, category=label, answer=answer)
    words = _WORD.findall((reply or "").lower())
    if not words:
        return None
    if words[0] in ("yes", "yeah", "yep", "valid", "counts"):
        return True
    if words[0] in ("no", "nope", "invalid"):
        return False
    return None


def judge(table: Table, category: str, heard: str, used: set[str]) -> tuple[str, str | None]:
    """("ok", answer key) or (why out, None): "time", "pass", "repeat" or "wrong"."""
    label = CATEGORIES[category][0]
    tokens = _tokens(heard)
    key = _find(tokens, _KEYS[category])
    if key is None:
        text = " ".join(_WORD.findall(heard.lower().replace("’", "'")))
        if any(f" {phrase} " in f" {text} " for phrase in GIVE_UP):
            return "pass", None
        content = [t for t in tokens if t not in _LEAD_IN]
        if not content:
            return "time", None
        key = " ".join(content[:4])
        if key in used:
            return "repeat", None
        elsewhere = any(_find(tokens, keys) for k, keys in _KEYS.items() if k != category)
        ruling = _judge(table, label, heard, key)
        if ruling is False or (ruling is None and elsewhere):
            return "wrong", None
    if key in used:
        return "repeat", None
    return "ok", key


def _seconds(round_no: int) -> int:
    return max(FLOOR_SECONDS, START_SECONDS - (round_no - 1))


def run(table: Table, rng: random.Random, seats: int, rig: dict[str, Any], options: Options, state: State) -> None:
    order = [str(c) for c in rig.get("categories") or []]
    unknown = [c for c in order if c not in CATEGORIES]
    if unknown:
        raise ValueError(f"no Hot Seat category {unknown}; they are {sorted(CATEGORIES)}")
    rest = [c for c in CATEGORIES if c not in order]
    rng.shuffle(rest)
    order += rest

    state.extra.update(category=None, seconds=START_SECONDS)
    state.phase = "category"
    state.report(table)
    table.look(None)
    table.say(INTRO)

    seconds = START_SECONDS
    while len(state.living) > 1:
        if state.round >= MAX_ROUNDS:
            table.look(None)
            table.say(_TIE)
            finish(table, state, None, rng)
            return
        state.round += 1
        category = order[(state.round - 1) % len(order)]
        label = CATEGORIES[category][0]
        if _seconds(state.round) != seconds:
            seconds = _seconds(state.round)
            table.look(None)
            table.say(f"Faster now. {lines.number_word(seconds).capitalize()} seconds.")
        state.phase = "category"
        state.extra.update(category=category, seconds=seconds)
        state.report(table)
        table.mood("tense")
        table.say(rng.choice(_FIRST if state.round == 1 else _NEXT).format(label))

        state.phase = "turn"
        state.report(table)
        before = len(state.living)
        used: set[str] = set()
        for seat in sorted(state.living):
            if len(state.living) == 1:
                break
            table.look(seat)
            table.say(f"{lines.player(seat)}, go!")
            heard = hear(table, seconds)
            verdict, key = judge(table, category, heard, used)
            if verdict == "ok" and key is not None:
                used.add(key)
                if rng.random() < 0.5:
                    table.say(rng.choice(_REACT))
                continue
            line = rng.choice(_OUT[verdict]).format(p=lines.player(seat))
            if rng.random() < 0.4:
                line += " " + rng.choice(_SEND_OFF)
            state.eliminate(seat)
            state.report(table)
            table.say(line)
        if 1 < len(state.living) < before:
            left = len(state.living)
            table.look(None)
            table.say("Down to two. Here we go." if left == 2 else f"{lines.number_word(left).capitalize()} of you left.")

    winner = state.living[0]
    table.look(winner)
    table.say(f"{lines.player(winner)} wins Hot Seat!")
    table.look(None)
    finish(table, state, str(winner), rng)
