"""Record the host's fixed lines once with ElevenLabs (D30), into voice/<voice id>/<line_key>.wav.

The brain plays a recorded line when one exists in the voice ROB speaks in now
(brain/voice.py, CachedVoice) and speaks the rest live, so this runs by hand, once per
voice, with a key, and never in a test lane. Lines already recorded in that voice are
skipped, so a rerun only fills gaps.

  python scripts/make-voice.py --dry-run                 # list what it would record
  ELEVENLABS_API_KEY=... python scripts/make-voice.py    # the brain's default voice
  ELEVENLABS_API_KEY=... python scripts/make-voice.py --voice-id george

The voice: an ElevenLabs voice id, or one of the dashboard's voices by name (chris,
jessica, george, charlie, brian); by default ELEVENLABS_VOICE_ID, else the brain's own
default (brain.voice.ELEVEN_VOICE), the voice the brain speaks in when nothing else is
picked. Each voice has its own folder, so the recordings of one never play in another's
place.

The lines: brain.lines.fixed_lines() (every line the host can say whose words are
known ahead of time), plus voice/lines.txt if present (one line per row, # comments).
Each WAV is 16 kHz mono 16-bit, ElevenLabs' pcm_16000 output wrapped as a WAV, and
voice/<voice id>/index.tsv lists every recording's key and text.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Protocol

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brain import personas  # noqa: E402 - after the path
from brain.keys import load_env  # noqa: E402
from brain.voice import ELEVEN_VOICE, line_key, pcm_to_wav  # noqa: E402

API = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_MODEL = "eleven_multilingual_v2"


class TTS(Protocol):
    def pcm(self, text: str) -> bytes:
        """The line as 16 kHz mono s16le PCM."""
        ...


class ElevenLabs:
    """The ElevenLabs text-to-speech REST API, output_format pcm_16000."""

    def __init__(self, api_key: str, voice_id: str, model: str = DEFAULT_MODEL, timeout: float = 60.0) -> None:
        self.api_key, self.voice_id, self.model, self.timeout = api_key, voice_id, model, timeout

    def pcm(self, text: str) -> bytes:
        body = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35, "use_speaker_boost": True},
        }
        req = urllib.request.Request(
            f"{API}/{self.voice_id}?output_format=pcm_16000",
            data=json.dumps(body).encode(),
            method="POST",
            headers={"xi-api-key": self.api_key, "Content-Type": "application/json", "Accept": "audio/pcm"},
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as res:
                    return res.read()
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 3:  # rate limited: back off and retry
                    time.sleep(2 ** attempt)
                    continue
                raise SystemExit(f"ElevenLabs answered {e.code} for {text!r}: {e.read().decode('utf-8', 'replace')[:300]}") from e
        raise SystemExit("unreachable")


def fixed_lines() -> list[str]:
    try:
        from brain.lines import fixed_lines as from_script
    except ImportError as e:
        raise SystemExit(f"brain.lines.fixed_lines() is missing ({e}); the script of lines is built in brain/lines.py") from e
    return list(from_script())


def extra_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    rows = (row.strip() for row in path.read_text().splitlines())
    return [row for row in rows if row and not row.startswith("#")]


def unique(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for line in lines:
        key = line_key(line)
        if key not in seen:
            seen.add(key)
            out.append(line)
    return out


def record(lines: list[str], out: Path, tts: TTS | None, dry_run: bool = False, log: Callable[[str], None] = print) -> list[str]:
    """Record each line not yet in `out`; returns the lines recorded (or, dry, that would be)."""
    out.mkdir(parents=True, exist_ok=True)
    todo = [line for line in unique(lines) if not (out / f"{line_key(line)}.wav").is_file()]
    log(f"{len(unique(lines))} lines, {len(todo)} to record")
    for i, line in enumerate(todo, 1):
        if dry_run:
            log(f"  would record: {line}")
            continue
        assert tts is not None
        pcm = tts.pcm(line)
        if len(pcm) < 2 or len(pcm) % 2:
            raise SystemExit(f"ElevenLabs sent {len(pcm)} bytes for {line!r}, not 16-bit PCM")
        path = out / f"{line_key(line)}.wav"
        tmp = path.with_suffix(".wav.tmp")
        tmp.write_bytes(pcm_to_wav(pcm))
        tmp.replace(path)
        log(f"  [{i}/{len(todo)}] {line}")
    if not dry_run:
        write_index(lines, out)
    return todo


def write_index(lines: list[str], out: Path) -> None:
    rows = [f"{line_key(line)}\t{line}" for line in unique(lines) if (out / f"{line_key(line)}.wav").is_file()]
    (out / "index.tsv").write_text("".join(row + "\n" for row in rows))


def main(argv: list[str] | None = None, tts: TTS | None = None, lines: list[str] | None = None) -> int:
    if tts is None:
        load_env()  # the key and voice set from the dashboard (.env)
    parser = argparse.ArgumentParser(prog="make-voice.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--voice-id", default=os.environ.get("ELEVENLABS_VOICE_ID") or ELEVEN_VOICE,
                        help=f"ElevenLabs voice id or a dashboard voice's name (default ELEVENLABS_VOICE_ID, else {ELEVEN_VOICE})")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"ElevenLabs model (default {DEFAULT_MODEL})")
    parser.add_argument("--out", type=Path, default=ROOT / "voice", help="where the voices' folders go (default voice/)")
    parser.add_argument("--lines-file", type=Path, default=ROOT / "voice" / "lines.txt", help="extra lines, one per row")
    parser.add_argument("--dry-run", action="store_true", help="list the lines it would record; call nothing")
    args = parser.parse_args(argv)

    named = personas.VOICES.get(args.voice_id.lower())
    voice_id = named.eleven_id if named else args.voice_id
    if not voice_id.isalnum():
        parser.error(f"--voice-id {voice_id!r} is not an ElevenLabs voice id (letters and digits) or a voice's name")
    todo = unique((fixed_lines() if lines is None else lines) + extra_lines(args.lines_file))
    if tts is None and not args.dry_run:
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            parser.error("ELEVENLABS_API_KEY is not set")
        tts = ElevenLabs(key, voice_id, args.model)
    record(todo, args.out / voice_id, tts, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
