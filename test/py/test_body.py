"""The brain's gateway client against the fake gateway: every Body method reaches the
gateway as the right tool with the right arguments (read back from the fake's record,
the far side), and every kind of refusal raises BodyError."""

import os
import socket

import numpy as np
import pytest

import table
from brain import cards
from brain.body import Body, BodyError, Gateway
from brain.table import Card
from brain.voice import encode_test_pcm


def _calls(fake, tool):
    return [c for c in fake.device.calls if c["tool"] == tool]


def test_the_gateway_lists_the_tools_the_brain_uses(fake):
    names = Gateway(fake.mcp_url).tools()
    for tool in ("move_head", "take_photo", "listen", "set_avatar", "load_avatar_set", "set_blink", "set_all_leds"):
        assert tool in names


def test_turn_sends_whole_degrees_clamped_to_the_heads_range_at_the_working_pitch(fake):
    body = Body(Gateway(fake.mcp_url), fake.pcm_url, pitch=55)
    body.turn(-30.4)
    body.turn(140)
    assert [c["args"] for c in _calls(fake, "move_head")] == [
        {"yaw": -30, "pitch": 55, "speed": "high"},
        {"yaw": 90, "pitch": 55, "speed": "high"},
    ]
    assert (fake.device.yaw, fake.device.pitch) == (90, 55)


def test_flip_yaw_turns_the_other_way(fake):
    Body(Gateway(fake.mcp_url), fake.pcm_url, flip_yaw=True).turn(20)
    assert _calls(fake, "move_head")[0]["args"]["yaw"] == -20


def test_photo_is_the_cameras_frame_as_bgr_and_its_capture_file_is_deleted(fake, body):
    fake.device.push_frame(table.png(0, [table.Face(0)]), None)
    image = body.photo()
    assert image.shape == (240, 320, 3) and image.dtype == np.uint8
    call = _calls(fake, "take_photo")[0]
    assert call["args"] == {"question": ""}
    assert not os.path.exists(call["answer"]["image_path"])


def test_photo_with_nothing_on_the_camera_raises(body):
    with pytest.raises(BodyError, match="no frame"):
        body.photo()


def test_listen_asks_for_english_from_faster_whisper_and_returns_the_text(fake, body):
    fake.device.heard.append("let's play mafia")
    assert body.listen(4) == "let's play mafia"
    assert _calls(fake, "listen")[0]["args"] == {"duration_ms": 4000, "engine": "faster-whisper", "language": "en", "motion": "none"}
    assert body.listen(0.01) == ""
    assert body.listen(99) == ""
    assert [c["args"]["duration_ms"] for c in _calls(fake, "listen")] == [4000, 100, 30000]


def test_play_posts_16k_mono_pcm_and_the_fake_hears_the_line(fake, body):
    body.play(encode_test_pcm("One at a time."))
    body.play(b"")  # nothing to play: nothing sent
    pcm = _calls(fake, "pcm")
    assert len(pcm) == 1
    assert pcm[0]["args"]["sample_rate"] == "16000" and pcm[0]["args"]["channels"] == "1"
    assert pcm[0]["line"] == "One at a time."


def test_avatar_takes_the_seven_faces_and_refuses_others(fake, body):
    body.avatar("off")
    assert fake.device.face == "off"
    with pytest.raises(ValueError):
        body.avatar("smug")


def test_a_loaded_set_shows_its_card_only_on_its_slot(fake, body, tmp_path):
    path = cards.write_set([Card("MAFIA"), Card("DOCTOR")], tmp_path)
    body.load_set(str(path))
    load = _calls(fake, "load_avatar_set")[0]
    assert load["args"]["mode"] == "layered" and load["answer"]["bytes_transferred"] == 537_600
    assert fake.device.screen()["showing"] is None
    body.avatar(cards.slot_of(cards.read_manifest(path), Card("DOCTOR")))
    assert fake.device.screen()["showing"] == {"text": "DOCTOR", "sub": None}
    body.avatar("off")
    assert fake.device.screen()["showing"] is None


def test_a_set_of_the_wrong_size_is_refused_by_the_gateway(body, tmp_path):
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"\0" * 1000)
    with pytest.raises(BodyError, match="size_mismatch"):
        body.load_set(str(bad))
    with pytest.raises(BodyError, match="archive_not_found"):
        body.load_set(str(tmp_path / "missing.bin"))


def test_setup_blink_leds_and_status(fake, body):
    body.setup()
    body.blink(False)
    body.leds([(1, 2, 3)])
    body.leds([(9, 9, 9), (8, 8, 8)])
    assert fake.device.leds[0] == [9, 9, 9] and fake.device.leds[2] == [1, 2, 3]
    body.clear_leds()
    assert fake.device.leds == [[0, 0, 0]] * 12
    assert _calls(fake, "set_off_timeout")[0]["args"] == {"seconds": 0}
    assert fake.device.blink is False
    assert body.status()["connected"] is True


def test_a_schema_refusal_raises(fake):
    with pytest.raises(BodyError, match="Input validation error"):
        Gateway(fake.mcp_url).call("move_head", {"yaw": 0})


def test_a_lost_session_is_logged_in_again_once(fake):
    gw = Gateway(fake.mcp_url)
    gw.call("get_head_angles")
    gw._session = "a-session-the-gateway-forgot"  # noqa: SLF001 - what a gateway restart leaves behind
    assert gw.call("get_head_angles").data == {"yaw": 0, "pitch": 45}


def test_no_gateway_raises():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    with pytest.raises(BodyError, match="no gateway"):
        Gateway(f"http://127.0.0.1:{port}/mcp", timeout=2).call("get_status")


def _tone(seconds: float, amplitude: int) -> bytes:
    t = np.arange(int(16_000 * seconds)) / 16_000
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype("<i2").tobytes()


def test_mouth_steps_follow_the_lines_loudness_and_end_closed():
    from brain.body import mouth_steps

    pcm = _tone(0.3, 0) + _tone(0.4, 12_000) + _tone(0.2, 3_000) + _tone(0.3, 0)
    steps = mouth_steps(pcm)
    assert [s["shape"] for s in steps] == ["closed", "open", "half", "closed"]
    assert [s["duration_ms"] for s in steps] == [300, 400, 200, 300]
    long = mouth_steps(_tone(60, 8_000))  # a minute of speech still fits the device's 256 steps
    assert len(long) <= 256 and long[-1]["shape"] == "closed"
    assert all(10 <= s["duration_ms"] <= 10_000 for s in long)


def test_speaker_mac_plays_here_and_only_moves_the_robots_mouth(monkeypatch):
    from brain import body as body_module

    played, calls = [], []

    class Player:
        returncode = 0

        def __init__(self, args):
            played.append((args[0], open(args[1], "rb").read()[:4]))

        def wait(self):
            return 0

    class Recorder:
        def call(self, name, args=None, timeout=None):
            calls.append((name, args))

    monkeypatch.setattr(body_module.subprocess, "Popen", Player)
    Body(Recorder(), "http://127.0.0.1:9/pcm", speaker="mac").play(_tone(0.5, 10_000))
    assert played == [("afplay", b"RIFF")]
    assert [name for name, _ in calls] == ["set_mouth_sequence"]
    assert calls[0][1]["steps"][-1]["shape"] == "closed"
    with pytest.raises(ValueError):
        Body(Recorder(), "http://127.0.0.1:9/pcm", speaker="radio")
