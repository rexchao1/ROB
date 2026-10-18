"""The host's talk: short lines from a cloud model (Anthropic by default, Gemini as an
option, Ollama kept), behind Host.chat and Host.quip. Mac only; the referee never
reaches the internet (it asks the Table, which calls this).

The model writes words and nothing else (D14). The games decide every rule, count and
winner; a spoken line that runs long, sounds like an assistant or names a seat is
dropped by fit() and the game says a scripted line instead. Anything slow, missing or
broken returns None for the same reason, so every game still plays offline.

Which provider, which model and which personality are read from brain.settings at each
call, so the dashboard can change them mid-game. Keys come from the environment or
.env.local (ANTHROPIC_API_KEY, GEMINI_API_KEY or GOOGLE_API_KEY) and are
never logged.

Situations (Host.chat(situation, heard, **facts)):
  welcome          lobby small talk; facts players, answering, suggestion
  twenty.guesser   20 Questions, the robot guessing: the next yes/no question or a
                   guess "Is it a ...?"; facts history [[q, a], ...], number, left
  twenty.answer    20 Questions, the robot answering: exactly yes, no, sort of or
                   unknown; facts secret, question
  hotseat.judge    Hot Seat: does the answer fit the category, exactly yes or no;
                   facts category, answer
  anything else    a short generic reply
Quips (Host.quip(slot, **context)) come through quip(); brain/banter.py's slots say
what each moment is.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from brain import banter, personas, settings

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env.local"

TIMEOUT = 4.0  # seconds: past this the game says a scripted line
MAX_WORDS = 20
MAX_SENTENCES = 2

DEFAULT_MODELS = {
    "anthropic": "claude-haiku-5-5",  # claude-sonnet-5-5 also works (--talk-model)
    "gemini": "gemini-2.5-flash",
    "ollama": "llama3.2:3b",
}
KEYS = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
}

HOUSE_RULES = (
    "You are the voice of a small robot hosting game night for a group of friends, "
    "talking out loud. House rules:\n"
    "- One line, two at most, about fifteen words. It is spoken, so keep it natural.\n"
    "- Every line moves the game on. Off-topic chat gets one quick joke, then back to the game.\n"
    "- Sound like a funny friend, never an assistant: no 'great question', no 'I'd be happy to', "
    "no 'certainly', no 'absolutely', never explain yourself or mention being an AI.\n"
    "- Tease the move, never the person: nothing about looks, bodies or identity.\n"
    "- Never decide a rule, a count, a score or a winner, and never hint at anyone's secret.\n"
    "- No emoji, no stage directions, no quotation marks, at most one exclamation mark, no dashes."
)

BLOCKLIST = (
    "great question",
    "good question",
    "i'd be happy to",
    "i would be happy to",
    "happy to help",
    "certainly",
    "absolutely",
    "as an ai",
    "language model",
    "let's dive",
    "dive in",
    "feel free",
    "delve",
    "how can i help",
    "how can i assist",
)

STRUCTURED = {
    "twenty.answer": ("yes", "no", "sort of", "unknown"),
    "hotseat.judge": ("yes", "no"),
}

_NUMBER_WORDS = "one two three four five six seven eight nine ten eleven twelve".split()
_SEAT_NAMED = re.compile(r"\b(?:player|seat)s?\s+(?:\d+|" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)
_EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿️‍]")
_STAGE = re.compile(r"\*[^*]*\*|\([^)]*\)|\[[^\]]*\]")
_SENTENCE = re.compile(r"[^.!?]+[.!?]*")

_env_lock = threading.Lock()
_env_loaded = False


def load_env_local(path: Path = ENV_FILE) -> None:
    """KEY=VALUE lines from .env.local into os.environ, once; a variable
    already set wins. Comments, blank lines and `export ` are allowed."""
    global _env_loaded
    with _env_lock:
        if _env_loaded:
            return
        _env_loaded = True
        try:
            text = path.read_text()
        except OSError:
            return
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :]
            name, _, value = line.partition("=")
            name, value = name.strip(), value.strip().strip("\"'")
            if name and name not in os.environ:
                os.environ[name] = value


def key_for(provider: str) -> str | None:
    for name in KEYS.get(provider, ()):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def fit(line: Any, facts: dict[str, Any] | None = None) -> str | None:
    """A model line fit to say out loud, or None: the first line only, stage directions,
    quotes and emoji stripped, dashes turned into commas; at most two sentences and
    about twenty words; no assistant phrases; no "player three" unless the facts allow
    seats (allow_seats=True)."""
    if not isinstance(line, str):
        return None
    facts = facts or {}
    text = next((part.strip() for part in line.strip().splitlines() if part.strip()), "")
    text = _STAGE.sub("", text)
    text = _EMOJI.sub("", text)
    text = re.sub(r"\s*[—–]\s*|\s+-{1,2}\s+", ", ", text)
    text = text.replace("“", "").replace("”", "").replace('"', "")
    text = re.sub(r"\s+", " ", text).strip().strip("'‘’").strip()
    if not text:
        return None
    lower = text.lower()
    if any(phrase in lower for phrase in BLOCKLIST):
        return None
    if not facts.get("allow_seats") and _SEAT_NAMED.search(text):
        return None
    if len(text.split()) > MAX_WORDS:
        return None
    sentences = [s.strip() for s in _SENTENCE.findall(text) if s.strip()]
    if len(sentences) > MAX_SENTENCES:
        return None
    text = re.sub(r"([!?])[!?]+", r"\1", text)  # "!!" and "?!" read as one mark
    if text.count("!") > 1:  # at most one exclamation mark: keep the last
        head, _, tail = text.rpartition("!")
        text = head.replace("!", ".") + "!" + tail
    return text


def structured(situation: str, text: Any) -> str | None:
    """A structured answer, lower-cased and matched to its options, or None."""
    if not isinstance(text, str):
        return None
    options = STRUCTURED[situation]
    answer = re.sub(r"[^a-z ]", " ", text.lower())
    answer = re.sub(r"\s+", " ", answer).strip()
    if answer in options:
        return answer
    for option in sorted(options, key=len, reverse=True):  # "sort of" before "no"
        if answer.startswith(option + " ") or answer == option:
            return option
    return None


class Talk:
    """The talk client Host.chat and Host.quip call. Every call reads brain.settings."""

    def __init__(
        self,
        ollama_url: str = "http://127.0.0.1:11434",
        timeout: float = TIMEOUT,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self.ollama_url = ollama_url.rstrip("/")
        self.timeout = timeout
        self._log = log or (lambda msg: print(msg, file=sys.stderr, flush=True))
        self._warned: set[str] = set()
        load_env_local()
        provider, model = self.choice()
        if provider == "off":
            self._log("talk: off, scripted lines only")
        elif provider in KEYS and key_for(provider) is None:
            self._warn_no_key(provider)
        else:
            self._log(f"talk: {provider} {model}")

    # --- what the host calls ------------------------------------------------------

    def choice(self) -> tuple[str, str]:
        """(provider, model) from brain.settings; a model meant for another provider is
        replaced by this provider's default."""
        s = settings.current
        provider = s.talk if s.talk in ("anthropic", "gemini", "ollama", "off") else "off"
        model = (s.talk_model or "").strip()
        if provider == "anthropic" and not model.startswith("claude"):
            model = ""
        elif provider == "gemini" and not model.startswith("gemini"):
            model = ""
        elif provider == "ollama" and model.startswith(("claude", "gemini")):
            model = ""
        return provider, model or DEFAULT_MODELS.get(provider, "")

    def active(self) -> bool:
        """A model is set up to answer: not off, and the key is there (Ollama needs none)."""
        provider, _ = self.choice()
        if provider == "off":
            return False
        return provider == "ollama" or key_for(provider) is not None

    def reply(self, situation: str, heard: str, facts: dict[str, Any]) -> str | None:
        facts = dict(facts or {})
        if situation in STRUCTURED:
            text = self._ask(_JUDGE, self._prompt(situation, heard, facts), max_tokens=8, temperature=0.0)
            return structured(situation, text)
        text = self._ask(self._system(), self._prompt(situation, heard, facts), max_tokens=80, temperature=0.9)
        line = fit(text, facts)
        if situation == "twenty.guesser" and line is not None and not (
            line.rstrip().endswith("?") or re.match(r"(?i)^guess\s*:", line.strip())
        ):
            return None
        return line

    def quip(self, slot: str, context: dict[str, Any]) -> str | None:
        """One short line at a slot the script marks (D14), held to banter's stricter
        rules: no player, seat or number, at most twelve words."""
        about = banter.SLOTS.get(slot, "Something just happened in the game.")
        safe = {k: v for k, v in (context or {}).items() if isinstance(v, (str, bool)) and not banter._BANNED.search(str(v))}  # noqa: SLF001
        extra = f" Context: {json.dumps(safe)}." if safe else ""
        prompt = (
            f"The moment: {about}{extra}\n"
            f"Say one short line for it, at most {banter.MAX_WORDS} words. Never name a player, "
            "never use a number, never hint at anyone's secret role. Output only the line."
        )
        text = self._ask(self._system(), prompt, max_tokens=40, temperature=0.9)
        line = fit(text)
        return banter.clean(line) if line else None

    # --- prompts ------------------------------------------------------------------

    def _system(self) -> str:
        persona = personas.get(settings.current.persona)
        return f"{HOUSE_RULES}\n\nYour personality: {persona.style}"

    def _prompt(self, situation: str, heard: str, facts: dict[str, Any]) -> str:
        said = heard.strip()
        if situation == "welcome":
            ask = (
                "They asked you something: answer it in a few words, then steer back to picking a game."
                if facts.get("answering")
                else "Reply in one short, playful line, then steer back to picking a game."
            )
            pick = f" You suggested {facts['suggestion']}." if facts.get("suggestion") else ""
            return (
                "Game night is about to start and the group is picking a game."
                f"{pick} Someone just said: \"{said}\"\n{ask}\n"
                "Do not use any numbers and do not say 'player' or 'seat'. Output only the line."
            )
        if situation == "twenty.guesser":
            history = facts.get("history") or []
            asked = "\n".join(f"Q: {q} A: {a}" for q, a in history) or "(nothing yet)"
            number = facts.get("number", len(history) + 1)
            left = facts.get("left")
            last = " This is one of your last questions: if you have a good idea, guess now." if isinstance(left, int) and left <= 2 else ""
            return (
                "You are playing 20 Questions. The player thought of something and you are guessing it.\n"
                f"So far:\n{asked}\n"
                f"This is question {number}.{last}\n"
                "Ask the one yes/no question that narrows it down best, without repeating one, "
                "or if you are fairly sure, guess it by writing GUESS: and the thing, like GUESS: a toaster. "
                "Under twelve words. Output only the question."
            )
        if situation == "twenty.answer":
            return (
                "You are answering in 20 Questions.\n"
                f"The secret thing is: {facts.get('secret', '')}\n"
                f"The question: \"{facts.get('question') or said}\"\n"
                "Answer about the secret thing with exactly one of: yes, no, sort of, unknown. "
                "Say unknown if it is not a yes/no question or cannot be answered about it."
            )
        if situation == "hotseat.judge":
            return (
                f"Category: {facts.get('category', '')}\n"
                f"Answer said out loud: \"{facts.get('answer') or said}\"\n"
                "Is the answer a real example of the category? Be generous with speech-to-text "
                "spelling mistakes. Answer with exactly yes or no."
            )
        known = {k: v for k, v in facts.items() if isinstance(v, (str, int, float, bool))}
        context = f" Facts: {json.dumps(known)}." if known else ""
        parts = [f"The moment in the game: {situation}.{context}"]
        if said:
            parts.append(f"Someone just said: \"{said}\"")
        parts.append("Reply with one short line. Output only the line.")
        return "\n".join(parts)

    # --- providers ----------------------------------------------------------------

    def _ask(self, system: str, prompt: str, *, max_tokens: int, temperature: float) -> str | None:
        provider, model = self.choice()
        if provider == "off":
            return None
        try:
            if provider == "anthropic":
                return self._anthropic(model, system, prompt, max_tokens, temperature)
            if provider == "gemini":
                return self._gemini(model, system, prompt, max_tokens, temperature)
            return self._ollama(model, system, prompt, max_tokens, temperature)
        except urllib.error.HTTPError as e:
            self._log(f"talk: {provider} answered HTTP {e.code}")
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError, TypeError) as e:
            self._log(f"talk: {provider} failed ({type(e).__name__})")
        return None

    def _post(self, url: str, body: dict[str, Any], headers: dict[str, str]) -> Any:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json", **headers}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as res:
            return json.loads(res.read())

    def _anthropic(self, model: str, system: str, prompt: str, max_tokens: int, temperature: float) -> str | None:
        key = key_for("anthropic")
        if key is None:
            self._warn_no_key("anthropic")
            return None
        answer = self._post(
            "https://api.anthropic.com/v1/messages",
            {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
        )
        parts = [c.get("text", "") for c in answer.get("content", []) if isinstance(c, dict) and c.get("type") == "text"]
        return "".join(parts).strip() or None

    def _gemini(self, model: str, system: str, prompt: str, max_tokens: int, temperature: float) -> str | None:
        key = key_for("gemini")
        if key is None:
            self._warn_no_key("gemini")
            return None
        config: dict[str, Any] = {"maxOutputTokens": max_tokens, "temperature": temperature}
        if model.startswith("gemini-2.5"):
            config["thinkingConfig"] = {"thinkingBudget": 0}  # no thinking: a quick line, not an essay
        answer = self._post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            {
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": config,
            },
            {"x-goog-api-key": key},
        )
        parts = answer["candidates"][0]["content"].get("parts", [])
        return "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip() or None

    def _ollama(self, model: str, system: str, prompt: str, max_tokens: int, temperature: float) -> str | None:
        answer = self._post(
            self.ollama_url + "/api/generate",
            {
                "model": model,
                "system": system,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "30m",
                "options": {"num_predict": max_tokens, "temperature": temperature},
            },
            {},
        )
        text = answer.get("response") if isinstance(answer, dict) else None
        return text.strip() if isinstance(text, str) and text.strip() else None

    def _warn_no_key(self, provider: str) -> None:
        if provider in self._warned:
            return
        self._warned.add(provider)
        names = " or ".join(KEYS[provider])
        self._log(f"talk: no {names} (environment or .env.local), scripted lines only")


_JUDGE = (
    "You are a quick, fair judge for a party game. Answer with only the word or words "
    "asked for, lower-case, nothing else."
)
