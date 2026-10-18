"""The host's script: every line the host says, written once, here.

The feature files quote lines exactly ("Player three, heads down means heads DOWN."),
so each ruled line is a constant or a small function and nothing else builds host
text. Flavor (D14) is a set of variations per moment, chosen with the game's rng and
said as a separate line, so the ruled lines never change; no flavor line names a
player or a seat. fixed_lines() lists every line known ahead of time, for the voice
cache (scripts/make-voice.py records each with ElevenLabs, D30); the rest (tallies,
the tie and no-majority lines that carry a tally, two Mafia named together) is
composed at play time and spoken by the local voice.

The welcome's lines (D38 to D43) come in variations too, chosen with the rng, and are
written to sound like a person running game night, not an assistant (D46): short,
casual, contractions, no lists, no dashes. A suggestion always names the game the
headcount points to (suggested()); the model never picks it.
"""

from __future__ import annotations

import random
from typing import Sequence

# --- numbers ------------------------------------------------------------------

_ONES = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
)
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def number_word(n: int) -> str:
    """0..100 in words: 4 -> "four", 23 -> "twenty-three", 100 -> "one hundred"."""
    if not 0 <= n <= 100:
        raise ValueError(f"number_word covers 0..100, not {n}")
    if n < 20:
        return _ONES[n]
    if n == 100:
        return "one hundred"
    tens, ones = divmod(n, 10)
    return _TENS[tens] + ("" if ones == 0 else "-" + _ONES[ones])


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def player(n: int) -> str:
    """"Player four"."""
    return f"Player {number_word(n)}"


# --- the table: counting, the private screen ----------------------------------


def count_line(n: int) -> str:
    """D5: "Five of you. Player one is on my left, then two, three, four, five going clockwise.\""""
    if n <= 0:
        return NOBODY_HERE
    if n == 1:
        return "Just one of you. Player one is right in front of me."
    rest = ", ".join(number_word(i) for i in range(2, n + 1))
    return f"{_cap(number_word(n))} of you. Player one is on my left, then {rest} going clockwise."


NOBODY_HERE = "I don't see anyone yet."


def only_see(n: int) -> str:
    """D6, a spoken count above the host's: "I only see five. Who's hiding?\""""
    if n <= 0:
        return "I don't see anyone. Who's hiding?"
    return f"I only see {number_word(n)}. Who's hiding?"


def see_more(n: int) -> str:
    """A spoken count below the host's (not ruled; the mirror of D6)."""
    return f"I see {number_word(n)}. Is someone just watching?"


COUNT_GIVE_UP = "Let's try again when everyone's ready."
COUNT_AGREED = "Great."


def too_few(game: str, minimum: int) -> str:
    """"Mafia needs at least four players.\""""
    return f"{game_name(game)} needs at least {number_word(minimum)} players."


GAME_NAMES = {
    "mafia": "Mafia", "imposter": "Imposter", "wavelength": "Wavelength",
    "twenty": "Twenty Questions", "hotseat": "Hot Seat", "wordle": "Wordle",
}


def game_name(game: str) -> str:
    """A game's spoken name; a game registered without one in GAME_NAMES still gets a name."""
    return GAME_NAMES.get(game) or game.replace("_", " ").title()


def lean_in(seat: int) -> str:
    """D7: "Player two, lean in.\""""
    return f"{player(seat)}, lean in."


def lean_in_again(seat: int) -> str:
    """The lean-in asked again, with the way round the camera: "show me" puts the card up."""
    return f"{player(seat)}, lean in close, or say show me."


ONE_AT_A_TIME = "One at a time."
SPEAKER_MAC = "Okay, I'll talk through the Mac."  # "change your speaker to the Mac"
SPEAKER_ROBOT = "Okay, back to my own speaker."


def come_back(seat: int) -> str:
    """A player who did not lean in is dealt again after the others."""
    return f"{player(seat)}, I'll come back to you."


