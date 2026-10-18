"""20 Questions, one player (or a group playing as one) against the robot.

The robot asks which way round, and either works:

  robot_guesses   the player thinks of something; the robot asks yes/no questions and
                  may guess at any point (a guess uses a question). A right guess wins
                  for the robot; twenty used up wins for the player, and the robot asks
                  what it was.
  player_guesses  code picks the secret from the offline table before the first
                  question, and it never changes. The player asks; the robot answers
                  yes, no or sort of, or "can't answer that one" (not counted). A right
                  guess wins; "hint" costs a question; "I give up", or twenty used,
                  reveals it.

The model (Table.chat, on the Mac) only words a question or picks an answer from a
fixed set; code counts, keeps the secret, checks every model line and decides who
won. With no model it plays from brain/games/twenty_things.py, and where that table
has the trait a question asks about, its answer wins, so the secret never drifts.

A rig fixes the random choices: {"mode": "player_guesses", "secret": "toaster"}.
"""

from __future__ import annotations

import random
import re
from typing import Any

from brain import ears, lines
from brain.games.common import Options, State, abandon, hear
from brain.games.twenty_things import KINDS, THINGS, TRAIT, TRAITS, Thing, Trait
from brain.table import Table

QUESTIONS = 20
NUDGE_AT = 8.0  # seconds of silence before a nudge
EASE_AT = 20.0  # ... before "take your time"
GONE_AT = 180.0  # ... before the robot stops waiting and ends the game
GUESS_FROM = 18  # offline, the robot guesses from this question on
MODEL_MISSES = 2  # model calls in a row that give nothing usable before it plays offline

ROBOT, PLAYER = "robot_guesses", "player_guesses"

_ALIASES: dict[str, Thing] = {a: t for t in THINGS for a in t.aliases}


class _Gone(Exception):
    """Nobody has said anything for GONE_AT seconds."""


def run(table: Table, rng: random.Random, seats: int, rig: dict[str, Any], options: Options, state: State) -> None:
    Twenty(table, rng, seats, rig, state).play()


