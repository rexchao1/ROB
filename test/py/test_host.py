"""The host (brain/host.py) on the fake gateway and a virtual clock: what the rules ask
of the Table reaches the robot as it should, read back from the fake's record (the far
side). The camera is the synthetic table (test/fixtures/table.py), so vision runs for
real; the only thing set by hand is the seats, where a test starts mid-game."""

import random
import threading

import pytest

import table
from brain import cards, games, lines, settings, vision
from brain.banter import NoBanter
from brain.clock import RealClock, VirtualClock
from brain.body import BodyError
from brain.games.common import GameStopped
from brain.remote import RemoteTable, TableServer
from brain.lobby import PAUSE, QUIET, QUIET_WINDOW
from brain.host import (
    GIVE_UP,
    HEAR_AFTER,
    HEAR_SECONDS,
    MOOD_LEDS,
    PAUSED,
    PAUSED_LEDS,
    PAUSED_WINDOW,
    RESUMED,
    PHOTO_TRIES,
    RECOVERY,
    REPROMPT,
    RETURN_SPEED,
    SCAN_SEEN,
    SWEEP_SPEED,
    TRUST,
    TURN_SETTLE,
    Host,
    HostError,
    glide_seconds,
)
from brain.table import Card
from brain.voice import TestVoice

SEATS = [-60.0, -30.0, 0.0, 30.0, 60.0]
CLOSE = [table.Face(0, close=True)]
DOCTOR = {"text": "DOCTOR", "sub": None}
TWO_CLOSE = [table.Face(-15, close=True), table.Face(15, close=True)]


class Worker:
    """fn(*args) on its own thread registered on the clock, as the host's loop is; the
    test moves the clock and reads .result once .done."""

    def __init__(self, clock, fn, *args):
        self.done = False
        self.result = None
        self.error = None
        ready = threading.Event()

        def work():
            clock.register()
            ready.set()
            try:
                self.result = fn(*args)
            except BaseException as e:  # noqa: BLE001 - handed to the test
                self.error = e
            finally:
                self.done = True
                clock.unregister()

        threading.Thread(target=work, daemon=True).start()
        ready.wait(5)
        clock.settle()


@pytest.fixture
def clock():
    return VirtualClock()


@pytest.fixture
def host(body, fake, clock, tmp_path):
    fake.device.now = clock.now  # the touch pad keeps the table's time
    return Host(body, clock, TestVoice(), NoBanter(), sets_dir=tmp_path, rng=random.Random(0), log=lambda _: None)


def _calls(fake, tool):
    return [c for c in fake.device.calls if c["tool"] == tool]


def _said(fake):
    return [c["line"] for c in _calls(fake, "pcm")]


def _faces(fake):
    return [c["args"]["face"] for c in _calls(fake, "set_avatar")]


def _show(fake, faces):
    """What the camera sees wherever the head points."""
    fake.device.push_frame(table.png(0, faces), None)


def _scene(fake, faces, pans):
    """What the camera sees at each of these pans."""
    for pan in pans:
        fake.device.push_frame(table.png(pan, faces), pan)


def _dealing(host, fake, clock, seat=3, card=Card("DOCTOR")):
    """show_private(seat, card) mid-game, run until the head has turned, the host has
    asked for the lean-in, and the first photo (nobody close) is taken: t = 0.2."""
    host.seat_bearings = list(SEATS)
    host.prepare([Card("MAFIA"), card])
    _show(fake, [])
    w = Worker(clock, host.show_private, seat, card)
    clock.advance(0.2)
    return w


def test_count_sweeps_left_to_right_finds_the_seats_and_comes_back(host, fake, clock):
    _scene(fake, [table.Face(b) for b in SEATS], vision.sweep_pans())
    w = Worker(clock, host.count)
    clock.advance(30)
    assert w.done and w.result == 5
    assert [c["args"]["yaw"] for c in _calls(fake, "move_head")] == [round(p) for p in vision.sweep_pans()] + [0]
    assert len(_calls(fake, "take_photo")) == len(vision.sweep_pans())
    assert host.seat_bearings == pytest.approx(SEATS, abs=3)


