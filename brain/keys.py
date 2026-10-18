"""The API keys and tokens, set from the dashboard and never shown again.

They live in .env.local beside package.json (git ignores it; brain/voice.py and
brain/talk.py read the same file), one KEY=value line each, and
reach the brain the way they always have: as environment variables, which load_env()
fills in at start for any the environment does not already set. The dashboard writes
them with Keys.set() and reads back only whether each one is set: no route, log line
or event ever carries a value.

Where a key can take effect at once it does (the gateway's token goes straight to the
body, and the talk reads its key at every call); the referee's table token and the
ElevenLabs key and voice take effect at the next start (scripts/make-voice.py reads
them too).
"""

from __future__ import annotations

import dataclasses
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

ENV_FILE = Path(__file__).resolve().parent.parent / ".env.local"
MAX_LEN = 512


@dataclasses.dataclass(frozen=True)
class Key:
    key: str
    label: str
    applies: str  # "now" or "next start"
    help: str


KEYS: tuple[Key, ...] = (
    Key("STACKCHAN_TOKEN", "Robot gateway token", "now", "The bearer token the stackchan-mcp gateway expects, if it has one."),
    Key("GM_TABLE_TOKEN", "Referee table token", "next start", "The token the QNX referee must send to play through this brain."),
    Key("ANTHROPIC_API_KEY", "Anthropic API key", "now", "The host's talk with --talk anthropic: the welcome chat, quips, 20 Questions, Hot Seat."),
    Key(
        "ANTHROPIC_WORKSPACE_ID", "Anthropic workspace ID", "now",
        "Only for a key that is not tied to a workspace (one starting sk-ant-usr): the workspace's ID (wrkspc_...) from the Anthropic Console.",
    ),
    Key("GEMINI_API_KEY", "Gemini API key", "now", "The host's talk with --talk gemini."),
    Key("ELEVENLABS_API_KEY", "ElevenLabs API key", "next start", "The live ElevenLabs voice, and recording the fixed lines (scripts/make-voice.py)."),
    Key("ELEVENLABS_VOICE_ID", "ElevenLabs voice", "next start", "The voice id, when the personality names none."),
)
_BY_KEY = {k.key: k for k in KEYS}
_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


class KeysError(ValueError):
    """A key the dashboard does not know, or a value it will not write; answered 400."""


def read_env(path: Path = ENV_FILE) -> dict[str, str]:
    """KEY=value pairs from a .env file (quotes stripped); empty when there is none."""
    try:
        text = path.read_text()
    except OSError:
        return {}
    out = {}
    for line in text.splitlines():
        m = _LINE.match(line)
        if m and not line.lstrip().startswith("#"):
            value = m.group(2)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            out[m.group(1)] = value
    return out


def load_env(path: Path = ENV_FILE) -> None:
    """Fill in the environment from .env; a variable already set wins."""
    for name, value in read_env(path).items():
        os.environ.setdefault(name, value)


def _write_env(path: Path, updates: dict[str, str | None]) -> None:
    """Set or remove keys in .env, keeping every other line as it was; owner-only."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        lines = []
    done: set[str] = set()
    out = []
    for line in lines:
        m = _LINE.match(line)
        name = m.group(1) if m and not line.lstrip().startswith("#") else None
        if name in updates:
            if updates[name] is not None and name not in done:
                out.append(f"{name}={updates[name]}")
            done.add(name)
        else:
            out.append(line)
    out += [f"{name}={value}" for name, value in updates.items() if value is not None and name not in done]
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(out) + ("\n" if out else ""))
    tmp.replace(path)
    os.chmod(path, 0o600)


class Keys:
    """The dashboard's side: which keys are set, and setting or clearing them. With no
    path (test mode) they live in memory only and never touch the environment."""

    def __init__(self, path: Path | None, apply: Callable[[str, str | None], None] | None = None) -> None:
        self.path = path
        self._apply = apply or (lambda name, value: None)
        self._memory: dict[str, str] = {}

    def _value(self, name: str) -> str | None:
        if self.path is None:
            return self._memory.get(name)
        return os.environ.get(name) or None

    def status(self) -> dict[str, Any]:
        return {"keys": [{**dataclasses.asdict(k), "set": self._value(k.key) is not None} for k in KEYS]}

    def set(self, body: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, str | None] = {}
        for name, value in body.items():
            if name not in _BY_KEY:
                raise KeysError(f"no key {name!r}")
            if value is None or value == "":
                updates[name] = None
                continue
            if not isinstance(value, str) or len(value) > MAX_LEN or not value.strip() or re.search(r"[\s\"'\\]", value.strip()):
                raise KeysError(f"{name} must be one line of text with no spaces or quotes, at most {MAX_LEN} characters")
            updates[name] = value.strip()
        if self.path is None:
            for name, value in updates.items():
                if value is None:
                    self._memory.pop(name, None)
                else:
                    self._memory[name] = value
        else:
            _write_env(self.path, updates)
            for name, value in updates.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        for name, value in updates.items():
            self._apply(name, value)
        return self.status()
