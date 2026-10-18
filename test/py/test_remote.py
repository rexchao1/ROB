"""The Table over the network (brain/remote.py) and the referee that plays through it
(brain/referee.py): a game played by a referee tells the robot exactly what the host
playing it alone would, on the same virtual clock; the clock waits for a referee that
is attached and not for one that is gone; a call is run once however often it is
sent; a reset, another referee and a wrong token are each told apart; and the referee
needs nothing but the standard library."""

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from calls import call
from conftest import _start
from fake_table import FakeTable

from brain import games, lines
from brain.__main__ import make_test_brain
from brain.clock import RealClock, VirtualClock
from brain.lobby import PAUSE
from brain.referee import Referee
from brain.remote import RemoteError, RemoteTable, TableRefused, TableReset, TableServer, TableUnreachable
from brain.table import Card

ROOT = Path(__file__).resolve().parents[2]
SETUP = ["set_off_timeout", "set_blink", "set_avatar", "set_all_leds", "move_head"]
FIVE = [{"bearing": b} for b in (-60, -30, 0, 30, 60)]


def _tools(fake):
    return [c["tool"] for c in fake.device.calls]


def _record(fake):
    """What the robot was told, without the wall times."""
    return [(c["tool"], c["args"], c.get("error"), c.get("line")) for c in fake.device.calls]


def _said(fake):
    return [c.get("line") for c in fake.device.calls if c["tool"] == "pcm" and c.get("error") is None]


def _until(check, seconds=5.0):
    give_up = time.monotonic() + seconds
    while not check():
        assert time.monotonic() < give_up, "timed out"
        time.sleep(0.01)


class _Remote:
    """A test-mode brain with --referee remote and a referee playing on it, in this process."""

    def __init__(self, fake, sets_dir):
        self.tb = make_test_brain(fake.mcp_url, sets_dir=sets_dir, referee="remote")
        self.url = _start(self.tb.server)
        self.tb.clock.settle()
        self.remote = RemoteTable(self.tb.table.url, patience=2.0)
        self.referee = Referee(self.remote, log=lambda msg: None, retry=0.05)
        self.thread = threading.Thread(target=self.referee.run, name="referee", daemon=True)
        self.thread.start()
        _until(self.tb.table.attached)
        assert call(self.url, "POST", "/test/reset") == (200, {"ok": True, "now": 0.0})

    def close(self):
        self.referee.stop()
        self.tb.table.stop()
        self.thread.join(5)
        self.remote.close()
        self.tb.server.shutdown()
        self.tb.server.server_close()


@pytest.fixture
def remote(fake, tmp_path):
    r = _Remote(fake, tmp_path / "sets")
    yield r
    r.close()


def _play_mafia(url):
    call(url, "POST", "/test/table", {"faces": FIVE})
    call(url, "POST", "/test/rig", {"mafia": {"mafia": [2], "doctor": 4}})
    call(url, "POST", "/test/hear", {"text": "let's play mafia"})
    for _ in range(2):  # the count, the deal, and nobody leaning in: the photo poll, the reprompts
        call(url, "POST", "/test/advance", {"seconds": 30})
    return call(url, "GET", "/test/state")[1]


# --- the referee against the brain, end to end ---------------------------------------


def test_a_game_played_by_the_referee_tells_the_robot_what_the_host_alone_would(fake, tmp_path):
    tb = make_test_brain(fake.mcp_url, sets_dir=tmp_path / "sets")
    url = _start(tb.server)
    try:
        call(url, "POST", "/test/reset")
        local_state, local = _play_mafia(url), _record(fake)
    finally:
        tb.host.stop()
        tb.server.shutdown()
        tb.server.server_close()
    r = _Remote(fake, tmp_path / "sets")
    try:
        remote_state, remote = _play_mafia(r.url), _record(fake)
    finally:
        r.close()
    assert local_state["game"] == "mafia" and len(local) > 100
    assert any(line and line.startswith("Five of you.") for _, _, _, line in local)
    assert remote == local  # every call, its arguments and its order, on the same clock
    assert remote_state == local_state


