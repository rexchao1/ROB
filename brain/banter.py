"""Banter: one short in-character quip from a small local model, at a slot the script
marks (D14). It decorates and never decides: a quip that names a player, holds a
number up to ten (a seat, a count, a score) or runs long is thrown away, and so is any
answer that does not come back in time. The host says nothing then.

The model runs under Ollama on the brain (llama3.2:3b fits the Pi's 8 GB); nothing here
reaches past the brain's own loopback.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

MAX_WORDS = 12

PERSONA = (
    "You are ROB, a small robot hosting party games for a table of friends: quick, warm, "
    "a bit cheeky, talking like a person, never like an assistant. You speak one short line "
    "out loud. Never name a player, never use a number, never reveal or hint at anyone's "
    "role, never give instructions or rules. No emoji, no quotation marks."
)

# What each slot is about; the games name the slots (brain/games/), an unknown slot gets the generic one.
SLOTS: dict[str, str] = {
    "start": "The game is about to begin.",
    "deal": "Secret roles are being handed out one at a time.",
    "night": "Night falls; everyone has their head down.",
    "morning": "Morning comes and the table wakes up.",
    "killed": "Someone was killed in the night.",
    "saved": "Nobody died last night; the doctor guessed right.",
    "discussion": "The table is arguing about who to vote out.",
    "vote": "The vote is about to happen.",
    "tie": "The vote was a tie; nobody leaves.",
    "out": "Someone was just voted out.",
    "reveal": "A secret is being revealed.",
    "win": "The game is over.",
    "clues": "Everyone is giving one-word clues.",
    "guess": "The group is about to guess.",
    "score": "A round was just scored.",
}

_NUMBER_WORDS = "zero one two three four five six seven eight nine ten first second third fourth fifth".split()
_BANNED = re.compile(r"\b(player|players|seat|seats|" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)


def clean(text: str) -> str | None:
    """The quip fit to say, or None: first line only, quotes and stage directions stripped;
    rejected when it names a player or a seat, holds a digit or a number word, or runs past MAX_WORDS."""
    line = text.strip().splitlines()[0].strip() if text.strip() else ""
    line = re.sub(r"\*[^*]*\*|\([^)]*\)", "", line)  # *laughs*, (pause)
    line = line.strip().strip("\"'“”‘’").strip()
    if not line:
        return None
    if re.search(r"\d", line) or _BANNED.search(line):
        return None
    if len(line.split()) > MAX_WORDS:
        return None
    return line


class NoBanter:
    """The host with nothing extra to say (test mode, or no model installed)."""

    def line(self, slot: str, context: dict[str, Any]) -> str | None:  # noqa: ARG002 - the Banter surface
        return None


class Banter:
    """Quips from Ollama's /api/generate, non-streaming, bounded by `timeout` seconds."""

    def __init__(self, url: str = "http://127.0.0.1:11434", model: str = "llama3.2:3b", timeout: float = 2.0) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def prompt(self, slot: str, context: dict[str, Any]) -> str:
        about = SLOTS.get(slot, "Something just happened in the game.")
        facts = {k: v for k, v in context.items() if isinstance(v, (str, bool)) and not _BANNED.search(str(v))}
        extra = f" Context: {json.dumps(facts)}." if facts else ""
        return f"{PERSONA}\n\nThe moment: {about}{extra}\nYour one line (at most {MAX_WORDS} words):"

    def line(self, slot: str, context: dict[str, Any]) -> str | None:
        return self._generate(self.prompt(slot, context), self.timeout)

    def warm(self, timeout: float = 60.0) -> bool:
        """Load the model into memory ahead of the first quip (the first call is slow)."""
        return self._generate("Say hello in three words.", timeout, raw=True) is not None

    def _generate(self, prompt: str, timeout: float, raw: bool = False) -> str | None:
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
        if raw:
            return text.strip() or None
        return clean(text)
