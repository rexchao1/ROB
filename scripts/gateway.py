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
names. Without mlx-whisper it falls back to faster-whisper small.en, beam 5, with VAD.
GM_STT_MODEL picks the mlx model (default mlx-community/whisper-large-v3-turbo).
"""

from __future__ import annotations

import asyncio
import logging
import os
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
        self.trace: list[int] = []

    def summary(self) -> str:
        text = f"room {self.floor or 0:.0f}, speech bar {self.threshold():.0f}, loudest {self.loudest:.0f}"
        return text + (f", frames/100 {self.trace}" if os.environ.get("GM_ENDPOINT_TRACE") else "")

    def threshold(self) -> float:
        return max(self.speech_rms, (self.floor or 0.0) * FLOOR_RATIO)

    def feed(self, rms: float) -> bool:
        """Takes one frame's RMS; True once speech has started and then stopped."""
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


def install() -> None:
    """Patch the gateway's listen orchestrator to close the window at the end of speech."""
    from stackchan_mcp.stt import orchestrator
    from stackchan_mcp.stt.audio_utils import StreamingOpusDecoder

    real_start = orchestrator.start_recording
    state = SimpleNamespace(done=None, ends=None)

    def start_recording(session_id, *args, **kwargs):
        if kwargs.get("frame_hook") is not None:  # some other capture with its own hook
            state.done = None
            return real_start(session_id, *args, **kwargs)
        done = asyncio.Event()
        decoder = StreamingOpusDecoder()
        ends = Endpointer()
        opened = time.monotonic()

        def hook(frame: bytes) -> None:
            if done.is_set():
                return
            if ends.feed(frame_rms(decoder.decode_frame(frame))):
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


def install_stt() -> None:
    """Replace faster-whisper's transcribe with one that drops the chime and uses a
    better model."""
    import numpy as np
    from stackchan_mcp.stt import faster_whisper as engine_module

    chime = 16000 * 2 * SKIP_MS // 1000  # bytes of 16 kHz 16-bit mono
    try:
        import mlx_whisper
    except ImportError:
        mlx_whisper = None
        log.warning("mlx-whisper not installed; using faster-whisper small.en")
    fallback = SimpleNamespace(model=None)

    def run(audio: np.ndarray) -> str:
        if mlx_whisper is not None:
            out = mlx_whisper.transcribe(audio, path_or_hf_repo=STT_MODEL, language="en", initial_prompt=PROMPT,
                                         condition_on_previous_text=False)
            return str(out["text"]).strip()
        if fallback.model is None:
            from faster_whisper import WhisperModel

            fallback.model = WhisperModel("small.en", device="cpu", compute_type="int8")
        segments, _ = fallback.model.transcribe(audio, language="en", beam_size=5, vad_filter=True, initial_prompt=PROMPT)
        return "".join(seg.text for seg in segments).strip()

    async def transcribe(self, pcm: bytes, **opts):
        audio = np.frombuffer(pcm[chime:] if len(pcm) > chime else b"", dtype=np.int16).astype(np.float32) / 32768.0
        started = time.monotonic()
        frames = audio[: audio.size // 960 * 960].reshape(-1, 960) * 32768.0
        loudest = float(np.sqrt((frames * frames).mean(axis=1)).max()) if frames.size else 0.0
        # nobody spoke: Whisper would make words up out of the room noise or the prompt
        text = await asyncio.to_thread(run, audio) if loudest >= HEARD_RMS else ""
        if text.rstrip(".") and text.rstrip(".") in PROMPT:
            text = ""
        log.info("heard %r (%.2f s, %.1f s of audio)", text, time.monotonic() - started, audio.size / 16000)
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