CANT_DEAL = "I can't deal without everyone. Let's start over."
STOPPING = "Okay, stopping the game."
RESTARTING = "Okay, starting over."  # "reset" mid-game: the welcome comes next (D38)
DRAW = "That's enough rounds for one night. Let's call it a draw."
GOOD_GAME = "Good game, everyone."

# --- votes (D12, D13), shared by Mafia and Imposter ----------------------------


def who(seat: int) -> str:
    """D12: "Player one, who?\""""
    return f"{player(seat)}, who?"


def who_again(seat: int) -> str:
    """A vote not heard is asked for again, once."""
    return f"{player(seat)}, I didn't catch that. Who?"


PICK_LIVING = "Pick someone who's still in."


def tally(counts: Sequence[tuple[int, int]]) -> str:
    """D12: [(4, 3), (1, 2)] (seat, votes), most votes first -> "Three for Player four, two for Player one.\""""
    parts = [f"{number_word(votes)} for {player(seat)}" for seat, votes in counts]
    return _cap(", ".join(parts)) + "."


def tie(counts: Sequence[tuple[int, int]]) -> str:
    """D13: "Two for Player two, two for Player four. It's a tie. Nobody leaves.\""""
    return f"{tally(counts)} It's a tie. Nobody leaves."


def no_majority(counts: Sequence[tuple[int, int]]) -> str:
    """Most votes, but not a majority of the living players (D12 asks for a majority)."""
    return f"{tally(counts)} Nobody has a majority. Nobody leaves."


NO_VOTES = "Nobody voted. Nobody leaves."


def voted_out(seat: int) -> str:
    """D12: "Player four, you're out.\""""
    return f"{player(seat)}, you're out."


# --- Mafia ---------------------------------------------------------------------

MAFIA, DOCTOR, VILLAGER = "MAFIA", "DOCTOR", "VILLAGER"  # the role cards (D15)


def mafia_intro(mafia: int) -> str:
    if mafia == 1:
        return "Let's play Mafia. One of you is the Mafia, one of you is the Doctor, and everyone else is a Villager."
    return f"Let's play Mafia. {_cap(number_word(mafia))} of you are the Mafia, one of you is the Doctor, and everyone else is a Villager."


DEAL_ROLES = "Roles, one at a time. When I call your number, lean in close."
HEADS_DOWN = "Everyone, heads down."


def warn(seat: int) -> str:
    """D9: "Player three, heads down means heads DOWN.\""""
    return f"{player(seat)}, heads down means heads DOWN."


def sit_out(seat: int) -> str:
    """D11: "Player three, you're sitting this round out.\""""
    return f"{player(seat)}, you're sitting this round out."


MAFIA_WHISPER = "Mafia, whisper your target."
MAFIA_AGAIN = "Mafia, once more, quietly. Who?"
MAFIA_DOWN = "Mafia, heads back down."
DOCTOR_WHISPER = "Doctor, whisper who you save."
DOCTOR_AGAIN = "Doctor, once more, quietly. Who?"
DOCTOR_DOWN = "Doctor, head back down."
MORNING = "Everyone, heads up. It's morning."


def killed(seat: int) -> str:
    """D16: "Player four was killed in the night.\""""
    return f"{player(seat)} was killed in the night."


NOBODY_DIED = "Nobody died last night."  # D17


def discussion(seconds: float) -> str:
    """The start of the day: "You have two minutes. Talk it out.\""""
    return f"You have {_duration(seconds)}. Talk it out."


def time_left(seconds: float) -> str:
    """D18's halfway call: 60 -> "One minute left."; 15 -> "Fifteen seconds left.\""""
    return f"{_cap(_duration(seconds))} left."


def _duration(seconds: float) -> str:
    s = max(1, int(round(seconds)))
    if s % 60 == 0 and s <= 600:
        m = s // 60
        return f"{number_word(m)} minute" + ("" if m == 1 else "s")
    if s > 100:
        return f"about {number_word(min(10, round(s / 60)))} minutes"
    return f"{number_word(s)} second" + ("" if s == 1 else "s")