def test_count_turns_quickly_to_the_start_then_glides_and_fills_the_ring(host, fake, clock):
    _scene(fake, [table.Face(b) for b in SEATS], vision.sweep_pans())
    w = Worker(clock, host.count)
    clock.advance(30)
    assert w.done and w.result == 5
    speeds = [c["args"]["speed"] for c in _calls(fake, "move_head")]
    assert speeds == ["high"] + [SWEEP_SPEED] * (len(vision.sweep_pans()) - 1) + [RETURN_SPEED]
    rings = [c["args"]["colors"] for c in _calls(fake, "set_leds")]
    assert len(rings) == len(vision.sweep_pans())
    assert [sum(rgb != [0, 0, 0] for rgb in ring) for ring in rings] == sorted(sum(rgb != [0, 0, 0] for rgb in ring) for ring in rings)
    assert all(rgb != [0, 0, 0] for rgb in rings[-1]), "the ring is full when the sweep ends"
    assert len({i for i, rgb in enumerate(rings[-1]) if rgb == list(SCAN_SEEN)}) >= 5, "a green light where each player was seen"
    assert _calls(fake, "set_all_leds")[-1]["args"] == dict(zip("rgb", MOOD_LEDS["idle"])), "the ring goes back to the mood"


def test_a_sweep_step_waits_until_the_head_has_settled():
    assert glide_seconds(0, SWEEP_SPEED) == TURN_SETTLE
    assert 0.2 <= glide_seconds(vision.SWEEP_DEFAULT_DEG, SWEEP_SPEED) <= 0.3  # quicker than the 0.32 s of 12 degrees at 24, measured sharp on the robot
    assert glide_seconds(90, RETURN_SPEED) > glide_seconds(12, RETURN_SPEED)


def test_a_photo_that_fails_is_tried_again_after_a_pause(host, fake, clock):
    w = Worker(clock, host.count)  # nothing pushed to the camera yet: take_photo is refused
    clock.advance(1)
    assert len(_calls(fake, "take_photo")) == 1 and not w.done
    _scene(fake, [table.Face(b) for b in SEATS], vision.sweep_pans())
    clock.advance(30)
    assert w.done and w.error is None and w.result == 5
    assert len(_calls(fake, "take_photo")) == len(vision.sweep_pans()) + 1


def test_a_photo_that_keeps_failing_ends_the_count(host, fake, clock):
    w = Worker(clock, host.count)
    clock.advance(30)
    assert w.done and isinstance(w.error, BodyError)
    assert len(_calls(fake, "take_photo")) == PHOTO_TRIES


def test_keep_photos_saves_each_photo_with_its_faces(body, fake, clock, tmp_path):
    host = Host(body, clock, TestVoice(), NoBanter(), sets_dir=tmp_path / "sets", keep_photos=tmp_path / "photos", log=lambda _: None)
    _scene(fake, [table.Face(b) for b in SEATS], vision.sweep_pans())
    w = Worker(clock, host.count)
    clock.advance(30)
    assert w.done and w.result == 5
    kept = sorted(p.name for p in (tmp_path / "photos").iterdir())
    assert len(kept) == len(vision.sweep_pans())
    assert all("-count-yaw" in name and name.endswith("faces.jpg") for name in kept)
    assert any("-count-yaw-090-" in name for name in kept) and any("-count-yaw+090-" in name for name in kept)


def test_the_card_shows_only_while_one_face_is_close_and_the_deal_ends_when_they_lean_back(host, fake, clock):
    w = _dealing(host, fake, clock)
    assert fake.device.yaw == 0 and _said(fake) == ["Player three, lean in."]
    assert fake.device.screen()["showing"] is None
    _show(fake, CLOSE)
    clock.advance(0.3)  # the next photo
    assert fake.device.screen()["showing"] == {"text": "DOCTOR", "sub": None}
    assert fake.device.blink is False  # a blink would swap the card for an eye frame
    clock.advance(2)
    _show(fake, [])
    clock.advance(0.3)
    assert fake.device.screen()["showing"] is None and not w.done
    clock.advance(1)
    assert w.done and w.result is True
    screen = fake.device.screen()
    assert (screen["face"], screen["blink"], screen["showing"]) == ("idle", True, None)


