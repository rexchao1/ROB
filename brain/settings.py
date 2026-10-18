"""What the dashboard can change while the host runs: the personality, the talk (its
provider, model and effort), the voice and the speaker. The referee mirrors only the
talk choices in RAM. One shared object, read at the moment of use, so a change
applies to the next line."""

from __future__ import annotations

import json
import sys
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class Settings:
    persona: str = "host"  # a key of brain.personas.PERSONAS
    talk: str = "anthropic"  # anthropic | gemini | ollama | off
    talk_model: str | None = None  # None: the provider's default
    effort: str = "low"  # one of brain.talk.EFFORTS: low is quickest, a party host wants speed
    voice: str = "piper"  # piper | eleven (ElevenLabs live, needs ELEVENLABS_API_KEY)
    eleven_voice: str | None = None  # a key of brain.personas.VOICES; None: the personality's or the default
    speaker: str = "robot"  # robot | mac: where ROB's voice plays (Host.set_speaker)
    # robot | mac: which microphone ROB hears through (Body.listen; the Mac's needs scripts/gateway.py).
    # The Mac's by default on a Mac: the robot's beeps each time it opens and cannot hear while ROB talks.
    mic: str = "mac" if sys.platform == "darwin" else "robot"


SAVED = ("persona", "eleven_voice", "talk", "talk_model", "effort", "voice", "speaker", "mic")  # kept across starts
CHOICES = {  # the only values these take; brain.talk.EFFORTS is the effort's
    "talk": ("anthropic", "gemini", "ollama", "off"),
    "effort": ("low", "medium", "high", "max"),
    "voice": ("piper", "eleven"),
    "speaker": ("robot", "mac"),
    "mic": ("robot", "mac"),
}
_MAY_BE_NONE = ("talk_model", "eleven_voice")


current = Settings()
_lock = threading.Lock()


file: Path | None = None  # where SAVED is kept (gamemaster.rob.json); None keeps nothing


def _fits(name: str, value: Any) -> bool:
    if value is None:
        return name in _MAY_BE_NONE
    return isinstance(value, str) and value in CHOICES.get(name, (value,))


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
        for name in changes:
            if not hasattr(current, name):
                raise KeyError(name)
        changed = any(name in SAVED and getattr(current, name) != value for name, value in changes.items())
        for name, value in changes.items():
            setattr(current, name, value)
        snap = asdict(current)
        if file is not None and changed:
            try:
                file.write_text(json.dumps({n: snap[n] for n in SAVED}) + "\n")
            except OSError:
                pass
    return snap


def snapshot() -> dict[str, Any]:
    with _lock:
        return asdict(current)


TALK = ("talk", "talk_model", "effort", "persona")


def apply_talk(choices: dict[str, Any]) -> None:
    """Mirror the Mac's choices on the Pi, without a settings file or any disk write."""
    with _lock:
        for name in TALK:
            if name in choices and _fits(name, choices[name]):
                setattr(current, name, choices[name])