TIME_VOTE = "Time. Let's vote."  # D18
EARLY_VOTE = "Okay, let's vote."
_ROLE_NAMES = {MAFIA: "the Mafia", DOCTOR: "the Doctor", VILLAGER: "a Villager"}


def was(seat: int, role: str) -> str:
    """D18: "Player four was a Villager." / "... was the Doctor." / "... was the Mafia.\""""
    return f"{player(seat)} was {_ROLE_NAMES[role]}."


MAFIA_WIN = "The Mafia win."  # D19
VILLAGE_WINS = "The village wins."


def village_wins(last_mafia: int) -> str:
    """D19, the last Mafia voted out: "Player one was the Mafia. The village wins.\""""
    return f"{was(last_mafia, MAFIA)} {VILLAGE_WINS}"


def mafia_were(seats: Sequence[int]) -> str:
    """After the Mafia win, who they were."""
    if len(seats) == 1:
        return f"The Mafia was {player(seats[0])}."
    names = [player(s) for s in seats]
    return f"The Mafia were {', '.join(names[:-1])} and {names[-1]}."


# --- Imposter (D20) --------------------------------------------------------------

IMPOSTER = "IMPOSTER"  # the card the Imposter sees
IMPOSTER_INTRO = "Let's play Imposter. Everyone gets the same secret word, except one of you: the Imposter."
DEAL_WORDS = "Words, one at a time. When I call your number, lean in close."
CLUES = "One word each, in seat order. Don't make it too easy."


def clue(seat: int) -> str:
    """The clue turn, one address per player: "Player one, one word.\""""
    return f"{player(seat)}, one word."


IMPOSTER_VOTE = "Who's the Imposter? Let's vote."


def was_imposter(seat: int) -> str:
    """D20: "Player three was the Imposter.\""""
    return f"{player(seat)} was the Imposter."


def imposter_survives(seat: int) -> str:
    """D20: "The Imposter survives. It was Player three.\""""
    return f"The Imposter survives. It was {player(seat)}."


def word_was(word: str) -> str:
    return f"The word was {word}."


# --- Wavelength (D21) --------------------------------------------------------------

WAVELENGTH_INTRO = (
    "Let's play Wavelength. One of you sees a number from one to ten on a scale. "
    "Give a clue, and everyone else guesses the number."
)


def round_line(n: int) -> str:
    return f"Round {number_word(n)}."


def psychic_clue(seat: int) -> str:
    return f"{player(seat)}, give us your clue."


WAVELENGTH_TALK = "Everyone else, talk it over. Tell me your number when you're ready."
WAVELENGTH_AGAIN = "What's your number?"
NO_GUESS = "No guess. Zero points."


def points(score: int) -> str:
    """D21: "Nine points." (and "One point.")"""
    return f"{_cap(number_word(score))} point" + ("." if score == 1 else "s.")


def target_was(target: int) -> str:
    return f"It was {number_word(target)}."


def total(points_total: int) -> str:
    """D21: "Twenty-three points. Nice work.\""""
    return f"{points(points_total)} Nice work."


# --- flavor (D14): variations, never naming a player ---------------------------------

FLAVOR: dict[str, tuple[str, ...]] = {
    "night": ("Night falls on the village.", "The sun goes down.", "It's getting dark out there."),
    "death": ("The village mourns.", "A sad morning.", "Rest in peace."),
    "saved": ("A quiet night, for once.", "Somebody had a good Doctor."),
    "vote": ("Choose wisely.", "Point those fingers.", "No pressure."),
    "deal": ("Eyes on your own screen.", "No peeking at each other's."),
    "tie": ("The village can't decide.", "Deadlock."),
    "win": ("What a game.", "Well played."),
    "imposter": ("Somebody here is bluffing.", "Choose your word carefully."),
    "wavelength": ("Get on the same wavelength.", "Read each other's minds."),
}


def flavor(moment: str, rng: random.Random) -> str:
    """One variation for a moment (FLAVOR's keys)."""
    return rng.choice(FLAVOR[moment])


# --- the welcome (D38 to D43) ------------------------------------------------------------

