"""Wordle, out loud (Workstream X), after the table has been gathered.

The host picks a secret five-letter word; the table gets six guesses. One player plays
alone; with more seats the seats take turns (the host turns to each and says whose turn
it is), but anyone may say the guess. A guess is a word said aloud ("crane", "is it
crane?") or spelled ("c r a n e", "see are ay en ee", "c as in cat"). A word the host
does not know, or that is not five letters, uses no guess. The host starts its answer
with the word it heard, so a mishearing can be undone at once ("no", "wrong, I said
stare") for free; the last guess is confirmed before it is scored.

The feedback is spoken short ("Crane. A is spot on, R is in there somewhere."), and
the board (each row a list of [letter, "g" | "y" | "x"]) is reported for the
dashboard. "What do we know?" gets a recap; "I give up" reveals the word.

State (Table.report): game "wordle", phase "guess" then "over", over, winner
("players" or None), and guesses, left, board, turn (the seat whose turn it is, or
None for one player).

A rig fixes the word: {"word": "crane"}. Standard library only (the QNX referee).
"""

from __future__ import annotations

import random
import re
from collections import Counter
from typing import Any

from brain import ears, lines
from brain.games.common import Options, State, abandon, finish, hear
from brain.games.wordle_words import ALLOWED, ANSWERS
from brain.table import Table

GUESSES = 6
LISTEN_SECONDS = 8.0  # one listen for a guess
CONFIRM_SECONDS = 5.0  # the last guess's "final answer?"
GIVE_UP_LISTENS = 15  # silent listens in a row (about two minutes) before the host ends it
MAX_NOT_CAUGHT = 2  # "didn't catch that" at most this often in a row, then quiet

# --- hearing a guess ---------------------------------------------------------------------

_LETTERS = {c: c for c in "abcdefghijklmnopqrstuvwxyz"}
_LETTERS.update({
    "ay": "a", "bee": "b", "be": "b", "see": "c", "sea": "c", "cee": "c", "dee": "d", "ee": "e",
    "ef": "f", "eff": "f", "gee": "g", "aitch": "h", "eye": "i", "aye": "i", "jay": "j", "kay": "k",
    "el": "l", "ell": "l", "em": "m", "en": "n", "oh": "o", "owe": "o", "pee": "p", "pea": "p",
    "queue": "q", "cue": "q", "are": "r", "ar": "r", "es": "s", "ess": "s", "tea": "t", "tee": "t",
    "you": "u", "vee": "v", "ex": "x", "why": "y", "zee": "z", "zed": "z",
})
# Five-letter words people say around a guess; a guess that is one of them still counts
# when nothing else in the sentence is a word.
_FRAME = {"guess", "think", "maybe", "about", "there", "their", "which", "would", "could", "going", "gonna",
          "sorry", "again", "right", "words", "hello", "yeahs", "first", "spell", "letter", "wanna", "let's"}
_TRYING = ("guess", "try", "is it", "how about", "what about", "spell", "my word", "maybe", "it's", "its")
_WRONG = ("wrong", "i said", "misheard", "not what i said", "didn't say", "didnt say", "that's not what",
          "thats not what", "undo", "you heard", "not what")
_BARE_NO = {"no", "nope", "nah", "not", "that", "uh", "um", "oh"}
_GIVE_UP = ("i give up", "we give up", "give up", "tell me the word", "tell us the word", "what's the word",
            "whats the word", "what is the word", "just tell", "you win")
_RECAP = ("recap", "remind me", "remind us", "what do we know", "what have we got", "what we got", "where are we",
          "say that again", "repeat", "what letters", "which letters", "what's left", "whats left", "so far")


def _words(text: str) -> list[str]:
    """Lower-case words; "c-r-a-n-e" and "C. R. A." split into letters."""
    return re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower().replace("’", "'"))


