"""The host's voice: a line of text in, the audio the body plays out.

The brain owns the voice (the gateway's own TTS engines are never used): every line
becomes 16 kHz mono signed 16-bit little-endian PCM here, and the host sends it to the
gateway's POST /pcm, which plays it outside the gateway's command queue.

  CachedVoice  the fixed lines, recorded once with ElevenLabs by scripts/make-voice.py
               into voice/<line_key>.wav (D30); a line not recorded goes to the fallback
  ElevenVoice  a live ElevenLabs voice for the lines not recorded, when the settings ask
               for it and ELEVENLABS_API_KEY is set; each line is kept on disk, so a
               repeat costs nothing; any failure falls back to Piper for that line
  PiperVoice   a local voice (piper-tts) for the composed lines, offline (D28)
  TestVoice    the test lane never synthesizes: its "audio" carries the line's text, so
               the fake gateway recovers exactly what the body was told to say
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import struct
import sys
import time
import urllib.error
import wave
from collections.abc import Callable
from collections import OrderedDict
from pathlib import Path
from typing import Any, Protocol

import numpy as np

SAMPLE_RATE = 16_000
_TEST_MAGIC = b"GMVOICE1"  # the head of a TestVoice clip: magic, the text's length (u32 LE), the UTF-8 text


class VoiceError(Exception):
    """No audio for a line: nothing recorded and no local voice to fall back on."""


def line_key(text: str) -> str:
    """The name a recorded line is filed under: sha256 hex of the text, whitespace collapsed."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def seconds(pcm: bytes) -> float:
    """How long a clip of 16 kHz mono 16-bit PCM plays."""
    return len(pcm) / 2 / SAMPLE_RATE


class Voice(Protocol):
    def pcm(self, text: str) -> bytes:
        """The line as 16 kHz mono signed 16-bit little-endian PCM."""
        ...


# --- the test lane ----------------------------------------------------------------


def encode_test_pcm(text: str) -> bytes:
    """A short clip that carries the text: the magic, its length, its UTF-8 bytes, padded
    to whole samples. Valid PCM (it plays as a click), decodable by decode_test_pcm."""
    data = text.encode("utf-8")
    clip = _TEST_MAGIC + struct.pack("<I", len(data)) + data
    return clip + b"\x00" * (len(clip) % 2)


def decode_test_pcm(pcm: bytes) -> str | None:
    """The text a TestVoice clip carries; None for any audio that is not one."""
    head = len(_TEST_MAGIC) + 4
    if len(pcm) < head or not pcm.startswith(_TEST_MAGIC):
        return None
    (n,) = struct.unpack("<I", pcm[len(_TEST_MAGIC) : head])
    if len(pcm) < head + n:
        return None
    try:
        return pcm[head : head + n].decode("utf-8")
    except UnicodeDecodeError:
        return None


class TestVoice:
    """The voice of the test lane: no synthesis, the text rides in the clip."""

    __test__ = False  # not a pytest class

    def pcm(self, text: str) -> bytes:
        return encode_test_pcm(text)


# --- conversion -------------------------------------------------------------------


def to_16k_mono(samples: np.ndarray, rate: int) -> bytes:
    """Float or int samples, (n,) or (n, channels), at any rate, as 16 kHz mono s16le."""
    x = np.asarray(samples)
    if np.issubdtype(x.dtype, np.integer):
        x = x.astype(np.float64) / float(np.iinfo(x.dtype).max + 1)  # to -1..1 before mixing
    else:
        x = x.astype(np.float64)
    if x.ndim == 2:
        x = x.mean(axis=1)
    if rate != SAMPLE_RATE and len(x) > 0:
        x = _resample(x, rate, SAMPLE_RATE)
    return (np.clip(x, -1.0, 1.0) * 32767.0).round().astype("<i2").tobytes()