class Twenty:
    def __init__(self, table: Table, rng: random.Random, seats: int, rig: dict[str, Any], state: State) -> None:
        self.table = table
        self.rng = rng
        self.seats = seats
        self.rig = rig
        self.state = state
        self.mode: str | None = rig.get("mode") if rig.get("mode") in (ROBOT, PLAYER) else None
        self.used = 0
        self.online = True
        self.misses = 0

    # --- the game ---------------------------------------------------------------------

    def play(self) -> None:
        self.table.look(1 if self.seats == 1 else None)
        self._report("choose")
        try:
            if self.mode is None:
                self.mode = self._choose()
            if self.mode == ROBOT:
                self._robot_guesses()
            else:
                self._player_guesses()
        except _Gone:
            self.table.say("I'll be here when you're back.")
            abandon(self.table, self.state)

    def _choose(self) -> str:
        self.table.mood("day")
        self.table.say("Twenty Questions. Want me to guess yours, or you guess mine?")
        for again in (True, False):
            heard = hear(self.table, 8.0)
            mode = _mode_said(heard)
            if mode == "either":
                break
            if mode is not None:
                return mode
            if again:
                self.table.say("You think of something and I guess, or the other way round?")
        mode = self.rng.choice((ROBOT, PLAYER))
        self.table.say("I'll pick, then. " + ("You think of something." if mode == ROBOT else "I've got one."))
        return mode

    def _report(self, phase: str) -> None:
        self.state.phase = phase
        self.state.extra = {"mode": self.mode, "questions": self.used, "left": QUESTIONS - self.used}
        self.state.report(self.table)

    def _end(self, winner: str, line: str) -> None:
        self.state.over = True
        self.state.winner = winner
        self.state.phase = "over"
        self.state.extra = {"mode": self.mode, "questions": self.used, "left": QUESTIONS - self.used}
        self.state.report(self.table)
        self.table.mood("win")
        self.table.say(line)
        self.table.quip("win", game="twenty", outcome="you won this one" if winner == "robot" else "the player beat you")
        self.table.say("Good game." if self.seats == 1 else lines.GOOD_GAME)

    def _await(self, nudge: str, ease: str, usable) -> str:
        """The next usable thing said. Silence gets a nudge, then "take your time", then
        quiet; "hold on" or "wait" pauses the nudges. Stop and reset end the game (hear)."""
        quiet = 0.0
        step = 0
        patient = False
        while True:
            chunk = NUDGE_AT if quiet < NUDGE_AT else EASE_AT - NUDGE_AT if quiet < EASE_AT else 20.0
            heard = hear(self.table, chunk)
            if heard.strip() and _holding(heard):
                self.table.say(self.rng.choice(("Sure, take your time.", "Take your time.", "No rush.")))
                patient, quiet = True, 0.0
                continue
            if heard.strip() and usable(heard):
                return heard
            quiet += chunk
            if quiet >= GONE_AT:
                raise _Gone()
            if patient:
                continue
            if step == 0 and quiet >= NUDGE_AT:
                self.table.say(nudge)
                step = 1
            elif step == 1 and quiet >= EASE_AT:
                self.table.say(ease)
                step = 2

    # --- the robot guesses ------------------------------------------------------------------

    def _robot_guesses(self) -> None:
        self._report("think")
        self.table.say("Think of something. Got one? Say ready.")
        while True:
            heard = self._await("Say ready when you've got one.", "Take your time.",
                                lambda h: _answer(h) is not None or ears.meaningful(h, answering=True) or "ready" in h)
            if "ready" in heard or _answer(heard) != "no":
                break
            self.table.say("No rush. Say ready when you've got one.")
        self.table.say(self.rng.choice(("Okay. Here we go.", "Alright, let's do this.", "Okay, game face on.")))
        self._report("questions")
        penalty = {t: 0 for t in THINGS}
        wrong: set[Thing] = set()
        asked: set[str] = set()
        history: list[list[str]] = []
        heard = ""
        joked = getting_warm = False
        react = ""
        for n in range(1, QUESTIONS + 1):
            remaining = _candidates(penalty, wrong)
            question, guess, trait = self._next_question(n, heard, history, remaining, asked)
            prefix = {10: "Question ten, halfway.", QUESTIONS - 4: "Five left.", QUESTIONS: "Last one. Here goes."}.get(n, "")
            if n >= QUESTIONS - 4:
                self.table.mood("tense")
            self.table.say(" ".join(p for p in (react, prefix, question) if p))
            react = ""
            heard = self._await("Yes, no, or sort of?", "Take your time.", lambda h: _answer(h) is not None)
            answer = _answer(heard)
            if answer is None or answer == "unknown":  # "don't know" still uses the question
                answer = "unknown"
            if answer == "win" and guess is None:
                guess = question  # they said "you got it" to an ordinary question
            self.used = n
            history.append([question, answer])
            self._report("questions")
            if guess is not None and answer in ("yes", "win"):
                name = guess.name if isinstance(guess, Thing) else guess
                self._end("robot", self.rng.choice((f"Yes! {_cap(name)}. Too easy.", f"Called it. {_cap(name)}.",
                                                    f"{_cap(name)}! I knew it.")))
                return
            if answer == "win":
                answer = "yes"
            if isinstance(guess, Thing):
                wrong.add(guess)
            if guess is not None:
                react = self.rng.choice(("Worth a shot.", "Hm. Not that.", "Okay, okay.", "Damn."))
            if trait is not None:
                asked.add(trait[0].key)
                _score(penalty, trait, answer)
                left = _candidates(penalty, wrong)
                if not joked and left and penalty[left[0]] > 0 and n >= 4:
                    joked = True
                    react = self.rng.choice(("Nothing I know fits that. Bold.", "Huh. You're making this up, aren't you?",
                                             "A living rock. Bold."))
                elif not getting_warm and len(left) <= 3 and n >= 5 and penalty[left[0]] == 0:
                    getting_warm = True
                    react = "Ooh, I'm getting somewhere."
        self._end_robot_lost(_candidates(penalty, wrong))

    def _end_robot_lost(self, remaining: list[Thing]) -> None:
        self.table.say("Twenty's up. You win. What was it?")
        heard = hear(self.table, 10.0)
        thing = _thing_in(heard)
        if thing is not None:
            line = "Ugh, I was so close." if thing in remaining[:3] else f"{_cap(thing.name)}? I was nowhere near."
        elif ears.meaningful(heard, answering=True):
            line = "Huh. Never would've got that."
        else:
            line = "Keep your secrets, then."
        self._end("player", line)

    def _next_question(self, n: int, heard: str, history: list[list[str]], remaining: list[Thing],
                       asked: set[str]) -> tuple[str, Thing | str | None, tuple[Trait, bool] | None]:
        """(what to say, the guess if it is one, the trait it asks about if known)."""
        if self.online:
            line = self.table.chat(
                "twenty.guesser", heard, history=history, number=n, left=QUESTIONS - n,
                rules="You are playing 20 Questions and guessing what the player thinks of. Ask one short "
                      "yes/no question that narrows it down. To guess, write GUESS: and the thing, like "
                      "GUESS: a toaster. Never repeat a question.",
            )
            fit = _fit_question(line, history)
            if fit is not None:
                self.misses = 0
                return fit
            self.misses += 1
            if self.misses >= MODEL_MISSES:
                self.online = False
        trait = None if len(remaining) <= 2 or n >= GUESS_FROM else _best_trait(remaining, asked)
        if trait is None:
            guess = self.rng.choice(remaining[:2] if remaining else list(THINGS))
            return f"Is it {guess.name}?", guess, None
        return trait.question, None, (trait, False)

    # --- the player guesses -----------------------------------------------------------------

    def _player_guesses(self) -> None:
        secret = _ALIASES.get(str(self.rig.get("secret", "")).lower()) or self.rng.choice(THINGS)
        hinted: set[str] = set()
        wild: Thing | None = None
        self._report("questions")
        self.table.say(self.rng.choice(("Okay, I've got one. Ask me yes or no questions.",
                                        "Got it. Ask away, yes or no questions.")))
        while self.used < QUESTIONS:
            heard = self._await("Got a question for me?", "Take your time. Want a hint? Just say hint.",
                                lambda h: ears.meaningful(h, answering=True))
            said = " ".join(_tokens(heard))
            if _has(said, ("give up", "i quit", "just tell me", "tell me what it is", "you win")):
                self._end("robot", self.rng.choice((f"It was {secret.name}. So close. Kind of.",
                                                    f"{_cap(secret.name)}! It was {secret.name}.")))
                return
            if _has(said, ("hint", "clue")):
                self.used += 1
                self._say_counted(_hint(secret, hinted, self.rng))
                continue
            guess = _thing_in(heard, guess_only=True)
            if guess is not None or (tail := _guess_tail(heard)) is not None:
                if guess is secret or (guess is None and self._model_says_yes(heard, secret)):
                    self.used += 1
                    self._end("player", self.rng.choice((
                        f"Yes! It was {secret.name}. Got it in {lines.number_word(self.used)}.",
                        f"Yes! {_cap(secret.name)}. Nice.",
                    )))
                    return
                self.used += 1
                if guess is not None:
                    close = _overlap(guess, secret)
                    if wild is None and close < 0.15:
                        wild = guess
                    line = "Ooh, close. Not it though." if close >= 0.7 else self.rng.choice(
                        (f"Nope, not {guess.name}.", "Nope.", f"No. Not {guess.name}."))
                else:
                    line = self.rng.choice(("Nope.", "Nope, not that.", "No."))
                self._say_counted(line)
                continue
            if not _asks(heard):
                continue  # talking among themselves
            answer = self._answer(heard, secret)
            if answer is None:
                self.table.say("Can't answer that one. Try another way.")
                continue
            self.used += 1
            self._say_counted(self.rng.choice({"yes": ("Yes.", "Yep.", "Yeah."), "no": ("No.", "Nope.", "Nah."),
                                               "sort of": ("Sort of.", "Kind of.", "Ehh, sort of.")}[answer]))
        line = f"That's twenty. It was {secret.name}."
        if wild is not None and self.rng.random() < 0.5:
            line += f" Still thinking about {wild.name}, though."
        self._end("robot", line)

    def _say_counted(self, line: str) -> None:
        self._report("questions")
        extra = {10: "That's ten. Halfway.", QUESTIONS - 5: "Five left.", QUESTIONS - 1: "Last one. Make it count."}
        if self.used >= QUESTIONS - 5:
            self.table.mood("tense")
        self.table.say(" ".join(p for p in (line, extra.get(self.used, "")) if p))

    def _answer(self, heard: str, secret: Thing) -> str | None:
        """"yes", "no", "sort of", or None for can't answer. The table wins where it has the
        trait; elsewhere the model answers, if there is one."""
        hit = _trait_of(heard)
        if hit is not None:
            trait, flipped = hit
            mine = secret.answer(trait.key)
            if flipped:
                mine = {"yes": "no", "no": "yes"}.get(mine, mine)
            if trait.key in KINDS or trait.key in secret.yes or trait.key in secret.sort or not self.online:
                return mine
            theirs = self._ask_model(heard, secret)
            return theirs if theirs in ("yes", "no", "sort of") else mine
        theirs = self._ask_model(heard, secret)
        return theirs if theirs in ("yes", "no", "sort of") else None

    def _ask_model(self, heard: str, secret: Thing) -> str | None:
        if not self.online:
            return None
        line = self.table.chat(
            "twenty.answer", heard, secret=secret.name, question=heard, options=["yes", "no", "sort of", "unknown"],
            rules="You are playing 20 Questions and you are thinking of the secret. Answer the player's question "
                  "with exactly one of: yes, no, sort of, unknown.",
        )
        answer = _model_answer(line)
        if answer is None:
            self.misses += 1
            if self.misses >= MODEL_MISSES:
                self.online = False
        else:
            self.misses = 0
        return answer

    def _model_says_yes(self, heard: str, secret: Thing) -> bool:
        return self._ask_model(heard, secret) == "yes"


