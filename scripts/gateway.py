"""The stackchan-mcp gateway, with listen() ending when the talker stops.

stackchan-mcp 0.18.0's listen() keeps the microphone open for the whole `duration_ms`
and only then transcribes, so ROB answered a two-word "be quiet" after a 4 to 12 second
window. This launcher runs the same gateway with one change: while a listen is open,
each 60 ms frame from the robot is decoded and its loudness checked, and once someone
has spoken and then gone quiet for END_SILENCE_MS the window closes early. A window
nobody speaks in still runs to the end, exactly as before.

Run it with the gateway's own Python, with the gateway's arguments:

    "$(uv tool dir)/stackchan-mcp/bin/python" scripts/gateway.py serve --transport streamable-http

Tuning (environment): GM_END_SILENCE_MS (default 700), GM_SPEECH_RMS (the quietest
frame that can count as speech, default 400 on a 0 to 32767 scale).

It also swaps the speech-to-text: the gateway's faster-whisper "base" with beam 1 heard
"tell me about Wordle" as "tell me about where it all", and turned the robot's own
listening chime (the first ~0.5 s of every window) into "You" or "Oh". Here the chime
is cut off before transcribing, and the words go to Whisper large-v3-turbo on the Mac's
GPU through mlx-whisper (about 0.2 s an utterance on an M5), prompted with the game
names. Without mlx-whisper it falls back to faster-whisper small.en, beam 5.
GM_STT_MODEL picks the mlx model (default mlx-community/whisper-large-v3-turbo).

Music used to come out as words: a beat is loud enough to pass any loudness bar, never
goes quiet so the window ran to its end, and Whisper turned those seconds of beat into
"Thank you.", "the the the" or a 100-word loop of "the name. the name.". So a voice
detector decides what is speech: Silero VAD, the copy faster-whisper ships, run on ONNX.
While listening it has to agree a frame is a voice before the frame counts as speech,
so talking over music still ends the window on time; after the window it picks out the
stretches with a voice in them, and only those go to Whisper (none: nothing was said).
Whisper's answer is then checked the way Whisper checks itself (a loop, or tokens it
was unsure of), loops of the same phrase are cut to one, and the prompt read back is
dropped. Every window logs one "heard" line saying what was heard or why nothing was.
GM_VAD=0 turns the voice detector off and goes by loudness alone, as before.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
from collections import deque
from types import SimpleNamespace

FRAME_MS = 60
END_SILENCE_MS = int(os.environ.get("GM_END_SILENCE_MS", "700"))
SPEECH_RMS = float(os.environ.get("GM_SPEECH_RMS", "400"))
SKIP_MS = 600  # the robot's own "listening" chime: loud in frames 3 to 7 of every window
CALIBRATE = 3  # frames after the chime that measure the room, never counted as speech
SPEECH_FRAMES = 3  # loud frames out of the last four before it counts as speech
FLOOR_RATIO = 3.0  # speech is this many times louder than the room
USE_VAD = os.environ.get("GM_VAD", "1") != "0"
VOICE_ON = 0.5  # Silero's chance that 32 ms is a voice, above which it is (speech 0.95, beats under 0.5)
VOICE_OFF = 0.35  # once talking, it stays a voice until the chance falls below this

log = logging.getLogger("gamemaster.endpoint")


class Endpointer:
    """Decides, one frame's loudness at a time, when an utterance has ended."""

    def __init__(self, end_silence_ms: int = END_SILENCE_MS, speech_rms: float = SPEECH_RMS) -> None:
        self.end_frames = max(1, end_silence_ms // FRAME_MS)
        self.speech_rms = speech_rms
        self.skip = SKIP_MS // FRAME_MS
        self.seen = 0
        self.floor: float | None = None
        self.recent: deque[bool] = deque(maxlen=4)
        self.spoke = False
        self.quiet = 0
        self.ended = False
        self.loudest = 0.0
        self.not_voice = 0
        self.trace: list[int] = []

    def summary(self) -> str:
        text = f"room {self.floor or 0:.0f}, speech bar {self.threshold():.0f}, loudest {self.loudest:.0f}"
        if self.not_voice:
            text += f", {self.not_voice} loud frames that were not a voice"
        return text + (f", frames/100 {self.trace}" if os.environ.get("GM_ENDPOINT_TRACE") else "")

    def threshold(self) -> float:
        return max(self.speech_rms, (self.floor or 0.0) * FLOOR_RATIO)

    def feed(self, rms: float, voice: bool | None = None) -> bool:
        """Takes one frame's RMS, and whether the voice detector heard a voice in it (None:
        no detector); True once speech has started and then stopped. A loud frame that is
        not a voice (a drum hit, a bass note) is neither speech nor the room."""
        self.seen += 1
        self.loudest = max(self.loudest, rms)
        self.trace.append(round(rms / 100))
        if self.ended or self.seen <= self.skip:
            return self.ended
        if self.seen <= self.skip + CALIBRATE:  # the quietest of these is the room
            self.floor = rms if self.floor is None else min(self.floor, rms)
            return False
        loud = rms >= self.threshold()
        if not loud:  # the room's level, followed down fast and up slowly
            self.floor = rms if self.floor is None or rms < self.floor else self.floor * 0.95 + rms * 0.05
        elif voice is False:
            self.not_voice += 1
            loud = False
        self.recent.append(loud)
        if not self.spoke:
            self.spoke = sum(self.recent) >= SPEECH_FRAMES
            return False
        self.quiet = 0 if loud else self.quiet + 1
        self.ended = self.quiet >= self.end_frames
        return self.ended


def frame_rms(pcm: bytes) -> float:
    import numpy as np

    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0


def voice_model():
    """faster-whisper's Silero VAD (an ONNX session), or None without it or with GM_VAD=0."""
    if not USE_VAD:
        return None
    try:
        from faster_whisper.vad import get_vad_model

        return get_vad_model()
    except Exception as exc:  # no faster-whisper or onnxruntime: loudness alone, as before
        log.warning("no voice detector (%s); speech is told from music by loudness alone", exc)
        return None


class VoiceDetector:
    """Silero VAD over one window's audio as it streams in, 512 samples at a time, keeping
    the model's memory between frames (the same numbers as running it on the whole clip)."""

    def __init__(self, model) -> None:
        import numpy as np

        self.np = np
        self.session = model.session
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, 64), dtype=np.float32)
        self.pending = np.zeros(0, dtype=np.float32)
        self.voice = False

    def feed(self, pcm: bytes) -> bool:
        """Takes one frame of 16 kHz 16-bit audio; True while it sounds like someone talking."""
        np = self.np
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        self.pending = np.concatenate([self.pending, samples])
        best = None
        while self.pending.size >= 512:
            chunk, self.pending = self.pending[None, :512], self.pending[512:]
            inputs = {"input": np.concatenate([self.context, chunk], axis=1), "h": self.h, "c": self.c}
            prob, self.h, self.c = self.session.run(None, inputs)
            self.context = chunk[:, -64:]
            best = max(best or 0.0, float(np.ravel(prob)[0]))
        if best is not None:
            self.voice = best >= (VOICE_OFF if self.voice else VOICE_ON)
        return self.voice