def _resample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Band-limit (a windowed sinc when going down) then interpolate. Plenty for speech."""
    if dst < src:
        cutoff = 0.5 * dst / src * 0.95  # cycles per source sample, a little under Nyquist
        taps = np.arange(-32, 33)
        kernel = 2 * cutoff * np.sinc(2 * cutoff * taps) * np.hamming(len(taps))
        x = np.convolve(x, kernel / kernel.sum(), mode="same")
    n = int(round(len(x) * dst / src))
    return np.interp(np.arange(n) * (src / dst), np.arange(len(x)), x)


def wav_to_pcm(data: bytes) -> bytes:
    """A PCM WAV of any rate, width (8, 16, 24 or 32 bit) and channel count as 16 kHz mono s16le."""
    try:
        with wave.open(io.BytesIO(data)) as w:
            rate, width, channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
            raw = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as e:
        raise VoiceError(f"not a PCM WAV: {e}") from e
    if width == 1:
        x = (np.frombuffer(raw, np.uint8).astype(np.int16) - 128) * 256
    elif width == 2:
        x = np.frombuffer(raw, "<i2")
    elif width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        x = ((b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)) << 8) >> 8  # sign-extend 24 bits
        x = (x >> 8).astype(np.int16)
    elif width == 4:
        x = np.frombuffer(raw, "<i4")
    else:
        raise VoiceError(f"a {width * 8}-bit WAV is not supported")
    if channels > 1:
        x = x.reshape(-1, channels)
    return to_16k_mono(x, rate)


def pcm_to_wav(pcm: bytes, rate: int = SAMPLE_RATE) -> bytes:
    """Mono s16le PCM wrapped as a WAV file."""
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return out.getvalue()


# --- the real voices --------------------------------------------------------------


class _Memo:
    """A small LRU of lines already turned into PCM (the tallies and seat lines repeat)."""

    def __init__(self, size: int = 256) -> None:
        self.size = size
        self._items: OrderedDict[str, bytes] = OrderedDict()

    def get(self, key: str) -> bytes | None:
        if key in self._items:
            self._items.move_to_end(key)
            return self._items[key]
        return None

    def put(self, key: str, pcm: bytes) -> None:
        self._items[key] = pcm
        self._items.move_to_end(key)
        while len(self._items) > self.size:
            self._items.popitem(last=False)


class CachedVoice:
    """The recorded lines (<directory>/<line_key>.wav, any rate, width and channel count),
    a miss going to the fallback; with no fallback a miss raises VoiceError."""

    def __init__(self, directory: Path, fallback: Voice | None = None) -> None:
        self.directory = Path(directory)
        self.fallback = fallback
        self._memo = _Memo()

    def recorded(self, text: str) -> bool:
        return (self.directory / f"{line_key(text)}.wav").is_file()

    def pcm(self, text: str) -> bytes:
        key = line_key(text)
        hit = self._memo.get(key)
        if hit is not None:
            return hit
        path = self.directory / f"{key}.wav"
        if path.is_file():
            pcm = wav_to_pcm(path.read_bytes())
        elif self.fallback is not None:
            return self.fallback.pcm(text)  # not kept here: the fallback keeps its own, and its voice can change
        else:
            raise VoiceError(f"no recording of {text!r} in {self.directory} and no local voice")
        self._memo.put(key, pcm)
        return pcm


class PiperVoice:
    """A local voice through piper-tts (imported here, so the brain runs without it until
    one is asked for), resampled to 16 kHz. VoiceError when piper or the model is missing."""

    def __init__(self, model: Path, speaker: int | None = None) -> None:
        self.model = Path(model)
        if not self.model.is_file():
            raise VoiceError(f"no Piper model at {self.model}")
        try:
            from piper import PiperVoice as _Piper  # type: ignore[import-not-found]
        except ImportError as e:
            raise VoiceError("piper-tts is not installed (pip install piper-tts, the voice extra)") from e
        try:
            self._voice: Any = _Piper.load(str(self.model))
        except Exception as e:  # a corrupt model, a missing .onnx.json beside it
            raise VoiceError(f"Piper could not load {self.model}: {e}") from e
        self.speaker = speaker
        self._memo = _Memo()

    def pcm(self, text: str) -> bytes:
        key = line_key(text)
        hit = self._memo.get(key)
        if hit is not None:
            return hit
        try:
            config = None
            if self.speaker is not None:
                from piper import SynthesisConfig  # type: ignore[import-not-found]

                config = SynthesisConfig(speaker_id=self.speaker)
            chunks = list(self._voice.synthesize(text, syn_config=config))
        except Exception as e:
            raise VoiceError(f"Piper failed on {text!r}: {e}") from e
        if not chunks:
            return b""
        rate = chunks[0].sample_rate
        samples = np.concatenate([np.frombuffer(c.audio_int16_bytes, "<i2") for c in chunks])
        pcm = to_16k_mono(samples, rate)
        self._memo.put(key, pcm)
        return pcm


# --- ElevenLabs, live ------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
ELEVEN_API = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVEN_MODEL = "eleven_flash_v2_5"  # the fast one; --eleven-model overrides
ELEVEN_VOICE = "iP95p4xoKVk53GoZ742B"  # "Chris", a stock premade voice: natural, casual, American
ELEVEN_TIMEOUT = 5.0
ELEVEN_CACHE = ROOT / ".cache" / "eleven"  # .cache/ is gitignored
ELEVEN_REST = 30.0  # after a failure, Piper alone for this long, so a dead network does not stall every line
ELEVEN_WARM = "https://api.elevenlabs.io/v1/models"  # a free GET that opens the connection (ElevenVoice.warm)


def env(name: str) -> str | None:
    """A setting from the environment, else from .env.local (NAME=value
    lines; never printed). None when neither has it."""
    value = os.environ.get(name)
    if value:
        return value
    path = Path(os.environ.get("GM_ENV_FILE") or ROOT / ".env.local")
    try:
        rows = path.read_text().splitlines()
    except OSError:
        return None
    for row in rows:
        row = row.strip()
        if row.startswith("export "):
            row = row[len("export ") :].strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        k, v = row.split("=", 1)
        if k.strip() == name:
            v = v.strip().strip('"').strip("'")
            return v or None
    return None


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


class ElevenVoice:
    """A live ElevenLabs voice (16 kHz PCM straight from the API, output_format
    pcm_16000). Used only while brain.settings says voice "eleven"; otherwise, and on any
    error or a slow answer, the line goes to the fallback (Piper), with one log line.
    The voice is the personality's (brain.personas), else the one given here. Every line
    made is kept in cache_dir, keyed by voice, model and text."""

    def __init__(
        self,
        api_key: str,
        voice_id: str = ELEVEN_VOICE,
        model: str = ELEVEN_MODEL,
        fallback: Voice | None = None,
        cache_dir: Path | None = ELEVEN_CACHE,
        timeout: float = ELEVEN_TIMEOUT,
        log: Callable[[str], None] = _log,
    ) -> None:
        self._key = api_key
        self.voice_id, self.model, self.fallback = voice_id, model, fallback
        self.cache_dir, self.timeout, self.log = cache_dir, timeout, log
        self._memo = _Memo()
        self._resting_until = 0.0

    def __repr__(self) -> str:  # never show the key
        return f"ElevenVoice(voice_id={self.voice_id!r}, model={self.model!r})"

    def _wanted(self) -> str | None:
        """The voice id to use now, or None when the settings want another voice."""
        from brain import personas, settings

        if settings.current.voice != "eleven":
            return None
        picked = personas.VOICES.get(settings.current.eleven_voice or "")
        return picked.eleven_id if picked else personas.get(settings.current.persona).eleven_voice or self.voice_id

    def _fall_back(self, text: str) -> bytes:
        if self.fallback is None:
            raise VoiceError(f"no voice for {text!r}: ElevenLabs is off or failed and there is no local voice")
        return self.fallback.pcm(text)

    def pcm(self, text: str) -> bytes:
        voice_id = self._wanted()
        if voice_id is None:
            return self._fall_back(text)
        key = hashlib.sha256(f"{voice_id}\0{self.model}\0{' '.join(text.split())}".encode("utf-8")).hexdigest()
        hit = self._memo.get(key)
        if hit is not None:
            return hit
        path = self.cache_dir / f"{key}.pcm" if self.cache_dir is not None else None
        if path is not None and path.is_file():
            pcm = path.read_bytes()
            self._memo.put(key, pcm)
            return pcm
        if time.monotonic() < self._resting_until:
            return self._fall_back(text)
        try:
            pcm = self._fetch(text, voice_id)
        except Exception as e:  # offline, a bad key, rate limited, slow: Piper says this one
            self._resting_until = time.monotonic() + ELEVEN_REST
            self.log(f"voice: ElevenLabs failed ({_why(e)}); Piper for the next {ELEVEN_REST:.0f} s")
            return self._fall_back(text)
        if path is not None:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(pcm)
                tmp.replace(path)
            except OSError as e:
                self.log(f"voice: could not keep an ElevenLabs line ({e})")
        self._memo.put(key, pcm)
        return pcm

    def warm(self) -> int | None:
        """Open the ElevenLabs connection before a line needs it, or freshen one that has
        sat idle a while (brain.net.warm): the ms it took, 0 when it was warm already,
        None while the settings want another voice or it is unreachable."""
        from brain import net

        if self._wanted() is None:
            return None
        return net.warm(ELEVEN_WARM, {"xi-api-key": self._key})

    def _fetch(self, text: str, voice_id: str) -> bytes:
        """The line's audio, over the kept connection (brain/net.py); its time goes to the log."""
        from brain import net

        body = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.8, "style": 0.35, "use_speaker_boost": True},
        }
        start = time.monotonic()
        pcm = net.request(
            "POST",
            f"{ELEVEN_API}/{voice_id}?output_format=pcm_16000",
            json.dumps(body).encode("utf-8"),
            {"xi-api-key": self._key, "Content-Type": "application/json", "Accept": "audio/pcm"},
            self.timeout,
        )
        if not pcm:
            raise VoiceError("ElevenLabs sent no audio")
        self.log(f"voice: ElevenLabs {int((time.monotonic() - start) * 1000)} ms for {seconds(pcm):.1f} s of audio")
        return pcm + b"\x00" * (len(pcm) % 2)  # whole 16-bit samples


def _why(e: Exception) -> str:
    """A short reason for the log, never the request (it carries the key)."""
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP {e.code}"
    if isinstance(e, urllib.error.URLError):
        return f"{type(e.reason).__name__}: {e.reason}"
    return f"{type(e).__name__}: {e}"


def make_voice(
    voice_dir: Path | None,
    piper_model: Path | None,
    eleven_key: str | None = None,
    eleven_voice: str = ELEVEN_VOICE,
    eleven_model: str = ELEVEN_MODEL,
) -> Voice:
    """The real voice: the recorded lines first, then ElevenLabs live (with a key, while
    the settings ask for it), then Piper. Any one alone works; none raises VoiceError,
    since a host that cannot speak cannot run a game."""
    piper = PiperVoice(piper_model) if piper_model is not None else None
    rest: Voice | None = piper
    if eleven_key:
        rest = ElevenVoice(eleven_key, eleven_voice, eleven_model, fallback=piper)
    if voice_dir is not None:
        return CachedVoice(voice_dir, fallback=rest)
    if rest is not None:
        return rest
    raise VoiceError("no voice: give a directory of recorded lines, a Piper model, or both")