def test_a_second_face_blanks_the_card_at_the_next_photo_and_it_comes_back_after(host, fake, clock):
    """D8: blank within one second, "One at a time." once, the card back once alone."""
    w = _dealing(host, fake, clock)
    _show(fake, CLOSE)
    clock.advance(0.3)
    assert fake.device.screen()["showing"] is not None
    _show(fake, TWO_CLOSE)
    clock.advance(0.3)  # the next photo, well inside a second
    assert fake.device.screen()["showing"] is None
    clock.advance(2)  # several more photos with both still close
    assert fake.device.screen()["showing"] is None
    assert _said(fake).count(lines.ONE_AT_A_TIME) == 1
    _show(fake, CLOSE)
    clock.advance(0.3)
    assert fake.device.screen()["showing"] == {"text": "DOCTOR", "sub": None}
    clock.advance(2)
    _show(fake, [])
    clock.advance(2)
    assert w.done and w.result is True
    assert _said(fake).count(lines.ONE_AT_A_TIME) == 1


def test_nobody_leaning_in_is_asked_again_every_ten_seconds_and_given_up_on_at_thirty(host, fake, clock):
    w = _dealing(host, fake, clock)
    clock.advance(REPROMPT + 0.5)
    again = "Player three, lean in close, or say show me."
    assert _said(fake) == ["Player three, lean in.", again]
    clock.advance(GIVE_UP - REPROMPT - 0.8)  # t = 29.9
    assert not w.done and _said(fake) == ["Player three, lean in.", again, again]
    clock.advance(1)
    assert w.done and w.result is False
    assert _faces(fake) == ["idle"]  # the card's slot was never set
    assert [c["args"]["duration_ms"] for c in _calls(fake, "listen")] == [HEAR_SECONDS * 1000] * 4  # at 4, 10, 16 and 22 s


def test_show_me_typed_puts_the_card_up_on_trust_and_other_lines_wait_for_the_game(host, fake, clock):
    w = _dealing(host, fake, clock)
    host.inject("player two")  # not for the deal: the game's next listen hears it
    host.inject("Show me")
    clock.advance(0.3)
    assert fake.device.screen()["showing"] == DOCTOR  # nobody close: on trust
    clock.advance(TRUST - 0.5)
    assert not w.done and fake.device.screen()["showing"] == DOCTOR
    clock.advance(0.5)
    assert w.done and w.result is True and fake.device.screen()["showing"] is None
    assert _calls(fake, "listen") == []
    w = Worker(clock, host.listen, 4)
    clock.advance(4)
    assert w.done and w.result == "player two"


def test_i_m_looking_said_in_the_short_listen_shows_the_card_and_got_it_moves_on(host, fake, clock):
    w = _dealing(host, fake, clock)
    fake.device.heard.append("I'm looking.")
    clock.advance(HEAR_AFTER + HEAR_SECONDS)  # the listen from 4 s heard it
    assert fake.device.screen()["showing"] == DOCTOR
    host.inject("got it")
    clock.advance(0.3)
    assert w.done and w.result is True
    assert fake.device.screen()["showing"] is None and fake.device.screen()["face"] == "idle"


def test_stop_the_game_during_a_lean_in_ends_the_game_with_the_card_blanked(host, fake, clock):
    w = _dealing(host, fake, clock)
    _show(fake, CLOSE)
    clock.advance(0.3)
    assert fake.device.screen()["showing"] == DOCTOR
    host.inject("stop the game")
    clock.advance(0.3)
    assert w.done and isinstance(w.error, GameStopped) and not w.error.reset
    screen = fake.device.screen()
    assert (screen["face"], screen["blink"], screen["showing"]) == ("idle", True, None)


def test_a_stop_the_host_raises_reaches_the_referee_as_a_stop():
    class Stopping:
        def show_private(self, seat, card):
            raise GameStopped(reset=True)

    server = TableServer(Stopping(), RealClock(), "127.0.0.1", 0).start()
    try:
        remote = RemoteTable(server.url, patience=1.0, log=lambda msg: None)
        remote.hello()
        with pytest.raises(GameStopped) as raised:
            remote.show_private(1, Card("MAFIA"))
        assert raised.value.reset
        remote.close()
    finally:
        server.stop()