# --- reading what was said ------------------------------------------------------------------


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower().replace("’", "'").replace("-", " "))


def _has(said: str, phrases: tuple[str, ...]) -> bool:
    padded = f" {said} "
    return any(f" {p} " in padded for p in phrases)


def _cap(name: str) -> str:
    return name[:1].upper() + name[1:]


_ROBOT_WORDS = ("you guess", "guess mine", "guess my", "i'll think", "ill think", "i will think", "i think of one",
                "i'll pick", "i'll choose", "i have one", "i've got one", "i got one", "first one", "the first",
                "you guessing", "you're guessing")
_PLAYER_WORDS = ("i'll guess", "ill guess", "i will guess", "let me guess", "i want to guess", "i guess yours",
                 "guess yours", "guess your", "you think", "you pick", "you choose", "you go first", "second one",
                 "the second", "the other", "other way", "your turn to think", "me guess", "i'm guessing")
_EITHER = ("either", "whatever", "don't care", "dont care", "you decide", "up to you", "doesn't matter", "surprise me")


def _mode_said(heard: str) -> str | None:
    said = " ".join(_tokens(heard))
    if not said:
        return None
    if _has(said, _PLAYER_WORDS):
        return PLAYER
    if _has(said, _ROBOT_WORDS):
        return ROBOT
    if _has(said, _EITHER):
        return "either"
    if said in ("me", "i do", "i will", "mine"):
        return PLAYER if said != "mine" else ROBOT
    if said in ("you", "you do", "you will", "yours"):
        return ROBOT if said != "yours" else PLAYER
    return None


