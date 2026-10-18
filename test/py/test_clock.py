"""The virtual clock: sleepers wake in deadline order, advance() returns only once the
registered workers are asleep again, and a stuck worker raises instead of hanging."""

import threading
import time

import pytest

from brain.clock import ClockStuck, RealClock, VirtualClock


def _worker(clock: VirtualClock, body, started: threading.Event | None = None) -> threading.Thread:
    def run():
        clock.register()
        try:
            if started:
                started.set()
            body()
        finally:
            clock.unregister()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def test_a_sleeper_wakes_only_when_the_clock_passes_its_deadline():
    clock = VirtualClock()
    log = []

    def body():
        clock.sleep(2)
        log.append(("woke", clock.now()))
        clock.sleep(100)

    _worker(clock, body)
    clock.settle()
    assert clock.advance(1.5) == 1.5
    assert log == []
    clock.advance(0.5)
    assert log == [("woke", 2.0)]


def test_advance_steps_through_every_deadline_in_order_and_waits_for_the_work_between():
    clock = VirtualClock()
    log = []

    def body():
        for _ in range(4):
            clock.sleep(0.25)
            time.sleep(0.01)  # real work between sleeps: advance must wait for it
            log.append(clock.now())
        clock.sleep(1000)

    _worker(clock, body)
    clock.settle()
    clock.advance(1.0)
    assert log == [0.25, 0.5, 0.75, 1.0]
    assert clock.now() == 1.0


def test_a_finished_worker_does_not_hold_advance():
    clock = VirtualClock()
    done = threading.Event()
    t = _worker(clock, lambda: done.set())
    t.join(2)
    assert done.is_set()
    assert clock.advance(5) == 5


def test_a_worker_blocked_off_the_clock_raises_instead_of_hanging():
    clock = VirtualClock(settle_limit=0.3)
    gate = threading.Event()
    _worker(clock, lambda: gate.wait(5))
    with pytest.raises(ClockStuck):
        clock.advance(1)
    gate.set()


def test_two_workers_both_settle():
    clock = VirtualClock()
    log = []

    def make(name, step):
        def body():
            for _ in range(2):
                clock.sleep(step)
                log.append((name, clock.now()))
            clock.sleep(1000)

        return body

    _worker(clock, make("a", 1))
    _worker(clock, make("b", 1.5))
    clock.settle()
    clock.advance(3)
    assert sorted(log, key=lambda e: (e[1], e[0])) == [("a", 1), ("b", 1.5), ("a", 2), ("b", 3)]


def test_an_unregistered_sleeper_wakes_without_being_waited_for():
    clock = VirtualClock()
    woke = threading.Event()

    def loader():
        clock.sleep(1)
        woke.set()

    threading.Thread(target=loader, daemon=True).start()
    while not clock._sleeping:  # noqa: SLF001 - wait for it to fall asleep
        time.sleep(0.001)
    clock.advance(2)
    assert woke.wait(2)


def test_the_clock_never_runs_backwards_and_resets_only_when_nobody_sleeps():
    clock = VirtualClock()
    with pytest.raises(ValueError):
        clock.advance(-1)
    clock.advance(3)
    assert clock.reset() == 0.0


def test_the_real_clock_moves_with_the_wall():
    clock = RealClock()
    a = clock.now()
    clock.sleep(0.02)
    assert clock.now() - a >= 0.015


def test_a_cancelled_worker_raises_out_of_its_sleep_and_every_later_one():
    from brain.clock import ClockCancelled

    clock = VirtualClock()
    seen = []

    def body():
        try:
            clock.sleep(100)
        except ClockCancelled:
            seen.append("first")
        try:
            clock.sleep(1)
        except ClockCancelled:
            seen.append("second")

    t = _worker(clock, body)
    clock.settle()
    clock.cancel(t.ident)
    t.join(2)
    assert seen == ["first", "second"]
