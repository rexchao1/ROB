"""A replay set for ROB's lobby talk: a handful of realistic conversations, each played
through the real welcome (brain/games/welcome.py) and the real talk model (brain/talk.py),
the transcript growing turn by turn exactly as at a game night, and printed for a person
to read: does ROB answer what was said, stay coherent, steer to a game too often, repeat
himself, sound like one character? Nothing is heard or said out loud: a stand-in table
feeds each line in and writes down what ROB says, the model's lines marked with their
wait. --quips plays a Mafia game's quips through the same path as Host.quip.

    .venv/bin/python scripts/talk-replay.py                        # every conversation, the default personality
    .venv/bin/python scripts/talk-replay.py --persona sarcastic --only teasing,joke
    .venv/bin/python scripts/talk-replay.py --quips --persona dramatic
    .venv/bin/python scripts/talk-replay.py --model claude-sonnet-5-5

It makes real calls with the key in .env.local (or the file GM_ENV_FILE names); with no
key every reply is the scripted fallback, which is worth reading too. Nothing is
written anywhere.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brain import banter, personas, settings, talk  # noqa: E402
from brain.games.common import Options  # noqa: E402
from brain.games.welcome import Choice, Welcome  # noqa: E402

LISTEN = 4.0  # seconds per listen, the host's own window


class Quiet:
    """Nobody says anything for `seconds`."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds


# name: (what it tries, what the group says in turn, facts the group asked ROB to remember)
CONVERSATIONS: dict[str, tuple[str, list[Any], list[str]]] = {
    "hello": ("a greeting and small talk, then a game", [
        "hey rob!", "how's your night going?", "what did you do today?", "ha, same. long week",
        "okay, what should we play?", "there are four of us", "sure",
    ], []),
    "teasing": ("someone teases ROB", [
        "you're tiny, rob", "can you even see us from down there?", "are you sure you're qualified to host this?",
        "okay fine, you're kind of funny",
    ], []),
    "confused": ("a confused player asks what a game is", [
        "wait, what is this?", "how does this work?", "what's imposter?", "so who's the faker, me?",
        "hmm okay, i think i get it",
    ], []),
    "follow-up": ("a follow-up that needs the earlier line", [
        "we just got back from the beach", "yeah, but it was freezing", "my brother fell in the water",
        "he's fine, he's sitting right here", "he says you're mean",
    ], []),
    "joke": ("someone asks for a joke", [
        "rob, tell us a joke", "that was terrible", "okay, one more", "better. a little better",
    ], []),
    "lost": ("someone says they lost last time", [
        "i lost so badly last time", "everyone ganged up on me", "can you go easy on me tonight?",
        "you're supposed to be on my side!",
    ], []),
    "quiet": ("a table goes quiet, then someone says hi", [
        Quiet(30), "hi, sorry, we were getting snacks", "what did we miss?", "did you miss us?",
    ], []),
    "remembered": ("the group asked ROB to remember things before", [
        "hey rob, maya's here", "she says she's going to win again", "and jordan's here too",
        "what's new with you?",
    ], ["Maya is the reigning champion", "Jordan hates losing to a robot", "the cat is named Biscuit"]),
}

QUIPS = [  # a Mafia game's quips, in order: (slot, context)
    ("death", {"game": "mafia"}),
    ("out", {"game": "mafia"}),
    ("saved", {"game": "mafia"}),
    ("tie", {"game": "mafia"}),
    ("death", {"game": "mafia"}),
    ("out", {"game": "mafia"}),
    ("win", {"game": "mafia", "outcome": "the village won"}),
]


class _Done(BaseException):
    """The conversation's lines are used up."""