GREETINGS = (
    "Hey, what's up, everyone? I'm ROB. Let me see who we've got.",
    "Hey hey, it's game night! ROB here. Hold still, I'm counting heads.",
    "Hey, everybody! I'm ROB, your host. Give me a sec to see who's here.",
    "Hey, what's going on? ROB here. Let me get a look at you all.",
    "Hey there, I'm ROB! Okay, let's see who showed up.",
)


def greeting(rng: random.Random) -> str:
    return rng.choice(GREETINGS)


def _hellos(seat: int, seats: int) -> tuple[str, ...]:
    p = player(seat)
    if seat == 1:
        return (f"Hi, {p}.", f"You're {p}.", f"{p}, hi.")
    if seat == seats:
        return (f"And {p}.", f"And you're {p}.")
    return (f"Hi, {p}.", f"{p}, hello.", f"You're {p}.")


def hello(seat: int, seats: int, rng: random.Random) -> str:
    """The welcome's hello to one seat, the head turned to it: "Hi, Player one.\""""
    return rng.choice(_hellos(seat, seats))


def _registered() -> list[str]:
    """The games built so far: MINIMUM gets an entry when a game is added to brain/games."""
    return list(MINIMUM)


def suggested(seats: int) -> str | None:
    """The game a headcount points to (D38): two Wavelength, three or four Imposter, five
    or more Mafia, one player Twenty Questions, else Wordle; when that game is not built,
    the first built one the count can play; None when none can."""
    if seats >= 5:
        prefer = ["mafia"]
    elif seats >= 3:
        prefer = ["imposter"]
    elif seats == 2:
        prefer = ["wavelength"]
    else:
        prefer = ["twenty", "wordle"]
    for game in prefer + _registered():
        if game in MINIMUM and seats >= max(MINIMUM[game], 1):
            return game
    return None


def _suggestions(seats: int) -> tuple[str, ...]:
    game = suggested(seats)
    n, w = _cap(number_word(seats)), number_word(seats)
    if game is not None and seats == 1:
        g = game_name(game)
        return (
            f"Just you? That's fine, we can do {g}. Want to, or pick something else?",
            f"Just you and me, then. I'm thinking {g}. Sound good?",
        )
    if game == "wavelength":
        return (
            "Two of you? Perfect for Wavelength. Want to play, or pick something else?",
            "Just the two of you. I'd go with Wavelength. Sound good, or want another game?",
        )
    if game == "imposter":
        return (
            f"{n} of you. I'm thinking Imposter. Sound good, or want something else?",
            f"{n} players, that's an Imposter crowd. Want to play, or pick another game?",
        )
    if game == "mafia":
        return (
            f"{n} of you, that's enough for Mafia. Want to play, or pick another game?",
            f"Ooh, {w} of you. That's a Mafia table. You in, or want something else?",
        )
    if game is not None:
        return (f"{n} of you. I'd go with {game_name(game)}. Sound good, or want something else?",)
    if seats >= 1:
        return (f"Just you? Grab a friend, every game needs at least {number_word(_fewest())}.",)
    return (NOBODY_YET,)


def _fewest() -> int:
    return min(MINIMUM.values())


NOBODY_YET = "I don't see anyone yet. Sit where I can see you and say reset."


def suggestion(seats: int, rng: random.Random) -> str:
    """The welcome's suggestion for the count, naming suggested(seats), ending on a question."""
    return rng.choice(_suggestions(seats))


RULES = {
    "mafia": (
        "In Mafia, someone's secretly the Mafia and takes a player out every night, while the Doctor tries to save them. "
        "By day you argue it out and vote. Want to play it?"
    ),
    "imposter": (
        "In Imposter, everyone gets the same secret word except one person, the Imposter. "
        "You each give a one-word clue, then vote on who's faking it. Want to play it?"
    ),
    "wavelength": (
        "In Wavelength, one of you sees a secret number on a scale and gives a clue. "
        "Everyone else talks it over and guesses the number. Want to play it?"
    ),
}


