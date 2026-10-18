"""The host between games, the same on the Mac (brain/host.py, Host.run) and on the
QNX referee (brain/referee.py). At the start (when asked) and whenever someone says
"reset", the welcome (brain/games/welcome.py) greets the table and talks with it until
a game is picked (D38); started without it, the lobby listens for a game's name. After
a game, or once the talk is over ("not now", or silence after the nudges), the host
naps: Table.sleep() keeps the microphone off until a tap on the head (or a line typed
on the dashboard) wakes it, and it says it is up, counts and talks again. A game that
fails says the recovery line.

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

from brain import ears, facts, games, lines
from brain.games.common import State
from brain.games.welcome import RESTART, Choice, Welcome, clear_memory
from brain.table import Table

PAUSE = 3.0  # seconds after a body error before listening again; the robot reconnects on its own
QUIET = 30.0  # seconds with nothing heard before the lobby listens in longer windows
QUIET_WINDOW = 10.0  # the longer window: the robot chimes each time its microphone opens
NAP_WINDOW = 10.0  # seconds per Table.sleep() call: a referee's call never holds the table for long


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
        remembered: facts.Facts | None = None,
    ) -> None:
        self.table = table
        self.facts = remembered if remembered is not None else facts.for_table(table)
        self.rng = rng
        self.options = options
        self.listen_window = listen_window
        self.recovery = recovery
        self.rigs = rigs
        self.stopped = stopped
        self.pause = pause
        self.playing: str | None = None  # the game being played
        self.seats = 0  # the count the last game settled on
        self._log = log
        self._failing = False
        self._heard_at: float | None = None  # the last time the lobby heard anything

    def run(self, welcome: bool = False, nap: bool = False) -> None:
        """The welcome first when `welcome`, a nap when `nap` (a referee picking up after
        the recovery line, which says to tap), else a listen for a game's name; then games
        and naps, until stopped(). "reset" brings the welcome again."""
        try:
            self._run(welcome, nap)
        finally:
            clear_memory(self.table)

    def _run(self, welcome: bool, nap: bool) -> None:
        step = "welcome" if welcome else "sleep" if nap else "listen"
        self._played = False
        while not self.stopped():
            try:
                step = {"welcome": self._welcome, "listen": self._idle_listen, "sleep": self._sleep}[step]()
            except Exception as e:  # the robot, not the rules: wait and carry on
                self._trouble(e)
                if step == "welcome" or (step == "listen" and self._played):
                    step = "sleep"  # a body error mid-welcome or after a game: a tap starts the talk again

    def _idle_listen(self) -> str:
        """One listen for a game's name (a start without the welcome); the next step."""
        now = self.table.now()
        if self._heard_at is None:
            self._heard_at = now
        quiet = now - self._heard_at >= QUIET
        heard = self.table.listen(max(self.listen_window, QUIET_WINDOW) if quiet else self.listen_window)
        self._answered()
        if heard.strip():
            self._heard_at = self.table.now()
        if ears.wants_to_reset(heard):
            return "welcome"
        if ears.wants_pause(heard) or ears.wants_to_stop(heard) or ears.wants_later(heard):
            self.table.say(lines.NAP)
            return "sleep"
        name = ears.game_named(heard)
        return "listen" if name is None else self._after(self.play(name, heard), name)

    def _sleep(self) -> str:
        """Nap until a tap on the head or a typed line; then that line's game, or the talk
        again; the next step."""
        typed = None
        while typed is None:
            if self.stopped():
                return "sleep"
            typed = self.table.sleep(NAP_WINDOW)
        self._answered()
        if ears.wants_to_reset(typed):
            return "welcome"
        name = ears.game_named(typed)
        if name is not None and ears.asks_rules(typed) is None:  # a rules question goes to the talk
            return self._after(self.play(name, typed), name)
        if ears.wants_to_stop(typed) or ears.wants_pause(typed):
            return "sleep"  # the page's Stop or Pause: already resting
        if ears.wants_resume(typed):
            typed = ""  # the page's Resume or Wake ROB: as good as a tap
        return self._welcome(woke=typed)

    def _welcome(self, woke: str | None = None, too_few: str | None = None) -> str:
        """The welcome and its conversation, then the game picked; or, `woke` (by a tap,
        or a typed line it answers first), the short wake-up and the same talk; or, after
        `too_few` (a game named outside the talk that this count cannot play), a game it
        can. The next step: "welcome" when someone said "reset" (in it, or in
        the game), else a nap."""
        self._log("welcome" if woke is None and too_few is None else "awake")
        w = Welcome(self.table, self.rng, self.options, self.listen_window, self.facts)
        if too_few is not None:
            w.instead_of(too_few, self.seats)
        elif woke is None:
            w.greet()
        else:
            w.wake()
        self._answered()
        first = woke or ""
        while not self.stopped():
            choice = w.converse(first)
            first = ""
            if choice == RESTART:
                return "welcome"
            if not isinstance(choice, Choice):
                return "sleep"
            outcome = self.play(choice.game, choice.heard, choice.counted, choice.seen)
            if outcome != "too few":
                return self._after(outcome, choice.game)
            w.too_few(choice.game, self.seats)
        return "sleep"

    def _after(self, outcome: str, game: str) -> str:
        """After a game: the welcome again on "reset"; the talk, offering a game this
        count can play, on "too few"; else a nap (the recovery line already says to tap
        when the game failed)."""
        self._played = True
        if outcome == "reset":
            return "welcome"
        if outcome == "too few":
            return self._welcome(too_few=game)
        if outcome != "failed":
            try:
                self.table.say(lines.NAP)
            except Exception as e:  # the robot dropped off: nap all the same
                self._log(f"could not say the nap line: {e}")
        return "sleep"

    def play(self, name: str, heard: str, counted: int | None = None, seen: bool = True) -> str:
        """One game, the recovery line if it fails, then the idle look; how it went
        (brain/games/__init__.py), or "failed". self.seats: the count it settled on."""
        rig = self.rigs(name)
        self._log(f"game: {name}" + (f" (rigged: {rig})" if rig else "") + (f" on the welcome's count of {counted}" if counted else ""))
        self.playing = name
        more = {} if counted is None else {"counted": counted, "seen": seen}
        state = State()
        try:
            outcome = games.play(name, self.table, self.rng, heard=heard, rig=rig, options=self.options, state=state, **more) or "played"
        except Exception:
            self._log("the game failed:\n" + traceback.format_exc())
            outcome = "failed"
            try:
                self.table.say(self.recovery)
            except Exception:
                pass
        finally:
            # A game boundary drops the preceding lobby's dialogue, even on reset/loss.
            clear_memory(self.table)
        if state.game == name and outcome in ("played", "stopped", "reset"):
            try:
                self.facts.played(name, state.winner if outcome == "played" else None)
            except OSError:
                self._log("could not save public game totals")
        self.seats = state.seats
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
