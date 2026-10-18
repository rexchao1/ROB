"""The host's talk: short lines from a cloud model (Anthropic by default, Gemini as an
option, Ollama kept), behind Host.chat and Host.quip. Mac only; the referee never
reaches the internet (it asks the Table, which calls this).

The model writes words and nothing else (D14). The games decide every rule, count and
winner; a spoken line that runs long, sounds like an assistant or names a seat is
dropped by fit() and the game says a scripted line instead. Anything slow, missing or
broken returns None for the same reason, so every game still plays offline.

Which provider, which model, which effort and which personality are read from
brain.settings at each call, so the dashboard can change them mid-game. MODELS lists the
models the page offers (the first of each provider is its default); any name starting
with "claude" or "gemini" also works. Keys come from the environment or .env.local
(ANTHROPIC_API_KEY, GEMINI_API_KEY or GOOGLE_API_KEY) and are never logged.

Each Claude model takes a different request (anthropic_body): Claude 4.7 and later
answer HTTP 400 to a temperature, and thinking is turned off where the model allows it
at the effort asked, else it is given room. A failed call logs the provider's own error
message and status() keeps the last outcome for the page; test() makes one real call
for the page's Test button.

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
import http.client
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from brain import banter, personas, settings

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env.local"

TIMEOUT = 4.0  # seconds: the least any call waits; past its own wait the game says a scripted line
MAX_WORDS = 16
MAX_SENTENCES = 2

EFFORTS = settings.CHOICES["effort"]  # low, medium, high, max: how hard the model thinks

MODELS: dict[str, list[dict[str, str]]] = {  # what the page offers; the first is the default
    "anthropic": [
        {"key": "claude-haiku-5-5", "label": "Haiku 5.5", "blurb": "Fastest and cheapest."},
        {"key": "claude-sonnet-5-5", "label": "Sonnet 5.5", "blurb": "Smarter, a bit slower."},
        {"key": "claude-opus-5-5", "label": "Opus 5.5", "blurb": "Smartest and slowest; it always thinks first."},
    ],
    "gemini": [
        {"key": "gemini-2.5-flash", "label": "Gemini 2.5 Flash", "blurb": "Fast and cheap."},
        {"key": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash-Lite", "blurb": "Fastest and cheapest, a little plainer."},
        {"key": "gemini-2.5-pro", "label": "Gemini 2.5 Pro", "blurb": "Smartest and slowest; it always thinks first."},
    ],
    "ollama": [
        {"key": "llama3.2:3b", "label": "Llama 3.2 3B", "blurb": "Runs on this Mac, no key and no internet."},
    ],
}
DEFAULT_MODELS = {provider: models[0]["key"] for provider, models in MODELS.items()}
KEYS = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
}

HOUSE_RULES = (
    "You are ROB, a small robot hosting game night for a group of friends, "
    "talking out loud. Your name is ROB; say it only when someone asks who you are. House rules:\n"
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
_ORDINALS = "first second third fourth fifth sixth seventh eighth ninth tenth".split()
_SEAT_NUMBER = r"(?:\d+|" + "|".join(_NUMBER_WORDS + _ORDINALS) + r")"
# "player three", "player number three", "seat 4", "number three", "the third player"
_SEAT_NAMED = re.compile(
    r"\b(?:(?:player|seat)s?\s+(?:number\s+)?" + _SEAT_NUMBER + r"|number\s+" + _SEAT_NUMBER
    + r"|the\s+(?:" + "|".join(_ORDINALS) + r")\s+(?:player|seat))\b",
    re.IGNORECASE,
)
_EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿️‍]")
_STAGE = re.compile(r"\*[^*]*\*|\([^)]*\)|\[[^\]]*\]")
_SENTENCE = re.compile(r"[^.!?]+[.!?]*")
_CLAUDE = re.compile(r"claude-([a-z]+)-(\d+)(?:-(\d{1,2}))?(?!\d)")  # family, major, minor (a date is not a minor)
_KEYLIKE = re.compile(r"sk-ant-[\w-]+|AIza[\w-]{20,}")

THINKING_TOKENS = {"low": 1024, "medium": 2048, "high": 4096, "max": 8192}  # room for thinking, when it runs
GEMINI_BUDGETS = {"low": 0, "medium": 1024, "high": 4096, "max": 8192}  # thinkingBudget by effort
GEMINI_THINKING = (  # (model prefix, its least thinking budget); flash-lite before flash
    ("gemini-2.5-flash-lite", 0),
    ("gemini-2.5-flash", 0),
    ("gemini-2.5-pro", 128),  # Pro always thinks
)
_SLOWER = {"high": 1.5, "max": 2.0}  # more wait at the high efforts
TEST_PROMPT = "Say a one-line hello to the table, under ten words."

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
    about fifteen words; no assistant phrases; no "player three", "the third player"
    or "number three" unless the facts allow seats (allow_seats=True)."""
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


