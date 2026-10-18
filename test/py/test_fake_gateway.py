"""The fake gateway itself: it records what it was told in arrival order (refusals too),
serves the camera the way the device does, and resets to nothing. Its MCP face is the
SDK's own session manager; the brain's client is exercised against it in test_body.py."""

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import pytest

import table
from brain.body import BodyError, Gateway

ROOT = Path(__file__).resolve().parents[2]


def _post(url, data, content_type="application/json", headers=None):
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": content_type, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as res:
        return json.loads(res.read())


def test_every_call_is_recorded_in_order_with_its_answer_or_its_refusal(fake):
    gw = Gateway(fake.mcp_url)
    gw.call("set_blink", {"enabled": False})
    with pytest.raises(BodyError):
        gw.call("set_avatar", {"face": "smug"})
    gw.call("get_head_angles")
    calls = _get(fake.url + "/mock/calls")
    assert [c["tool"] for c in calls] == ["set_blink", "set_avatar", "get_head_angles"]
    assert [c["seq"] for c in calls] == [1, 2, 3]
    assert calls[0]["answer"] == {"ok": True, "enabled": False}
    assert calls[1]["error"].startswith("Input validation error")
    assert calls[2]["answer"] == {"yaw": 0, "pitch": 45}


def test_the_camera_serves_the_pushed_pan_nearest_the_head(fake):
    gw = Gateway(fake.mcp_url)
    for pan in (-60, 0, 60):
        assert _post(fake.url + f"/mock/frame?pan={pan}", table.png(pan, [table.Face(pan)]), "image/png")[0] == 200
    gw.call("move_head", {"yaw": 50, "pitch": 45})
    shot = gw.call("take_photo", {"question": ""})
    image = cv2.imdecode(np.frombuffer(shot.images[0], np.uint8), cv2.IMREAD_COLOR)
    expected = cv2.resize(table.render(60, [table.Face(60)]), (320, 240), interpolation=cv2.INTER_AREA)
    assert image.shape == (240, 320, 3)
    assert np.abs(image.astype(int) - expected.astype(int)).mean() < 4  # JPEG of the same frame
    assert shot.data["size_bytes"] == len(shot.images[0])


def test_a_frame_without_a_pan_is_seen_everywhere_and_drops_the_per_pan_ones(fake):
    gw = Gateway(fake.mcp_url)
    _post(fake.url + "/mock/frame?pan=0", table.png(0, [table.Face(0)]), "image/png")
    _post(fake.url + "/mock/frame", table.png(0, [table.Face(0, close=True)]), "image/png")
    gw.call("move_head", {"yaw": 0, "pitch": 45})
    image = cv2.imdecode(np.frombuffer(gw.call("take_photo", {"question": ""}).images[0], np.uint8), 1)
    close = cv2.resize(table.render(0, [table.Face(0, close=True)]), (320, 240), interpolation=cv2.INTER_AREA)
    assert np.abs(image.astype(int) - close.astype(int)).mean() < 4


def test_the_table_is_rendered_wherever_the_head_faces(fake):
    gw = Gateway(fake.mcp_url)
    _post(fake.url + "/mock/frame", table.png(0, []), "image/png")
    faces = [{"bearing": -40}, {"bearing": 25, "pose": "down"}, {"bearing": 5, "close": True}]
    assert _post(fake.url + "/mock/table", json.dumps({"faces": faces}).encode()) == (200, {"ok": True, "faces": 3})
    gw.call("move_head", {"yaw": -33, "pitch": 45})
    image = cv2.imdecode(np.frombuffer(gw.call("take_photo", {"question": ""}).images[0], np.uint8), 1)
    scene = [table.Face(-40), table.Face(25, "down"), table.Face(5, close=True)]
    expected = cv2.resize(table.render(-33, scene), (320, 240), interpolation=cv2.INTER_AREA)
    assert np.abs(image.astype(int) - expected.astype(int)).mean() < 4
    for bad in ({"faces": [{"bearing": "left"}]}, {"faces": [{"bearing": 0, "pose": "sideways"}]}, {"faces": 3}, [1]):
        assert _post(fake.url + "/mock/table", json.dumps(bad).encode())[0] == 400


def test_a_bad_frame_is_refused(fake):
    status, answer = _post(fake.url + "/mock/frame", b"not an image", "image/png")
    assert status == 400 and "PNG" in answer["error"]


def test_listen_hears_everything_queued_once(fake):
    gw = Gateway(fake.mcp_url)
    _post(fake.url + "/mock/hear", json.dumps({"text": "player"}).encode())
    _post(fake.url + "/mock/hear", json.dumps({"text": "four"}).encode())
    assert gw.call("listen", {"duration_ms": 3000, "language": "en"}).data["text"] == "player four"
    assert gw.call("listen", {"duration_ms": 3000, "language": "en"}).data["text"] == ""
    assert _post(fake.url + "/mock/hear", b"{}")[0] == 400


def test_pcm_without_a_sample_rate_is_refused_and_recorded(fake):
    status, _ = _post(fake.url + "/pcm", b"\0\0", "application/octet-stream")
    assert status == 400
    assert _get(fake.url + "/mock/calls")[-1]["error"] == "X-Sample-Rate is required"


def test_reset_clears_the_record_frames_transcripts_head_and_screen(fake):
    gw = Gateway(fake.mcp_url)
    _post(fake.url + "/mock/frame", table.png(0, []), "image/png")
    _post(fake.url + "/mock/hear", json.dumps({"text": "hello"}).encode())
    gw.call("move_head", {"yaw": 30, "pitch": 60})
    gw.call("set_avatar", {"face": "off"})
    assert _post(fake.url + "/mock/reset", b"")[0] == 200
    assert _get(fake.url + "/mock/calls") == []
    assert _get(fake.url + "/mock/head") == {"yaw": 0, "pitch": 45}
    assert _get(fake.url + "/mock/screen")["face"] == "idle"
    assert gw.call("listen", {}).data["text"] == ""
    with pytest.raises(BodyError, match="no frame"):
        gw.call("take_photo", {"question": ""})


def test_the_cli_says_where_it_listens():
    proc = subprocess.Popen([sys.executable, str(ROOT / "test" / "fake_gateway.py"), "--port", "0"], stdout=subprocess.PIPE, text=True)
    try:
        line = proc.stdout.readline()
        assert line.startswith("fake gateway: listening on http://127.0.0.1:")
        url = line.split("listening on ")[1].strip()
        assert Gateway(url + "/mcp").call("get_head_angles").data == {"yaw": 0, "pitch": 45}
    finally:
        proc.terminate()
        proc.wait(5)
