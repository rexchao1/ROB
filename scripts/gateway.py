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

A listen with "source": "mac" (the dashboard's hidden Microphone setting) records this
Mac's microphone with ffmpeg instead of the robot's, ends on the same end-of-speech
rule and goes through the same Whisper. GM_MAC_MIC picks the avfoundation input
(default ":default", the Mac's current input; `ffmpeg -f avfoundation -list_devices
true -i ""` lists them). The first time, macOS asks to let the terminal use the mic.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
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

MAC_MIC = os.environ.get("GM_MAC_MIC", ":default")

log = logging.getLogger("gamemaster.endpoint")
ears = SimpleNamespace(hear=None, vad=None)  # install_stt's hear(audio) and the voice detector, for the Mac's mic


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
    ears.hear, ears.vad = hear, vad
    if mlx_whisper is not None:  # load the model now, not on the first thing someone says
        run(np.zeros(16000, dtype=np.float32))


def record_mac(duration_ms: int) -> bytes:
    """Up to duration_ms of this Mac's microphone as 16 kHz 16-bit mono, ended early once
    someone has spoken and gone quiet, as on the robot (no chime to skip here)."""
    frame = 16000 * 2 * FRAME_MS // 1000
    cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "avfoundation", "-i", MAC_MIC,
           "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        raise RuntimeError(f"the Mac's microphone: ffmpeg did not start ({exc})") from None
    ends = Endpointer()
    ends.skip = 0
    voice = VoiceDetector(ears.vad) if ears.vad is not None else None
    chunks: list[bytes] = []
    try:
        for _ in range(max(1, duration_ms // FRAME_MS)):
            pcm = proc.stdout.read(frame)
            if len(pcm) < frame:
                break
            chunks.append(pcm)
            if ends.feed(frame_rms(pcm), voice.feed(pcm) if voice is not None else None):
                log.info("listen (Mac mic): speech ended %.1f s in (%s)", len(chunks) * FRAME_MS / 1000, ends.summary())
                break
        else:
            log.info("listen (Mac mic): the whole window ran (%s)", ends.summary())
    finally:
        proc.terminate()
        try:
            _, err = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, err = proc.communicate()
    if not chunks:
        raise RuntimeError(f"the Mac's microphone gave no sound: {err.decode('utf-8', 'replace').strip()[:200] or 'no reason given'}")
    pcm = b"".join(chunks)
    if not pcm.strip(b"\x00"):
        log.warning("the Mac's microphone gave pure silence: allow the terminal running ROB in System Settings, Privacy & Security, Microphone")
    return pcm


AUDIO_DIR = os.environ.get("GM_AUDIO_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".cache", "audio")
KEEP_S = 30  # seconds of the stream kept in memory
BACKLOG_S = 12.0  # a listen hears what was said up to this long before it, since the last listen
PREROLL_FRAMES = 5  # 0.3 s kept before the voice starts, so the first word is whole
MAX_UTTERANCE_S = 15.0  # one listen hears at most this much of someone talking
BARGE_FRAMES = 5  # 0.3 s of voice out of the last BARGE_OF frames: someone is talking over ROB
BARGE_OF = 7
VOICE_PORT = int(os.environ.get("GM_VOICE_PORT", "8769"))


class MicStream:
    """The Mac's microphone as one stream that never closes (rob-audio's mic.sock, ROB's
    own voice already taken out): frames kept for KEEP_S with their loudness and whether
    they are a voice. A listen takes what was said since the last one, so nothing said
    while ROB talks or thinks is lost, and nothing is cut at either end
    (docs/LISTEN-PLAN.md)."""

    def __init__(self, detector=None, speech_rms: float = SPEECH_RMS) -> None:
        self.frames: deque[tuple[bytes, float, bool]] = deque(maxlen=KEEP_S * 1000 // FRAME_MS)
        self.end = 0  # index of the next frame to arrive
        self.cursor = 0  # index of the first frame no listen has taken
        self.detector = detector
        self.speech_rms = speech_rms
        self.cond = __import__("threading").Condition()
        self.last = 0.0  # time.monotonic() of the last frame

    def live(self) -> bool:
        return time.monotonic() - self.last < 1.0

    def push(self, pcm: bytes) -> None:
        rms = frame_rms(pcm)
        voice = rms >= self.speech_rms
        if self.detector is not None:
            try:
                voice = self.detector.feed(pcm) and rms >= self.speech_rms / 4
            except Exception as exc:  # a broken detector must not stop the stream
                log.warning("voice detector failed on the stream (%s); loudness alone from here", exc)
                self.detector = None
        with self.cond:
            self.frames.append((pcm, rms, voice))
            self.end += 1
            self.last = time.monotonic()
            self.cond.notify_all()

    def _frame(self, i: int) -> tuple[bytes, float, bool] | None:
        base = self.end - len(self.frames)
        return self.frames[i - base] if base <= i < self.end else None

    def _wait_for(self, i: int, until: float) -> bool:
        """With the lock held: True once frame i is in, False at `until` (monotonic)."""
        while self.end <= i:
            left = until - time.monotonic()
            if left <= 0 or not self.cond.wait(min(left, 0.5)):
                if time.monotonic() >= until:
                    return False
        return True

    def take(self, duration_ms: int) -> tuple[bytes, str]:
        """What someone says next, as 16 kHz 16-bit PCM, and how the listen went: from what
        was said since the last listen (up to BACKLOG_S back), else from now for up to
        duration_ms; ends END_SILENCE_MS after the voice stops. b"" when nobody spoke."""
        end_frames = max(1, END_SILENCE_MS // FRAME_MS)
        with self.cond:
            base = self.end - len(self.frames)
            i = max(self.cursor, base, self.end - int(BACKLOG_S * 1000 // FRAME_MS))
            backlog = self.end - i
            give_up = time.monotonic() + duration_ms / 1000
            recent: deque[bool] = deque(maxlen=4)
            start = None
            quiet = 0
            while True:
                hard_stop = give_up if start is None else time.monotonic() + 5.0
                if not self._wait_for(i, hard_stop):
                    break
                frame = self._frame(i)
                voice = frame is not None and frame[2]
                recent.append(voice)
                if start is None:
                    if sum(recent) >= 3:
                        start = i - len(recent) + 1
                        quiet = 0
                else:
                    quiet = 0 if voice else quiet + 1
                    if quiet >= end_frames or i - start >= MAX_UTTERANCE_S * 1000 // FRAME_MS:
                        i += 1
                        break
                i += 1
            self.cursor = i
            if start is None:
                return b"", f"nobody spoke ({backlog * FRAME_MS / 1000:.1f} s before the listen and {duration_ms / 1000:.1f} s after)"
            first = max(start - PREROLL_FRAMES, self.end - len(self.frames))
            pcm = b"".join(f[0] for k in range(first, i) if (f := self._frame(k)) is not None)
            how = f"speech {(i - start) * FRAME_MS / 1000:.1f} s"
            return pcm, how + (f", {backlog * FRAME_MS / 1000:.1f} s of backlog looked at" if backlog else "")

    def peek(self, ms: int) -> bytes:
        """The last `ms` of the stream, without taking it from the next listen."""
        with self.cond:
            n = min(len(self.frames), ms // FRAME_MS)
            return b"".join(f[0] for f in list(self.frames)[len(self.frames) - n:])

    def voice_after(self, index: int, wait_s: float) -> bool:
        """True as soon as BARGE_FRAMES of the BARGE_OF frames from `index` on are a voice:
        someone started talking. False after wait_s with nobody."""
        until = time.monotonic() + wait_s
        window: deque[bool] = deque(maxlen=BARGE_OF)
        with self.cond:
            i = max(index, self.end - len(self.frames))
            while self._wait_for(i, until):
                frame = self._frame(i)
                window.append(frame is not None and frame[2])
                if sum(window) >= BARGE_FRAMES:
                    return True
                i += 1
        return False

    def run(self, path: str) -> None:
        """Read rob-audio's mic.sock for ever, reconnecting when it restarts."""
        import socket

        frame = 16000 * 2 * FRAME_MS // 1000
        said = False
        while True:
            try:
                with socket.socket(socket.AF_UNIX) as sock:
                    sock.connect(path)
                    log.info("the Mac's microphone: streaming from %s (ROB's voice taken out)", path)
                    said = False
                    pending = b""
                    while True:
                        data = sock.recv(8192)
                        if not data:
                            break
                        pending += data
                        while len(pending) >= frame:
                            self.push(pending[:frame])
                            pending = pending[frame:]
            except OSError as exc:
                if not said:
                    log.info("the Mac's microphone: no stream at %s (%s); listens record with ffmpeg", path, exc)
                    said = True
            time.sleep(1.0)


def serve_voice(stream: MicStream, port: int = VOICE_PORT) -> None:
    """GET /voice?wait=S on 127.0.0.1:port: {"voice": true} as soon as someone starts
    talking after the request, false after S seconds; {"live": false} with no stream.
    Outside the gateway's one-at-a-time command queue, so ROB's head and face keep moving
    while the brain waits on it."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            url = urlparse(self.path)
            if url.path != "/voice":
                self.send_error(404)
                return
            try:
                wait = min(60.0, max(0.0, float(parse_qs(url.query).get("wait", ["10"])[0])))
            except ValueError:
                wait = 10.0
            if not stream.live():
                body = {"live": False, "voice": False}
            else:
                body = {"live": True, "voice": stream.voice_after(stream.end, wait)}
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):  # the gateway's log is for listens
            pass

    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        log.warning("no voice endpoint on port %d (%s): ROB cannot be talked over", port, exc)
        return
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="voice", daemon=True).start()


def install_mac_mic() -> None:
    """Let listen take "source": "mac" and hear through this Mac's microphone."""
    import numpy as np
    from stackchan_mcp import stdio_server

    real_listen = stdio_server.listen_and_transcribe
    import threading

    stream = MicStream(VoiceDetector(ears.vad) if ears.vad is not None else None)
    threading.Thread(target=stream.run, args=(os.path.join(AUDIO_DIR, "mic.sock"),), name="mic", daemon=True).start()
    serve_voice(stream)

    def record(duration_ms: int) -> bytes:
        if not stream.live():
            return record_mac(duration_ms)
        pcm, how = stream.take(duration_ms)
        log.info("listen (Mac mic stream): %s", how)
        return pcm

    async def listen_and_transcribe(arguments, **kwargs):
        if arguments.get("source") != "mac" or ears.hear is None:
            return await real_listen({k: v for k, v in arguments.items() if k != "source"}, **kwargs)
        duration_ms = arguments.get("duration_ms", 5000)
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or not 100 <= duration_ms <= 30_000:
            raise ValueError(f"'duration_ms' must be an integer from 100 to 30000; got {duration_ms!r}")
        pcm = await asyncio.to_thread(record, duration_ms)
        if not pcm:
            return {"engine": "faster-whisper", "text": "", "language": "en", "duration_ms": 0, "frame_count": 0}
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        started = time.monotonic()
        text, note, voiced = await asyncio.to_thread(ears.hear, audio)
        took = f"{voiced:.1f} s of voice in {audio.size / 16000:.1f} s of Mac mic, {time.monotonic() - started:.2f} s"
        log.info("heard %r (%s)", text, f"{note}; {took}" if note else took)
        return {"engine": "faster-whisper", "text": text, "language": "en",
                "duration_ms": len(pcm) * 1000 // 32000, "frame_count": len(pcm) // (32 * FRAME_MS)}

    stdio_server.listen_and_transcribe = listen_and_transcribe


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
    install_mac_mic()
    logging.getLogger("gamemaster.endpoint").setLevel(logging.INFO)
    sys.argv[0] = "stackchan-mcp"
    return gateway_main()


if __name__ == "__main__":
    sys.exit(main())
