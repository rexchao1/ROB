"""Deliberately selected group facts and public totals, never conversation history.

A Mac table gets a RAM-only store. The referee supplies a path outside ~/gm.
The 30-entry limit includes one aggregate per game; full stores reject new entries.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import weakref
from pathlib import Path
from typing import Any

LIMIT = 30
WIDTH = 100
MAX_COUNT = 999999
SIDES = {
    "mafia": ("mafia", "village"), "imposter": ("players", "imposter"),
    "wavelength": (), "hotseat": (), "wordle": ("players",),
    "twenty": ("player", "robot"),
}
# Explicit memory is for group preferences, never identities or private assignments.
_PRIVATE = re.compile(
    r"\b(?:player|seat)s?\b|\b(?:my|his|her|their) name\b|\bcall me\b|"
    r"\b(?:i am|i'm|he is|he's|she is|she's|is|was) (?:the |a )?(?:mafia|doctor|villager|imposter)\b",
    re.IGNORECASE,
)
_stores: weakref.WeakKeyDictionary[Any, Facts] = weakref.WeakKeyDictionary()


def for_table(table: Any) -> Facts:
    """Session-only facts shared by welcomes at a Mac table; never a Mac file."""
    try:
        return _stores.setdefault(table, Facts())
    except TypeError:
        return Facts()


class Facts:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._facts: list[str] = []
        self._history: dict[str, dict[str, Any]] = {}
        if path is not None:
            self._load()

    def _load(self) -> None:
        try:
            # Bound even a corrupt or hand-edited file before parsing it.
            if self.path.stat().st_size > 32768:
                return
            data = json.loads(self.path.read_text())
            if not isinstance(data, dict):
                return
            facts, history = data.get("facts", []), data.get("history", {})
            if isinstance(facts, list):
                for text in facts[:LIMIT]:
                    self.remember(text, write=False)
            if isinstance(history, dict):
                for game, entry in history.items():
                    if game not in SIDES or not isinstance(entry, dict) or self.size >= LIMIT:
                        continue
                    n, wins = entry.get("played"), entry.get("wins", {})
                    if type(n) is not int or not 1 <= n <= MAX_COUNT or not isinstance(wins, dict):
                        continue
                    self._history[game] = {"played": n, "wins": {
                        side: count for side, count in wins.items()
                        if side in SIDES[game] and type(count) is int and 1 <= count <= n
                    }}
        except (OSError, ValueError):
            pass  # missing or invalid memory is an empty store, never a failed referee

    @property
    def size(self) -> int:
        return len(self._facts) + len(self._history)

    def remembered(self) -> list[str]:
        entries = list(self._facts)
        for game, entry in self._history.items():
            line = f"{game}: played {entry['played']}"
            for side, count in entry["wins"].items():
                line += f"; {side} won {count}"
            entries.append(line + ".")
        return entries

    def remember(self, text: str, *, write: bool = True) -> str:
        if not isinstance(text, str):
            return "invalid"
        text = " ".join(text.split())
        if not text or len(text) > WIDTH or _PRIVATE.search(text):
            return "invalid"
        if text.casefold() in {f.casefold() for f in self.remembered()}:
            return "duplicate"
        if self.size >= LIMIT:
            return "full"
        self._change([*self._facts, text], self._history, write=write)
        return "saved"

    def forget_last(self) -> bool:
        if not self._facts:
            return False
        self._change(self._facts[:-1], self._history)
        return True

    def forget_all(self) -> bool:
        if not self.size:
            return False
        self._change([], {})
        return True

    def played(self, game: str, winner: str | None = None) -> None:
        """Only a game id and an allowlisted public side enter the durable aggregate."""
        if game not in SIDES or (game not in self._history and self.size >= LIMIT):
            return
        previous = self._history.get(game, {"played": 0, "wins": {}})
        entry = {"played": min(previous["played"] + 1, MAX_COUNT), "wins": dict(previous["wins"])}
        if winner in SIDES[game]:
            entry["wins"][winner] = min(entry["wins"].get(winner, 0) + 1, MAX_COUNT)
        self._change(self._facts, {**self._history, game: entry})

    def _change(self, facts: list[str], history: dict[str, Any], *, write: bool = True) -> None:
        if facts == self._facts and history == self._history:
            return
        if write and self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".facts-", dir=self.path.parent)
            try:
                with os.fdopen(fd, "w") as stream:
                    json.dump({"facts": facts, "history": history}, stream)
                    stream.write("\n")
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        self._facts, self._history = facts, history
