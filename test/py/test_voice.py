"""brain/voice.py: test clips carry their line exactly; recorded lines are found by their
key and converted to 16 kHz mono 16-bit whatever they were saved as; a miss goes to
the fallback, and with none it says so."""

import io
import math
import wave
from pathlib import Path

import numpy as np
import pytest

from brain import voice
from brain.voice import CachedVoice, TestVoice, VoiceError

PIPER_MODEL = Path(__file__).resolve().parents[2] / "voice" / "piper" / "en_US-lessac-medium.onnx"


def tone(rate: int, seconds: float, channels: int = 1, width: int = 2, hz: float = 440.0) -> bytes:
    t = np.arange(int(rate * seconds)) / rate
    x = 0.5 * np.sin(2 * math.pi * hz * t)
    if width == 1:
        raw = (x * 127 + 128).astype(np.uint8)
    elif width == 2:
        raw = (x * 32767).astype("<i2")
    elif width == 3:
        v = (x * (2**23 - 1)).astype("<i4")
        raw = np.frombuffer(v.tobytes(), np.uint8).reshape(-1, 4)[:, :3].copy()
    else:
        raw = (x * (2**31 - 1)).astype("<i4")
    if channels > 1:
        raw = np.repeat(raw, channels, axis=0) if raw.ndim == 1 else np.repeat(raw, channels, axis=0)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(raw.tobytes())
    return out.getvalue()


@pytest.mark.parametrize("text", ["Player three, heads down means heads DOWN.", "", "Who's hiding? — ünïcode ✓", "a" * 5000])
def test_a_test_clip_carries_its_line(text):
    pcm = voice.encode_test_pcm(text)
    assert len(pcm) % 2 == 0
    assert voice.decode_test_pcm(pcm) == text
    assert TestVoice().pcm(text) == pcm


def test_other_audio_is_not_a_test_clip():
    assert voice.decode_test_pcm(b"") is None
    assert voice.decode_test_pcm(b"\x00\x01" * 800) is None
    assert voice.decode_test_pcm(voice.encode_test_pcm("hello")[:-3]) is None  # cut short


def test_line_key_collapses_whitespace():
    assert voice.line_key("One at  a time.") == voice.line_key(" One at a\ttime. ")
    assert voice.line_key("One at a time.") != voice.line_key("One at a time")
    assert len(voice.line_key("x")) == 64


@pytest.mark.parametrize(("rate", "channels", "width"), [(16000, 1, 2), (44100, 2, 2), (22050, 1, 1), (24000, 1, 3), (48000, 2, 4)])
def test_a_recorded_line_plays_at_16k_mono(tmp_path, rate, channels, width):
    line = "Five of you."
    (tmp_path / f"{voice.line_key(line)}.wav").write_bytes(tone(rate, 0.5, channels, width))
    v = CachedVoice(tmp_path)
    assert v.recorded(line)
    pcm = v.pcm(line)
    assert abs(voice.seconds(pcm) - 0.5) < 0.01
    x = np.frombuffer(pcm, "<i2").astype(float) / 32767
    assert 0.3 < np.abs(x[500:-500]).max() < 0.6  # the tone's level survives, no clipping
    spectrum = np.abs(np.fft.rfft(x))
    assert abs(np.argmax(spectrum) * voice.SAMPLE_RATE / len(x) - 440) < 5  # and its pitch


def test_a_miss_goes_to_the_fallback_or_raises(tmp_path):
    with pytest.raises(VoiceError):
        CachedVoice(tmp_path).pcm("Never recorded.")
    v = CachedVoice(tmp_path, fallback=TestVoice())
    assert voice.decode_test_pcm(v.pcm("Never recorded.")) == "Never recorded."


def test_a_bad_wav_is_a_voice_error(tmp_path):
    (tmp_path / f"{voice.line_key('x')}.wav").write_bytes(b"not a wav")
    with pytest.raises(VoiceError):
        CachedVoice(tmp_path).pcm("x")


def test_make_voice_needs_something(tmp_path):
    with pytest.raises(VoiceError):
        voice.make_voice(None, None)
    assert isinstance(voice.make_voice(tmp_path, None), CachedVoice)
    with pytest.raises(VoiceError):
        voice.make_voice(tmp_path, tmp_path / "missing.onnx")


def test_pcm_to_wav_round_trip():
    pcm = (np.arange(1600) % 200 - 100).astype("<i2").tobytes()
    assert voice.wav_to_pcm(voice.pcm_to_wav(pcm)) == pcm


@pytest.mark.skipif(not PIPER_MODEL.is_file(), reason="no Piper model in voice/piper/")
def test_piper_speaks_a_composed_line():
    pytest.importorskip("piper")
    v = voice.PiperVoice(PIPER_MODEL)
    pcm = v.pcm("Three for Player four, two for Player one.")
    assert 1.0 < voice.seconds(pcm) < 6.0
    assert np.abs(np.frombuffer(pcm, "<i2")).max() > 1000
    assert voice.make_voice(None, PIPER_MODEL).pcm("Hello.")  # Piper alone is a voice


def test_eleven_keeps_only_scripted_speech_on_disk(tmp_path, monkeypatch):
    import hashlib

    from brain.lines import fixed_lines

    scripted = fixed_lines()[0]
    composed = "A one-off answer about tonight's conversation."
    monkeypatch.setattr(voice.ElevenVoice, "_wanted", lambda self: "test-voice")
    fetched = []

    def fetch(self, text, voice_id):
        fetched.append(text)
        return b"\x01\x00"

    monkeypatch.setattr(voice.ElevenVoice, "_fetch", fetch)
    v = voice.ElevenVoice("test-key", cache_dir=tmp_path)
    assert v.pcm(scripted) == b"\x01\x00"
    assert len(list(tmp_path.glob("*.pcm"))) == 1
    assert voice.ElevenVoice("test-key", cache_dir=tmp_path).pcm(scripted) == b"\x01\x00"
    assert fetched == [scripted]  # another instance reuses the fixed disk recording
    key = hashlib.sha256(f"test-voice\0{v.model}\0{composed}".encode()).hexdigest()
    old = tmp_path / f"{key}.pcm"
    old.write_bytes(b"old conversation audio")
    assert v.pcm(composed) == b"\x01\x00"  # never reads a legacy conversational recording
    assert v.pcm(composed) == b"\x01\x00"  # repeat uses RAM
    assert fetched == [scripted, composed]
    assert old.read_bytes() == b"old conversation audio"  # no migration or deletion
    v.pcm("Another new answer.")
    assert len(list(tmp_path.glob("*.pcm"))) == 2  # only the fixed line and the legacy file
    assert not list(tmp_path.glob("*.tmp"))
