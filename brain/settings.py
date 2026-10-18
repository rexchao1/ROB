"""What the dashboard can change while the host runs: the personality, the talk (its
provider, model and effort), the voice and the speaker. Mac only (the referee never
reads it). One shared object, read at the moment of use, so a change applies to the
next line."""

from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from brain import personas


@dataclass
class Settings:
    persona: str = "host"  # a key of brain.personas.PERSONAS
    talk: str = "anthropic"  # anthropic | gemini | ollama | off
    talk_model: str | None = None  # None: the provider's default
    effort: str = "low"  # one of brain.talk.EFFORTS: low is quickest, a party host wants speed
    voice: str = "piper"  # piper | eleven (ElevenLabs live, needs ELEVENLABS_API_KEY)
    eleven_voice: str | None = None  # a key of brain.personas.VOICES; None: the personality's or the default
    speaker: str = "robot"  # robot | mac: where ROB's voice plays (Host.set_speaker)


SAVED = ("persona", "eleven_voice", "talk", "talk_model", "effort", "voice", "speaker")  # kept across starts
CHOICES = {  # the only values these take; brain.talk.EFFORTS is the effort's
    "talk": ("anthropic", "gemini", "ollama", "off"),
    "effort": ("low", "medium", "high", "max"),
    "voice": ("piper", "eleven"),
    "speaker": ("robot", "mac"),
}
_MAY_BE_NONE = ("talk_model", "eleven_voice")


current = Settings()
_lock = threading.Lock()


file: Path | None = None  # where SAVED is kept (gamemaster.rob.json); None keeps nothing


_KEYLIKE = ("sk-", "sk_", "aiza", "xi-")  # a key pasted where a model name goes is never believed
_HEXRUN = re.compile(r"[0-9a-fA-F]{32}")


def _fits(name: str, value: Any) -> bool:
    if value is None:
        return name in _MAY_BE_NONE
    if not isinstance(value, str) or value not in CHOICES.get(name, (value,)):
        return False
    if name == "persona" and value not in personas.PERSONAS:
        return False
    if name == "eleven_voice" and value not in personas.VOICES:
        return False
    if name == "talk_model" and (value.lower().startswith(_KEYLIKE) or _HEXRUN.search(value)):
        return False
    return True


def load(path: Path) -> None:
    """Read ROB's saved picks, and keep later changes there. A saved value of the wrong
    type, or outside its choices, is ignored and the setting keeps what it had."""
    global file
    file = path
    try:
        saved = json.loads(path.read_text())
    except (OSError, ValueError):
        return
    if not isinstance(saved, dict):
        return
    with _lock:
        for name in SAVED:
            if name in saved and _fits(name, saved[name]):
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