_HOLD = ("hold on", "wait", "one sec", "one second", "give me a sec", "give me a second", "hang on",
         "let me think", "gimme a sec", "just a sec", "a sec", "a second")


def _holding(heard: str) -> bool:
    tokens = _tokens(heard)
    return 0 < len(tokens) <= 5 and _has(" ".join(tokens), _HOLD)


_UNKNOWN = ("don't know", "dont know", "not sure", "no idea", "idk", "no clue", "unsure", "who knows")
_SORT = ("sort of", "kind of", "kinda", "sorta", "sometimes", "maybe", "partly", "a little", "depends", "somewhat",
         "a bit", "ish", "could be", "in a way")
_WIN = ("you got it", "got it", "that's it", "thats it", "you're right", "youre right", "bingo", "exactly",
        "how did you know", "yes it is", "correct", "nailed it", "that's right", "thats right")
_NO_PHRASES = ("don't think so", "dont think so", "not really", "of course not")
_YES_PHRASES = ("think so", "guess so", "uh huh", "it is", "it does", "it can", "of course")
_YES = {"yes", "yeah", "yep", "yup", "yea", "ya", "yah", "right", "true", "definitely", "absolutely", "sure", "mhm",
        "totally", "affirmative", "correct", "usually", "mostly"}
_NO = {"no", "nope", "nah", "not", "isn't", "doesn't", "can't", "wrong", "never", "negative", "nay", "don't"}