def test_speaker_mac_at_a_listen_moves_the_voice_and_the_listen_goes_on(host, fake, clock, monkeypatch):
    played = []
    monkeypatch.setattr(host.body, "_play_here", played.append)  # no afplay in a test
    monkeypatch.setattr(settings, "file", None)
    monkeypatch.setattr(settings.current, "speaker", settings.current.speaker)  # put back after
    fake.device.heard.append("change your speaker to the Mac")
    w = Worker(clock, host.listen, 4)
    clock.advance(4)
    assert host.body.speaker == "mac" and settings.current.speaker == "mac"
    assert len(played) == 1 and _said(fake) == []  # "Okay, I'll talk through the Mac." played on the Mac
    fake.device.heard.append("player two")
    clock.advance(4)
    assert w.done and w.result == "player two"


def test_two_faces_that_never_part_end_the_wait(host, fake, clock):
    w = _dealing(host, fake, clock)
    _show(fake, TWO_CLOSE)
    clock.advance(GIVE_UP + 2)
    assert w.done and w.result is False and _said(fake).count(lines.ONE_AT_A_TIME) == 1


def test_show_private_before_prepare_and_a_seat_not_counted_are_refused(host, clock):
    w = Worker(clock, host.show_private, 1, Card("MAFIA"))
    assert w.done and isinstance(w.error, HostError)
    host.seat_bearings = [0.0]
    w = Worker(clock, host.look, 2)
    assert w.done and isinstance(w.error, HostError)


def test_the_same_cards_load_once(host, fake, clock):
    deck = [Card("MAFIA"), Card("CIVILIAN")]
    for cards_ in (deck, list(deck), [Card("WORD", "beach")]):
        Worker(clock, host.prepare, cards_)
    loads = _calls(fake, "load_avatar_set")
    assert len(loads) == 2
    assert fake.device.manifest == cards.read_manifest(loads[-1]["args"]["archive_path"])


def test_faces_up_names_the_seats_looking_up(host, fake, clock):
    host.seat_bearings = list(SEATS)
    fake.device.set_table([{"bearing": b, "pose": "frontal" if i == 1 else "down"} for i, b in enumerate(SEATS)])
    w = Worker(clock, host.faces_up)
    clock.advance(10)
    assert w.done and w.result == [2]


def test_listening_takes_its_window_on_the_clock_in_pieces_the_gateway_allows(host, fake, clock):
    fake.device.heard.append("Player Four")
    w = Worker(clock, host.listen, 45)
    clock.advance(44)
    assert not w.done
    clock.advance(2)
    assert w.done and w.result == "player four"
    assert [c["args"]["duration_ms"] for c in _calls(fake, "listen")] == [30000, 15000]


def test_after_a_listen_the_ring_turns_back_while_the_line_is_made(host, fake):
    from brain.voice import VoiceError

    turned = threading.Event()
    leds = host.body.leds

    def ring(colors):
        leds(colors)
        turned.set()

    class Slow:
        def pcm(self, text):
            assert turned.wait(5), "the ring waited for the line's audio"
            return TestVoice().pcm(text)

    host.body.leds = ring
    host.voice = Slow()
    host._listening = True  # as a listen leaves it
    host.say("Mafia it is.")
    tools = [c["tool"] for c in fake.device.calls]
    assert tools.index("set_all_leds") < tools.index("pcm") and _said(fake) == ["Mafia it is."]

    class Broken:
        def pcm(self, text):
            raise VoiceError("no voice")

    host.voice = Broken()
    host._listening = True
    with pytest.raises(VoiceError):
        host.say("Wordle it is.")
    assert _said(fake) == ["Mafia it is."]


def test_mood_keeps_the_hosts_face_and_colours_the_ring(host, fake, clock):
    Worker(clock, host.mood, "night")
    assert fake.device.face == "idle"
    assert fake.device.leds == [[0, 0, 36]] * 12


def test_the_loop_starts_the_named_game(host, fake, clock):
    _scene(fake, [table.Face(b) for b in SEATS], vision.sweep_pans())
    host.start()
    try:
        clock.settle()
        fake.device.heard.append("let's play mafia")
        clock.advance(host.listen_window + 30)
        assert host.state["game"] == "mafia" and host.state["seats"] == 5
        assert lines.count_line(5) in _said(fake) and "Player one, lean in." in _said(fake)
    finally:
        host.stop()


