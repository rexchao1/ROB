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
    "stop this game", "end this game", "quit this game", "cancel this game", "exit the game",
    "exit this game", "leave the game", "end game", "exit game", "quit game", "stop game",
    "we're done", "were done", "i'm done playing", "im done playing", "let's stop", "lets stop",
    "no more games", "enough of this game",
)
_SLEEP = ("go to sleep", "go to bed", "take a nap", "nap time", "time for bed", "good night rob", "goodnight rob", "go to sleep rob")
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
    "we are six", "6 players", "six people", "we have six", "just me". A stray number is
    not a count ("player four", "let's play mafia", "there are two mafia")."""
    if _has(text, _JUST_ME):
        return 1
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
    return wants_to_reset(text) or wants_sleep(text) or _phrase(t, _STOP)


def _phrase(t: str, phrases: tuple[str, ...]) -> bool:
    """One of `phrases` in the joined tokens `t`, as whole words ("end game", not "weekend games")."""
    padded = f" {t} "
    return any(f" {p} " in padded for p in phrases)


def hard_command(text: str) -> bool:
    """Words that act whenever they are said, even over the host's own line: a stop, a
    reset, "go to sleep", or a pause ("pause", "shut up", "be quiet")."""
    return wants_to_stop(text) or wants_pause(text)


def wants_sleep(text: str) -> bool:
    """"Go to sleep", "take a nap": the host ends any game and naps until a tap."""
    return _phrase(" ".join(_tokens(text)), _SLEEP)


_RESET = re.compile(r"\b(?:reset|restart|start (?:over|again)|begin again)\b")  # not "restarted": "you never restarted?" is talk


def wants_to_reset(text: str) -> bool:
    """"reset", "start over", "restart": the welcome again, ending any game (D38)."""
    return bool(_RESET.search(" ".join(_tokens(text))))


_PAUSE = re.compile(r"\b(?:pause|pause the game|hold the game|shut up|be quiet|quiet please|stop talking|hush)\b")
_RESUME = re.compile(r"\b(?:resume|unpause|un pause|continue|keep going|play on|we're back|were back|i'm back|im back|back to the game|let's go|lets go|go on)\b")
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
    """"resume", "unpause", "we're back", "keep going": the end of a pause."""
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
              "what you got", "what do you got", "options", "what else", "anything else", "other games", "what other")
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


_JUST_ME = ("just me", "only me", "just myself", "by myself", "on my own")
_COUNT_US = ("count us", "count everyone", "count the room", "count the table", "count heads", "count people",
             "look around", "look at us", "check the room", "how many do you see", "how many of us do you see",
             "who's here", "whos here", "see who's here", "see whos here")


def wants_count(text: str) -> bool:
    """"Count us", "look around": the host should sweep the table and count it."""
    return _has(text, _COUNT_US)


def asks_games(text: str) -> bool:
    """"What games do you have?\""""
    return _has(text, _ASK_GAMES)


def asks_pick(text: str) -> bool:
    """"What should we play?", "you pick\""""
    return _has(text, _ASK_PICK)


_HELLO = ("hi", "hello", "hey", "hiya", "howdy", "yo", "sup", "what's up", "whats up", "wassup", "what up",
          "good evening", "good morning", "good afternoon", "greetings")
_HOW = ("how are you", "how are ya", "how you doing", "how're you", "how's it going", "hows it going",
        "how is it going", "how have you been", "how's your night", "hows your night", "you good", "you okay", "you ok")
_WHO = ("who are you", "what are you", "what's your name", "whats your name", "what is your name", "who's this",
        "whos this", "who is this", "introduce yourself")
_JOKE = ("joke", "jokes", "something funny", "make me laugh", "make us laugh")
_NAME = {"rob", "robb", "robbie", "robot"}
_TO_YOU = re.compile(r"^(?:what|who|how|where|why|when|are|can|could|do|did|will|would|have|is)\b.*\b(?:you|your|ya|yourself)\b")
_RUN_ON = 40  # words: past this, an utterance is the transcriber running on, not something said to the host