def install() -> None:
    """Patch the gateway's listen orchestrator to close the window at the end of speech."""
    from stackchan_mcp.stt import orchestrator
    from stackchan_mcp.stt.audio_utils import StreamingOpusDecoder

    real_start = orchestrator.start_recording
    state = SimpleNamespace(done=None, ends=None, model=voice_model())

    def start_recording(session_id, *args, **kwargs):
        if kwargs.get("frame_hook") is not None:  # some other capture with its own hook
            state.done = None
            return real_start(session_id, *args, **kwargs)
        done = asyncio.Event()
        decoder = StreamingOpusDecoder()
        ends = Endpointer()
        ears = SimpleNamespace(voice=VoiceDetector(state.model) if state.model is not None else None)
        opened = time.monotonic()

        def heard_voice(pcm: bytes) -> bool | None:
            if ears.voice is None or ends.seen < ends.skip:  # the chime is not fed to the detector
                return None
            try:
                return ears.voice.feed(pcm)
            except Exception as exc:  # a broken detector must not break listening
                log.warning("voice detector failed (%s); this window goes by loudness alone", exc)
                ears.voice = None
                return None

        def hook(frame: bytes) -> None:
            if done.is_set():
                return
            pcm = decoder.decode_frame(frame)
            if ends.feed(frame_rms(pcm), heard_voice(pcm)):
                log.info("listen: speech ended %.1f s into the window (%s)", time.monotonic() - opened, ends.summary())
                done.set()

        state.done, state.ends = done, ends
        return real_start(session_id, *args, frame_hook=hook, **kwargs)

    async def sleep(delay, result=None):
        done = state.done
        if done is None or delay < 0.5:  # the short settle before the window is a plain sleep
            return await asyncio.sleep(delay, result)
        state.done = None
        try:
            await asyncio.wait_for(done.wait(), delay)
        except TimeoutError:
            if state.ends is not None:
                log.info("listen: the whole window ran (%s)", state.ends.summary())
        return result

    orchestrator.start_recording = start_recording
    orchestrator.asyncio = SimpleNamespace(**{k: getattr(asyncio, k) for k in dir(asyncio) if not k.startswith("_")})
    orchestrator.asyncio.sleep = sleep