def test_naming_a_game_counts_the_table_and_starts_the_deal(remote, fake):
    assert _tools(fake) == SETUP
    call(remote.url, "POST", "/test/table", {"faces": FIVE})
    call(remote.url, "POST", "/test/hear", {"text": "let's play mafia"})
    call(remote.url, "POST", "/test/advance", {"seconds": 20})
    said = _said(fake)
    assert said[0].startswith("Five of you.")
    assert lines.lean_in(1) in said
    assert call(remote.url, "GET", "/test/state")[1]["seats"] == 5


def test_a_reset_mid_game_puts_the_referee_back_to_idle_listening_without_a_word(remote, fake):
    call(remote.url, "POST", "/test/table", {"faces": FIVE})
    call(remote.url, "POST", "/test/hear", {"text": "let's play mafia"})
    call(remote.url, "POST", "/test/advance", {"seconds": 15})
    epoch = remote.referee.epoch
    assert call(remote.url, "POST", "/test/reset") == (200, {"ok": True, "now": 0.0})
    assert _tools(fake) == SETUP
    assert call(remote.url, "GET", "/test/state") == (200, {"game": None})
    call(remote.url, "POST", "/test/advance", {"seconds": 5})
    assert _tools(fake) == [*SETUP, "set_all_leds", "listen", "get_touch_state"]  # the ring shows it listens (D43), the idle loop's first window, then a look for a hand on the head, as with the host alone
    assert remote.referee.epoch != epoch and remote.referee.playing is None
    assert _said(fake) == []


def test_a_rig_reaches_the_referee_and_is_used_once(remote, fake):
    call(remote.url, "POST", "/test/table", {"faces": FIVE})
    call(remote.url, "POST", "/test/rig", {"imposter": {"word": "beach", "imposter": 3}})
    call(remote.url, "POST", "/test/hear", {"text": "let's play imposter"})
    call(remote.url, "POST", "/test/advance", {"seconds": 20})
    assert remote.tb.host.rigs == {}
    loaded = [c for c in fake.device.calls if c["tool"] == "load_avatar_set" and c.get("error") is None]
    assert loaded and "beach" in str(remote.tb.host._manifest)  # noqa: SLF001


def test_the_dashboard_shows_the_pi_waiting_until_the_referee_calls_in(fake, tmp_path):
    tb = make_test_brain(fake.mcp_url, sets_dir=tmp_path, referee="remote")
    url = _start(tb.server)
    try:
        assert call(url, "GET", "/dash/api/state")[1]["links"]["pi"] == "waiting"
        tb.table.hello("dash-test")
        assert call(url, "GET", "/dash/api/state")[1]["links"]["pi"] == "connected"
    finally:
        tb.table.stop()
        tb.server.shutdown()
        tb.server.server_close()


def test_without_a_referee_the_clock_moves_freely_and_the_robot_is_still_set_up(fake, tmp_path):
    tb = make_test_brain(fake.mcp_url, sets_dir=tmp_path, referee="remote")
    url = _start(tb.server)
    try:
        assert call(url, "POST", "/test/reset") == (200, {"ok": True, "now": 0.0})
        assert _tools(fake) == SETUP
        started = time.monotonic()
        assert call(url, "POST", "/test/advance", {"seconds": 600}) == (200, {"now": 600.0})
        assert time.monotonic() - started < 2
        assert _tools(fake) == SETUP
        assert call(tb.table.url, "GET", "/table/attached")[1]["attached"] is False
    finally:
        tb.table.stop()
        tb.server.shutdown()
        tb.server.server_close()


# --- TableServer and RemoteTable --------------------------------------------------


class _Recorder:
    """A Table that records what reached it and answers with fixed values."""

    def __init__(self, clock=None):
        self.clock = clock or RealClock()
        self.log = []

    def now(self):
        return self.clock.now()

    def wait(self, seconds):
        self.log.append(("wait", seconds))
        self.clock.sleep(seconds)

    def say(self, line):
        self.log.append(("say", line))

    def look(self, seat):
        if seat == 9:
            raise LookupError("no seat 9: the host counted 5")
        self.log.append(("look", seat))

    def count(self):
        self.log.append(("count",))
        return 5

    def prepare(self, cards):
        self.log.append(("prepare", cards))

    def show_private(self, seat, card):
        self.log.append(("show_private", seat, card))
        return seat != 4

    def reveal(self, card, line):
        self.log.append(("reveal", card, line))

    def listen(self, seconds):
        self.log.append(("listen", seconds))
        self.clock.sleep(seconds)
        return "player four"

    def faces_up(self):
        self.log.append(("faces_up",))
        return [2, 5]

    def mood(self, name):
        self.log.append(("mood", name))

    def report(self, state):
        self.log.append(("report", state))

    def quip(self, slot, **context):
        self.log.append(("quip", slot, context))