def rules(game: str) -> str:
    """Asked how a game goes: its RULES line; a game added without one gets a line that
    states no rule (D14)."""
    return RULES.get(game) or f"{game_name(game)}? Easier to show you than explain. Want to play it?"


def _join(games: list[str], word: str) -> str:
    names = [game_name(g) for g in games]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" {word} " + names[-1]


def _or(games: list[str]) -> str:
    return _join(games, "or")


def fits(seats: int) -> list[str]:
    """The games this many players can play, in the order they were built."""
    return [g for g in _registered() if seats >= max(MINIMUM[g], 1)]


def games_list(seats: int) -> str:
    """Asked what the host has: every game built, and the pick for the count."""
    have = f"I've got {_join(_registered(), 'and')}."
    game = suggested(seats)
    if game is None:
        return f"{have} Sit where I can see you first." if seats < 1 else f"{have} You'll need at least {number_word(_fewest())} people, though."
    who = "just you" if seats == 1 else f"{number_word(seats)} of you"
    return f"{have} With {who} I'd pick {game_name(game)}. Which one?"


def _declines(seats: int, game: str | None) -> tuple[str, ...]:
    others = [g for g in fits(seats) if g != game]
    if not others:
        if game is None:
            return ("Fair. Grab a friend and we'll play something.",)
        who = "just you" if seats == 1 else f"{number_word(seats)} of you"
        return (f"Fair. With {who} it's {game_name(game)} or bust, though.",)
    if len(others) == 1:
        return (f"Fair enough. Want {_or(others)} instead?",)
    return (f"Fair enough. There's also {_or(others)}. Which one?", f"No problem. You could do {_or(others)} instead. Which one?")


def declined(seats: int, game: str | None, rng: random.Random) -> str:
    """A "no" to the suggestion: the other games the count can play."""
    return rng.choice(_declines(seats, game))


def instead(game: str) -> str:
    """After "Mafia needs at least four players.": the game the count can play."""
    return f"Want to try {game_name(game)} instead?"


LATER = (
    "No rush. Say a game's name whenever you're ready.",
    "Cool, I'll be here. Just say a game when you want one.",
)


def later(rng: random.Random) -> str:
    return rng.choice(LATER)


def _nudges(game: str | None) -> tuple[str, ...]:
    plain = (
        "No rush. Just say a game's name when you're ready.",
        "Whenever you're ready, just name a game.",
    )
    if game is None:
        return plain
    g = game_name(game)
    return (f"Still with me? Say {g} and we're off.", f"Anyone? {g}'s right there.", *plain)


def nudges(game: str | None, rng: random.Random) -> list[str]:
    """Two different nudges for a quiet table, in the order to say them."""
    return rng.sample(_nudges(game), 2)


def _chat_fallbacks(game: str | None) -> tuple[str, ...]:
    if game is None:
        return ("Ha, fair enough. So what are we playing?", "Noted. Now, which game?", "I like you already. Pick a game when you're ready.")
    g = game_name(game)
    return (
        f"Ha, fair enough. So, {g}?",
        f"Honestly, same. Anyway, {g}?",
        f"I like you already. {g}, yes or no?",
        f"Noted. Now, are we doing {g} or what?",
    )


def chat_fallback(game: str | None, rng: random.Random) -> str:
    """A reply to small talk when no model answers (no key, offline, slow): short, and
    back to the game."""
    return rng.choice(_chat_fallbacks(game))


def recounted(before: int, after: int) -> str:
    """Said after looking again, before the new suggestion."""
    if after > before:
        return "There you are."
    if after == before:
        return f"Hmm, still {number_word(after)}."
    return f"Now I see {number_word(after)}."


def count_agreed(seats: int, game: str | None) -> str:
    """Someone in the welcome says the same count the host has."""
    return f"Yep, {number_word(seats)}." + (f" So, {game_name(game)}?" if game else "")


# --- what the voice cache records ------------------------------------------------------

