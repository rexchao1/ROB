"""The dashboard's faces: the robot's own (speaking, mood, screen, volume) mirrored in
/dash/api/state, and a face and an avatar per seat, cropped from the counting sweep on
the dash's own thread (brain/dash.py, brain/portraits.py)."""

import re
import threading
import time
import urllib.error
import urllib.request

import cv2
import numpy as np
from calls import call

from brain import portraits, vision

FIVE = [{"bearing": b} for b in (-60, -30, 0, 30, 60)]
HEX = re.compile(r"[0-9a-f]{6}")


def _until(check, seconds=10.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return False


def _raw(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as res:
            return res.status, res.headers, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def _robot(brain):
    return call(brain.url, "GET", "/dash/api/state")[1]["robot"]


def _blocking_play(monkeypatch, brain):
    """body.play held until the returned event is set; the second event says it started."""
    release, started = threading.Event(), threading.Event()

    def play(_pcm):
        started.set()
        release.wait(5)

    monkeypatch.setattr(brain.host.body, "play", play)
    return release, started


def test_the_robot_is_speaking_only_while_a_dashboard_line_plays(brain, monkeypatch):
    release, started = _blocking_play(monkeypatch, brain)
    assert _robot(brain)["speaking"] is False
    assert call(brain.url, "POST", "/dash/api/say", {"text": "Hold that thought."}) == (200, {"ok": True})
    assert started.wait(5)
    robot = _robot(brain)
    assert robot["speaking"] is True and robot["line"] == "Hold that thought." and robot["speaking_since"] > 0
    release.set()
    assert _until(lambda: _robot(brain)["speaking"] is False)
    robot = _robot(brain)
    assert robot["line"] is None and robot["speaking_since"] is None


def test_the_robot_is_speaking_while_the_host_says_a_line(brain, monkeypatch):
    release, started = _blocking_play(monkeypatch, brain)
    saying = threading.Thread(target=brain.host.say, args=("Night falls.",), daemon=True)
    saying.start()
    assert started.wait(5)
    robot = _robot(brain)
    assert robot["speaking"] is True and robot["line"] == "Night falls."
    release.set()
    saying.join(5)
    assert _robot(brain)["speaking"] is False


def test_the_mood_the_ring_and_the_face_style_are_mirrored(brain):
    state = call(brain.url, "GET", "/dash/api/state")[1]
    robot = state["robot"]
    assert robot["mood"] == "idle" and robot["face"] == "idle" and robot["led"] == [24, 20, 30]
    assert set(state["face_style"]) == {"bg", "ink", "cheek", "mouth"}
    assert all(re.fullmatch(r"#[0-9a-f]{6}", v) for v in state["face_style"].values())
    brain.host.mood("night")
    robot = _robot(brain)
    assert robot["mood"] == "night" and robot["led"] == [0, 0, 36]
    status, got = call(brain.url, "GET", "/dash/api/robot")
    assert status == 200 and got["robot"]["mood"] == "night" and got["face_style"] == state["face_style"]


def test_volume_is_read_from_the_robot_and_set_live(brain, fake):
    assert _until(lambda: _robot(brain)["volume"] == 70)  # the fake's get_device_info
    assert call(brain.url, "POST", "/dash/api/volume", {"volume": 35}) == (200, {"volume": 35})
    sets = [c for c in fake.device.calls if c["tool"] == "set_volume" and c["error"] is None]
    assert [c["args"] for c in sets] == [{"volume": 35}]
    assert _robot(brain)["volume"] == 35
    for bad in ({"volume": 101}, {"volume": -1}, {"volume": "50"}, {"volume": True}, {"volume": 50.5}, {}):
        assert call(brain.url, "POST", "/dash/api/volume", bad)[0] == 400
    assert len([c for c in fake.device.calls if c["tool"] == "set_volume"]) == 1


def test_after_a_count_each_seat_gets_a_face_and_an_avatar_off_the_hosts_thread(brain):
    assert call(brain.url, "GET", "/dash/api/state")[1]["seats_info"] == []
    assert _raw(brain.url + "/dash/api/seat/1.jpg")[0] == 404
    call(brain.url, "POST", "/test/table", {"faces": FIVE})
    call(brain.url, "POST", "/dash/api/game", {"name": "imposter"})
    call(brain.url, "POST", "/test/advance", {"seconds": 20})
    assert len(call(brain.url, "GET", "/dash/api/state")[1]["seats"]) == 5

    def ready():
        info = call(brain.url, "GET", "/dash/api/state")[1]["seats_info"]
        return len(info) == 5 and all(s["face"] for s in info)

    assert _until(ready)
    info = call(brain.url, "GET", "/dash/api/state")[1]["seats_info"]
    assert [s["seat"] for s in info] == [1, 2, 3, 4, 5]
    assert [round(s["bearing"]) for s in info] == [-60, -30, 0, 30, 60]
    for s in info:
        a = s["avatar"]
        assert a["style"] == "lorelei" and a["seed"].startswith(f"seat-{s['seat']}-")
        assert HEX.fullmatch(a["skin"]) and a["skin"] in portraits.SKIN_TONES
        assert a["hair"] == "none" or (HEX.fullmatch(a["hair"]) and a["hair"] in portraits.HAIR_COLORS)
        assert a["options"]["seed"] == a["seed"] and a["options"]["skinColor"] == [a["skin"]]
    skins = [s["avatar"]["skin"] for s in info]
    assert portraits.SKIN_TONES.index(skins[3]) < portraits.SKIN_TONES.index(skins[4])  # the fixture's lightest and darkest
    assert info[0]["avatar"]["hair"] == "1b1b1b"  # seat one's hair is drawn near-black
    again = call(brain.url, "GET", "/dash/api/state")[1]["seats_info"]
    assert [s["avatar"]["seed"] for s in again] == [s["avatar"]["seed"] for s in info]  # stable between polls

    status, headers, data = _raw(brain.url + "/dash/api/seat/3.jpg")
    assert status == 200 and headers["Content-Type"] == "image/jpeg"
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    assert image.shape == (portraits.SIZE, portraits.SIZE, 3)
    for missing in ("6.jpg", "0.jpg", "x.jpg", "1.png"):
        assert _raw(brain.url + "/dash/api/seat/" + missing)[0] == 404

    call(brain.url, "POST", "/test/reset")
    assert call(brain.url, "GET", "/dash/api/state")[1]["seats_info"] == []
    assert _raw(brain.url + "/dash/api/seat/1.jpg")[0] == 404


def test_the_avatar_script_is_served_from_the_vendor_folder_only(brain):
    status, headers, body = _raw(brain.url + "/dash/vendor/dicebear.js")
    assert status == 200 and headers["Content-Type"].startswith("text/javascript")
    assert b"createAvatar" in body and b"export" in body
    for name in ("missing.js", "LICENSES.md", "..%2Findex.html", "a/dicebear.js"):
        assert _raw(brain.url + "/dash/vendor/" + name)[0] == 404


def test_no_hair_over_a_bare_forehead_and_nothing_read_in_the_dark():
    frame = np.full((240, 320, 3), (170, 175, 180), np.uint8)  # a wall
    cv2.rectangle(frame, (140, 100), (180, 150), (120, 160, 210), -1)  # a face, no hair above it
    cv2.circle(frame, (152, 115), 3, (30, 30, 30), -1)
    cv2.circle(frame, (168, 115), 3, (30, 30, 30), -1)
    face = vision.Face(cx=160 / 320, cy=125 / 240, w=40 / 320, h=50 / 240, score=0.9, frontal=True)
    found = portraits.traits(frame, face)
    assert found["hair"] == "none" and found["skin"] in portraits.SKIN_TONES
    assert portraits.traits(np.zeros_like(frame), face) == {"skin": None, "hair": None}
    a = portraits.avatar(2, 7, found)
    assert a["seed"] == "seat-2-7" and "hairColor" not in a["options"]
    jpeg = portraits.crop(frame, face)
    assert jpeg is not None and jpeg[:2] == b"\xff\xd8"
