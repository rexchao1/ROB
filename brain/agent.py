"""ROB's own moves (docs/CHAT-PLAN.md): one heard line, one talk-model turn, the line he
says and the tools he picked, each checked here before it runs. The model chooses words
and actions; the code still decides every rule, count, score, winner and secret
(D14, D42 as amended by D-chat).

Table.act(situation, heard, **facts) asks the model (on the Mac, or the Pi's own talk)
and answers {"line": str | None, "actions": [{"name": str, "args": {...}}]} or None
(no model, no internet, too slow). run_turn() checks and runs the actions through the
Table, says the line, and, when an information tool ran (count_table, rules), asks once
more with its result so the line can use it.

Standard library only: the QNX referee imports it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from brain.table import Table

GESTURES = ("nod", "shake", "tilt", "look_around")
FACES = ("idle", "night", "day", "tense", "win")  # brain.table.MOODS less "listening", which is the ears'
SETTINGS = ("persona", "eleven_voice", "voice", "speaker", "volume")

# Every tool the model may be offered; a situation offers a subset (LOBBY, GAME).
TOOLS = (
    "look",  # {"seat": int | None}: turn to a seat, None for straight ahead
    "gesture",  # {"name": one of GESTURES}
    "face",  # {"name": one of FACES}
    "setting",  # {"name": one of SETTINGS, "value": str | int}
    "count_table",  # {}: the camera sweep; information, its result goes back to the model
    "rules",  # {"game": str}: the game's scripted rules, said as written; information
    "start_game",  # {"game": str}: ends the turn with that game picked
    "remember",  # {"fact": str}: brain/facts.py filters as for "remember that"
    "forget",  # {}: the last fact
    "nap",  # {}: the lobby naps after the line
)
LOBBY = TOOLS
GAME = ("look", "gesture", "setting")  # side talk in play: no games, no counting, no faces over the game's mood
INFORMATION = ("count_table", "rules")


@dataclass
class Outcome:
    """What one turn did, for the caller."""

    said: str | None = None  # the line ROB said, None when he said nothing
    game: str | None = None  # start_game picked this game
    nap: bool = False  # nap was called
    ran: list[str] = field(default_factory=list)  # the tools that passed their check and ran, in order
    dropped: list[str] = field(default_factory=list)  # the tools refused, "name: why"


def run_turn(table: Table, situation: str, heard: str, facts: dict[str, Any], allowed: tuple[str, ...] = LOBBY) -> Outcome | None:
    """One turn: ask Table.act, check and run each action, say the line. None when the
    model gave nothing (the caller says its scripted line instead).

    facts: what the model sees (transcript, remembered, games, suggestion, seats, ...),
    plus "memory", a brain.facts.Facts for remember and forget, which stays here and
    never travels. "seats" bounds look's seat."""
    facts = dict(facts or {})
    memory = facts.pop("memory", None)
    told = {k: v for k, v in facts.items() if k not in ("tools", "results")}
    answer = _ask(table, situation, heard, told, list(allowed))
    if answer is None:
        return None
    out = Outcome()
    results = _run(table, answer["actions"], allowed, facts, memory, out)
    line = answer["line"]
    if results:  # an information tool ran: one more turn, the line written with what it found
        follow = _ask(table, situation, heard, {**told, "seats": facts.get("seats"), "results": results},
                      [t for t in allowed if t not in INFORMATION])
        if follow is not None:
            _run(table, follow["actions"], tuple(t for t in allowed if t not in INFORMATION), facts, memory, out)
            line = follow["line"] or line
    if line:
        table.say(line)
        out.said = line
    return out


def _ask(table: Table, situation: str, heard: str, facts: dict[str, Any], tools: list[str]) -> dict[str, Any] | None:
    """Table.act's answer in its checked shape, {"line": str | None, "actions": [...]}, or None."""
    answer = table.act(situation, heard, tools=tools, **facts)
    if not isinstance(answer, dict):
        return None
    line = answer.get("line")
    line = line.strip() if isinstance(line, str) and line.strip() else None
    actions = [a for a in answer.get("actions") or () if isinstance(a, dict) and isinstance(a.get("name"), str)]
    if line is None and not actions:
        return None
    return {"line": line, "actions": actions}