def _has(tokens: list[str], phrases: tuple[str, ...]) -> bool:
    t = " " + " ".join(tokens) + " "
    return any(f" {p} " in t for p in phrases)


def _spelled(tokens: list[str]) -> list[str]:
    """Each run of spelled letters: "c r a n e" -> ["crane"]; "double you" is w, and
    "c as in cat" is c."""
    runs: list[str] = []
    cur: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        letter, step = None, 1
        if t == "double" and i + 1 < len(tokens) and tokens[i + 1] in ("u", "you"):
            letter, step = "w", 2
        elif t in _LETTERS:
            letter = _LETTERS[t]
        if letter is None:
            if cur:
                runs.append("".join(cur))
                cur = []
            i += 1
            continue
        if tokens[i + step : i + step + 2] == ["as", "in"] or tokens[i + step : i + step + 1] == ["like"]:
            step += 3 if tokens[i + step] == "as" else 2  # "as in cat", "like cat"
        cur.append(letter)
        i += step
    if cur:
        runs.append("".join(cur))
    return runs


def read_guess(text: str) -> tuple[str | None, str | None]:
    """What a guess said: (an allowed word, None); (None, a five-letter word the host does
    not know); or (None, None) when no five letters were made out. Spelled letters win
    over words; of several words, the last that is not just talk ("guess", "think"),
    which counts only on its own in a short try."""
    tokens = _words(text)
    unknown: list[str] = []
    for run in reversed(_spelled(tokens)):
        tries = [run] if len(run) == 5 else [run[-5:], run[:5]] if len(run) > 5 else []
        for w in tries:
            if w in ALLOWED:
                return w, None
        if len(run) == 5:
            unknown.append(run)
    five = [t for t in tokens if len(t) == 5 and t.isalpha()]
    known = [t for t in five if t in ALLOWED]
    plain = [t for t in known if t not in _FRAME]
    if plain:
        return plain[-1], None
    if known and len(tokens) <= 3:  # "guess?", "is it about": only a short try counts
        return known[-1], None
    unknown += [t for t in five if t not in _FRAME]
    return None, (unknown[-1] if unknown else None)


def _correction(tokens: list[str]) -> bool:
    """"No", "nope", "wrong", "I said stare": the host misheard the last guess."""
    if _has(tokens, _WRONG):
        return True
    return 0 < len(tokens) <= 3 and all(t in _BARE_NO for t in tokens) and any(t in ("no", "nope", "nah") for t in tokens)


def _attempt(tokens: list[str]) -> bool:
    """Something that sounds like a try at a guess, not the table talking among itself."""
    content = [t for t in tokens if t not in ("uh", "um", "hmm", "oh", "the", "a", "i", "so", "like", "okay")]
    return 0 < len(content) <= 3 or _has(tokens, _TRYING)


# --- scoring and the feedback ------------------------------------------------------------


def score(guess: str, answer: str) -> list[str]:
    """Standard Wordle marks per letter: "g" right spot, "y" in the word elsewhere, "x"
    not (again). Repeated letters count only as often as the answer has them, greens first."""
    marks = ["x"] * 5
    left: Counter[str] = Counter()
    for i, (g, a) in enumerate(zip(guess, answer)):
        if g == a:
            marks[i] = "g"
        else:
            left[a] += 1
    for i, g in enumerate(guess):
        if marks[i] == "x" and left[g] > 0:
            marks[i] = "y"
            left[g] -= 1
    return marks


