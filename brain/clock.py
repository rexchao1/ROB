"""The brain's clock. Game time (the two-minute day, the one-second blank, the photo
poll, every listening window) is read and waited on here and nowhere else, so test
mode can run it virtually.

RealClock is the wall: sleep() is time.sleep().

VirtualClock moves only when advance() moves it. A worker thread (the host's loop)
that calls sleep() blocks until the clock passes its deadline. advance(n) steps
through the sleepers' deadlines in order, waking each in turn, and returns only once
every registered worker is blocked in sleep() again (or has finished): so when a
test's POST /test/advance answers, the brain has done everything it would do in that
time, and nothing it does depends on how fast the machine is. A worker that blocks
on anything but the clock for longer than the real-time limit makes advance() raise
ClockStuck instead of hanging the test.
"""

from __future__ import annotations

import threading
import time
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float:
        """Seconds since the clock's start."""
        ...

    def sleep(self, seconds: float) -> None:
        """Let `seconds` pass on this clock."""
        ...


class RealClock:
    def __init__(self) -> None:
        self._start = time.monotonic()

    def now(self) -> float:
        return time.monotonic() - self._start

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class ClockStuck(RuntimeError):
    """A registered worker did not get back to sleep() within the real-time limit."""


class ClockCancelled(BaseException):
    """Raised inside a cancelled thread's sleep() (a test resetting the brain). A
    BaseException, so a game's or the host's ordinary error handling cannot swallow it."""


class VirtualClock:
    def __init__(self, settle_limit: float = 10.0) -> None:
        self._now = 0.0
        self._cond = threading.Condition()
        self._advancing = threading.Lock()  # one advance() at a time
        self._workers: set[int] = set()  # thread idents advance() waits for
        self._sleeping: dict[int, float] = {}  # thread ident -> deadline
        self._cancelled: set[int] = set()  # threads whose sleep() raises ClockCancelled
        self.settle_limit = settle_limit

    def now(self) -> float:
        with self._cond:
            return self._now

    # --- the workers -------------------------------------------------------------

    def register(self, ident: int | None = None) -> None:
        """advance() waits for this thread (default: the caller) to block in sleep()."""
        with self._cond:
            self._workers.add(threading.get_ident() if ident is None else ident)
            self._cond.notify_all()

    def unregister(self, ident: int | None = None) -> None:
        with self._cond:
            me = threading.get_ident() if ident is None else ident
            self._workers.discard(me)
            self._cancelled.discard(me)
            self._cond.notify_all()

    def cancel(self, ident: int | None) -> None:
        """Make the thread's sleep(), now and from now on until it unregisters, raise
        ClockCancelled: how a test's reset stops the host wherever it is."""
        if ident is None:
            return
        with self._cond:
            self._cancelled.add(ident)
            self._cond.notify_all()

    def sleep(self, seconds: float) -> None:
        """Block the caller until the clock reaches now + seconds. Zero or less returns at
        once. Any thread may sleep; only registered ones are waited for by advance()."""
        me = threading.get_ident()
        with self._cond:
            if me in self._cancelled:
                raise ClockCancelled()
            if seconds <= 0:
                return
            deadline = self._now + seconds
            self._sleeping[me] = deadline
            self._cond.notify_all()
            try:
                while self._now < deadline and me not in self._cancelled:
                    self._cond.wait()
            finally:
                del self._sleeping[me]
                self._cond.notify_all()
            if me in self._cancelled:
                raise ClockCancelled()

    # --- the test side -----------------------------------------------------------

    def reset(self) -> float:
        """Back to zero. Only with no sleepers (the host's worker stopped first)."""
        with self._cond:
            if self._sleeping:
                raise RuntimeError("reset() with threads still asleep on the clock")
            self._now = 0.0
            return self._now

    def settle(self) -> float:
        """Wait (real time, bounded) until every registered worker is asleep; the clock
        does not move."""
        with self._advancing, self._cond:
            self._wait_quiet()
            return self._now

    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("the clock does not run backwards")
        with self._advancing, self._cond:
            target = self._now + seconds
            self._wait_quiet()
            while True:
                # Deadlines already passed belong to sleepers woken and not yet run.
                due = [d for d in self._sleeping.values() if self._now < d <= target]
                if not due:
                    break
                self._now = max(self._now, min(due))
                self._cond.notify_all()
                self._wait_quiet()
            self._now = target
            self._cond.notify_all()
            return self._now

    def _quiet(self) -> bool:
        return all(w in self._sleeping and self._sleeping[w] > self._now for w in self._workers)

    def _wait_quiet(self) -> None:
        give_up = time.monotonic() + self.settle_limit
        while not self._quiet():
            left = give_up - time.monotonic()
            if left <= 0:
                busy = sorted(w for w in self._workers if not (w in self._sleeping and self._sleeping[w] > self._now))
                names = {t.ident: t.name for t in threading.enumerate()}
                raise ClockStuck(
                    f"at t={self._now:.2f} the worker(s) {[names.get(w, w) for w in busy]} did not get back to "
                    f"sleep within {self.settle_limit} s of real time"
                )
            self._cond.wait(left)
