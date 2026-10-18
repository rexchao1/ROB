"""Banter: one short in-character quip at a slot the script marks (D14). It decorates
and never decides: a quip that names a player, holds a number up to ten (a seat, a
count, a score) or runs past its moment's length is thrown away, and so is any answer
that does not come back in time. The host says nothing then.

A quip is a reaction during play, so it is brief, and how brief fits the moment
(words()): a beat while the roles go out, a little more for a death or a vote, the
most at the end of a game. The cloud talk (brain/talk.py, Talk.quip) holds its quips to
the same lengths.

The recap (Recap) is what ROB remembers of the game being played, so a quip can call
back to an earlier moment and never says the same thing twice: the public moments so
far ("someone was voted out", never who or what anyone was) and the quips already
said. It lives in RAM on the host, is bounded, and is forgotten when the game ends.

The local model runs under Ollama on the brain (llama3.2:3b fits the Pi's 8 GB); nothing
here reaches past the brain's own loopback.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import deque
from typing import Any

MAX_WORDS = 12  # a quip at a moment with no length of its own

PERSONA = (
    "You are ROB, a tiny robot hosting party games for a table of friends. You take hosting "
    "slightly too seriously, love suspense, tease a bold move, and now and then make yourself "
    "the joke. You talk like a person, never like an assistant. You speak one short line out "
    "loud. Never name a player, never use a number, never reveal or hint at anyone's role, "
    "never give instructions or rules. No emoji, no quotation marks."
)

# What each slot is about; the games name the slots (brain/games/), an unknown slot gets the generic one.
SLOTS: dict[str, str] = {
    "start": "The game is about to begin.",
    "deal": "Secret roles are being handed out one at a time.",
    "night": "Night falls; everyone has their head down.",
    "morning": "Morning comes and the table wakes up.",
    "killed": "Someone was killed in the night.",
    "death": "Morning came and someone was killed in the night.",
    "saved": "Nobody died last night; the doctor guessed right.",
    "discussion": "The table is arguing about who to vote out.",
    "vote": "The vote is about to happen.",
    "tie": "The vote was a tie; nobody leaves.",
    "out": "Someone was just voted out and their role was revealed.",
    "reveal": "A secret is being revealed.",
    "win": "The game is over.",
    "clues": "Everyone is giving one-word clues.",
    "guess": "The group is about to guess.",
    "score": "A round was just scored.",
}

# How many words a quip may run at each slot: a beat during play, more for a death or a
# vote, the most when the game is over.
WORDS: dict[str, int] = {
    "deal": 8, "night": 8, "morning": 8, "discussion": 8, "vote": 8, "clues": 8, "guess": 8, "score": 8,
    "killed": 10, "death": 10, "saved": 10, "tie": 10, "out": 10, "reveal": 10,
    "start": 12,
    "win": 16,
}

# What the recap keeps of each slot once it has happened: public, and never who.
EVENTS: dict[str, str] = {
    "start": "the game began",
    "deal": "the secret cards went out",
    "night": "night fell",
    "killed": "someone was killed in the night",
    "death": "someone was killed in the night",
    "saved": "a night passed and nobody died",
    "tie": "a vote ended in a tie",
    "out": "someone was voted out",
    "reveal": "a secret was revealed",
    "score": "a round was scored",
    "win": "the game ended",
}

_NUMBER_WORDS = "zero one two three four five six seven eight nine ten first second third fourth fifth".split()
_BANNED = re.compile(r"\b(player|players|seat|seats|" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)


def words(slot: str) -> int:
    """The most words a quip may run at `slot`."""
    return WORDS.get(slot, MAX_WORDS)


def clean(text: str, limit: int = MAX_WORDS) -> str | None:
    """The quip fit to say, or None: first line only, quotes and stage directions stripped;
    rejected when it names a player or a seat, holds a digit or a number word, or runs past `limit` words."""
    line = text.strip().splitlines()[0].strip() if text.strip() else ""
    line = re.sub(r"\*[^*]*\*|\([^)]*\)", "", line)  # *laughs*, (pause)
    line = line.strip().strip("\"'“”‘’").strip()
    if not line:
        return None
    if re.search(r"\d", line) or _BANNED.search(line):
        return None
    if len(line.split()) > limit:
        return None
    return line


def _key(line: str) -> str:
    """A quip as compared for repeats: lower-case words, no punctuation."""
    return " ".join(re.findall(r"[a-z']+", line.lower()))


class Recap:
    """What ROB remembers of the game being played, for the quips: the public moments
    so far, in order, and the quips already said. RAM only, bounded, never who had
    which role; the host clears it when the game ends (Host.mood("idle"))."""

    MOMENTS = 10  # public moments kept, the latest
    SAID = 30  # quips kept for the repeat check; the prompt shows the last few

    def __init__(self) -> None:
        self.moments: deque[str] = deque(maxlen=self.MOMENTS)
        self.said: deque[str] = deque(maxlen=self.SAID)

    def clear(self) -> None:
        self.moments.clear()
        self.said.clear()

    def keep(self, slot: str, line: str | None) -> str | None:
        """Note that `slot` happened and that `line` was the quip for it; the line back,
        or None when it repeats one already said this game."""
        event = EVENTS.get(slot)
        if line is not None and any(_key(line) == _key(old) for old in self.said):
            line = None
        if line is not None:
            self.said.append(line)
        if event is not None:
            self.moments.append(event)
        return line

    def so_far(self) -> str:
        """The public moments so far, oldest first: "night fell, then someone was voted
        out"; "" before any."""
        return ", then ".join(self.moments)

    def recent(self, n: int = 6) -> list[str]:
        """The last `n` quips said this game, oldest first."""
        return list(self.said)[-n:]