@pytest.fixture
def served():
    servers = []

    def serve(table=None, clock=None, **kwargs):
        clock = clock or RealClock()
        table = table or _Recorder(clock)
        server = TableServer(table, clock, "127.0.0.1", 0, **kwargs).start()
        servers.append(server)
        return server, table

    yield serve
    for server in servers:
        server.stop()


def _attached(server, **kwargs):
    remote = RemoteTable(server.url, patience=1.0, log=lambda msg: None, **kwargs)
    remote.hello()
    return remote


def test_every_table_method_reaches_the_table_as_the_rules_called_it(served):
    server, table = served()
    remote = _attached(server)
    cards = [Card("MAFIA"), Card("7", "cold - hot")]
    assert isinstance(remote.now(), float)
    remote.wait(0)
    remote.say("Five of you.")
    remote.look(None)
    remote.look(3)
    assert remote.count() == 5
    remote.prepare(cards)
    assert remote.show_private(2, cards[1]) is True
    assert remote.show_private(4, cards[0]) is False
    remote.reveal(Card("VILLAGE", "wins", "win"), "The village wins.")
    assert remote.listen(0) == "player four"
    assert remote.faces_up() == [2, 5]
    remote.mood("night")
    remote.report({"game": "mafia", "warnings": {"3": 1}, "living": [1, 2]})
    remote.quip("death", game="mafia")
    assert table.log == [
        ("wait", 0), ("say", "Five of you."), ("look", None), ("look", 3), ("count",), ("prepare", cards),
        ("show_private", 2, cards[1]), ("show_private", 4, cards[0]),
        ("reveal", Card("VILLAGE", "wins", "win"), "The village wins."), ("listen", 0), ("faces_up",), ("mood", "night"),
        ("report", {"game": "mafia", "warnings": {"3": 1}, "living": [1, 2]}), ("quip", "death", {"game": "mafia"}),
    ]


def test_what_the_host_raises_comes_back_as_a_remote_error_and_the_table_carries_on(served):
    server, table = served()
    remote = _attached(server)
    with pytest.raises(RemoteError, match="no seat 9") as raised:
        remote.look(9)
    assert raised.value.type_name == "LookupError"
    remote.look(1)
    assert table.log == [("look", 1)]


def test_a_call_sent_twice_runs_once(served):
    server, table = served()
    hello = call(server.url, "POST", "/table/hello", {"session": "s"})[1]
    request = {"session": "s", "id": 1, "epoch": hello["epoch"], "method": "say", "args": ["Hi."], "kwargs": {}}
    first = call(server.url, "POST", "/table/call", request)
    assert first == call(server.url, "POST", "/table/call", request) == (200, {"ok": True, "result": None})
    assert table.log == [("say", "Hi.")]
    assert call(server.url, "POST", "/table/call", {**request, "id": 2}) == first
    assert table.log == [("say", "Hi."), ("say", "Hi.")]


def test_a_long_call_is_answered_pending_and_asked_for_again(served):
    server, table = served(hold=0.1)
    remote = _attached(server)
    remote.wait(0.5)
    assert table.log == [("wait", 0.5)]


def test_a_malformed_call_is_refused(served):
    server, _ = served()
    for bad in ({}, {"session": "s", "id": 1, "method": "fly"}, {"session": "s", "id": "1", "method": "say"},
                {"session": "s", "id": 1, "method": "say", "args": "Hi."}):
        assert call(server.url, "POST", "/table/call", bad)[0] == 400
    assert call(server.url, "GET", "/table/nothing")[0] == 404


def test_a_dropped_table_is_waited_for_and_given_up_on(served):
    probe = TableServer(_Recorder(), RealClock(), "127.0.0.1", 0)
    port = probe.address[1]
    probe.stop()  # never served: the port is free and refuses
    late = []
    threading.Timer(0.4, lambda: late.append(served_on(port))).start()

    def served_on(p):
        return TableServer(_Recorder(), RealClock(), "127.0.0.1", p).start()

    remote = RemoteTable(f"http://127.0.0.1:{port}", patience=5.0, log=lambda msg: None)
    try:
        assert remote.hello()["epoch"]  # refused at first, answered once the server is up
    finally:
        _until(lambda: late)
        late[0].stop()
    gone = RemoteTable(f"http://127.0.0.1:{port}", patience=0.5, log=lambda msg: None)
    started = time.monotonic()
    with pytest.raises(TableUnreachable):
        gone.hello()
    assert time.monotonic() - started < 3


