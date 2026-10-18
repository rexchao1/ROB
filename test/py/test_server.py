"""The brain's HTTP server: /test/* exists only in test mode, seeds nothing, and what a
test pushes reaches the brain only the way the robot's would, through the fake
gateway's camera and microphone. Read back on the fake's side."""

import subprocess
import sys
from pathlib import Path

import table
from calls import call
from conftest import _start

from brain.__main__ import main, make_test_brain
from brain.server import serve

ROOT = Path(__file__).resolve().parents[2]


def _tools(fake):
    return [c["tool"] for c in fake.device.calls]


def test_reset_answers_with_the_clock_at_zero_and_no_game(brain):
    call(brain.url, "POST", "/test/advance", {"seconds": 12})
    assert call(brain.url, "POST", "/test/reset") == (200, {"ok": True, "now": 0.0})
    assert call(brain.url, "GET", "/test/state") == (200, {"game": None})
    assert call(brain.url, "GET", "/state") == (200, {"game": None})


def test_reset_resets_the_fake_and_the_host_starts_over(brain, fake):
    call(brain.url, "POST", "/test/frame?pan=30", table.png(30, []), "image/png")
    call(brain.url, "POST", "/test/hear", {"text": "hello"})
    call(brain.url, "POST", "/test/advance", {"seconds": 10})
    assert "listen" in _tools(fake)
    call(brain.url, "POST", "/test/reset")
    assert fake.device.frames == {} and fake.device.heard == []
    assert fake.device.calls[0]["seq"] == 1
    assert _tools(fake) == ["set_off_timeout", "set_blink", "set_avatar", "set_all_leds", "move_head"]  # the setup again


def test_the_clock_moves_only_when_advanced_and_never_backwards(brain, fake):
    call(brain.url, "POST", "/test/reset")
    assert "listen" not in _tools(fake)
    assert call(brain.url, "POST", "/test/advance", {"seconds": 5}) == (200, {"now": 5.0})
    assert _tools(fake).count("listen") == 1  # the idle loop's first window, 0.15 s turn + 4 s
    for bad in ({"seconds": -1}, {"seconds": "5"}, {"seconds": True}, {}, [5]):
        assert call(brain.url, "POST", "/test/advance", bad)[0] == 400
    assert brain.clock.now() == 5.0


def test_a_pushed_frame_is_what_the_camera_sees_facing_its_pan(brain, fake):
    frame = table.png(-40, [table.Face(-40)])
    assert call(brain.url, "POST", "/test/frame?pan=-40", frame, "image/png")[0] == 200
    assert list(fake.device.frames) == [-40.0]
    status, answer = call(brain.url, "POST", "/test/frame", b"not an image", "image/png")
    assert status == 400 and "PNG" in answer["error"]


def test_a_pushed_table_is_what_the_camera_sees_wherever_it_faces(brain, fake):
    faces = [{"bearing": -30}, {"bearing": 30, "pose": "down"}]
    assert call(brain.url, "POST", "/test/table", {"faces": faces}) == (200, {"ok": True, "faces": 2})
    assert fake.device.scene == [table.Face(-30), table.Face(30, "down")]
    assert call(brain.url, "POST", "/test/table", {"faces": [{}]})[0] == 400


def test_what_a_test_says_is_heard_on_the_hosts_next_listen(brain, fake):
    assert call(brain.url, "POST", "/test/hear", {"text": "Hello there"})[0] == 200
    call(brain.url, "POST", "/test/advance", {"seconds": 5})
    listens = [c for c in fake.device.calls if c["tool"] == "listen"]
    assert listens[0]["answer"]["text"] == "Hello there"
    assert call(brain.url, "POST", "/test/hear", {"words": "x"})[0] == 400


def test_a_rig_waits_for_the_next_game_of_its_name(brain):
    rig = {"imposter": {"word": "beach", "imposter": 3}}
    assert call(brain.url, "POST", "/test/rig", rig) == (200, {"ok": True, "rigged": ["imposter"]})
    assert brain.host.rigs == rig
    assert call(brain.url, "POST", "/test/rig", {"imposter": 3})[0] == 400
    call(brain.url, "POST", "/test/reset")
    assert brain.host.rigs == {}


def test_nothing_else_is_served(brain):
    for method, path in (("GET", "/test/seats"), ("POST", "/test/state"), ("POST", "/state"), ("GET", "/")):
        assert call(brain.url, method, path)[0] == 404


def test_the_test_endpoints_do_not_exist_outside_test_mode(brain):
    server = serve(brain.host, "127.0.0.1", 0)
    url = _start(server)
    try:
        assert call(url, "GET", "/state") == (200, {"game": None})
        for path in ("/test/reset", "/test/advance", "/test/hear", "/test/rig", "/test/frame"):
            assert call(url, "POST", path, {})[0] == 404
        assert call(url, "GET", "/test/state")[0] == 404
    finally:
        server.shutdown()
        server.server_close()


def test_reset_fails_loudly_when_the_fake_gateway_is_gone(tmp_path):
    tb = make_test_brain("http://127.0.0.1:9/mcp", sets_dir=tmp_path)
    url = _start(tb.server)
    try:
        status, answer = call(url, "POST", "/test/reset")
        assert status == 500 and "did not reset" in answer["error"]
    finally:
        tb.host.stop()
        tb.server.shutdown()
        tb.server.server_close()


def test_without_a_voice_the_real_brain_refuses_to_start(tmp_path, capsys):
    assert main(["--voice-dir", str(tmp_path / "none"), "--banter", "none", "--port", "0"]) == 2
    assert "no voice" in capsys.readouterr().err


def test_python_m_brain_test_runs_against_the_fake_gateways_cli():
    fake = subprocess.Popen([sys.executable, str(ROOT / "test" / "fake_gateway.py"), "--port", "0"], stdout=subprocess.PIPE, text=True)
    brain = None
    try:
        fake_url = fake.stdout.readline().split("listening on ")[1].strip()
        brain = subprocess.Popen(
            [sys.executable, "-m", "brain", "--test", "--gateway", fake_url + "/mcp", "--port", "0"],
            cwd=ROOT, stdout=subprocess.PIPE, text=True,
        )
        line = brain.stdout.readline()
        assert "(test mode" in line
        url = line.split("listening on ")[1].split()[0]
        assert call(url, "POST", "/test/reset") == (200, {"ok": True, "now": 0.0})
        assert call(url, "POST", "/test/advance", {"seconds": 5}) == (200, {"now": 5.0})
        status, calls = call(fake_url, "GET", "/mock/calls")
        assert status == 200 and [c["tool"] for c in calls][-2:] == ["listen", "get_touch_state"]
    finally:
        for proc in (brain, fake):
            if proc is not None:
                proc.terminate()
                proc.wait(5)
