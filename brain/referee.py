"""`python3 -m brain.referee --table http://MAC:8090`: the game master's rules on the
QNX Pi, playing through the Table the brain on the Mac serves (brain/remote.py).

  python3 -m brain.referee --table URL [--token T] [--seed N]

The same loop as the Host's own (brain/lobby.py, shared with brain/host.py): listen
for a game's name, play it (brain/games/), go back to idle; a game that fails says the
recovery line, and the robot dropping off Wi-Fi between games is waited out. The brain
on the Mac sets the robot up; the referee only plays.

Standard library only: it imports the rules, the ears, the lines and brain.remote,
never the body, the camera or the voice (no numpy, OpenCV or Pillow on QNX).

When the table starts over (a test's reset, or the brain restarted) the referee drops
the game without a word and attaches again; on a fresh table it runs the welcome
first when the brain's hello asks for it (the brain's --welcome). When the table stops answering it keeps
trying; a game cut off that way ends with the recovery line once the table is back.
Without --seed the rng is the brain's seed when it sends one (test mode: reseeded at
every reset, so a game deals as it would in the brain), else random.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import random
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from brain import games
from brain.facts import Facts
from brain.lobby import Lobby
from brain.pi_talk import PiTable
from brain.remote import RemoteTable, TableRefused, TableReset, TableUnreachable

RETRY = 2.0  # seconds between attempts to reach the table
RECOVERY = "Sorry, I lost my place. Tap my head to start again."  # the brain's line when it sends none
LISTEN_WINDOW = 4.0


class Referee:
    def __init__(self, table: Any, seed: int | None = None, log: Callable[[str], None] | None = None, retry: float = RETRY, remembered: Facts | None = None) -> None:
        self.table = table
        self.facts = remembered if remembered is not None else Facts()
        self.seed = seed
        self.rng = random.Random(seed)
        self.options = games.Options()
        self.listen_window = LISTEN_WINDOW
        self.recovery = RECOVERY
        self.retry = retry
        self.epoch: str | None = None
        self.stopped = threading.Event()  # stop(): run() returns at its next chance
        self._log = log or (lambda msg: print(msg, file=sys.stderr, flush=True))
        self._lobby: Lobby | None = None

    @property
    def playing(self) -> str | None:
        """The game being played, if any."""
        return self._lobby.playing if self._lobby is not None else None

    def stop(self) -> None:
        """Return from run() once the call in flight answers (an embedding's teardown)."""
        self.stopped.set()

    def run(self) -> None:
        """Attach and play, until the table refuses this referee or stop()."""
        first = True
        lost = False  # a game was cut off by the table going away
        while not self.stopped.is_set():
            try:
                hello = self.table.hello()
            except TableUnreachable as e:
                self._log(f"referee: {e}")
                self.stopped.wait(self.retry)
                continue
            self._attach(hello)
            try:
                welcome = bool(hello.get("welcome")) and not hello.get("calls") and not lost  # a fresh table
                nap = lost or bool(first and hello.get("calls"))  # picking up after a cut, or after another referee
                if nap:
                    if lost:
                        self._say_recovery()  # "... Tap my head to start again."
                    self._idle()
                lost = first = False
                self.idle_loop(welcome, nap=nap)
            except TableReset:
                self._log("referee: the table started over")
            except TableUnreachable as e:
                self._log(f"referee: {e}")
                lost = self.playing is not None
                self.stopped.wait(self.retry)
            self._lobby = None

    def _attach(self, hello: dict[str, Any]) -> None:
        known = {f.name for f in dataclasses.fields(games.Options)}
        self.options = games.Options(**{k: v for k, v in (hello.get("options") or {}).items() if k in known})
        self.listen_window = float(hello.get("listen_window") or LISTEN_WINDOW)
        self.recovery = str(hello.get("recovery") or RECOVERY)
        seed = self.seed if self.seed is not None else hello.get("seed")
        if hello["epoch"] != self.epoch:
            if seed is not None:
                self.rng.seed(seed)
            self._log(f"referee: attached to the table at {getattr(self.table, 'url', '?')} (epoch {hello['epoch']})")
        self.epoch = hello["epoch"]

    def idle_loop(self, welcome: bool = False, nap: bool = False) -> None:
        """The welcome (when the brain asks for it on a fresh table), or a nap until a
        tap (`nap`: picking a table up), else a listen for a game's name; then games and
        naps (brain/lobby.py), until stop()."""
        self._lobby = Lobby(
            self.table, self.rng, options=self.options, listen_window=self.listen_window, recovery=self.recovery,
            remembered=self.facts, rigs=self.table.rig, stopped=self.stopped.is_set, log=lambda msg: self._log(f"referee: {msg}"),
        )
        self._lobby.run(welcome, nap=nap)

    def _say_recovery(self) -> None:
        try:
            self.table.say(self.recovery)
        except Exception:
            pass

    def _idle(self) -> None:
        try:
            self.table.mood("idle")
            self.table.look(None)
        except Exception as e:
            self._log(f"referee: could not get back to idle: {e}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m brain.referee")
    p.add_argument("--table", required=True, help="the brain's Table for the referee, http://HOST:PORT (its port 8090 by default)")
    p.add_argument("--token", default=os.environ.get("GM_TABLE_TOKEN") or None, help="the table's token (default $GM_TABLE_TOKEN)")
    p.add_argument("--seed", type=int, default=None, help="the rng's seed (default: the brain's, else random)")
    p.add_argument("--facts-file", default=os.environ.get("GM_FACTS_FILE", "~/gm-memory/facts.json"),
                   help="lasting group facts outside deployed code (default ~/gm-memory/facts.json)")
    p.add_argument("--key-file", default=os.environ.get("GM_PI_KEY_FILE", "~/gm-memory/talk.env"),
                   help="opt-in Pi talk key file (default ~/gm-memory/talk.env)")
    args = p.parse_args(argv)
    # Talk reads this file but never writes it. Deploy copies it only with --with-key.
    os.environ.setdefault("GM_ENV_FILE", str(Path(args.key_file).expanduser()))
    try:
        table = PiTable(RemoteTable(args.table, token=args.token))
    except ValueError as e:
        print(f"python3 -m brain.referee: {e}", file=sys.stderr)
        return 2
    print(f"referee: playing on the table at {table.url}", flush=True)
    try:
        Referee(table, seed=args.seed, remembered=Facts(Path(args.facts_file).expanduser())).run()
    except KeyboardInterrupt:
        return 0
    except TableRefused as e:
        print(f"referee: {e}", file=sys.stderr, flush=True)
        return 3
    finally:
        table.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
