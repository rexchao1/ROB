"""What the dashboard can change while the host runs: the personality, the talk and
the voice. Mac only (the referee never reads it). One shared object, read at the
moment of use, so a change applies to the next line."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Settings:
    persona: str = "host"  # a key of brain.personas.PERSONAS
    talk: str = "anthropic"  # anthropic | gemini | ollama | off
    talk_model: str | None = None  # None: the provider's default
    voice: str = "piper"  # piper | eleven (ElevenLabs live, needs ELEVENLABS_API_KEY)


current = Settings()
_lock = threading.Lock()


def update(**changes: Any) -> dict[str, Any]:
    """Change some settings; an unknown name is a KeyError. Returns the new snapshot."""
    with _lock:
        for name, value in changes.items():
            if not hasattr(current, name):
                raise KeyError(name)
            setattr(current, name, value)
        return asdict(current)


def snapshot() -> dict[str, Any]:
    with _lock:
        return asdict(current)