def _run(table: Table, actions: list[dict[str, Any]], allowed: tuple[str, ...], facts: dict[str, Any], memory: Any, out: Outcome) -> list[str]:
    """Check and run each action in order; what the information tools found."""
    from brain.games.common import GameStopped

    results: list[str] = []
    for action in actions:
        name = action["name"]
        args = action.get("args") if isinstance(action.get("args"), dict) else {}
        if name not in allowed:
            out.dropped.append(f"{name}: not offered")
            continue
        why = _check(name, args, facts, memory, out)
        if why is not None:
            out.dropped.append(f"{name}: {why}")
            continue
        try:
            why, found = _do(table, name, args, facts, memory, out)
        except GameStopped:
            raise
        except Exception as e:  # a move that failed is dropped, never spoken
            why, found = f"failed ({type(e).__name__}: {e})", None
        if why is not None:
            out.dropped.append(f"{name}: {why}")
            continue
        out.ran.append(name)
        if found:
            results.append(found)
    return results


def _check(name: str, args: dict[str, Any], facts: dict[str, Any], memory: Any, out: Outcome) -> str | None:
    """Why the action may not run, or None."""
    from brain import games

    if name == "look":
        seat = args.get("seat")
        seats = facts.get("seats")
        if seat is None:
            return None
        if isinstance(seat, bool) or not isinstance(seat, int):
            return f"seat {seat!r} is not a number"
        if not isinstance(seats, int) or not 1 <= seat <= seats:
            return f"no seat {seat}"
        return None
    if name == "gesture":
        return None if args.get("name") in GESTURES else f"no gesture {args.get('name')!r}"
    if name == "face":
        return None if args.get("name") in FACES else f"no face {args.get('name')!r}"
    if name == "setting":
        return None if args.get("name") in SETTINGS and "value" in args else f"no setting {args.get('name')!r}"
    if name in ("rules", "start_game"):
        if args.get("game") not in games.GAMES:
            return f"no game {args.get('game')!r}"
        if name == "start_game" and out.game is not None:
            return "a game is already picked"
        return None
    if name in ("remember", "forget"):
        if memory is None:
            return "no memory here"
        if name == "remember" and not isinstance(args.get("fact"), str):
            return "no fact"
        return None
    if name in ("count_table", "nap"):
        return None
    return "unknown tool"


def _do(table: Table, name: str, args: dict[str, Any], facts: dict[str, Any], memory: Any, out: Outcome) -> tuple[str | None, str | None]:
    """Run one checked action: (why it did not take, or None; what it found, for an
    information tool)."""
    from brain import lines

    if name == "look":
        table.look(args.get("seat"))
    elif name == "gesture":
        table.gesture(args["name"])
    elif name == "face":
        table.mood(args["name"])
    elif name == "setting":
        if not table.setting(args["name"], args["value"]):
            return f"{args['value']!r} is not a {args['name']}", None
        if args["name"] in ("persona", "eleven_voice", "voice"):  # the line comes after, in the new voice
            return None, f"setting: your {args['name']} is now {args['value']}; say your line as the new you"
    elif name == "start_game":
        out.game = args["game"]
    elif name == "nap":
        out.nap = True
    elif name == "remember":
        result = memory.remember(args["fact"])
        if result != "saved":
            return result, None
    elif name == "forget":
        if not memory.forget_last():
            return "nothing to forget", None
    elif name == "count_table":
        n = table.count()
        facts["seats"] = n  # the follow-up may look at the seats just found
        return None, f"count_table: you counted {n} {'person' if n == 1 else 'people'} at the table"
    elif name == "rules":
        table.say(lines.rules(args["game"]))
        return None, f"rules: you just said the rules of {lines.game_name(args['game'])} out loud, as written; do not repeat them"
    return None, None