IMPOSTER_WORDS = (
    "beach", "pizza", "airport", "library", "volcano", "wedding", "hospital", "circus",
    "castle", "jungle", "museum", "submarine", "bakery", "casino", "spaceship",
)
SPECTRA = (
    "cold - hot", "bad - good", "boring - exciting", "cheap - expensive", "quiet - loud",
    "underrated - overrated", "useless - useful", "soft - hard", "scary - cute", "old - new",
)
MINIMUM = {"mafia": 4, "imposter": 3, "wavelength": 2}
MINIMUM["hotseat"] = 2
MINIMUM["wordle"] = 1
MINIMUM["twenty"] = 1
RULES["wordle"] = (
    "In Wordle, I pick a secret five-letter word and you get six guesses. "
    "After each one I tell you which letters are spot on and which are in there somewhere. Want to play it?"
)


def fixed_lines(max_seats: int = 10) -> list[str]:
    """Every line the host can say that is known ahead of time, in a stable order, each
    once: the constants, every flavor variation, the per-seat lines for seats
    1..max_seats, the welcome's lines for tables up to max_seats, the counts, the role reveals, Wavelength's points (0..10) and totals
    (0..30), the halfway call and discussion start for two minutes, and the built-in
    Imposter words. Not included, because they are composed at play time: tallies and
    the tie and no-majority lines that carry one, two or more Mafia named together, and
    a halfway call or discussion start for another day length."""
    out: list[str] = []
    out += [
        NOBODY_HERE, only_see(0), COUNT_GIVE_UP, COUNT_AGREED, ONE_AT_A_TIME, CANT_DEAL, STOPPING, DRAW, GOOD_GAME,
        PICK_LIVING, NO_VOTES, DEAL_ROLES, HEADS_DOWN, MAFIA_WHISPER, MAFIA_AGAIN, MAFIA_DOWN,
        DOCTOR_WHISPER, DOCTOR_AGAIN, DOCTOR_DOWN, MORNING, NOBODY_DIED, TIME_VOTE, EARLY_VOTE,
        MAFIA_WIN, VILLAGE_WINS, IMPOSTER_INTRO, DEAL_WORDS, CLUES, IMPOSTER_VOTE, WAVELENGTH_INTRO,
        WAVELENGTH_TALK, WAVELENGTH_AGAIN, NO_GUESS, discussion(120), time_left(60), SPEAKER_MAC, SPEAKER_ROBOT,
    ]
    out += [mafia_intro(1), mafia_intro(2)]
    out += [too_few(g, m) for g, m in MINIMUM.items()]
    for variations in FLAVOR.values():
        out += variations
    for n in range(1, max_seats + 1):
        out += [count_line(n), only_see(n), see_more(n)]
        out += [lean_in(n), lean_in_again(n), come_back(n), who(n), who_again(n), voted_out(n), warn(n), sit_out(n), killed(n)]
        out += [was(n, MAFIA), was(n, DOCTOR), was(n, VILLAGER), village_wins(n), mafia_were([n])]
        out += [clue(n), was_imposter(n), imposter_survives(n), psychic_clue(n)]
    out += [target_was(t) for t in range(1, 11)]
    out += [round_line(n) for n in (1, 2, 3)]
    out += [points(s) for s in range(0, 11)]
    out += [total(t) for t in range(0, 31)]
    out += [word_was(w) for w in IMPOSTER_WORDS]
    out += [RESTARTING, NOBODY_YET, *GREETINGS, *RULES.values(), *LATER, *_nudges(None), *_chat_fallbacks(None)]
    for game in {**GAME_NAMES, **MINIMUM}:
        out += [rules(game), instead(game), *_nudges(game), *_chat_fallbacks(game)]
    for n in range(0, max_seats + 1):
        out += [*_suggestions(n), games_list(n)]
        out += [line for g in (suggested(n), None) for line in _declines(n, g)]
        out += [recounted(n, after) for after in range(0, max_seats + 1)] + [count_agreed(n, g) for g in (None, *GAME_NAMES)]
        out += [line for seat in range(1, n + 1) for line in _hellos(seat, n)]
    seen: set[str] = set()
    unique = []
    for line in out:
        if line not in seen:
            seen.add(line)
            unique.append(line)
    return unique