class NoBanter:
    """The host with nothing extra to say (test mode, or no model installed)."""

    def line(self, slot: str, context: dict[str, Any], recap: Recap | None = None) -> str | None:  # noqa: ARG002 - the Banter surface
        return None


class Banter:
    """Quips from Ollama's /api/generate, non-streaming, bounded by `timeout` seconds."""

    def __init__(self, url: str = "http://127.0.0.1:11434", model: str = "llama3.2:3b", timeout: float = 2.0) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def prompt(self, slot: str, context: dict[str, Any], recap: Recap | None = None) -> str:
        about = SLOTS.get(slot, "Something just happened in the game.")
        facts = {k: v for k, v in context.items() if isinstance(v, (str, bool)) and not _BANNED.search(str(v))}
        extra = f" Context: {json.dumps(facts)}." if facts else ""
        earlier = f"\nEarlier this game: {recap.so_far()}." if recap is not None and recap.so_far() else ""
        said = f"\nDon't repeat: {' | '.join(recap.recent(3))}" if recap is not None and recap.said else ""
        return f"{PERSONA}\n\nThe moment: {about}{extra}{earlier}{said}\nYour one line (at most {words(slot)} words):"

    def line(self, slot: str, context: dict[str, Any], recap: Recap | None = None) -> str | None:
        text = self._generate(self.prompt(slot, context, recap), self.timeout)
        return clean(text, words(slot)) if text is not None else None

    def warm(self, timeout: float = 60.0) -> bool:
        """Load the model into memory ahead of the first quip (the first call is slow)."""
        return self._generate("Say hello in three words.", timeout) is not None

    def _generate(self, prompt: str, timeout: float) -> str | None:
        """The model's answer, stripped, or None when it is down, slow or not JSON."""
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {"num_predict": 32, "temperature": 0.9},
        }
        req = urllib.request.Request(
            self.url + "/api/generate", data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                answer = json.loads(res.read())
        except (urllib.error.URLError, OSError, ValueError):
            return None  # down, slow, or not JSON: no quip
        text = answer.get("response") if isinstance(answer, dict) else None
        if not isinstance(text, str):
            return None
        return text.strip() or None