STT_MODEL = os.environ.get("GM_STT_MODEL", "mlx-community/whisper-large-v3-turbo")
HEARD_RMS = 300.0  # a window with no frame this loud is silence (the room sits near 150 to 200)
PROMPT = "ROB, let's play Mafia, Imposter, Wavelength, Wordle, Hot Seat or Twenty Questions."
GAMES = ("mafia", "imposter", "wavelength", "wordle", "hot seat", "twenty questions")
# What has a voice in it: a stretch under 250 ms is a drum hit or a click, and pauses
# under half a second stay inside the sentence.
SPEECH = {"threshold": VOICE_ON, "min_speech_duration_ms": 250, "min_silence_duration_ms": 500, "speech_pad_ms": 200}
LOOP_RATIO = 2.4  # Whisper's own bar: text that gzips better than this is a loop
UNSURE_LOGPROB = -1.0  # Whisper's own bar: tokens less likely than this on average are a guess
SILENT = 0.6  # Whisper's own bar for no_speech_prob (silence, when the tokens are a guess too)
LOOP_WORDS = 8  # the longest phrase looked for when cutting a repeat loop
WORDS_PER_S = 5.0  # faster than anyone talks; more words than this in the speech are made up


def plain(text: str) -> list[str]:
    """The words of text in lower case without punctuation, for comparing."""
    return re.findall(r"[a-z0-9']+", text.lower())


def failed(segment: dict) -> str:
    """Why Whisper would call a segment's decode a failure, or "" when it is fine.
    large-v3-turbo's no_speech_prob is 0.0 even on a beat, so the stats that catch music
    are the loop (compression) and the guess (average log probability, NaN included)."""
    ratio = float(segment.get("compression_ratio", 0.0))
    logprob = float(segment.get("avg_logprob", 0.0))
    silent = float(segment.get("no_speech_prob", 0.0))
    if ratio > LOOP_RATIO:
        return f"a loop, compression {ratio:.1f}"
    if silent > SILENT and not logprob >= UNSURE_LOGPROB:
        return f"silence, no-speech chance {silent:.2f}"
    if not logprob >= UNSURE_LOGPROB:
        return f"a guess, logprob {logprob:.2f}"
    return ""


def collapse_repeats(text: str) -> str:
    """Cuts a phrase said three or more times running down to once, so Whisper stuck in a
    loop ("The name. The name. The name.") and "resume, resume, resume" both say it once."""
    words = text.split()
    keys = [" ".join(plain(w)) for w in words]
    out: list[str] = []
    i = 0
    while i < len(words):
        step = 1
        for n in range(1, LOOP_WORDS + 1):
            phrase = keys[i : i + n]
            times = 1
            while len(phrase) == n and keys[i + times * n : i + (times + 1) * n] == phrase:
                times += 1
            if times >= 3:
                step = times * n
                out += words[i + step - n : i + step]  # the last time, with its full stop
                break
        else:
            out.append(words[i])
        i += step
    return " ".join(out)


def echoes_prompt(text: str) -> bool:
    """True for Whisper reading its prompt back: a stretch of the prompt that names three or
    more games. "ROB, let's play Mafia" or a lone "Wordle." is someone answering."""
    said = " ".join(plain(text))
    return bool(said) and said in " ".join(plain(PROMPT)) and sum(game in said for game in GAMES) >= 3


# What Whisper says over silence or room noise, learned from subtitled video, as the
# whole of a segment. Nobody needs these to play: no game answers with them.
STOCK = {
    "you", "thank you", "thanks", "thank you very much", "thank you so much", "thanks for watching",
    "thank you for watching", "thanks for listening", "please subscribe", "like and subscribe",
    "please wait", "bye", "bye bye", "we'll be right back", "see you next time",
    "see you in the next video", "all in the community", "subtitles by the amara org community",
}


def stock(text: str) -> str:
    """Why a segment's text is Whisper filling a quiet room, or "" when it may be someone:
    no word in it at all ("!", "! ."), or one of the STOCK lines."""
    words = plain(text)
    if not words:
        return "no words in it"
    if " ".join(words) in STOCK:
        return "a stock line Whisper makes up from silence"
    return ""


def judge(segments: list[dict], seconds: float) -> tuple[str, str]:
    """Whisper's segments for `seconds` of speech, to the words someone said and a note on
    what was thrown out and why ("" when nothing was)."""
    kept, notes = [], []
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        why = (failed(segment) or stock(text)) if text else ""
        if why:
            notes.append(f"dropped {text[:80]!r} as made up: {why}")
        elif text:
            kept.append(text)
    text = " ".join(kept)
    short = collapse_repeats(text)
    if short != text:
        notes.append(f"cut a repeat loop: {text[:80]!r}")
        text = short
    if echoes_prompt(text):
        notes.append(f"dropped {text!r} as the prompt read back")
        text = ""
    said = plain(text)
    if len(said) == 1 and len(said[0]) == 1 and not said[0].isdigit():  # "d": a lone letter answers nothing
        notes.append(f"dropped {text!r} as a lone letter")
        text = ""
    words = len(plain(text))
    if words > 4 + WORDS_PER_S * seconds:
        notes.append(f"dropped {words} words in {seconds:.1f} s of voice as too many: {text[:80]!r}")
        text = ""
    return text, "; ".join(notes)