def small_talk(text: str) -> str | None:
    """What kind of small talk an utterance is, for the scripted answer to it: "joke"
    ("tell us a joke"), "who" ("who are you?"), "how" ("how are you?"), "hello" (a
    short "hi", "hey rob", "what's up"), else None."""
    if _has(text, _JOKE):
        return "joke"
    if _has(text, _WHO):
        return "who"
    if _has(text, _HOW):
        return "how"
    if _has(text, _HELLO) and len(_tokens(text)) <= 4:
        return "hello"
    return None


def addressed(text: str) -> bool:
    """Said to the host, however short: a greeting, "how are you", "who are you", a joke
    asked for, a question with "you" in it, or its name ("rob", "robot")."""
    tokens = _tokens(text)
    return (
        small_talk(text) is not None
        or _has(text, _HELLO)
        or bool(_NAME & set(tokens))
        or bool(_TO_YOU.search(" ".join(tokens)))
    )


def side_talk(text: str) -> bool:
    """A line said to the host that no game listen could use, for a short reply in
    character during play (docs/CHAT-PLAN.md, step 7): addressed to it (addressed()),
    and with no seat or number in it, no short yes or no, no "let's vote", no hard
    command, no request to repeat, no card or memory command, and not transcriber junk."""
    tokens = _tokens(text)
    if not tokens or junk(text) or not addressed(text):
        return False
    if _numbers(tokens) or _pointed(tokens) or _one_number(tokens) is not None:
        return False
    if len(tokens) <= 3 and (says_yes(text) or says_no(text)):
        return False
    return not (
        hard_command(text)
        or wants_resume(text)
        or wants_to_vote(text)
        or wants_repeat(text)
        or wants_card(text)
        or saw_card(text)
        or memory_command(text) is not None
        or speaker_said(text) is not None
    )


def junk(text: str) -> bool:
    """What the transcriber writes when it loses the thread, not speech: a run-on past
    _RUN_ON words, or one short phrase over and over ("the name. the name. the name.";
    a single word four times)."""
    tokens = _tokens(text)
    if len(tokens) > _RUN_ON:
        return True
    for n in range(1, 5):
        times = 4 if n == 1 else 3
        for i in range(len(tokens) - n * times + 1):
            phrase = tokens[i : i + n]
            if all(tokens[i + k * n : i + (k + 1) * n] == phrase for k in range(1, times)):
                return True
    return False


def meaningful(text: str, answering: bool = False) -> bool:
    """Something said to the host, not room noise: three or more real words; or one,
    right after the host asked something; or, asked or not, a greeting, a short question
    to it ("what's up", "how are you", "who are you") or anything with its name in it.
    Whisper's phantoms for noise ("you", "thank you", "oh") never are (D43), and neither
    is transcription junk (junk())."""
    tokens = _tokens(text)
    if not tokens or " ".join(tokens) in _PHANTOMS or junk(text):
        return False
    if addressed(text):
        return True
    words = [t for t in tokens if t not in _FILLER]
    return len(words) >= (1 if answering else 3)


def wants_to_vote(text: str) -> bool:
    """The group is ready to vote before the day's time is up."""
    t = " ".join(_tokens(text))
    return any(p in t for p in _VOTE_NOW)


# --- deliberately selected lasting facts -----------------------------------------

def memory_command(text: str) -> tuple[str, str] | None:
    """An explicit remember/forget/recall command, before game-name parsing.

    Keep the selected fact's words, but normalize spaces. Never infer a fact from chat.
    """
    text = " ".join(text.split()).strip()
    text = re.sub(r"^(?:(?:hey|okay|please)[, ]+)*(?:rob[, ]+)?", "", text, flags=re.IGNORECASE)
    plain = text.casefold().rstrip(".!?")
    if plain in ("forget everything", "forget it all", "forget all your memories"):
        return "clear", ""
    if plain in ("forget that", "forget the last thing", "forget the last fact"):
        return "forget", ""
    if plain in ("what do you remember", "what do you remember about us", "what have you remembered"):
        return "recall", ""
    match = re.fullmatch(r"remember\s+(?:that\s+)?(.+)", text, re.IGNORECASE)
    return ("remember", match[1].strip()) if match else None