def anthropic_body(model: str, effort: str, system: str, prompt: str, max_tokens: int, temperature: float) -> dict[str, Any]:
    """The Messages API body for one line, shaped for the model, since each answers HTTP
    400 to a field it does not take. Claude 4.6 and older take a temperature and think
    only when asked; the effort goes to the ones that take it (not Haiku 4.5 or Sonnet
    4.5). Claude 4.7 and later take no temperature. On the 5 models thinking is turned
    off where the model allows it at this effort (Haiku and the 5.0 models by "disabled",
    Sonnet 5.5 by "between_tools", none at max); where it still runs (Opus 5.5, Fable,
    any effort at max) max_tokens leaves it room. A name we do not know gets only the
    fields every model takes."""
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    m = _CLAUDE.match(model)
    if m is None:
        return body
    family, version = m.group(1), (int(m.group(2)), int(m.group(3) or 0))
    if version <= (4, 6):
        body["temperature"] = temperature
        if version == (4, 6):
            body["output_config"] = {"effort": effort}
        elif family == "opus" and version == (4, 5):
            body["output_config"] = {"effort": "high" if effort == "max" else effort}  # max came with 4.6
        return body
    body["output_config"] = {"effort": effort}
    if version < (5, 0):  # Opus 4.7 and 4.8: no thinking unless asked for
        return body
    off: dict[str, str] | None = None
    if effort != "max":
        if family == "sonnet" and version >= (5, 5):
            off = {"type": "between_tools"}
        elif family == "haiku" or (family in ("sonnet", "opus") and version == (5, 0)):
            off = {"type": "disabled"}
    if off is not None:
        body["thinking"] = off
    else:
        body["max_tokens"] = max_tokens + THINKING_TOKENS.get(effort, THINKING_TOKENS["max"])
    return body


def gemini_config(model: str, effort: str, max_tokens: int, temperature: float) -> dict[str, Any]:
    """Gemini's generationConfig for one line: no thinking on Flash and Flash-Lite at low
    effort, a bigger budget at each higher one (Pro takes 128 at least), with
    maxOutputTokens raised by the budget. A model we do not know keeps its own thinking."""
    config: dict[str, Any] = {"maxOutputTokens": max_tokens, "temperature": temperature}
    least = next((n for prefix, n in GEMINI_THINKING if model.startswith(prefix)), None)
    if least is None:
        return config
    budget = max(GEMINI_BUDGETS.get(effort, 0), least)
    config["thinkingConfig"] = {"thinkingBudget": budget}
    config["maxOutputTokens"] = max_tokens + budget
    return config


def timeout_for(provider: str, model: str, effort: str) -> float:
    """Seconds a cloud call may take before the game says a scripted line: about 6 for
    Haiku and quick Flash, 10 for Sonnet and thinking Flash, 20 for Opus, Fable and Pro,
    more at high and max. 0 for Ollama (the Talk's own timeout)."""
    if provider == "anthropic":
        wait = 6.0 if "haiku" in model else 10.0 if "sonnet" in model else 20.0
    elif provider == "gemini":
        wait = 20.0 if "pro" in model else 6.0 if effort == "low" else 10.0
    else:
        return 0.0
    return wait * _SLOWER.get(effort, 1.0)