def test_after_a_reset_the_old_epoch_is_answered_reset(served):
    server, table = served()
    remote = _attached(server)
    remote.say("one")
    server.reset(lambda: None)
    with pytest.raises(TableReset):
        remote.say("two")
    remote.hello()
    remote.say("three")
    assert table.log == [("say", "one"), ("say", "three")]


def test_a_new_referee_takes_the_table_and_the_old_one_is_refused(served):
    server, table = served()
    old = _attached(server)
    new = _attached(server)
    with pytest.raises(TableRefused):
        old.say("me?")
    new.say("me.")
    assert table.log == [("say", "me.")]


def test_with_a_token_a_referee_without_it_is_refused(served):
    server, table = served(token="s3cret")
    with pytest.raises(TableRefused, match="token"):
        _attached(server)
    _attached(server, token="s3cret").say("in")
    assert table.log == [("say", "in")]


def test_on_the_virtual_clock_the_worker_counts_while_attached_and_is_let_go_after_its_lease(served):
    clock = VirtualClock(settle_limit=5.0)
    server, table = served(clock=clock, lease=0.5)
    remote = _attached(server)
    done = threading.Event()
    threading.Thread(target=lambda: (remote.listen(4), done.set()), daemon=True).start()
    _until(lambda: table.log == [("listen", 4)])
    clock.settle()  # the worker asleep inside the call: quiet
    started = time.monotonic()
    clock.advance(10)  # the listen ends at 4; then the referee is computing, until its lease runs out
    waited = time.monotonic() - started
    assert done.is_set()
    assert 0.4 < waited < 3, waited
    started = time.monotonic()
    clock.advance(10)  # let go: the clock no longer waits for it
    assert time.monotonic() - started < 0.3


# --- the referee's loop, on a fake table -----------------------------------------------


class _Scripted(FakeTable):
    """A FakeTable a Referee can attach to: hello() (one epoch per hello, the last
    repeating) and rig(); once every scripted answer is heard and one more listen hears
    silence, the next listen raises TableRefused, which ends Referee.run()."""

    def __init__(self, *heard, epochs=("e-1",), **kwargs):
        super().__init__(**kwargs)
        self.hear(*heard)
        self.left = len(heard) + 1
        self.epochs = epochs
        self.hellos = 0
        self.rigged = {}

    def hello(self):
        self.hellos += 1
        epoch = self.epochs[min(self.hellos, len(self.epochs)) - 1]
        return {"epoch": epoch, "calls": 0, "seed": 7, "recovery": "Lost.", "listen_window": 4.0}

    def rig(self, game):
        return self.rigged.pop(game, None)

    def listen(self, seconds):
        if self.left == 0:
            raise TableRefused("the script is over")
        self.left -= 1
        return super().listen(seconds)

    def sleep(self, seconds):
        """A nap ends the script: nobody taps the head."""
        self._note("sleep", None)
        raise TableRefused("the script is over: the host is napping")


def _run(referee):
    with pytest.raises(TableRefused):
        referee.run()


def test_the_referee_plays_the_game_it_hears_named_and_goes_back_to_idle(monkeypatch):
    played = []
    monkeypatch.setattr(games, "play", lambda name, table, rng, **kw: played.append((name, kw["heard"], kw["rig"])))
    table = _Scripted("", "let's play wavelength")
    table.rigged = {"wavelength": {"psychic": 2}}
    _run(Referee(table, log=lambda msg: None))
    assert played == [("wavelength", "let's play wavelength", {"psychic": 2})]
    assert [(kind, value) for _, kind, value in table.log if kind in ("mood", "look")] == [("mood", "idle"), ("look", None)]
    assert table.said == [lines.NAP]  # then it naps until a tap
    assert table.log[-1][1] == "sleep"