def _answer(heard: str) -> str | None:
    """A yes/no answer to the robot: "yes", "no", "sort of", "unknown", "win" (a right
    guess, or "you got it"), or None for anything else."""
    tokens = _tokens(heard)
    said = " ".join(tokens)
    if not said:
        return None
    if _has(said, _UNKNOWN):
        return "unknown"
    if _has(said, _WIN):
        return "win"
    if _has(said, _NO_PHRASES):
        return "no"
    if _has(said, _SORT):
        return "sort of"
    for t in tokens:
        if t in _YES:
            return "yes"
        if t in _NO:
            return "no"
    if _has(said, _YES_PHRASES):
        return "yes"
    return None


def _model_answer(line: Any) -> str | None:
    if not isinstance(line, str):
        return None
    said = " ".join(_tokens(line))
    if not said:
        return None
    if _has(said, ("unknown", "can't say", "cant say", "not sure", "don't know", "dont know", "can't answer")):
        return "unknown"
    if _has(said, ("sort of", "kind of", "kinda", "sometimes", "partly")):
        return "sort of"
    for t in said.split():
        if t in ("yes", "yeah", "yep"):
            return "yes"
        if t in ("no", "nope"):
            return "no"
    return None


_ASK_WORDS = {"is", "are", "does", "do", "can", "could", "would", "will", "was", "were", "has", "have", "did",
              "should", "it's", "its", "am", "may", "might"}


def _asks(heard: str) -> bool:
    """A question, not chatter: a question mark, or a question word up front."""
    return "?" in heard or any(t in _ASK_WORDS for t in _tokens(heard)[:3])


def _trait_of(text: str) -> tuple[Trait, bool] | None:
    """The trait a question asks about, by its longest matching phrase, and whether it
    asks the opposite ("is it real?" -> madeup, flipped)."""
    padded = " " + " ".join(_tokens(text)) + " "
    best: tuple[int, Trait, bool] | None = None
    for trait in TRAITS:
        for words, flipped in ((trait.words, False), (trait.anti, True)):
            for w in words:
                if f" {w} " in padded and (best is None or len(w) > best[0]):
                    best = (len(w), trait, flipped)
    return None if best is None else (best[1], best[2])


_GUESS = re.compile(
    r"(?:^| )(?:is it|is that|it's|its|it is|is this|my guess is|i guess|i think it's|i think its|i think it is|"
    r"guess|was it|could it be|would it be|how about|what about)(?: an?| the| some)? (.+)$"
)
_TAIL_FILLER = ("right", "then", "maybe", "or not", "or something", "perhaps", "please", "now", "huh")


def _guess_text(text: str) -> str | None:
    said = " ".join(_tokens(text))
    m = _GUESS.search(said)
    if m is None:
        return None
    tail = m.group(1).strip()
    changed = True
    while changed:
        changed = False
        for f in _TAIL_FILLER:
            if tail.endswith(" " + f):
                tail, changed = tail[: -len(f) - 1].strip(), True
    return tail or None


