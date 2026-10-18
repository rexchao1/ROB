"""What the host makes of what it heard: game names, head counts, seat numbers and
guesses, parsed out of a transcript.

The input is lower-cased speech-to-text output (faster-whisper on the gateway),
punctuation and all: "player four.", "4", "i vote for four", "there are six of us".
Every parser answers None rather than guess: a vote or a whisper the host cannot make
out is asked for again (OUT-OF-SCOPE.md), so a wrong number is worse than none.

Whisper hears short numbers as words that sound like them ("for", "won", "too").
Those count only right after "player", "number" or "seat", or when the whole
utterance is a word or two, because "to" and "for" fill ordinary sentences.
"""

from __future__ import annotations

import re

_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}
_SOUNDALIKES = {
    "won": 1, "wan": 1, "to": 2, "too": 2, "tu": 2, "tree": 3, "for": 4, "fore": 4,
    "fo": 4, "fiv": 5, "sicks": 6, "sex": 6, "ate": 8, "nein": 9, "tin": 10,
}
_POINTERS = ("player", "players", "number", "seat", "seats", "plaire")
_GAMES = {
    "mafia": ("mafia", "mafias", "maffia", "mafiya", "mafiosa", "mafioso", "werewolf", "werewolves", "warewolf"),
    "imposter": ("imposter", "imposters", "impostor", "impostors", "imposture", "imposer"),
    "wavelength": ("wavelength", "wavelengths", "wavelenght"),
}
_SPLIT_GAMES = {("in", "poster"): "imposter", ("im", "poster"): "imposter", ("wave", "length"): "wavelength",
                ("wave", "lengths"): "wavelength", ("ma", "fia"): "mafia"}
_GAMES["hotseat"] = ("hotseat", "hotseats")
_SPLIT_GAMES.update({("hot", "seat"): "hotseat", ("hot", "seats"): "hotseat"})
_GAMES["wordle"] = ("wordle", "wordles", "wordel", "wurdle", "werdle")
_SPLIT_GAMES.update({("word", "game"): "wordle", ("word", "games"): "wordle", ("words", "game"): "wordle"})
_SPLIT_GAMES.update({("twenty", "questions"): "twenty", ("20", "questions"): "twenty",
                     ("twenty", "question"): "twenty", ("20", "question"): "twenty"})
_STOP = (
    "stop the game", "end the game", "quit the game", "cancel the game", "restart the game",
    "restart the round", "start over", "stop playing",
)
_VOTE_NOW = ("let's vote", "lets vote", "ready to vote", "vote now", "we're ready", "were ready", "time to vote")
_AGREE = ("okay", "ok", "fine", "yes", "yeah", "yep", "sure", "start", "go ahead", "let's go", "lets go",
          "never mind", "nevermind", "that's right", "thats right", "correct", "right")


def _tokens(text: str) -> list[str]:
    """Words and digits, lower-case; "we're" stays one token, "player-four" splits."""
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower().replace("\u2019", "'"))


def _strict(token: str) -> int | None:
    """A number word or digits, never a soundalike."""
    if token.isdigit():
        return int(token)
    return _WORDS.get(token)


def _loose(token: str) -> int | None:
    n = _strict(token)
    return n if n is not None else _SOUNDALIKES.get(token)


def _numbers(tokens: list[str]) -> list[tuple[int, int]]:
    """(index, value) of every strict number in the utterance, skipping "no one",
    "anyone"-style uses of "one" ("that one", "the one")."""
    out = []
    for i, t in enumerate(tokens):
        n = _strict(t)
        if n is None:
            continue
        if t == "one" and i > 0 and tokens[i - 1] in ("no", "that", "this", "the", "which", "every", "any", "some"):
            continue
        out.append((i, n))
    return out


def _pointed(tokens: list[str]) -> list[int]:
    """The numbers right after "player", "number" or "seat" (soundalikes allowed there)."""
    out = []
    for i, t in enumerate(tokens[:-1]):
        if t in _POINTERS:
            n = _loose(tokens[i + 1])
            if n is not None:
                out.append(n)
    return out


