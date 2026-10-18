"""The brain's client for the body: the stackchan-mcp gateway daemon
(`stackchan-mcp serve --transport streamable-http`), whether it fronts the real
StackChan or test/fake_gateway.py. Nothing here knows which.

Two channels, as the gateway has them (docs/BUILD-PLAN.md, Build run 2):

- MCP at http://HOST:8767/mcp: streamable HTTP with plain JSON answers. Gateway is a
  small synchronous JSON-RPC client for it: initialize, then notifications/initialized,
  then tools/call with the Mcp-Session-Id the gateway handed out. It re-initializes
  once when the session is lost (the gateway restarted) and retries when the
  gateway's one command queue is full. The daemon runs one command at a time, so a
  call can wait behind another client's (or our own loader thread's) long one.
- Raw PCM at http://HOST:8766/pcm: the host's voice. It plays outside the command
  queue, so the head can turn while the host talks, and answers when it has played.
  With speaker="mac" the voice plays on this machine's audio output instead (any
  speaker connected to it) and the robot only moves its mouth (set_mouth_sequence).

Body wraps the tools the host uses. A gateway answer of {"error": ...} or {"ok": false}
raises BodyError, as does a schema refusal (isError) and an answer without the
JSON-RPC shape (D4), so every failure the host sees from here is a BodyError.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

PROTOCOL_VERSION = "2025-06-18"  # a handshake revision both mcp 1.x (the gateway) and 2.x serve
FACES = ("idle", "happy", "thinking", "sad", "surprised", "embarrassed", "off")
SAMPLE_RATE = 16_000
QUEUE_FULL = -32000
CAPTURES = Path.home() / ".stackchan" / "captures"  # where the real gateway writes take_photo's files
MAX_RETRY_AFTER = 5.0  # seconds: the gateway's retry_after_ms is a hint, not an order


class BodyError(Exception):
    """The gateway refused a command, the device failed it, or nothing answered."""


@dataclass
class ToolResult:
    """One tools/call answer: the text items joined, parsed as JSON when they are JSON,
    and the bytes of any images."""

    text: str
    data: Any
    images: list[bytes] = field(default_factory=list)


class Gateway:
    def __init__(self, url: str, token: str | None = None, timeout: float = 15.0) -> None:
        self.url = url
        self.token = token
        self.timeout = timeout
        self._session: str | None = None
        self._protocol = PROTOCOL_VERSION
        self._lock = threading.Lock()  # the session handshake and the request ids
        self._next_id = 0

    # --- tools -------------------------------------------------------------------

    def call(self, name: str, args: dict[str, Any] | None = None, timeout: float | None = None) -> ToolResult:
        """Call one tool and return its answer; raise BodyError on any refusal."""
        result = self._request("tools/call", {"name": name, "arguments": args or {}}, timeout)
        content = result.get("content", [])
        if not isinstance(content, list) or not all(isinstance(item, dict) for item in content):
            raise BodyError(f"{name}: the gateway's answer has no content list: {str(result)[:200]}")
        text = "\n".join(str(item.get("text", "")) for item in content if item.get("type") == "text")
        try:
            images = [base64.b64decode(item["data"]) for item in content if item.get("type") == "image"]
        except (KeyError, TypeError, ValueError) as e:
            raise BodyError(f"{name}: the gateway's image does not decode: {e}") from None
        try:
            data = json.loads(text) if text else None
        except json.JSONDecodeError:
            data = text
        if result.get("isError"):
            raise BodyError(f"{name}: {text or 'refused'}")
        if isinstance(data, dict) and (data.get("ok") is False or ("error" in data and data.get("ok") is not True)):
            raise BodyError(f"{name}: {data.get('error', data)}")
        return ToolResult(text, data, images)

    def tools(self) -> list[str]:
        return [t["name"] for t in self._request("tools/list", {}, None).get("tools", [])]

    # --- JSON-RPC over streamable HTTP -------------------------------------------

    def _request(self, method: str, params: dict[str, Any], timeout: float | None) -> dict[str, Any]:
        self._ensure_session()
        relogged = False
        for attempt in range(40):
            try:
                return self._rpc(method, params, timeout)
            except _SessionLost:
                if relogged:
                    raise BodyError(f"{method}: the gateway lost the session twice") from None
                relogged = True
                with self._lock:
                    self._session = None
                self._ensure_session()
            except _QueueFull as e:
                if attempt == 39:
                    raise BodyError(f"{method}: the gateway's command queue stayed full") from None
                time.sleep(e.retry_after)
        raise BodyError(f"{method}: gave up")

    def _ensure_session(self) -> None:
        with self._lock:
            if self._session is not None:
                return
            answer, headers = self._post(
                {
                    "jsonrpc": "2.0",
                    "id": self._id(),
                    "method": "initialize",
                    "params": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "gamemaster-brain", "version": "0"},
                    },
                },
                None,
                with_session=False,
            )
            if "error" in answer:
                raise BodyError(f"initialize: {answer['error']}")
            self._protocol = answer.get("result", {}).get("protocolVersion", PROTOCOL_VERSION)
            self._session = headers.get("mcp-session-id")
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, None, with_session=True)

    def _rpc(self, method: str, params: dict[str, Any], timeout: float | None) -> dict[str, Any]:
        with self._lock:
            rid = self._id()
        answer, _ = self._post({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}, timeout, with_session=True)
        if "error" in answer:
            err = answer["error"]
            retry = err.get("data", {}).get("retry_after_ms") if isinstance(err.get("data"), dict) else None
            if err.get("code") == QUEUE_FULL and isinstance(retry, (int, float)) and not isinstance(retry, bool):
                raise _QueueFull(retry / 1000)
            raise BodyError(f"{method}: {err.get('message', err)}")
        return answer["result"]

    def _id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _post(self, message: dict[str, Any], timeout: float | None, with_session: bool) -> tuple[dict[str, Any], dict[str, str]]:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if with_session:
            if self._session:
                headers["Mcp-Session-Id"] = self._session
            headers["MCP-Protocol-Version"] = self._protocol
        req = urllib.request.Request(self.url, data=json.dumps(message).encode(), method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as res:
                raw = res.read()
                got = {k.lower(): v for k, v in res.headers.items()}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 404 and with_session and self._session:
                raise _SessionLost() from None
            raise BodyError(f"{message.get('method')}: the gateway answered {e.code}: {body[:300]}") from None
        except (urllib.error.URLError, OSError) as e:
            raise BodyError(f"{message.get('method')}: no gateway at {self.url}: {e}") from None
        if "id" not in message:
            return {}, got  # a notification: 202, no body
        return _parse(raw, got.get("content-type", ""), message["id"]), got


class _SessionLost(Exception):
    pass


class _QueueFull(Exception):
    def __init__(self, retry_after: float) -> None:
        super().__init__(retry_after)
        self.retry_after = min(MAX_RETRY_AFTER, max(0.05, retry_after))


def _parse(raw: bytes, content_type: str, rid: int) -> dict[str, Any]:
    """The JSON-RPC answer with this id, from a JSON body or an SSE stream; checked for
    its shape (an object with a "result" object or an "error" object), else BodyError."""
    if "text/event-stream" in content_type:
        for line in raw.decode("utf-8", "replace").splitlines():
            if line.startswith("data:"):
                try:
                    msg = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if isinstance(msg, dict) and msg.get("id") == rid:
                    return _shaped(msg)
        raise BodyError(f"no answer to request #{rid} in the gateway's event stream")
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as e:
        raise BodyError(f"the gateway's answer is not JSON: {raw[:200]!r}") from e
    if isinstance(msg, list):  # a batch: pick ours
        msg = next((m for m in msg if isinstance(m, dict) and m.get("id") == rid), {})
    return _shaped(msg)


def _shaped(msg: Any) -> dict[str, Any]:
    """`msg` as a JSON-RPC answer: an object with a "result" object or an "error" object."""
    if isinstance(msg, dict) and (isinstance(msg.get("result"), dict) or isinstance(msg.get("error"), dict)):
        return msg
    raise BodyError(f"the gateway's answer is not a JSON-RPC result: {str(msg)[:200]}")


class Body:
    """The tools the host uses, in the host's terms. Yaw is degrees in the host's frame
    (0 straight ahead, positive to the host's right, the synthetic table's convention);
    flip_yaw negates it for a robot whose servo turns the other way."""

    def __init__(
        self,
        gateway: Gateway,
        pcm_url: str,
        token: str | None = None,
        flip_yaw: bool = False,
        pitch: int = 25,
        speed: str | int = "high",
        speaker: str = "robot",
        captures: Path | None = None,
    ) -> None:
        if speaker not in ("robot", "mac"):
            raise ValueError("speaker must be robot or mac")
        self.gateway = gateway
        self.pcm_url = pcm_url
        self.token = token
        self.flip_yaw = flip_yaw
        self.pitch = int(min(85, max(5, pitch)))
        self.speed = speed
        self.speaker = speaker
        self.captures = Path(captures) if captures is not None else CAPTURES  # the only folder photo() deletes from

    def setup(self) -> None:
        """Keep the screen on for the whole game and start blinking."""
        self.gateway.call("set_off_timeout", {"seconds": 0})
        self.blink(True)

    def turn(self, yaw: float, speed: str | int | None = None) -> None:
        """Start the head toward `yaw`; returns at once, while it moves. `speed` (degrees
        per second, or low|mid|high) overrides the body's own for this move."""
        deg = int(round(min(90.0, max(-90.0, yaw))))
        if self.flip_yaw:
            deg = -deg
        answer = self.gateway.call("move_head", {"yaw": deg, "pitch": self.pitch, "speed": self.speed if speed is None else speed})
        if isinstance(answer.data, dict) and (answer.data.get("servo_ok") is False or answer.data.get("servo_init_ok") is False):
            raise BodyError(f"move_head: the servos failed: {answer.data}")

    def photo(self) -> np.ndarray:
        """One camera frame, BGR. The capture file is deleted when it is on this machine,
        in the gateway's own captures folder (never a path elsewhere that the answer names)."""
        answer = self.gateway.call("take_photo", {"question": ""}, timeout=20)
        path = answer.data.get("image_path") if isinstance(answer.data, dict) else None
        if not isinstance(path, str) or not self._capture(path):
            path = None
        jpeg = answer.images[0] if answer.images else None
        if jpeg is None and path and os.path.exists(path):
            with open(path, "rb") as f:
                jpeg = f.read()
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
        if jpeg is None:
            raise BodyError(f"take_photo: no image came back: {answer.text[:200]}")
        image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise BodyError("take_photo: the image is not a JPEG")
        return image

    def _capture(self, path: str) -> bool:
        """`path` is a file directly in the gateway's captures folder."""
        try:
            return Path(path).resolve().parent == self.captures.resolve()
        except OSError:
            return False

    def listen(self, seconds: float) -> str:
        """Transcribe the next `seconds` of the microphone (faster-whisper on the gateway)."""
        ms = int(min(30_000, max(100, round(seconds * 1000))))
        answer = self.gateway.call(
            "listen",
            {"duration_ms": ms, "engine": "faster-whisper", "language": "en", "motion": "none"},
            timeout=ms / 1000 + 60,
        )
        text = answer.data.get("text", "") if isinstance(answer.data, dict) else ""
        return text if isinstance(text, str) else ""

    def play(self, pcm: bytes) -> None:
        """Play 16 kHz mono s16le PCM on the speaker; returns once it has played."""
        if not pcm:
            return
        if self.speaker == "mac":
            self._play_here(pcm)
            return
        headers = {"Content-Type": "application/octet-stream", "X-Sample-Rate": str(SAMPLE_RATE), "X-Channels": "1"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        seconds = len(pcm) / (SAMPLE_RATE * 2)
        req = urllib.request.Request(self.pcm_url, data=pcm, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=seconds + 15) as res:
                res.read()
        except urllib.error.HTTPError as e:
            raise BodyError(f"POST /pcm answered {e.code}: {e.read().decode('utf-8', 'replace')[:200]}") from None
        except (urllib.error.URLError, OSError) as e:
            raise BodyError(f"POST /pcm: {e}") from None

    def _play_here(self, pcm: bytes) -> None:
        """Play on this machine's audio output (afplay) while the robot moves its mouth."""
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="gm-line-")
        try:
            with os.fdopen(fd, "wb") as f, wave.open(f, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(pcm)
            try:
                player = subprocess.Popen(["afplay", path])
            except OSError as e:
                raise BodyError(f"afplay: {e}") from None
            try:
                self.gateway.call("set_mouth_sequence", {"steps": mouth_steps(pcm)})
            except BodyError:
                pass  # the line still plays; only the mouth stays still
            if player.wait() != 0:
                raise BodyError(f"afplay exited with {player.returncode}")
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def avatar(self, face: str) -> None:
        if face not in FACES:
            raise ValueError(f"face must be one of {FACES}")
        self.gateway.call("set_avatar", {"face": face})

    def load_set(self, path: str, timeout: float = 180.0) -> None:
        """Load a layered avatar set (brain/cards.py); blocks until the device adopts it."""
        t = float(min(300.0, max(5.0, timeout)))
        self.gateway.call("load_avatar_set", {"archive_path": os.path.abspath(path), "mode": "layered", "timeout": t}, timeout=t + 15)

    def blink(self, on: bool) -> None:
        self.gateway.call("set_blink", {"enabled": bool(on)})

    def leds(self, colors: list[tuple[int, int, int]]) -> None:
        """Up to twelve [r, g, b] from LED 0; one colour sets them all."""
        if len(colors) == 1:
            r, g, b = colors[0]
            self.gateway.call("set_all_leds", {"r": int(r), "g": int(g), "b": int(b)})
        else:
            self.gateway.call("set_leds", {"colors": [[int(c) for c in rgb] for rgb in colors[:12]]})

    def touched(self, within: float) -> bool:
        """The head was touched now or in the last `within` seconds (get_touch_state); a
        robot that cannot say counts as not touched."""
        try:
            data = self.gateway.call("get_touch_state").data
        except BodyError:
            return False
        if not isinstance(data, dict):
            return False
        if any(data.get(f"zone{i}") for i in range(3)):
            return True
        age = data.get("last_event_age_ms")
        return data.get("last_event") not in (None, "idle") and isinstance(age, (int, float)) and 0 <= age <= within * 1000

    def clear_leds(self) -> None:
        self.gateway.call("clear_leds")

    def volume(self) -> int | None:
        """The speaker's volume (0..100) as the device reports it (get_device_info), or
        None when it does not say."""
        for tool in ("get_device_info", "get_status"):
            try:
                found = _find_volume(self.gateway.call(tool).data)
            except BodyError:
                continue
            if found is not None:
                return found
        return None

    def set_volume(self, volume: int) -> None:
        self.gateway.call("set_volume", {"volume": int(min(100, max(0, volume)))})

    def status(self) -> dict[str, Any]:
        answer = self.gateway.call("get_status")
        return answer.data if isinstance(answer.data, dict) else {"status": answer.text}


def _find_volume(data: Any) -> int | None:
    """The first "volume" number anywhere in a device's status answer (the firmware nests
    it, e.g. {"audio_speaker": {"volume": 70}})."""
    if isinstance(data, dict):
        v = data.get("volume")
        if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 100:
            return int(v)
        for value in data.values():
            found = _find_volume(value)
            if found is not None:
                return found
    return None


def mouth_steps(pcm: bytes, step_ms: int = 100, max_steps: int = 256) -> list[dict[str, Any]]:
    """A lip-sync sequence for 16 kHz mono s16le PCM: the loudness of each step_ms window,
    against the line's loudest, picks closed, half or open; runs of one shape merge, and
    the mouth ends closed. Long lines use longer windows to stay within max_steps."""
    samples = np.frombuffer(pcm[: len(pcm) - len(pcm) % 2], dtype="<i2").astype(np.float32)
    window = SAMPLE_RATE * step_ms // 1000
    count = max(1, -(-len(samples) // window))
    while count > max_steps - 1:
        step_ms *= 2
        window *= 2
        count = max(1, -(-len(samples) // window))
    padded = np.zeros(count * window, dtype=np.float32)
    padded[: len(samples)] = samples
    rms = np.sqrt((padded.reshape(count, window) ** 2).mean(axis=1))
    peak = float(rms.max()) or 1.0
    steps: list[dict[str, Any]] = []
    for level in rms / peak:
        shape = "closed" if level < 0.15 else "half" if level < 0.45 else "open"
        if steps and steps[-1]["shape"] == shape:
            steps[-1]["duration_ms"] += step_ms
        else:
            steps.append({"shape": shape, "duration_ms": step_ms})
    if steps[-1]["shape"] != "closed":
        steps.append({"shape": "closed", "duration_ms": step_ms})
    for step in steps:
        step["duration_ms"] = min(10_000, step["duration_ms"])
    return steps
