"""scripts/make-voice.py with a fake ElevenLabs: it records each line once, as a 16 kHz
WAV under the line's key in its voice's folder, skips what that voice has already
recorded, and a dry run records nothing."""

import importlib.util
import wave
from pathlib import Path

import numpy as np

from brain import voice

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "make-voice.py"
spec = importlib.util.spec_from_file_location("make_voice", SCRIPT)
assert spec and spec.loader
make_voice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_voice)


class FakeTTS:
    def __init__(self) -> None:
        self.asked: list[str] = []

    def pcm(self, text: str) -> bytes:
        self.asked.append(text)
        return (np.ones(1600) * 1000).astype("<i2").tobytes()  # 0.1 s


LINES = ["One at a time.", "Everyone, heads down.", "One  at a time."]  # the third is the first again


def test_records_each_line_once(tmp_path):
    tts = FakeTTS()
    make_voice.main(["--out", str(tmp_path), "--lines-file", str(tmp_path / "none.txt")], tts=tts, lines=LINES)
    assert tts.asked == ["One at a time.", "Everyone, heads down."]
    folder = tmp_path / voice.ELEVEN_VOICE  # the brain's default voice
    path = folder / f"{voice.line_key('One at a time.')}.wav"
    with wave.open(str(path)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()) == (16000, 1, 2, 1600)
    assert voice.CachedVoice(tmp_path).recorded("Everyone, heads down.")
    index = (folder / "index.tsv").read_text().splitlines()
    assert index == [f"{voice.line_key(t)}\t{t}" for t in ["One at a time.", "Everyone, heads down."]]

    again = FakeTTS()
    (tmp_path / "lines.txt").write_text("# a comment\n\nNobody died last night.\n")
    make_voice.main(["--out", str(tmp_path), "--lines-file", str(tmp_path / "lines.txt")], tts=again, lines=LINES)
    assert again.asked == ["Nobody died last night."]  # the rest were already recorded


def test_each_voice_records_into_its_own_folder(tmp_path):
    from brain import personas

    make_voice.main(["--out", str(tmp_path), "--lines-file", str(tmp_path / "x")], tts=FakeTTS(), lines=LINES)
    george = FakeTTS()
    make_voice.main(["--out", str(tmp_path), "--voice-id", "George", "--lines-file", str(tmp_path / "x")], tts=george, lines=LINES)
    assert george.asked == ["One at a time.", "Everyone, heads down."]  # nothing of the other voice's is reused
    assert (tmp_path / personas.VOICES["george"].eleven_id / f"{voice.line_key('One at a time.')}.wav").is_file()
    try:
        make_voice.main(["--out", str(tmp_path), "--voice-id", "../x", "--lines-file", str(tmp_path / "x")], tts=FakeTTS(), lines=LINES)
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("took a path for a voice id")


def test_dry_run_records_nothing(tmp_path, capsys):
    make_voice.main(["--out", str(tmp_path), "--dry-run", "--lines-file", str(tmp_path / "x")], tts=None, lines=LINES)
    assert "would record: Everyone, heads down." in capsys.readouterr().out
    assert not list(tmp_path.rglob("*.wav"))


def test_without_a_key_it_refuses(tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    try:
        make_voice.main(["--out", str(tmp_path), "--voice-id", "v", "--lines-file", str(tmp_path / "x")], lines=LINES)
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("ran without a key")