def _listing(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _unique(letters: list[str]) -> list[str]:
    return list(dict.fromkeys(letters))


_NOTHING = ("Nothing. Ouch.", "Not one letter. Ouch.", "Zero for five. Bold strategy.", "Nothing. At least we know what it isn't.")


def feedback(guess: str, marks: list[str], rng: random.Random) -> str:
    """"Crane. A is spot on, R is in there somewhere." Not every letter: the board has them."""
    head = guess.capitalize() + "."
    greens = _unique([c.upper() for c, m in zip(guess, marks) if m == "g"])
    yellows = _unique([c.upper() for c, m in zip(guess, marks) if m == "y"])
    if not greens and not yellows:
        return f"{head} {rng.choice(_NOTHING)}"
    parts: list[str] = []
    if marks.count("g") == 4:
        parts.append(rng.choice(("so close, four are spot on", "four in the right spot, so close")))
    elif greens:
        one = len(greens) == 1
        parts.append(rng.choice((
            f"{_listing(greens)} {'is' if one else 'are'} spot on",
            f"{_listing(greens)} {'is right where it belongs' if one else 'are right where they belong'}",
        )))
    if yellows:
        named = [f"another {c}" if c in greens else c for c in yellows]
        one = len(named) == 1
        parts.append(rng.choice((
            f"{_listing(named)} {'is' if one else 'are'} in there somewhere",
            f"{_listing(named)} {'is' if one else 'are'} in it, wrong spot" + ("" if one else "s"),
        )))
    text = ", ".join(parts)
    return f"{head} {text[0].upper()}{text[1:]}."


_WIN = {
    1: ("First try? Okay, who told you.", "One guess. I'm a little scared of you."),
    2: ("Two guesses. That's showing off.", "Two. Okay, genius."),
    3: ("Three guesses. Very nice.", "Got it in three. Smooth."),
    4: ("Four guesses. Solid.", "Four. Nicely done."),
    5: ("Five guesses. Phew.", "Five. Made me sweat a little."),
    6: ("Six. Cutting it close.", "On the last one. My heart."),
}
_LOSE = ("Tough one.", "That one was mean, I'll admit it.", "Next time.")
_NUDGE = ("Throw a word at me. Any word.", "Take a guess, even a bad one helps.", "Need a starter? Something with lots of vowels.")
_HOLD = ("Take your time.", "Sure, no rush.", "Got it, I'll wait.")
_NOT_CAUGHT = "Didn't catch that. Spell it?"
_POSITIONS = ("first", "second", "third", "fourth", "last")


def _intro(seats: int) -> list[str]:
    first = "Wordle time. I've got a five-letter word, and you get six guesses."
    if seats == 1:
        return [first, "Say a word, or spell it out."]
    return [first, f"Take turns, any of you can say it. {lines.player(1)}, you're up."]


def _turn(seat: int, rng: random.Random) -> str:
    return rng.choice((f"{lines.player(seat)}, your turn.", f"{lines.player(seat)}, you're up."))


def recap(board: list[list[list[str]]]) -> str:
    """What the board says so far, in at most three short sentences."""
    if not board:
        return "Nothing yet. Give me a word."
    spots: dict[int, str] = {}
    somewhere: list[str] = []
    seen_good: set[str] = set()
    for row in board:
        for i, (c, m) in enumerate(row):
            if m == "g":
                spots[i] = c.upper()
                seen_good.add(c)
            elif m == "y":
                somewhere.append(c.upper())
                seen_good.add(c)
    out_letters = _unique([c.upper() for row in board for c, m in row if m == "x" and c not in seen_good])
    somewhere = [c for c in _unique(somewhere) if c not in spots.values()]
    said: list[str] = []
    if spots:
        said.append(_listing([f"{c} is {_POSITIONS[i]}" for i, c in sorted(spots.items())]) + ".")
    if somewhere:
        said.append(f"{_listing(somewhere)} {'is' if len(somewhere) == 1 else 'are'} in there somewhere.")
    if out_letters:
        said.append(f"Ruled out: {', '.join(out_letters)}.")
    return "Here's what we know. " + " ".join(said) if said else "Nothing yet. Give me a word."


# --- the game -------------------------------------------------------------------------------


def run(table: Table, rng: random.Random, seats: int, rig: dict[str, Any], options: Options, state: State) -> None:
    answer = str(rig.get("word") or rng.choice(ANSWERS)).lower()
    if len(answer) != 5 or not answer.isalpha():
        raise ValueError(f"a Wordle rig needs a five-letter word: {rig}")
    board: list[list[list[str]]] = []
    tried: list[str] = []

    def turn_seat() -> int | None:
        return None if seats == 1 else len(tried) % seats + 1

    def report() -> None:
        state.phase = "over" if state.over else "guess"
        state.round = len(tried)
        state.extra = {"guesses": len(tried), "left": GUESSES - len(tried), "board": [list(map(list, r)) for r in board], "turn": turn_seat()}
        state.report(table)

    def start_turn() -> None:
        seat = turn_seat()
        if seat is not None:
            table.look(seat)
            table.say(_turn(seat, rng))

    state.phase = "guess"
    report()
    table.mood("day")
    table.look(1 if seats == 1 else None)
    for line in _intro(seats):
        table.say(line)
    if seats > 1:
        table.look(1)

    silent = 0
    nudged = False
    not_caught = 0
    undo_ok = False

    while True:
        heard = hear(table, LISTEN_SECONDS)
        tokens = _words(heard)
        if not ears.meaningful(heard, answering=True):
            silent += 1
            if silent == 1 and not nudged:
                table.say(rng.choice(_NUDGE))
                nudged = True
            elif silent >= GIVE_UP_LISTENS:
                table.say(f"I'll take that as a pass. The word was {answer}.")
                abandon(table, state)
                table.say(lines.GOOD_GAME)
                return
            continue
        silent = 0

        if _has(tokens, _GIVE_UP):
            table.say(f"Fine. The word was {answer}.")
            abandon(table, state)
            table.say(lines.GOOD_GAME)
            return
        if ears.wants_later(heard):
            table.say(rng.choice(_HOLD))
            nudged = True
            continue
        if _has(tokens, _RECAP):
            table.say(recap(board))
            continue

        word, unknown = read_guess(heard)
        if undo_ok and _correction(tokens):
            undo_ok = False
            board.pop()
            tried.pop()
            report()
            if word is None:
                table.say(rng.choice(("My bad. What was it?", "Oops. Say it again?")))
                continue
        undo_ok = False

        if word is None:
            if unknown is not None and _attempt(tokens):
                table.say(f"{unknown.capitalize()}? Not in my dictionary. Try another.")
                not_caught = 0
            elif _attempt(tokens) and not_caught < MAX_NOT_CAUGHT:
                table.say(_NOT_CAUGHT)
                not_caught += 1
            continue  # the table talking among itself: stay quiet
        not_caught = 0
        if word in tried:
            table.say(f"Already tried {word}.")
            continue

        if len(tried) == GUESSES - 1:  # the last guess: make sure before it counts
            table.say(f"{word.capitalize()}, final answer?")
            reply = hear(table, CONFIRM_SECONDS)
            other, _ = read_guess(reply)
            if other is not None and other != word and other not in tried:
                word = other
            elif ears.says_no(reply) or _correction(_words(reply)):
                table.say("Okay, say it again.")
                continue

        marks = score(word, answer)
        tried.append(word)
        board.append([[c, m] for c, m in zip(word, marks)])
        nudged = False

        if word == answer:
            state.over = True
            report()
            table.say(f"{word.capitalize()}. That's it! {rng.choice(_WIN[len(tried)])}")
            finish(table, state, "players", rng)
            return
        if len(tried) == GUESSES:
            table.say(feedback(word, marks, rng))
            table.say(f"Out of guesses. The word was {answer}. {rng.choice(_LOSE)}")
            abandon(table, state)
            table.say(lines.GOOD_GAME)
            return

        report()
        table.say(feedback(word, marks, rng))
        undo_ok = True
        left = GUESSES - len(tried)
        if left == 2:
            table.say("Two guesses left.")
        elif left == 1:
            table.mood("tense")
            table.say("Last guess. Make it count.")
        start_turn()
