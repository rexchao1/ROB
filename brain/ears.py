"""What the host makes of what it heard: game names, head counts, seat numbers and
guesses, parsed out of a transcript.

The input is lower-cased speech-to-text output (faster-whisper on the gateway),
punctuation and all: "player four.", "4", "i vote for four", "there are six of us".
Every parser answers None rather than guess: a vote or a whisper the host cannot make
out is asked for again (OUT-OF-SCOPE.md), so a wrong number is worse than none.

Whisper hears short numbers as words that sound like them ("for", "won", "too").
Those count only right after "player", "number" or "seat" (D91), because "to" and
"for" fill ordinary sentences and "me too" is not a vote.

A command to the host (stop, reset, vote now) is a short plain utterance, at most a
few words with no negation, that is the command and little else (D87): "let's reset",
"stop the game please"; a sentence that merely contains the word is talk.
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
# Short plain commands (D87, D88, D92): the phrase, with at most these wrappers around it.
_STOP = ("stop the game", "stop this game", "end the game", "end this game", "quit the game", "quit this game",
         "cancel the game", "stop playing")
_RESET = ("reset", "reset the game", "reset it", "restart", "restart the game", "restart this game", "restart it",
          "start over", "start again", "start the game over", "start it over", "begin again")
_ROUND_AGAIN = ("restart the round", "restart this round", "redo the round", "redo this round", "this round again",
                "the round again", "round again", "do the round again", "do this round again")
_VOTE_NOW = ("vote", "let's vote", "lets vote", "ready to vote", "vote now", "time to vote", "we're ready",
             "were ready", "we are ready", "can we vote")
_COMMAND_WRAPPERS = frozenset({
    "okay", "ok", "alright", "hey", "rob", "um", "uh", "so", "yeah", "yes", "let's", "lets", "can", "we", "could",
    "please", "just", "now", "i", "want", "to", "wanna", "guys", "everyone", "then", "already", "should", "it",
    "all", "we're", "were", "ready", "think", "go", "good",
})
_NEGATIONS = frozenset({"don't", "dont", "not", "never", "no", "nope", "nah", "isn't", "wrong"})
_AGREE = ("okay", "ok", "fine", "yes", "yeah", "yep", "sure", "start", "go ahead", "go on", "let's go", "lets go",
          "never mind", "nevermind", "that's right", "thats right", "correct", "right")
# A vote or a guess: a negated seat is no seat, and a correction takes the last number.
_NEGATED = frozenset({"not", "except", "but", "never", "don't", "dont", "without", "nobody", "neither", "nor"})
_CORRECTIONS = frozenset({"no", "wait", "actually", "sorry", "mean", "rather", "instead", "scratch"})
_NUMBER_FILLERS = frozenset({"uh", "um", "er", "umm", "hmm", "like"})
_DROPPED = (("out", "of", "ten"), ("out", "of", "10"), ("on", "the", "scale"))


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
        if i > 0 and tokens[i - 1] in ("you", "me", "us"):
            continue  # "you two", "me too": people, not a count
        if i + 1 < len(tokens) and tokens[i + 1] in ("sec", "second", "seconds", "minute", "moment"):
            continue  # "one sec"
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


def _corrected(tokens: list[str]) -> list[str]:
    """What stands after the last correction word ("four, no wait, two" -> ["two"])."""
    cut = max((i for i, t in enumerate(tokens) if t in _CORRECTIONS), default=-1)
    return tokens[cut + 1 :] if cut >= 0 else tokens


def _one_number(tokens: list[str]) -> int | None:
    """The single number an utterance names, or None when it names none, several, or
    negates one (D91). A soundalike counts only after a pointer; a correction word
    ("no wait", "actually", "i mean") keeps the last number."""
    if any(t in _NEGATED for t in tokens) or " no one " in f" {' '.join(tokens)} ":
        return None
    tokens = _corrected(tokens)
    named = {n for _, n in _numbers(tokens)} | set(_pointed(tokens))
    return named.pop() if len(named) == 1 else None


def _command(text: str, phrases: tuple[str, ...], max_tokens: int) -> bool:
    """A short plain command (D87): at most max_tokens words, no negation, one of the
    phrases with nothing but wrappers ("okay", "please", "can we") around it."""
    tokens = _tokens(text)
    if not 0 < len(tokens) <= max_tokens or any(t in _NEGATIONS for t in tokens):
        return False
    said = " ".join(tokens)
    for phrase in sorted(phrases, key=len, reverse=True):
        if f" {phrase} " in f" {said} ":
            rest = said.replace(phrase, " ", 1).split()
            if all(t in _COMMAND_WRAPPERS for t in rest):
                return True
    return False


_REQUEST = frozenset({
    "let's", "lets", "play", "please", "we", "want", "to", "how", "about", "can", "could", "start", "time", "with",
    "people", "players", "of", "us", "again", "okay", "ok", "yeah", "i", "wanna", "the", "a", "game", "do", "round",
    "try", "go", "for", "one", "more", "another", "hey", "rob", "maybe", "um", "uh", "now", "instead", "then",
    "sure", "and", "there", "are", "we're", "were", "some", "everyone", "all", "next", "this", "that",
})


def _game_at(tokens: list[str]) -> tuple[str, int, int] | None:
    """The first game the tokens name, with the span of its name: (game, start, end)."""
    for i, t in enumerate(tokens):
        for game, names in _GAMES.items():
            if t in names or t.rstrip("s") in names:
                return game, i, i + 1
        if i + 1 < len(tokens) and (t, tokens[i + 1]) in _SPLIT_GAMES:
            return _SPLIT_GAMES[(t, tokens[i + 1])], i, i + 2
    return None


def game_named(text: str) -> str | None:
    """The game a request names (D94): the name as the whole utterance or in a request
    frame ("let's play mafia", "wordle please", "imposter with six people"), the first
    if several. The name inside other talk ("that was a hot seat") is None."""
    tokens = _tokens(text)
    found = _game_at(tokens)
    if found is None:
        return None
    game, start, end = found
    rest = tokens[:start] + tokens[end:]
    return game if all(t in _REQUEST or _strict(t) is not None for t in rest) else None


def game_mentioned(text: str) -> str | None:
    """The game a sentence mentions anywhere ("that was a hot seat yesterday"): the
    doubtful hearing D94 confirms with "Hot Seat? Say yes to play it."."""
    found = _game_at(_tokens(text))
    return None if found is None else found[0]


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
    """An utterance that is just a number ("six.", "6", "uh six"), in lo..hi; no
    soundalike without a pointer ("sex", "for"), no "you two" (D91)."""
    tokens = [t for t in _tokens(text) if t not in ("uh", "um", "er", "like", "its", "it's", "just")]
    if not 1 <= len(tokens) <= 2:
        return None
    n = _one_number(tokens)
    return n if n is not None and lo <= n <= hi else None


def seat_said(text: str, seats: int) -> int | None:
    """The seat a vote or a whisper names (D91): "player four", "four", "4", "number
    four", "i vote for four", "player for"; only 1..seats, else None. Two seats, a
    negation ("anyone but four") or "me too" are None; a correction keeps the last."""
    n = _one_number(_tokens(text))
    return n if n is not None and 1 <= n <= seats else None


def number_said(text: str, lo: int = 1, hi: int = 10) -> int | None:
    """A guess (D95): the one number in a short answer, in lo..hi ("six", "i'd say
    seven", "seven out of ten", "nine, no, eight"); None for none, several, out of
    range, or a number inside a longer sentence (more than six words)."""
    tokens = [t for t in _tokens(text) if t not in _NUMBER_FILLERS]
    for dropped in _DROPPED:
        for i in range(len(tokens) - len(dropped) + 1):
            if tuple(tokens[i : i + len(dropped)]) == dropped:
                tokens = tokens[:i] + tokens[i + len(dropped) :]
                break
    if len(tokens) > 6:
        return None
    n = _one_number(tokens)
    return n if n is not None and lo <= n <= hi else None


def agrees(text: str) -> bool:
    """A plain go-ahead after the host's count ("okay", "yes", "fine, start"): a reply
    with a "no" or a "not" in it is a disagreement (D89)."""
    tokens = _tokens(text)
    if any(t in _NEGATIONS for t in tokens):
        return False
    t = " " + " ".join(tokens) + " "
    return any(f" {a} " in t for a in _AGREE)


def wants_to_stop(text: str) -> bool:
    """A short plain request to stop, reset or restart the round (D27, D87)."""
    return wants_to_reset(text) or wants_round_restart(text) or _command(text, _STOP, 5)


def wants_to_reset(text: str) -> bool:
    """"reset", "start over", "restart" said on their own: the welcome again, ending any
    game (D38, D87); a sentence that contains the word is talk."""
    return _command(text, _RESET, 5)


def wants_round_restart(text: str) -> bool:
    """"restart the round", "redo the round", "this round again" (D88): Mafia starts the
    round's night again; other games stop."""
    return _command(text, _ROUND_AGAIN, 5)


_PAUSE = re.compile(r"\b(?:pause|pause the game|hold the game|shut up|be quiet|quiet please|stop talking|hush)\b")
_RESUME = re.compile(r"\b(?:resume|unpause|un pause|continue|keep going|carry on|play on|we're back|were back|i'm back|im back|back to the game)\b")
_HALT = {"stop", "wait"}  # said on their own, with at most a word or two of _HALT_FILL, a pause
_HALT_FILL = {"stop", "wait", "please", "okay", "ok", "rob", "hey", "robot"}


def wants_pause(text: str) -> bool:
    """"pause", "shut up", "be quiet", or a bare "stop" or "wait" ("okay stop", "rob,
    wait"): the host holds the game until someone says to carry on. Never "stop the
    game" (that ends it) and never a resume. "Hold on" is the welcome's "later"."""
    if wants_to_stop(text) or wants_resume(text):
        return False
    tokens = _tokens(text)
    if 0 < len(tokens) <= 4 and set(tokens) <= _HALT_FILL and _HALT & set(tokens):
        return True
    return bool(_PAUSE.search(" ".join(tokens)))


def wants_resume(text: str) -> bool:
    """"resume", "unpause", "we're back", "keep going": the end of a pause. "let's go"
    and "go on" are a yes, never a resume (D93)."""
    return bool(_RESUME.search(" ".join(_tokens(text))))


# --- the host's own commands: the deal, the speaker, a repeat --------------------------

_SHORT = 6  # the deal's answers count only in an utterance this short, so table talk does not trigger them
_SHOW = ("i'm leaning in", "im leaning in", "leaning in", "i'm looking", "im looking", "i am looking",
         "i'm here", "im here", "i am here", "show me", "show it", "show the card", "show my card",
         "i can't see it", "i cant see it", "can't see it", "cant see it", "let me see")
_SEEN = ("got it", "saw it", "seen it", "i've seen it", "ive seen it", "move on", "next one", "next player",
         "next turn", "next person", "i'm done", "im done", "all done")
_SEEN_ALONE = {"done", "next", "skip"}  # these count only with nothing but _SEEN_FILL around them
_SEEN_FILL = {"okay", "ok", "alright", "please", "rob", "yeah", "yes", "cool", "thanks", "i'm", "im", "we're", "were"}
_NOT = ("not", "haven't", "havent", "didn't", "didnt", "can't", "cant", "don't", "dont", "never")


def wants_card(text: str) -> bool:
    """A player at the private screen says they are there: "I'm leaning in", "I'm
    looking", "show me", "I can't see it". Short utterances only."""
    return len(_tokens(text)) <= _SHORT and _has(text, _SHOW)


def saw_card(text: str) -> bool:
    """A player says they have seen their card: "got it", "I saw it", "done", "next",
    "move on". Short utterances only, and never with a "not" ("I haven't seen it")."""
    tokens = _tokens(text)
    if not 0 < len(tokens) <= _SHORT or _has(text, _NOT):
        return False
    if _has(text, _SEEN):
        return True
    return bool(_SEEN_ALONE & set(tokens)) and set(tokens) <= _SEEN_ALONE | _SEEN_FILL


_SPEAKER_WORDS = {"speaker", "speakers", "sound", "audio"}
_MAC = {"mac", "mack", "macbook", "laptop", "computer"}
_ROBOT = {"robot", "yourself", "own"}  # "your own speaker"
_SWITCH = {"use", "switch", "change", "move", "put", "set", "play", "talk", "speak", "through", "back", "go"}
_SPEAKER_FILL = {"the", "to", "on", "your", "voice", "please", "okay", "ok", "rob"}  # "speaker mac", "sound on the mac"


def speaker_said(text: str) -> str | None:
    """Where the voice should play, said out loud: "change your speaker to the Mac",
    "play the sound through the laptop", "speaker mac" -> "mac"; "use your own
    speaker", "speaker robot" -> "robot"; None for anything else. It needs a speaker
    word ("speaker", "sound", "audio", or "voice" with "through", "play" or "on"), a
    place, and a word that asks for the change ("use", "switch", "through"...) unless
    it is only the speaker and the place ("speaker mac", "sound on the Mac"), so "is it
    a computer speaker?" or "sound like a robot" in a game is not a command. Whisper hears "the Mac" as "the back". With both places named,
    the last one counts ("from the robot to the Mac")."""
    tokens = _tokens(text)
    words = set(tokens)
    if not (words & _SPEAKER_WORDS or ("voice" in words and words & {"through", "play", "on"})):
        return None
    if not words & _SWITCH and (len(tokens) > 4 or not words <= _SPEAKER_WORDS | _MAC | _ROBOT | _SPEAKER_FILL):
        return None
    place = None
    for i, t in enumerate(tokens):
        if t in _MAC or (t == "back" and i > 0 and tokens[i - 1] == "the"):
            place = "mac"
        elif t in _ROBOT:
            place = "robot"
    if place is None and words & {"your", "yours"} and words & _SWITCH:
        place = "robot"  # "use your speaker", "switch back to yours"
    return place


_REPEAT = ("say that again", "say it again", "repeat that", "repeat it", "can you repeat", "could you repeat",
           "please repeat", "what did you say", "come again")


def wants_repeat(text: str) -> bool:
    """"Say that again", "can you repeat", "what did you say": the host's last line again."""
    return _has(text, _REPEAT)


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
    game = game_mentioned(text)
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
    """The group is ready to vote before the day's time is up (D92): a short plain
    "let's vote", "we're ready to vote", "vote now"; a longer or negated sentence
    ("i'm not ready to vote", "we're ready to hear from player two") is talk."""
    return _command(text, _VOTE_NOW, 5)