def _thing_in(text: str, guess_only: bool = False) -> Thing | None:
    """A thing from the table that the words name: as a guess ("is it a dog?", "a dog"),
    or, unless guess_only, anywhere ("it was my dog")."""
    said = " ".join(_tokens(text))
    bare = re.sub(r"^(?:an?|the|some) ", "", said)
    if bare in _ALIASES:
        return _ALIASES[bare]
    tail = _guess_text(text)
    if tail is not None and tail in _ALIASES:
        return _ALIASES[tail]
    if guess_only:
        return None
    padded = f" {said} "
    found = [(len(a), t) for a, t in _ALIASES.items() if f" {a} " in padded]
    return max(found, key=lambda f: f[0])[1] if found else None


def _guess_tail(text: str) -> str | None:
    """A guess at something not in the table ("is it a kazoo?"): a short name after "is
    it", that no trait question matches."""
    tail = _guess_text(text)
    if tail is None or len(tail.split()) > 3 or _trait_of(text) is not None:
        return None
    return tail


def _fit_question(line: Any, history: list[list[str]]) -> tuple[str, Thing | str | None, tuple[Trait, bool] | None] | None:
    """A model's next question, if it is one short yes/no question and not a repeat:
    (the question, the guess if it is one, the trait if one matches)."""
    if not isinstance(line, str):
        return None
    s = line.strip().strip('"').strip()
    m = re.match(r"(?i)^guess\s*:\s*(.+)$", s)
    if m:
        name = re.sub(r"(?i)^is it\s+", "", m.group(1).strip(" .?!\"")).strip()
        if not name or len(name.split()) > 5 or "\n" in name:
            return None
        question = f"Is it {name}?"
        if _repeat(question, history):
            return None
        return question, _thing_in(question, guess_only=True) or name, None
    if "\n" in s or s.count("?") != 1 or not s.endswith("?") or len(s.split()) > 15:
        return None
    if _repeat(s, history):
        return None
    thing = _thing_in(s, guess_only=True)  # a model guess comes as GUESS: (above); only a thing
    if thing is not None:                  # the table knows by name counts as one here
        return s, thing, None
    return s, None, _trait_of(s)


def _repeat(question: str, history: list[list[str]]) -> bool:
    mine = _tokens(question)
    return any(_tokens(q) == mine for q, _ in history)


# --- the offline guesser -----------------------------------------------------------------------


def _candidates(penalty: dict[Thing, int], wrong: set[Thing]) -> list[Thing]:
    """The things that fit the answers best (fewest contradictions), not yet guessed."""
    left = [t for t in THINGS if t not in wrong]
    if not left:
        return []
    low = min(penalty[t] for t in left)
    return [t for t in left if penalty[t] == low]


def _score(penalty: dict[Thing, int], trait: tuple[Trait, bool], answer: str) -> None:
    key, flipped = trait[0].key, trait[1]
    if answer not in ("yes", "no"):
        return
    if flipped:
        answer = "no" if answer == "yes" else "yes"
    for t in penalty:
        has = t.answer(key)
        if (answer == "yes" and has == "no") or (answer == "no" and has == "yes"):
            penalty[t] += 1


def _best_trait(remaining: list[Thing], asked: set[str]) -> Trait | None:
    """The unasked trait that splits what is left most evenly; None if none splits it."""
    best: tuple[float, Trait] | None = None
    for trait in TRAITS:
        if trait.key in asked:
            continue
        yes = sum(1.0 if t.answer(trait.key) == "yes" else 0.5 if t.answer(trait.key) == "sort of" else 0.0
                  for t in remaining)
        split = min(yes, len(remaining) - yes)
        if split >= 1 and (best is None or split > best[0]):
            best = (split, trait)
    return None if best is None else best[1]


def _overlap(a: Thing, b: Thing) -> float:
    both = a.yes | b.yes
    return len(a.yes & b.yes) / len(both) if both else 0.0


def _hint(secret: Thing, hinted: set[str], rng: random.Random) -> str:
    """One trait the secret has that has not been hinted, kinds last; then its first letter."""
    open_ = [k for k in secret.yes if k not in hinted]
    specific = [k for k in open_ if k not in KINDS] or open_
    if specific:
        key = rng.choice(sorted(specific))
        hinted.add(key)
        return "Hint: " + TRAIT[key].hint
    letter = re.sub(r"^(?:an?|the) ", "", secret.name.lower())[:1].upper()
    return f"Hint: it starts with {letter}."