def _one_number(tokens: list[str]) -> int | None:
    """The single number an utterance names, or None when it names none or several."""
    pointed = set(_pointed(tokens))
    if len(pointed) == 1:
        return pointed.pop()
    if len(pointed) > 1:
        return None
    strict = {n for _, n in _numbers(tokens)}
    if len(strict) == 1:
        return strict.pop()
    if len(strict) > 1:
        return None
    if 1 <= len(tokens) <= 2:
        loose = {n for t in tokens if (n := _SOUNDALIKES.get(t)) is not None}
        if len(loose) == 1:
            return loose.pop()
    return None


def game_named(text: str) -> str | None:
    """The game a sentence names ("let's play mafia" -> "mafia"), the first if several."""
    tokens = _tokens(text)
    for i, t in enumerate(tokens):
        for game, names in _GAMES.items():
            if t in names or t.rstrip("s") in names:
                return game
        if i + 1 < len(tokens) and (t, tokens[i + 1]) in _SPLIT_GAMES:
            return _SPLIT_GAMES[(t, tokens[i + 1])]
    return None


def count_said(text: str) -> int | None:
    """A head count said out loud: "there are six of us", "six of us", "we're six",
    "we are six", "6 players", "six people", "we have six". A stray number is not a
    count ("player four", "let's play mafia", "there are two mafia")."""
    tokens = _tokens(text)
    for i, t in enumerate(tokens):
        n = _strict(t)
        if not n:
            continue
        prev1 = tokens[i - 1] if i >= 1 else ""
        prev2 = " ".join(tokens[i - 2 : i]) if i >= 2 else ""
        nxt = tokens[i + 1 : i + 3]
        if nxt[:2] == ["of", "us"] or nxt[:1] in (["players"], ["people"], ["humans"]):
            return n
        lead = prev1 in ("we're", "were", "there's", "theres") or prev2 in ("we are", "there are", "we have", "we've got", "there is")
        if lead and (not nxt or nxt[0] in ("of", "us", "here", "now", "today", "total", "in", "tonight", "playing")):
            return n
    return None


def bare_number(text: str, lo: int = 1, hi: int = 20) -> int | None:
    """An utterance that is just a number ("six.", "6", "uh six"), in lo..hi."""
    tokens = [t for t in _tokens(text) if t not in ("uh", "um", "er", "like", "its", "it's", "just")]
    if not 1 <= len(tokens) <= 2:
        return None
    n = _one_number(tokens)
    return n if n is not None and lo <= n <= hi else None


def seat_said(text: str, seats: int) -> int | None:
    """The seat a vote or a whisper names: "player four", "four", "4", "number four",
    "i vote for four", "player for"; only 1..seats, else None."""
    n = _one_number(_tokens(text))
    return n if n is not None and 1 <= n <= seats else None


def number_said(text: str, lo: int = 1, hi: int = 10) -> int | None:
    """A guess: the one number an utterance names, in lo..hi ("six", "i think seven",
    "7"); None for none, several, or out of range."""
    n = _one_number(_tokens(text))
    return n if n is not None and lo <= n <= hi else None


def agrees(text: str) -> bool:
    """A go-ahead after the host's count ("okay", "yes", "fine, start")."""
    t = " " + " ".join(_tokens(text)) + " "
    return any(f" {a} " in t for a in _AGREE)


def wants_to_stop(text: str) -> bool:
    """The group asks to stop or restart (D27: the group may restart by saying so)."""
    t = " ".join(_tokens(text))
    return wants_to_reset(text) or any(p in t for p in _STOP)


_RESET = re.compile(r"\b(?:reset|restart(?:ed|ing)?|start (?:over|again)|begin again)\b")


def wants_to_reset(text: str) -> bool:
    """"reset", "start over", "restart": the welcome again, ending any game (D38)."""
    return bool(_RESET.search(" ".join(_tokens(text))))


_PAUSE = re.compile(r"\b(?:pause|pause the game|hold the game)\b")
_RESUME = re.compile(r"\b(?:resume|unpause|un pause|continue|keep going|play on|we're back|were back|i'm back|im back|back to the game|let's go|lets go|go on)\b")


def wants_pause(text: str) -> bool:
    """"pause": the host holds the game until someone says to carry on."""
    return bool(_PAUSE.search(" ".join(_tokens(text)))) and not wants_resume(text)