def test_a_game_that_fails_says_the_brains_recovery_line_and_goes_back_to_idle(monkeypatch):
    def broken(name, table, rng, **kw):
        table.say("Five of you.")
        raise RemoteError("HostError", "the cards would not load")

    monkeypatch.setattr(games, "play", broken)
    table = _Scripted("let's play mafia")
    _run(Referee(table, log=lambda msg: None))
    assert table.said == ["Five of you.", "Lost."]  # no nap line: the recovery line says to tap
    assert table.log[-1][1] == "sleep"
    assert [(kind, value) for _, kind, value in table.log if kind in ("mood", "look")] == [("mood", "idle"), ("look", None)]


def test_a_reset_drops_the_game_silently_and_the_new_epoch_reseeds_the_rng(monkeypatch):
    rolls = []

    def play(name, table, rng, **kw):
        rolls.append(rng.random())
        raise TableReset("the next epoch")

    monkeypatch.setattr(games, "play", play)
    table = _Scripted("let's play mafia", "let's play mafia", epochs=("e-1", "e-2", "e-3"))
    _run(Referee(table, log=lambda msg: None))
    assert table.said == [] and table.hellos == 3
    assert len(rolls) == 2 and rolls[0] == rolls[1]  # seed 7 again at e-2


def test_a_game_cut_off_by_the_table_going_away_ends_with_the_recovery_line_once_it_is_back(monkeypatch):
    def cut(name, table, rng, **kw):
        table.say("Five of you.")
        raise TableUnreachable("the table at http://mac:8090 did not answer for 60 s")

    monkeypatch.setattr(games, "play", cut)
    table = _Scripted("let's play imposter")
    _run(Referee(table, log=lambda msg: None, retry=0))
    assert table.said == ["Five of you.", "Lost."]
    assert table.hellos == 2


class _Dropping(_Scripted):
    """A _Scripted table whose robot is off Wi-Fi for the first `drops` listens: the
    brain answers each with the BodyError it got (the referee exited on one, 03:2x)."""

    def __init__(self, *heard, drops=1, **kwargs):
        super().__init__(*heard, **kwargs)
        self.drops = drops

    def listen(self, seconds):
        if self.drops:
            self.drops -= 1
            raise RemoteError("BodyError", "listen: nothing answered")
        return super().listen(seconds)


def test_the_robot_dropping_off_wifi_between_games_is_waited_out(monkeypatch):
    played = []
    monkeypatch.setattr(games, "play", lambda name, table, rng, **kw: played.append(name))
    table = _Dropping("let's play mafia", drops=3)
    logged = []
    _run(Referee(table, log=logged.append))
    assert played == ["mafia"]
    assert [value for _, kind, value in table.log if kind == "wait"] == [PAUSE] * 3
    assert table.said == [lines.NAP] and table.hellos == 1
    assert sum("did not answer" in m for m in logged) == 1, logged
    assert any("answered again" in m for m in logged)


def test_a_referee_picking_up_a_table_already_used_puts_it_back_to_idle_first():
    table = _Scripted()
    table.hello = lambda: {"epoch": "e-1", "calls": 12}
    _run(Referee(table, log=lambda msg: None))
    assert [kind for _, kind, _ in table.log][:2] == ["mood", "look"]


def test_the_referee_needs_nothing_but_the_standard_library():
    check = "import sys, brain.referee; bad = [m for m in ('numpy', 'cv2', 'PIL') if m in sys.modules]; assert not bad, bad"
    done = subprocess.run([sys.executable, "-S", "-c", check], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    done = subprocess.run([sys.executable, "-S", "-m", "brain.referee", "--help"], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert done.returncode == 0 and "--table" in done.stdout, done.stderr
    done = subprocess.run([sys.executable, "-S", "-m", "brain.referee", "--table", "ftp://x"], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert done.returncode == 2 and "http://HOST:PORT" in done.stderr


def test_talk_settings_snapshot_travels_without_keys():
    class Table(FakeTable):
        def talk_settings(self):
            return {"talk": "gemini", "talk_model": "gemini-2.5-flash", "effort": "high", "persona": "host"}
    server = TableServer(Table(), RealClock(), "127.0.0.1", 0).start()
    remote = RemoteTable(server.url)
    try:
        hello = remote.hello()
        assert hello["talk_settings"] == server.table.talk_settings()
        assert remote.talk_settings() == server.table.talk_settings()
    finally:
        remote.close()
        server.stop()