def test_a_game_that_fails_says_so_and_the_host_naps_until_a_tap(host, fake, clock, monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("a bug in the rules")

    monkeypatch.setattr(games, "play", broken)
    _scene(fake, [table.Face(b) for b in SEATS], vision.sweep_pans())
    host.start()
    try:
        clock.settle()
        fake.device.heard.append("let's play imposter")
        clock.advance(host.listen_window + 0.5)  # the first listen ends at 4.15, after the setup's turn
        assert _said(fake) == [RECOVERY]
        assert host.asleep
        listens = len(_calls(fake, "listen"))
        clock.advance(30)
        assert len(_calls(fake, "listen")) == listens  # asleep: the microphone stays off
        assert _calls(fake, "get_touch_state")  # it reads the head instead
        fake.device.touching = True
        clock.advance(1.5)
        fake.device.touching = False
        clock.advance(20)
        assert not host.asleep
        assert _said(fake)[1] in lines.WOKE
    finally:
        host.stop()


def test_a_hand_on_the_head_between_games_puts_the_host_to_sleep(host, fake, clock):
    host.start()
    try:
        clock.settle()
        clock.advance(host.listen_window + 0.5)
        assert not host.asleep
        fake.device.touching = True
        clock.advance(host.listen_window + 1)
        fake.device.touching = False
        clock.advance(2)
        assert host.asleep
        assert _said(fake) == [lines.NAP]
        clock.advance(10)
        assert host.asleep  # the hand that put it to sleep does not wake it
    finally:
        host.stop()


def test_a_line_typed_while_the_host_naps_wakes_it_and_is_answered(host, fake, clock, monkeypatch):
    played = []
    monkeypatch.setattr(games, "play", lambda name, table, rng, **kw: played.append(name))
    host.start()
    try:
        clock.settle()
        fake.device.heard.append("let's play imposter")
        clock.advance(host.listen_window + 0.5)
        assert played == ["imposter"] and host.asleep
        assert _said(fake) == [lines.NAP]
        host.inject("let's play wavelength")
        clock.advance(2)
        assert played == ["imposter", "wavelength"]
    finally:
        host.stop()


def test_the_robot_dropping_off_wifi_between_games_does_not_end_the_loop(host, fake, clock, monkeypatch):
    listen = host.body.listen
    drops = [BodyError("listen: nothing answered")] * 2

    def flaky(seconds):
        if drops:
            raise drops.pop()
        return listen(seconds)

    monkeypatch.setattr(host.body, "listen", flaky)
    _scene(fake, [table.Face(b) for b in SEATS], vision.sweep_pans())
    host.start()
    try:
        clock.settle()
        clock.advance(2 * (host.listen_window + PAUSE) + 1)  # each failed listen takes its window, then the pause
        assert not drops and _said(fake) == []
        fake.device.heard.append("let's play mafia")
        clock.advance(host.listen_window + 30)
        assert host.state["game"] == "mafia" and lines.count_line(5) in _said(fake)
    finally:
        host.stop()


def test_stop_ends_a_game_wherever_it_is_without_a_word(host, fake, clock, monkeypatch):
    monkeypatch.setattr(games, "play", lambda name, table_, *a, **k: table_.wait(1000))
    host.start()
    clock.settle()
    fake.device.heard.append("wavelength")
    clock.advance(host.listen_window + 10)
    host.stop()
    assert _said(fake) == []
    assert clock.reset() == 0  # refused if the loop were still asleep on the clock


def test_pause_holds_the_listen_and_the_games_clock_until_resume(host, fake, clock):
    host.state = {"game": "mafia", "phase": "night", "over": False}  # a pause holds a game
    fake.device.heard.append("pause")
    w = Worker(clock, host.listen, 4)
    clock.advance(4)
    assert host.paused and _said(fake) == [PAUSED]
    assert fake.device.leds == [list(PAUSED_LEDS)] * 12
    clock.advance(PAUSED_WINDOW * 3)  # nothing said: still paused
    assert host.paused and not w.done
    fake.device.heard.append("okay resume")
    clock.advance(PAUSED_WINDOW)
    assert not host.paused and _said(fake) == [PAUSED, RESUMED]
    fake.device.heard.append("player two")
    clock.advance(4)
    assert w.done and w.result == "player two"
    assert host.now() == pytest.approx(clock.now() - PAUSED_WINDOW * 4, abs=0.01)  # the paused time is left out


def test_a_tap_on_the_head_ends_the_pause(host, fake, clock):
    host.state = {"game": "mafia", "phase": "night", "over": False}  # a pause holds a game
    fake.device.heard.append("pause")
    w = Worker(clock, host.listen, 4)
    clock.advance(4 + PAUSED_WINDOW)
    assert host.paused
    fake.device.touching = True
    clock.advance(PAUSED_WINDOW)
    assert not host.paused and _said(fake)[-1] == RESUMED
    fake.device.touching = False
    clock.advance(4)
    assert w.done and w.result == ""


def test_one_hand_on_the_head_wakes_one_nap_not_the_next(host, fake, clock):
    # The pad stays on seconds after the hand leaves and then reports a stroke: the
    # hold that woke the first nap must not end the second at once.
    w = Worker(clock, host.sleep, 30.0)
    clock.advance(2)
    fake.device.touching = True
    clock.advance(2)
    assert w.done and w.result == ""
    fake.device.touching = False  # the pad stays on about three seconds more
    w2 = Worker(clock, host.sleep, 10.0)
    clock.advance(12)
    assert w2.done and w2.result is None  # slept the whole time
    w3 = Worker(clock, host.sleep, 10.0)
    clock.advance(1)
    fake.device.touching = True  # a new hold wakes the next nap
    clock.advance(2)
    assert w3.done and w3.result == ""
    fake.device.touching = False


def test_a_pause_typed_mid_game_holds_the_next_line_and_a_stop_ends_the_game(host, fake, clock):
    host.state = {"game": "mafia", "phase": "day", "over": False}
    host.inject("pause")  # the dashboard's Pause, while the game is not listening
    w = Worker(clock, host.say, "Player two, who do you vote for?")
    clock.advance(1)
    assert host.paused and _said(fake) == [PAUSED] and not w.done
    host.inject("stop the game")
    clock.advance(PAUSED_WINDOW + 1)
    assert w.done and isinstance(w.error, GameStopped) and not host.paused
    assert "Player two, who do you vote for?" not in _said(fake)


def test_a_stop_typed_mid_game_ends_it_before_the_next_wait(host, fake, clock):
    host.state = {"game": "mafia", "phase": "night", "over": False}
    host.inject("stop the game")
    w = Worker(clock, host.wait, 3.0)
    assert w.done and isinstance(w.error, GameStopped)


def test_stop_said_while_paused_reaches_the_game(host, fake, clock):
    host.state = {"game": "mafia", "phase": "night", "over": False}  # a pause holds a game
    fake.device.heard.append("pause")
    w = Worker(clock, host.listen, 4)
    clock.advance(4)
    fake.device.heard.append("stop the game")
    clock.advance(PAUSED_WINDOW)
    assert w.done and w.result == "stop the game" and not host.paused
    assert RESUMED not in _said(fake)


def test_a_quiet_lobby_listens_in_longer_windows_and_closely_again_once_it_hears(host, fake, clock):
    host.start()
    try:
        clock.settle()
        clock.advance(QUIET + QUIET_WINDOW + host.listen_window * 2)  # the fake records a listen as it ends
        windows = [c["args"]["duration_ms"] for c in _calls(fake, "listen")]
        assert windows[0] == host.listen_window * 1000 and windows[-1] == QUIET_WINDOW * 1000
        fake.device.heard.append("hello")
        clock.advance(QUIET_WINDOW * 2)
        assert _calls(fake, "listen")[-1]["args"]["duration_ms"] == host.listen_window * 1000
    finally:
        host.stop()


def test_talk_settings_snapshot_contains_only_choices(host, monkeypatch):
    monkeypatch.setattr(settings, "current", settings.Settings(
        talk="gemini", talk_model="gemini-2.5-flash", effort="high", persona="spooky"))
    host.talk = object()
    assert host.talk_settings() == {
        "talk": "gemini", "talk_model": "gemini-2.5-flash", "effort": "high", "persona": "spooky"}
    host.talk = None
    assert host.talk_settings()["talk"] == "off"