def wants_resume(text: str) -> bool:
    """"resume", "unpause", "we're back", "keep going": the end of a pause."""
    return bool(_RESUME.search(" ".join(_tokens(text))))


# --- the welcome's conversation (D40 to D43) ---------------------------------------------

_YES = ("yes", "yeah", "yep", "yup", "yea", "ya", "sure", "okay", "ok", "alright", "all right", "sounds good",
        "let's do it", "lets do it", "let's go", "lets go", "do it", "go for it", "why not", "i'm in", "im in",
        "we're in", "were in", "absolutely", "definitely", "of course", "perfect", "deal", "fine", "let's play",
        "lets play", "go ahead", "bet", "love it", "down")
_NO = ("no", "nah", "nope", "not that", "something else", "another", "different", "other", "pass", "not really",
       "don't", "dont", "rather not")
_LATER = ("not now", "not yet", "maybe later", "later", "give us a minute", "give us a sec", "give us a second",
          "hold on", "one sec", "one second", "in a minute", "in a bit")
_ASK_RULES = ("how do", "how does", "how is", "how's", "hows", "how to", "how you play", "what is", "what's", "whats",
              "explain", "rules", "teach", "remind us", "never played", "know how")
_ASK_GAMES = ("what games", "which games", "what can we play", "what do you have", "what have you got",
              "what you got", "what do you got", "options")
_ASK_PICK = ("what should we play", "what do you recommend", "recommend", "suggest", "you pick", "you choose",
             "your call", "which one", "what game", "up to you")
_FILLER = {"oh", "uh", "um", "umm", "uhh", "hmm", "hm", "mm", "mhm", "ah", "eh", "er", "huh", "you", "the", "a",
           "and", "so", "it", "is", "to", "of", "i", "like", "just", "well"}
# What faster-whisper writes for room noise, a cough or a long silence.
_PHANTOMS = ("thank you", "thanks", "thanks for watching", "thank you for watching", "thank you so much",
             "please subscribe", "subtitles by the amara org community", "you", "bye", "bye bye", "okay",
             "music", "applause", "laughter", "silence", "foreign", "so", "oh", "yeah")


def _has(text: str, phrases: tuple[str, ...]) -> bool:
    t = " " + " ".join(_tokens(text)) + " "
    return any(f" {p} " in t for p in phrases)


def says_no(text: str) -> bool:
    """A "no" to the host's suggestion ("nah", "something else")."""
    return _has(text, _NO)


def says_yes(text: str) -> bool:
    """A go-ahead to the host's suggestion ("sure", "yeah, let's do it"): short, and no "no" in it."""
    tokens = _tokens(text)
    return 0 < len(tokens) <= 8 and _has(text, _YES) and not says_no(text)


def wants_later(text: str) -> bool:
    """"Not now", "give us a minute": the host stops asking and waits."""
    return _has(text, _LATER)


def asks_rules(text: str) -> str | None:
    """The game a question about the rules names ("how do you play imposter?"), else None.
    "How about Mafia?" is a choice, not a question."""
    game = game_named(text)
    if game is None or _has(text, ("how about", "what about")):
        return None
    return game if _has(text, _ASK_RULES) else None


def asks_games(text: str) -> bool:
    """"What games do you have?\""""
    return _has(text, _ASK_GAMES)


def asks_pick(text: str) -> bool:
    """"What should we play?", "you pick\""""
    return _has(text, _ASK_PICK)


def meaningful(text: str, answering: bool = False) -> bool:
    """Something said to the host, not room noise: three or more real words, or, right
    after the host asked something, one. Whisper's phantoms for noise ("you", "thank
    you", "oh") are never meaningful (D43)."""
    tokens = _tokens(text)
    if not tokens or " ".join(tokens) in _PHANTOMS:
        return False
    words = [t for t in tokens if t not in _FILLER]
    return len(words) >= (1 if answering else 3)


def wants_to_vote(text: str) -> bool:
    """The group is ready to vote before the day's time is up."""
    t = " ".join(_tokens(text))
    return any(p in t for p in _VOTE_NOW)
