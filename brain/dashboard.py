"""The host's settings API, which the game screen's drawer (GET /dash, brain/dash/index.html)
uses for ROB (personality, voice, speaker) and the AI (provider, model, effort, the
talk's status and a test call). It has no page of its own.

  GET  /dashboard/state      {"robot", "paused", "asleep", "settings", "personas", "games", "talks",
                              "talk_models", "efforts", "voices", "eleven_voices",
                              "speakers", "talk_status", "state", "feed"}; the page polls
                              it each second
  POST /dashboard/settings   {"persona"?, "talk"?, "talk_model"?, "effort"?, "voice"?,
                              "eleven_voice"?, "speaker"?}; an unknown name or value is a
                              400. A new talk drops a talk_model meant for another
                              provider; a new speaker applies at once (Host.set_speaker)
  POST /dashboard/talk-test  one real call to the talk now, the way the game calls it:
                              {"ok", "provider", "model", "line", "error", "ms"}
  POST /dashboard/command    {"say": "let's play wordle"} | {"game": "wordle"} |
                              {"action": "reset" | "stop"}: heard at the host's next
                              listen, as if someone said it

It never shows or takes an API key: the keys stay in .env.local, and talk_model takes a
model name only.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from brain import games, personas, settings, talk

TALKS = ("anthropic", "gemini", "ollama", "off")
VOICES = ("piper", "eleven")
SPEAKERS = {"robot": "Robot", "mac": "This Mac"}
LABELS = {
    "mafia": "Mafia",
    "imposter": "Imposter",
    "wavelength": "Wavelength",
    "twenty": "20 Questions",
    "hotseat": "Hot Seat",
    "wordle": "Wordle",
}
SPOKEN = {"twenty": "twenty questions", "hotseat": "hot seat"}  # what "let's play ..." says
ACTIONS = {"reset": "reset", "stop": "stop the game"}
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,63}")
_KEYLIKE = ("sk-", "aiza", "xi-")  # an API key pasted into the model box is refused
_NO_TALK = {"ok": False, "provider": None, "model": None, "line": None, "error": "the talk is not set up", "ms": 0}


def handle(host: Any, method: str, path: str, body: bytes) -> tuple[int, Any]:
    route = (method, path.rstrip("/") or "/")
    if route == ("GET", "/dashboard/state"):
        return 200, state(host)
    if route == ("POST", "/dashboard/talk-test"):  # takes seconds: this request's own thread waits
        return 200, host.talk.test() if host.talk is not None else dict(_NO_TALK)
    try:
        if route == ("POST", "/dashboard/settings"):
            return 200, change(host, _object(body))
        if route == ("POST", "/dashboard/command"):
            return 200, command(host, _object(body))
    except ValueError as e:
        return 400, {"error": str(e)}
    return 404, {"error": f"no {method} {path}"}


def state(host: Any) -> dict[str, Any]:
    with host._lock:  # noqa: SLF001 - the dashboard is the host's own page
        game = dict(host.state) if host.state is not None else {"game": None}
        feed = list(getattr(host, "feed", ()))
    return {
        "robot": getattr(host, "robot_ok", None),
        "paused": bool(getattr(host, "paused", False)),
        "asleep": bool(getattr(host, "asleep", False)),
        "settings": settings.snapshot(),
        "personas": [{"key": p.key, "label": p.label} for p in personas.PERSONAS.values()],
        "games": [{"key": g, "label": LABELS.get(g, g.replace("_", " ").title())} for g in games.GAMES],
        "talks": list(TALKS),
        "talk_models": talk.MODELS,
        "efforts": list(talk.EFFORTS),
        "voices": list(VOICES),
        "eleven_voices": [{"key": v.key, "label": v.label, "blurb": v.blurb} for v in personas.VOICES.values()],
        "speakers": [{"key": k, "label": label} for k, label in SPEAKERS.items()],
        "talk_status": host.talk.status() if host.talk is not None else None,
        "state": game,
        "feed": feed,
    }


def change(host: Any, body: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    speaker = None
    for name, value in body.items():
        if name == "persona":
            if value not in personas.PERSONAS:
                raise ValueError(f"no personality {value!r}")
        elif name == "talk":
            if value not in TALKS:
                raise ValueError(f"talk is one of {', '.join(TALKS)}")
        elif name == "voice":
            if value not in VOICES:
                raise ValueError(f"voice is one of {', '.join(VOICES)}")
        elif name == "eleven_voice":
            if value is not None and value not in personas.VOICES:
                raise ValueError(f"no voice {value!r}")
            if os.environ.get("ELEVENLABS_API_KEY"):
                changes["voice"] = "eleven"  # picking one turns ElevenLabs on
        elif name == "talk_model":
            if value in (None, ""):
                value = None
            elif not isinstance(value, str) or not _MODEL.fullmatch(value) or value.lower().startswith(_KEYLIKE):
                raise ValueError("talk_model is a model name, like claude-haiku-5-5")
        elif name == "effort":
            if value not in talk.EFFORTS:
                raise ValueError(f"effort is one of {', '.join(talk.EFFORTS)}")
        elif name == "speaker":
            if not isinstance(value, str) or value not in SPEAKERS:
                raise ValueError("speaker is robot or mac")
            speaker = value
            continue  # applied below, through the host, once everything else checks out
        elif name == "mic":
            if value not in settings.CHOICES["mic"]:
                raise ValueError("mic is robot or mac")
        else:
            raise ValueError(f"no setting {name!r}")
        changes[name] = value
    if "talk" in changes and "talk_model" not in changes:
        model = settings.snapshot()["talk_model"]
        if model and not _fits(changes["talk"], model):
            changes["talk_model"] = None  # the new provider's default, not a model it cannot run
    snap = settings.update(**changes)
    if speaker is not None:
        if hasattr(host, "set_speaker"):
            host.set_speaker(speaker)
        else:  # a host without set_speaker yet: the body and the saved pick by hand
            host.body.speaker = speaker
            settings.update(speaker=speaker)
        snap = settings.snapshot()
    return snap


def command(host: Any, body: dict[str, Any]) -> dict[str, Any]:
    if "say" in body:
        text = body["say"]
        if not isinstance(text, str) or not text.strip() or len(text) > 200:
            raise ValueError('expected {"say": "..."} under 200 characters')
    elif "game" in body:
        if body["game"] not in games.GAMES:
            raise ValueError(f"no game {body['game']!r}")
        text = "let's play " + SPOKEN.get(body["game"], body["game"])
    elif body.get("action") in ACTIONS:
        text = ACTIONS[body["action"]]
    else:
        raise ValueError('expected {"say": ...}, {"game": ...} or {"action": "reset" | "stop"}')
    host.inject(text)
    return {"ok": True, "heard": text.strip().lower()}


def _object(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body or b"null")
    except json.JSONDecodeError as e:
        raise ValueError("body is not JSON") from e
    if not isinstance(value, dict):
        raise ValueError("body is not a JSON object")
    return value


def _fits(provider: str, model: str) -> bool:
    """The model is one this provider can run (the test Talk.choice makes); off keeps any."""
    if provider == "anthropic":
        return model.startswith("claude")
    if provider == "gemini":
        return model.startswith("gemini")
    if provider == "ollama":
        return not model.startswith(("claude", "gemini"))
    return True

