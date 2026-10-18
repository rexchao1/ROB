"""The host between games, the same on the Mac (brain/host.py, Host.run) and on the
QNX referee (brain/referee.py): listen for a game's name, play it (brain/games/), go
back to idle. A game that fails says the recovery line. At the start (when asked)
and whenever someone says "reset", the welcome (brain/games/welcome.py) greets the
table and talks with it until a game is picked (D38).

The robot drops off Wi-Fi now and then, so a body error between games (a listen the
robot could not answer) does not end the loop: it is logged, the lobby waits PAUSE
seconds and listens again, and the log says when the robot answers. What does end it
is the caller's own BaseException: the host being stopped (a test's reset), the table
starting over or going away (brain/remote.py).

The robot chimes each time its microphone opens, so after QUIET seconds with nothing
heard the lobby listens in QUIET_WINDOW windows instead, until it hears something.

Standard library only: the referee imports it.
"""

from __future__ import annotations

import random
import time
import traceback
from collections.abc import Callable
from typing import Any

from brain import ears, games
from brain.games.welcome import RESTART, Choice, Welcome
from brain.table import Table

PAUSE = 3.0  # seconds after a body error before listening again; the robot reconnects on its own
QUIET = 30.0  # seconds with nothing heard before the lobby listens in longer windows
QUIET_WINDOW = 10.0  # the longer window: the robot chimes each time its microphone opens


class Lobby:
    def __init__(
        self,
        table: Table,
        rng: random.Random,
        *,
        options: games.Options,
        listen_window: float,
        recovery: str,
        rigs: Callable[[str], dict[str, Any] | None] = lambda game: None,
        stopped: Callable[[], bool] = lambda: False,
        log: Callable[[str], None] = lambda msg: None,
        pause: float = PAUSE,
    ) -> None:
        self.table = table
        self.rng = rng
        self.options = options
        self.listen_window = listen_window
        self.recovery = recovery
        self.rigs = rigs
        self.stopped = stopped
        self.pause = pause
        self.playing: str | None = None  # the game being played
        self._log = log
        self._failing = False
        self._heard_at: float | None = None  # the last time the lobby heard anything

    def run(self, welcome: bool = False) -> None:
        """Listen for a game's name and play it, until stopped(); the welcome first when
        `welcome`, and again whenever someone says "reset"."""
        while not self.stopped():
            try:
                if welcome:
                    welcome = False  # a body error mid-welcome falls back to idle-listening
                    welcome = self._welcome()
                else:
                    welcome = self._idle_listen()
            except Exception as e:  # the robot, not the rules: wait and carry on
                self._trouble(e)

    def _idle_listen(self) -> bool:
        """One idle listen; True when the welcome comes next."""
        now = self.table.now()
        if self._heard_at is None:
            self._heard_at = now
        quiet = now - self._heard_at >= QUIET
        heard = self.table.listen(max(self.listen_window, QUIET_WINDOW) if quiet else self.listen_window)
        self._answered()
        if heard.strip():
            self._heard_at = self.table.now()
        if ears.wants_to_reset(heard):
            return True
        name = ears.game_named(heard)
        return name is not None and self.play(name, heard) == "reset"

    def _welcome(self) -> bool:
        """The welcome and its conversation, then the game picked; True when someone said
        "reset" (in it, or in the game), so it runs again."""
        self._log("welcome")
        w = Welcome(self.table, self.rng, self.options, self.listen_window)
        w.greet()
        self._answered()
        while not self.stopped():
            choice = w.converse()
            if choice == RESTART:
                return True
            if not isinstance(choice, Choice):
                return False
            outcome = self.play(choice.game, choice.heard, choice.counted)
            if outcome == "reset":
                return True
            if outcome != "too few":
                return False
            w.too_few(choice.game)
        return False

    def play(self, name: str, heard: str, counted: int | None = None) -> str:
        """One game, the recovery line if it fails, then the idle look; how it went
        (brain/games/__init__.py), or "failed"."""
        rig = self.rigs(name)
        self._log(f"game: {name}" + (f" (rigged: {rig})" if rig else "") + (f" on the welcome's count of {counted}" if counted else ""))
        self.playing = name
        more = {} if counted is None else {"counted": counted}
        try:
            outcome = games.play(name, self.table, self.rng, heard=heard, rig=rig, options=self.options, **more) or "played"
        except Exception:
            self._log("the game failed:\n" + traceback.format_exc())
            outcome = "failed"
            try:
                self.table.say(self.recovery)
            except Exception:
                pass
        self.playing = None
        self._heard_at = None  # a game just ended: listen closely again
        self.idle()
        return outcome

    def idle(self) -> None:
        try:
            self.table.mood("idle")
            self.table.look(None)
        except Exception as e:
            self._log(f"could not get back to idle: {e}")

    def _trouble(self, e: Exception) -> None:
        if not self._failing:
            self._log(f"the robot did not answer ({type(e).__name__}: {e}); listening again in {self.pause:g} s")
            self._failing = True
        try:
            self.table.wait(self.pause)
        except Exception:
            time.sleep(self.pause)

    def _answered(self) -> None:
        if self._failing:
            self._log("the robot answered again")
            self._failing = False
