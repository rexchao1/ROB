"""The brain's HTTP server: /test/* exists only in test mode, seeds nothing, and what a
test pushes reaches the brain only the way the robot's would, through the fake
gateway's camera and microphone. Read back on the fake's side."""

import http.client
import stat
import subprocess
import sys
from pathlib import Path

import table
from calls import call
from conftest import _start, dash

from brain import keys
from brain.__main__ import TEST_DASH_KEY, TEST_TABLE_TOKEN, _table_token, main, make_test_brain
from brain.server import MAX_BODY, serve

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


def test_the_test_endpoints_and_the_rig_do_not_exist_outside_test_mode(brain):
    server = serve(brain.host, "127.0.0.1", 0)  # no fake, no reset: a real-mode server, with a key nobody was told
    url = _start(server)
    try:
        assert call(url, "GET", "/state") == (200, {"game": None})
        for path in ("/test/reset", "/test/advance", "/test/hear", "/test/rig", "/test/frame"):
            assert call(url, "POST", path, {})[0] == 404
        assert call(url, "GET", "/test/state")[0] == 404
        assert dash(url, "GET", "/dash/api/rig")[0] == 404 and dash(url, "POST", "/dash/api/rig", {"mafia": {}})[0] == 404  # D86: rigging is for tests
        assert dash(url, "GET", "/dash/api/state")[0] == 200
        assert dash(url, "POST", "/dash/api/hear", {"text": "x"})[0] == 403  # the test key is not this server's
    finally:
        server.shutdown()
        server.server_close()


def test_every_write_and_the_camera_need_the_dashboards_key(brain):
    """D86: a write without the key, or with another, is 403 whatever its origin; a read
    is open except the camera, the faces and the log."""
    for path, body in (("/dash/api/hear", {"text": "x"}), ("/dash/api/say", {"text": "x"}), ("/dash/api/game", {"name": "stop"}),
                       ("/dash/api/head", {"yaw": 0}), ("/dash/api/settings", {"pitch": 30}), ("/dash/api/content", {"spectra": ["a - b"]}),
                       ("/dash/api/keys", {"STACKCHAN_TOKEN": "x"}), ("/dash/api/rig", {"mafia": {}}), ("/dash/api/volume", {"volume": 50}),
                       ("/dashboard/settings", {"persona": "host"}), ("/dashboard/command", {"say": "hi"})):
        assert call(brain.url, "POST", path, body)[0] == 403, path
        assert dash(brain.url, "POST", path, body, key="wrong")[0] == 403, path
        assert dash(brain.url, "POST", path, body, key="")[0] == 403, path
    assert brain.host.rigs == {} and call(brain.url, "GET", "/dash/api/state")[1]["typed_pending"] == 0
    assert call(brain.url, "POST", "/dash/api/hear?key=" + TEST_DASH_KEY, {"text": "x"}) == (200, {"ok": True, "pending": 1})  # an <img> cannot send a header
    assert dash(brain.url, "POST", "/dashboard/command", {"say": "hello"})[0] == 200
    for path in ("/dash/api/state", "/dash/api/settings", "/dash/api/content", "/dash/api/keys", "/dash/api/robot", "/dashboard/state"):
        assert call(brain.url, "GET", path)[0] == 200, path
    for path in ("/dash/api/events", "/dash/api/photo", "/dash/api/seat/1.jpg"):
        assert call(brain.url, "GET", path)[0] == 403, path
    assert dash(brain.url, "GET", "/dash/api/events")[0] == 200
    assert brain.dash_key == TEST_DASH_KEY


def _raw_request(url, method, path, headers, body=b""):
    """One hand-built request; (status, body) without the client fixing the headers."""
    host, port = url.removeprefix("http://").split(":")
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    try:
        conn.putrequest(method, path, skip_accept_encoding=True)
        for name, value in headers.items():
            conn.putheader(name, value)
        conn.endheaders()
        conn.send(body)
        res = conn.getresponse()
        return res.status, res.read()
    finally:
        conn.close()


def test_a_content_length_that_is_not_a_number_and_a_body_too_long_are_answered(brain):
    """A4: the length is parsed inside the try (400), and a body over MAX_BODY is 413, unread."""
    status, body = _raw_request(brain.url, "POST", "/test/hear", {"Content-Type": "application/json", "Content-Length": "abc"})
    assert status == 400 and b"Content-Length" in body
    status, body = _raw_request(brain.url, "POST", "/test/hear", {"Content-Type": "application/json", "Content-Length": str(MAX_BODY + 1)}, b'{"text": "x"}')
    assert status == 413
    status, body = _raw_request(brain.url, "POST", "/test/hear", {"Content-Type": "application/json", "Content-Length": "13"}, b'{"text": "x"}')
    assert status == 200
    assert call(brain.url, "GET", "/dash/api/state")[1]["typed_pending"] == 0  # the test's hear goes to the fake, not the queue


def test_the_table_token_is_generated_once_and_kept_in_env_local(tmp_path, capsys, monkeypatch):
    """D85: no --table-token and no GM_TABLE_TOKEN: one is made, written owner-only beside
    the other keys, said on stdout, and used at the next start."""
    monkeypatch.delenv("GM_TABLE_TOKEN", raising=False)
    env = tmp_path / ".env.local"
    env.write_text("OTHER=1\n")
    token = _table_token(None, env)
    assert len(token) >= 32 and keys.read_env(env) == {"OTHER": "1", "GM_TABLE_TOKEN": token}
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    out = capsys.readouterr().out
    assert "generated" in out and str(env) in out and token not in out
    assert _table_token("given", env) == "given" and keys.read_env(env)["GM_TABLE_TOKEN"] == token  # a token given is used as is
    assert TEST_TABLE_TOKEN  # the fixed one of --test, as the harness sends it


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
        assert brain.stdout.readline().strip() == f"gamemaster: game screen at {url}/dash?key={TEST_DASH_KEY}"  # the fixed key the harness sends
        assert call(url, "POST", "/test/reset") == (200, {"ok": True, "now": 0.0})
        assert call(url, "POST", "/test/advance", {"seconds": 5}) == (200, {"now": 5.0})
        status, calls = call(fake_url, "GET", "/mock/calls")
        assert status == 200 and [c["tool"] for c in calls][-1] == "listen"
    finally:
        for proc in (brain, fake):
            if proc is not None:
                proc.terminate()
                proc.wait(5)
