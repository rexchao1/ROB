"""What the dashboard can change while the host runs: the personality, the talk and
the voice. Mac only (the referee never reads it). One shared object, read at the
moment of use, so a change applies to the next line."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class Settings:
    persona: str = "host"  # a key of brain.personas.PERSONAS
    talk: str = "anthropic"  # anthropic | gemini | ollama | off
    talk_model: str | None = None  # None: the provider's default
    voice: str = "piper"  # piper | eleven (ElevenLabs live, needs ELEVENLABS_API_KEY)
    eleven_voice: str | None = None  # a key of brain.personas.VOICES; None: the personality's or the default


SAVED = ("persona", "eleven_voice")  # ROB's personality and voice, kept across starts


current = Settings()
_lock = threading.Lock()


file: Path | None = None  # where SAVED is kept (gamemaster.rob.json); None keeps nothing


def load(path: Path) -> None:
    """Read ROB's saved personality and voice, and keep later changes there."""
    global file
    file = path
    try:
        saved = json.loads(path.read_text())
    except (OSError, ValueError):
        return
    with _lock:
        for name in SAVED:
            if name in saved:
                setattr(current, name, saved[name])


def update(**changes: Any) -> dict[str, Any]:
    """Change some settings; an unknown name is a KeyError. Returns the new snapshot."""
    with _lock:
        for name, value in changes.items():
            if not hasattr(current, name):
                raise KeyError(name)
            setattr(current, name, value)
        snap = asdict(current)
    if file is not None and any(n in SAVED for n in changes):
        try:
            file.write_text(json.dumps({n: snap[n] for n in SAVED}) + "\n")
        except OSError:
            pass
    return snap


def snapshot() -> dict[str, Any]:
    with _lock:
        return asdict(current)
