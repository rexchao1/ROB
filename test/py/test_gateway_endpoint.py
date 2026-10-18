"""scripts/gateway.py's end-of-speech check: a listen closes once someone has spoken and
gone quiet, and never on silence, a chime, a single click or music. And its hearing: a
window with no voice in it never reaches Whisper, and what Whisper makes up is dropped.
Whisper, the voice detector and the gateway are stubbed, so this runs without them."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location("gateway", Path(__file__).parents[2] / "scripts" / "gateway.py")
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)

QUIET, LOUD = 80.0, 3000.0


def run(levels, **kw):
    e = gateway.Endpointer(end_silence_ms=720, **kw)
    return next((i for i, rms in enumerate(levels) if e.feed(rms)), None)


def test_ends_after_speech_then_silence():
    levels = [QUIET] * 14 + [LOUD] * 10 + [QUIET] * 20
    assert run(levels) == 14 + 10 + 12 - 1  # 12 quiet frames of 60 ms after the last word


def test_silence_alone_never_ends():
    assert run([QUIET] * 200) is None


def test_the_opening_chime_is_not_speech():
    assert run([QUIET] * 3 + [LOUD] * 5 + [QUIET] * 50) is None  # as logged: loud in frames 3 to 7


def test_a_click_is_not_speech():
    assert run([QUIET] * 10 + [LOUD] + [QUIET] * 50) is None


def test_a_short_pause_inside_a_sentence_keeps_listening():
    levels = [QUIET] * 8 + [LOUD] * 6 + [QUIET] * 6 + [LOUD] * 6 + [QUIET] * 20
    assert run(levels) == 8 + 6 + 6 + 6 + 12 - 1


def test_a_noisy_room_raises_the_bar():
    room = 900.0  # above the fixed minimum, but steady from the start
    assert run([room] * 60) is None
    levels = [room] * 25 + [room * 5] * 8 + [room] * 20
    assert run(levels) == 25 + 8 + 12 - 1


def test_music_is_loud_but_never_speech():
    e = gateway.Endpointer(end_silence_ms=720)
    levels = [QUIET] * 14 + [LOUD, QUIET] * 40  # a beat: every other frame a drum hit
    assert not any(e.feed(rms, False if rms == LOUD else None) for rms in levels)
    assert not e.spoke and e.not_voice == 40


def test_talking_over_music_ends_when_the_voice_stops():
    e = gateway.Endpointer(end_silence_ms=720)
    frames = [(QUIET, None)] * 14 + [(LOUD, True)] * 10 + [(LOUD, False)] * 20  # the music plays on
    assert next(i for i, (rms, voice) in enumerate(frames) if e.feed(rms, voice)) == 14 + 10 + 12 - 1


def seg(text, logprob=-0.3, ratio=0.7, silent=0.0):
    return {"text": text, "avg_logprob": logprob, "compression_ratio": ratio, "no_speech_prob": silent}


def test_whisper_failures_by_its_own_bars():
    assert gateway.failed(seg("Let's play Mafia.")) == ""
    assert "loop" in gateway.failed(seg("the the the the", ratio=8.7))
    assert "guess" in gateway.failed(seg("Thank you.", logprob=-1.3))
    assert "guess" in gateway.failed(seg("!", logprob=float("nan")))
    assert "silence" in gateway.failed(seg("you", logprob=-1.2, silent=0.9))


def test_repeat_loops_are_cut_to_once():
    assert gateway.collapse_repeats("It's in the name. It's in the name. It's in the name.") == "It's in the name."
    assert gateway.collapse_repeats("The light. The name. The name. The name. The name.") == "The light. The name."
    assert gateway.collapse_repeats("No, no, no, no, no.") == "no."
    assert gateway.collapse_repeats("Resume. Resume.") == "Resume. Resume."  # twice is someone talking
    assert gateway.collapse_repeats("") == ""


def test_the_prompt_read_back_is_not_an_answer():
    assert gateway.echoes_prompt(gateway.PROMPT)
    assert gateway.echoes_prompt("Mafia, Imposter, Wavelength.")
    for said in ("ROB, let's play Mafia.", "Wordle.", "Mafia", "Hot Seat or Twenty Questions?", "Let's play Wordle."):
        assert not gateway.echoes_prompt(said), said


def test_judge_keeps_words_and_says_what_it_threw_out():
    assert gateway.judge([seg("Let's play Mafia.")], 1.6) == ("Let's play Mafia.", "")
    loop = "This is for the person to get the light. It's not in the name." + " The name." * 40
    text, note = gateway.judge([seg(loop, ratio=9.1)], 3.4)
    assert text == "" and "made up" in note and "compression 9.1" in note
    assert gateway.judge([seg("Resume. Resume. Resume.")], 1.5)[0] == "Resume."
    assert gateway.judge([seg(gateway.PROMPT)], 2.0)[0] == ""
    assert gateway.judge([seg("one two three four five six seven eight nine ten eleven")], 1.0)[0] == ""
    assert gateway.judge([seg("Wordle."), seg("Thank you.", logprob=-1.4)], 1.0)[0] == "Wordle."


class Stubs:
    """Whisper, the voice detector and the gateway's engine, stood in for in sys.modules."""

    def __init__(self, monkeypatch):
        self.voice: list[dict] = []  # what the detector finds in the next window
        self.said = [seg("Let's play Mafia.")]  # what Whisper says
        self.heard: list[np.ndarray] = []  # what Whisper was given
        engine = types.SimpleNamespace(FasterWhisperEngine=type("FasterWhisperEngine", (), {}))
        vad = types.SimpleNamespace(get_vad_model=lambda: object(), VadOptions=lambda **kw: kw,
                                    get_speech_timestamps=lambda audio, options: list(self.voice))
        stt = types.SimpleNamespace(faster_whisper=engine)
        modules = {"stackchan_mcp": types.SimpleNamespace(stt=stt), "stackchan_mcp.stt": stt,
                   "stackchan_mcp.stt.faster_whisper": engine, "faster_whisper": types.SimpleNamespace(vad=vad),
                   "faster_whisper.vad": vad, "mlx_whisper": types.SimpleNamespace(transcribe=self.transcribe)}
        for name, module in modules.items():
            monkeypatch.setitem(sys.modules, name, module)
        gateway.install_stt()
        self.heard.clear()  # the warm-up at install
        self.engine = engine.FasterWhisperEngine

    def transcribe(self, audio, **opts):
        assert opts["temperature"] == 0.0
        self.heard.append(audio)
        return {"segments": list(self.said)}

    def hear(self, seconds=3.0):
        """The patched transcribe on a window: the chime, then a loud tone."""
        t = np.arange(int(seconds * 16000)) / 16000
        pcm = np.zeros(16000 * gateway.SKIP_MS // 1000, np.int16).tobytes()
        pcm += (3000 * np.sin(2 * np.pi * 220 * t)).astype(np.int16).tobytes()
        return asyncio.run(self.engine.transcribe(None, pcm))["text"]


def test_a_window_with_no_voice_never_reaches_whisper(monkeypatch):
    stubs = Stubs(monkeypatch)
    stubs.said = [seg("Thank you.")]  # what Whisper makes of a beat
    assert stubs.hear() == "" and stubs.heard == []


def test_only_the_voiced_stretch_goes_to_whisper(monkeypatch):
    stubs = Stubs(monkeypatch)
    stubs.voice = [{"start": 8000, "end": 24000}]
    assert stubs.hear() == "Let's play Mafia."
    assert [a.size for a in stubs.heard] == [16000]


def test_a_hallucinated_loop_is_dropped(monkeypatch):
    stubs = Stubs(monkeypatch)
    stubs.voice = [{"start": 0, "end": 48000}]
    stubs.said = [seg("The name." * 60, logprob=-0.4, ratio=12.0)]
    assert stubs.hear() == ""


def test_what_whisper_made_of_a_quiet_room_is_dropped():
    # As logged live, right after ROB woke with nobody talking to it, with confident
    # stats: only the text gives these away.
    for junk in ("!", "! .", " ! ", "...", "d", "D.", "Thank you.", "thank you", "Thanks for watching!", "Please wait.",
                 "You", "Bye.", "All in the community.", "Subtitles by the Amara.org community"):
        assert gateway.judge([seg(junk)], 1.0)[0] == "", junk
    assert "no words" in gateway.judge([seg("!")], 1.0)[1]
    assert "lone letter" in gateway.judge([seg("d")], 1.0)[1]
    assert "stock line" in gateway.judge([seg("Thank you.")], 1.0)[1]
    # a stock line tacked onto real words goes, the words stay
    assert gateway.judge([seg("Wordle."), seg("Thank you.")], 1.0)[0] == "Wordle."


def test_short_real_answers_are_kept():
    for said in ("Yes.", "No.", "Next.", "Yeah.", "Nope.", "7", "Seven.", "Three!", "10", "Maya.", "Sam?", "Okay.",
                 "Got it.", "Show me.", "Resume.", "Mafia", "c r a n e", "Thank you, next.", "Bye, ROB."):
        assert gateway.judge([seg(said)], 1.0)[0] == said, said


def test_a_window_whisper_hears_as_punctuation_is_silence(monkeypatch):
    stubs = Stubs(monkeypatch)
    stubs.voice = [{"start": 0, "end": 16000}]
    for junk in ("!", "d", "Thank you."):
        stubs.said = [seg(junk)]
        assert stubs.hear() == "", junk