def _short(text: str, limit: int = 200) -> str:
    """A message fit for the log and the page: one line, no key, about limit characters."""
    text = _KEYLIKE.sub("[key]", re.sub(r"\s+", " ", text).strip())
    for names in KEYS.values():
        for name in names:
            value = os.environ.get(name, "").strip()
            if len(value) >= 8:
                text = text.replace(value, "[key]")
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _error_message(e: urllib.error.HTTPError) -> str:
    """The provider's own reason for an HTTP error ({"error": {"message": ...}}), or ""."""
    try:
        answer = json.loads(e.read() or b"null")
    except (OSError, ValueError, http.client.HTTPException):
        return ""
    error = answer.get("error") if isinstance(answer, dict) else None
    message = error.get("message") if isinstance(error, dict) else error
    if isinstance(message, str) and "not scoped to a workspace" in message:
        kind = "-".join((key_for("anthropic") or "").split("-")[:3])  # "sk-ant-usr": the key's type, never the key
        return (
            f"Anthropic says the saved key ({kind}...) is not tied to a workspace: paste a workspace "
            "key (sk-ant-api03...) in Keys, or set the Anthropic workspace ID (wrkspc_...)"
        )
    return _short(message) if isinstance(message, str) else ""


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
        self._lock = threading.Lock()  # the host thread and the dashboard's both call
        self._last: dict[str, Any] | None = None  # the last call's outcome, for status()
        load_env_local()
        provider, model = self.choice()
        if provider == "off":
            self._log("talk: off, scripted lines only")
        elif provider in KEYS and key_for(provider) is None:
            self._warn_no_key(provider)
        else:
            self._log(f"talk: {provider} {model}, effort {self.effort()}")

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

    def effort(self) -> str:
        """The effort from brain.settings; anything else reads as low."""
        effort = settings.current.effort
        return effort if effort in EFFORTS else "low"

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

    def status(self) -> dict[str, Any]:
        """What the page shows: the provider, model and effort now, whether the key is
        there (None when none is needed), and the last call's outcome (ok, a short error,
        when and how long), None until a call is made with these choices."""
        provider, model = self.choice()
        effort = self.effort()
        with self._lock:
            last = self._last if self._last and self._last["choice"] == (provider, model, effort) else None
        return {
            "provider": provider,
            "model": model or None,
            "effort": effort,
            "key_set": key_for(provider) is not None if provider in KEYS else None,
            "ok": last["ok"] if last else None,
            "error": last["error"] if last else None,
            "at": last["at"] if last else None,
            "ms": last["ms"] if last else None,
        }

    def test(self) -> dict[str, Any]:
        """One real call now, the way the game makes them (the page's Test button): a short
        hello through the system prompt and fit(). ok is whether the model answered; error
        says why not, or that its answer was not a line ROB would say."""
        provider, model = self.choice()
        text, error, ms = self._call(self._system(), TEST_PROMPT, max_tokens=40, temperature=0.9)
        ok = error is None
        line = fit(text) if ok else None
        if ok and line is None:
            error = "the model answered, but not with a line ROB would say" if text else "the model answered with no line"
        self._log(f"talk: test {provider} {model}: {line or error}, {ms} ms")
        return {"ok": ok, "provider": provider, "model": model or None, "line": line, "error": error, "ms": ms}

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
        return self._call(system, prompt, max_tokens=max_tokens, temperature=temperature)[0]

    def _call(self, system: str, prompt: str, *, max_tokens: int, temperature: float) -> tuple[str | None, str | None, int]:
        """(text, error, ms) of one call to the chosen model. error is None when the model
        answered (text may still be None: a refusal or no words); every failure is logged
        and kept for status(). Off or a missing key makes no call."""
        provider, model = self.choice()
        if provider == "off":
            return None, "the talk is off", 0
        if provider in KEYS and key_for(provider) is None:
            self._warn_no_key(provider)
            return None, f"no {' or '.join(KEYS[provider])} set", 0
        effort = self.effort()
        timeout = max(self.timeout, timeout_for(provider, model, effort))
        text: str | None = None
        error: str | None = None
        start = time.monotonic()
        try:
            if provider == "anthropic":
                text = self._anthropic(model, effort, system, prompt, max_tokens, temperature, timeout)
            elif provider == "gemini":
                text = self._gemini(model, effort, system, prompt, max_tokens, temperature, timeout)
            else:
                text = self._ollama(model, system, prompt, max_tokens, temperature, timeout)
        except urllib.error.HTTPError as e:
            message = _error_message(e)
            error = f"HTTP {e.code}: {message}" if message else f"HTTP {e.code}"
            self._log(f"talk: {provider} answered {error}")
        except (TimeoutError, urllib.error.URLError) as e:
            reason = getattr(e, "reason", e)
            error = f"no answer in {timeout:.0f} s" if isinstance(reason, TimeoutError) else _short(f"could not reach it ({reason})")
            self._log(f"talk: {provider} {error}")
        except (OSError, http.client.HTTPException, ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
            error = f"failed ({type(e).__name__})"
            self._log(f"talk: {provider} {error}")
        ms = int((time.monotonic() - start) * 1000)
        with self._lock:
            self._last = {"choice": (provider, model, effort), "ok": error is None, "error": error, "at": time.time(), "ms": ms}
        return text, error, ms

    def _post(self, url: str, body: dict[str, Any], headers: dict[str, str], timeout: float | None = None) -> Any:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json", **headers}
        )
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as res:
            return json.loads(res.read())

    def _anthropic(
        self, model: str, effort: str, system: str, prompt: str, max_tokens: int, temperature: float, timeout: float
    ) -> str | None:
        key = key_for("anthropic")
        if key is None:
            self._warn_no_key("anthropic")
            return None
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()
        if workspace:  # a key not tied to a workspace (sk-ant-usr...) names one on every call
            headers["anthropic-workspace-id"] = workspace
        answer = self._post(
            "https://api.anthropic.com/v1/messages",
            anthropic_body(model, effort, system, prompt, max_tokens, temperature),
            headers,
            timeout,
        )
        if answer.get("stop_reason") == "refusal":
            self._log("talk: anthropic refused the line")
            return None
        parts = [c.get("text", "") for c in answer.get("content", []) if isinstance(c, dict) and c.get("type") == "text"]
        text = "".join(parts).strip()
        if not text and answer.get("stop_reason") == "max_tokens":
            self._log(f"talk: {model} ran out of tokens before the line")
        return text or None

    def _gemini(
        self, model: str, effort: str, system: str, prompt: str, max_tokens: int, temperature: float, timeout: float
    ) -> str | None:
        key = key_for("gemini")
        if key is None:
            self._warn_no_key("gemini")
            return None
        answer = self._post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            {
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": gemini_config(model, effort, max_tokens, temperature),
            },
            {"x-goog-api-key": key},
            timeout,
        )
        parts = answer["candidates"][0]["content"].get("parts", [])
        return "".join(p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought")).strip() or None

    def _ollama(self, model: str, system: str, prompt: str, max_tokens: int, temperature: float, timeout: float) -> str | None:
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
            timeout,
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