def install_stt() -> None:
    """Replace faster-whisper's transcribe with one that drops the chime, sends Whisper
    only the stretches with a voice in them, uses a better model, and throws out what
    Whisper made up."""
    import numpy as np
    from stackchan_mcp.stt import faster_whisper as engine_module

    chime = 16000 * 2 * SKIP_MS // 1000  # bytes of 16 kHz 16-bit mono
    try:
        import mlx_whisper
    except ImportError:
        mlx_whisper = None
        log.warning("mlx-whisper not installed; using faster-whisper small.en")
    fallback = SimpleNamespace(model=None)
    vad = voice_model()

    def speech_parts(audio: np.ndarray) -> list[tuple[int, int]] | None:
        """(start, end) samples of each stretch with a voice in it; None without a detector."""
        if vad is None:
            return None
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        return [(part["start"], part["end"]) for part in get_speech_timestamps(audio, VadOptions(**SPEECH))]

    def run(audio: np.ndarray) -> list[dict]:
        # temperature 0 only: when the plain decode fails Whisper's checks, its retries at
        # higher temperatures only sample other made-up words ("We'll be right back.")
        if mlx_whisper is not None:
            out = mlx_whisper.transcribe(audio, path_or_hf_repo=STT_MODEL, language="en", initial_prompt=PROMPT,
                                         condition_on_previous_text=False, temperature=0.0)
            return list(out["segments"])
        if fallback.model is None:
            from faster_whisper import WhisperModel

            fallback.model = WhisperModel("small.en", device="cpu", compute_type="int8")
        segments, _ = fallback.model.transcribe(audio, language="en", beam_size=5, initial_prompt=PROMPT,
                                                condition_on_previous_text=False, temperature=0.0)
        return [{"text": s.text, "avg_logprob": s.avg_logprob, "compression_ratio": s.compression_ratio,
                 "no_speech_prob": s.no_speech_prob} for s in segments]

    def hear(audio: np.ndarray) -> tuple[str, str, float]:
        """The words in one window's audio, a note on why there are none (or what was cut),
        and how many seconds had a voice in them."""
        frames = audio[: audio.size // 960 * 960].reshape(-1, 960) * 32768.0
        loudest = float(np.sqrt((frames * frames).mean(axis=1)).max()) if frames.size else 0.0
        if loudest < HEARD_RMS:  # nobody spoke: Whisper would make words up out of the room
            return "", f"too quiet for speech: loudest {loudest:.0f}", 0.0
        parts = speech_parts(audio)
        if parts is not None and not parts:
            return "", f"no voice in it, so music or noise: loudest {loudest:.0f}", 0.0
        speech = np.concatenate([audio[a:b] for a, b in parts]) if parts else audio
        text, note = judge(run(speech), speech.size / 16000)
        return text, note, speech.size / 16000 if parts else 0.0

    async def transcribe(self, pcm: bytes, **opts):
        audio = np.frombuffer(pcm[chime:] if len(pcm) > chime else b"", dtype=np.int16).astype(np.float32) / 32768.0
        started = time.monotonic()
        text, note, voiced = await asyncio.to_thread(hear, audio)
        took = f"{audio.size / 16000:.1f} s of audio, {time.monotonic() - started:.2f} s"
        if voiced:
            took = f"{voiced:.1f} s of voice in {took}"
        log.info("heard %r (%s)", text, f"{note}; {took}" if note else took)
        return {"text": text, "language": "en", "language_probability": 1.0}

    engine_module.FasterWhisperEngine.transcribe = transcribe
    if mlx_whisper is not None:  # load the model now, not on the first thing someone says
        run(np.zeros(16000, dtype=np.float32))


def find_opus() -> None:
    """opuslib looks for libopus with ctypes, which on a Mac does not search Homebrew's
    folder; add it so the gateway can decode the robot's audio."""
    if sys.platform == "darwin" and os.path.isdir("/opt/homebrew/lib"):
        paths = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "").split(os.pathsep)
        if "/opt/homebrew/lib" not in paths:
            os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = os.pathsep.join([p for p in paths if p] + ["/opt/homebrew/lib"])


def main() -> int:
    find_opus()
    from stackchan_mcp.cli import main as gateway_main

    install()
    install_stt()
    logging.getLogger("gamemaster.endpoint").setLevel(logging.INFO)
    sys.argv[0] = "stackchan-mcp"
    return gateway_main()


if __name__ == "__main__":
    sys.exit(main())