class ReplayTable:
    """The Table the welcome talks to: each listen hears the conversation's next line,
    chat() asks the real talk model, and everything said is printed."""

    def __init__(self, t: talk.Talk, said: list[Any], remembered: list[str]) -> None:
        self.talk = t
        self.script: deque[Any] = deque(said)
        self.remembered = remembered
        self.clock = 0.0
        self.quiet = 0.0
        self.written: str | None = None  # the model's last line, to mark it when it is said
        self.ms = 0
        self.waits: list[int] = []

    def now(self) -> float:
        return self.clock

    def wait(self, seconds: float) -> None:
        self.clock += seconds

    def say(self, line: str) -> None:
        mark = f"model {self.ms} ms" if self.written and line in self.written else "scripted"
        print(f"  ROB:  {line}   [{mark}]")
        self.written = None

    def listen(self, seconds: float) -> str:
        self.clock += seconds
        if self.quiet > 0:
            self.quiet -= seconds
            return ""
        if not self.script:
            raise _Done()
        heard = self.script.popleft()
        if isinstance(heard, Quiet):
            print(f"  ({heard.seconds:g} seconds of quiet)")
            self.quiet = heard.seconds - seconds
            return ""
        print(f"  them: {heard}")
        return heard.lower()

    def chat(self, situation: str, heard: str = "", **facts: Any) -> str | None:
        if situation == "welcome" and self.remembered:
            facts["remembered"] = self.remembered
        start = time.monotonic()
        line = self.talk.reply(situation, heard, facts)
        self.ms = int((time.monotonic() - start) * 1000)
        if line is not None and situation == "welcome":
            self.waits.append(self.ms)
        self.written = line
        return line

    def count(self) -> int:
        return 4

    def seated(self, n: int) -> None:
        pass

    def look(self, seat: int | None) -> None:
        pass

    def mood(self, name: str) -> None:
        pass

    def report(self, state: dict[str, Any]) -> None:
        pass

    def quip(self, slot: str, **context: Any) -> None:
        pass

    def sleep(self, seconds: float) -> str | None:
        raise _Done()


def _ready(t: talk.Talk) -> None:
    """The greeting written ahead, as the host has it by the time the robot starts."""
    t.prepare()
    for slot in list((t._ready or {}).values()):  # noqa: SLF001
        slot["done"].wait(15)


def converse(t: talk.Talk, name: str) -> list[int]:
    what, said, remembered = CONVERSATIONS[name]
    print(f"\n=== {name}: {what}" + (f" (remembered: {'; '.join(remembered)})" if remembered else ""))
    _ready(t)
    table = ReplayTable(t, said, remembered)
    w = Welcome(table, random.Random(7), Options(), LISTEN)
    w.greet()
    try:
        while True:
            choice = w.converse()
            if isinstance(choice, Choice):
                print(f"  -> the game starts: {choice.game}")
                break
            if choice is None:
                print("  -> ROB naps")
                break
    except _Done:
        pass
    return table.waits


def quips(t: talk.Talk) -> None:
    """A Mafia game's quips through the host's path: the talk's quip with the recap, then
    the recap keeps the moment and drops a repeat."""
    print("\n=== quips: a game of Mafia, moment by moment")
    recap = banter.Recap()
    for slot, context in QUIPS:
        start = time.monotonic()
        line = recap.keep(slot, t.quip(slot, context, recap))
        ms = int((time.monotonic() - start) * 1000)
        print(f"  [{slot}, at most {banter.words(slot)} words]  {line or '(nothing)'}   [{ms} ms]")


def _note(msg: str) -> None:
    """The talk's log: only what went wrong (a dropped line, an error), inline."""
    if not msg.startswith("talk: ") or msg[6:].split(" ")[0].isdigit() or msg.startswith(("talk: anthropic claude", "talk: gemini", "talk: ollama")):
        return
    print(f"  ! {msg}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="talk-replay", description=__doc__.split("\n\n")[0])
    p.add_argument("--persona", default=personas.DEFAULT, choices=sorted(personas.PERSONAS))
    p.add_argument("--talk", default="anthropic", choices=("anthropic", "gemini", "ollama", "off"))
    p.add_argument("--model", default=None, help="the talk model (default: the provider's first)")
    p.add_argument("--effort", default="low", choices=talk.EFFORTS)
    p.add_argument("--only", default="", help="conversations to play, comma-separated (default: all)")
    p.add_argument("--quips", action="store_true", help="play a Mafia game's quips instead")
    args = p.parse_args(argv)

    settings.current = settings.Settings(persona=args.persona, talk=args.talk, talk_model=args.model, effort=args.effort)
    t = talk.Talk(log=_note)
    provider, model = t.choice()
    print(f"ROB as {personas.get(args.persona).label}, {provider} {model}, effort {t.effort()}")
    if not t.active():
        print("(no model set up: every reply is scripted)")
    t.warm()
    if args.quips:
        quips(t)
        return 0
    names = [n.strip() for n in args.only.split(",") if n.strip()] or list(CONVERSATIONS)
    unknown = [n for n in names if n not in CONVERSATIONS]
    if unknown:
        p.error(f"no conversation {unknown}; they are {', '.join(CONVERSATIONS)}")
    waits: list[int] = []
    for name in names:
        waits += converse(t, name)
    if waits:
        waits.sort()
        print(f"\n{len(waits)} model replies, wait median {waits[len(waits) // 2]} ms, slowest {waits[-1]} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
