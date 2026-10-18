"""The fake gateway: the stackchan-mcp 0.18.0 daemon as the brain sees it, served on
loopback so every brain test runs with no robot (docs/BUILD-PLAN.md, Build run 2).

Two faces, as the real gateway has them:

  /mcp   MCP over streamable HTTP with JSON answers and stateful sessions (the mcp
         SDK's own session manager, as the gateway uses it). The tools the brain uses,
         with the gateway's names, argument schemas (checked, refusing with
         "Input validation error: ..." and isError) and answer shapes (JSON text;
         take_photo adds a JPEG ImageContent; a refusal is {"error": ...} or
         {"ok": false, "error": ...}).
  /pcm   POST raw 16 kHz mono s16le PCM with X-Sample-Rate and X-Channels; answers
         when "played" (at once). The brain's test voice carries each line's text in
         its clip (brain.voice.decode_test_pcm), so the fake knows what was said.

Every tool call and every /pcm, accepted or refused, is recorded in arrival order with
its arguments and the fake's answer: that record is the far side a test asserts on
(what the body was told), never what the brain thinks it did.

The test side (never part of the gateway; the brain's /test/* forwards to it and the
harness reads it directly):

  POST /mock/reset            the record, frames, transcripts, head, screen and LEDs to
                              their start
  POST /mock/table            body: {"faces": [{"bearing": deg, "pose": "frontal"|"down",
                              "close": bool}, ...]}: the synthetic table
                              (test/fixtures/table.py), rendered at whatever yaw the head
                              faces when a photo is taken. Replaces any pushed frames.
  POST /mock/frame[?pan=deg]  body: a PNG or JPEG. With pan, what the camera sees while
                              the head faces that angle; take_photo serves the pushed pan
                              nearest the head's yaw. Without pan, the frame at every
                              angle, and the per-pan frames are dropped. Either replaces
                              the table. Every photo is served as the device sends it:
                              320x240 JPEG.
  POST /mock/hear             body: {"text": "..."}; queued for the next listen, which
                              answers every queued transcript joined by spaces
  GET  /mock/calls            the record: [{seq, tool, args, answer, error, line?}]
  GET  /mock/screen           {face, blink, showing: {text, sub} or null, set}
  GET  /mock/head             {yaw, pitch}

Until a table or a frame is pushed take_photo refuses (a camera with nothing to show is a test
that forgot its fixture, not an empty table).

  python test/fake_gateway.py [--host 127.0.0.1] [--port 0]

prints "fake gateway: listening on http://HOST:PORT" once it is bound; MCP is at
/mcp and PCM at /pcm on that one port.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import jsonschema
import numpy as np
import uvicorn
from mcp import types
from mcp.server.lowlevel import Server
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # brain.* when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))  # the synthetic table

import table  # noqa: E402 - after the path fix
from brain import cards, voice  # noqa: E402

PHOTO_W, PHOTO_H = 320, 240
LAYERED_BYTES = 537_600
MATRIX_BYTES = 3_456_000
FACES = ["idle", "happy", "thinking", "sad", "surprised", "embarrassed", "off"]
MOUTHS = ["closed", "half", "open", "e", "u"]

_RGB = {"type": "integer", "minimum": 0, "maximum": 255}
# The gateway's schemas (stackchan_mcp/stdio_server.py), for the tools the brain can reach.
SCHEMAS: dict[str, dict[str, Any]] = {
    "get_status": {"type": "object", "properties": {}},
    "get_device_info": {"type": "object", "properties": {}},
    "take_photo": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
    "set_volume": {"type": "object", "properties": {"volume": {"type": "integer"}}, "required": ["volume"]},
    "set_brightness": {"type": "object", "properties": {"brightness": {"type": "integer"}}, "required": ["brightness"]},
    "set_off_timeout": {
        "type": "object",
        "properties": {"seconds": {"type": "integer", "minimum": 0, "maximum": 86400}},
        "required": ["seconds"],
    },
    "move_head": {
        "type": "object",
        "properties": {
            "yaw": {"type": "integer", "minimum": -90, "maximum": 90},
            "pitch": {"type": "integer", "minimum": 5, "maximum": 85},
            "speed": {"oneOf": [{"enum": ["low", "mid", "high"]}, {"type": "integer", "minimum": 1, "maximum": 10000}]},
        },
        "required": ["yaw", "pitch"],
    },
    "get_head_angles": {"type": "object", "properties": {}},
    "set_avatar": {"type": "object", "properties": {"face": {"type": "string", "enum": FACES}}, "required": ["face"]},
    "set_mouth": {"type": "object", "properties": {"mouth": {"type": "string", "enum": MOUTHS}}, "required": ["mouth"]},
    "set_blink": {"type": "object", "properties": {"enabled": {"type": "boolean"}}, "required": ["enabled"]},
    "set_led": {
        "type": "object",
        "properties": {"index": {"type": "integer", "minimum": 0, "maximum": 11}, "r": _RGB, "g": _RGB, "b": _RGB},
        "required": ["index", "r", "g", "b"],
    },
    "set_all_leds": {"type": "object", "properties": {"r": _RGB, "g": _RGB, "b": _RGB}, "required": ["r", "g", "b"]},
    "set_leds": {
        "type": "object",
        "properties": {
            "colors": {
                "type": "array",
                "items": {"type": "array", "items": _RGB, "minItems": 3, "maxItems": 3},
                "minItems": 1,
                "maxItems": 12,
            }
        },
        "required": ["colors"],
    },
    "clear_leds": {"type": "object", "properties": {}},
    "get_touch_state": {"type": "object", "properties": {}},
    "say": {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "voice": {"type": "string", "default": "voicevox"},
            "speaker_id": {"type": "integer"},
            "speaker_name": {"type": "string"},
            "reference_audio": {"type": "string"},
        },
        "required": ["text"],
    },
    "listen": {
        "type": "object",
        "properties": {
            "duration_ms": {"type": "integer", "default": 5000, "minimum": 100, "maximum": 30000},
            "engine": {"type": "string", "default": "faster-whisper"},
            "language": {"type": "string", "default": "ja"},
            "model": {"type": "string"},
            "motion": {"type": "string", "enum": ["none", "face-only", "look-up"], "default": "none"},
            "look_up_pitch": {"type": "number", "default": 50.0, "minimum": 5, "maximum": 85},
        },
    },
    "load_avatar_set": {
        "type": "object",
        "properties": {
            "archive_path": {"type": "string"},
            "mode": {"type": "string", "enum": ["layered", "matrix"]},
            "timeout": {"type": "number", "default": 60.0, "minimum": 5.0, "maximum": 300.0},
        },
        "required": ["archive_path", "mode"],
    },
}


class Refused(Exception):
    """A gateway- or device-side refusal: answered as JSON text, not as isError."""

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(payload.get("error"))
        self.payload = payload


class Device:
    """The robot behind the fake gateway: its head, screen, LEDs, camera and microphone."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.captures = Path(tempfile.mkdtemp(prefix="fake-gateway-captures-"))
        self.reset()

    def reset(self) -> None:
        with getattr(self, "lock", threading.Lock()):
            self.yaw, self.pitch = 0, 45
            self.face, self.blink, self.mouth = "idle", True, "closed"
            self.leds: list[list[int]] = [[0, 0, 0] for _ in range(12)]
            self.off_timeout = 300
            self.set_path: str | None = None
            self.manifest: dict[str, Any] | None = None
            self.frames: dict[float, np.ndarray] = {}
            self.default_frame: np.ndarray | None = None
            self.scene: list[table.Face] | None = None
            self.heard: list[str] = []
            self.touching = False  # a hand on the head
            self.calls: list[dict[str, Any]] = []
            self.seq = 0
            self.epoch = time.monotonic()

    # --- the record ----------------------------------------------------------------

    def record(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self.seq += 1
            entry = {"seq": self.seq, "tool": tool, "args": args, "answer": None, "error": None, "t": round(time.monotonic() - self.epoch, 4)}
            self.calls.append(entry)
            return entry

    # --- the tools -----------------------------------------------------------------

    def tool(self, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], bytes | None]:
        """One tool's JSON answer (and a JPEG for take_photo); raises Refused."""
        with self.lock:
            return getattr(self, "_" + name)(args)

    def _get_status(self, _: dict[str, Any]):
        return {"connected": True, "device_id": "fake-stackchan", "session_id": "fake", "initialized": True, "tools_count": len(SCHEMAS), "tools": sorted(SCHEMAS)}, None

    def _get_device_info(self, _: dict[str, Any]):
        return {"battery": {"level": 100, "charging": True}, "volume": 70, "brightness": 80, "network": {"type": "wifi", "rssi": -40}}, None

    def _set_volume(self, args: dict[str, Any]):
        return {"ok": True, "volume": args["volume"]}, None

    def _set_brightness(self, args: dict[str, Any]):
        return {"ok": True, "brightness": args["brightness"]}, None

    def _set_off_timeout(self, args: dict[str, Any]):
        self.off_timeout = args["seconds"]
        return {"ok": True, "seconds": self.off_timeout}, None

    def _move_head(self, args: dict[str, Any]):
        yaw, pitch = args["yaw"], args["pitch"]
        if not isinstance(yaw, int) or isinstance(yaw, bool) or not isinstance(pitch, int) or isinstance(pitch, bool):
            raise Refused({"error": "yaw and pitch must be integers"})
        self.yaw, self.pitch = yaw, pitch
        return {"ok": True, "yaw": yaw, "pitch": pitch, "servo_ok": True}, None

    def _get_head_angles(self, _: dict[str, Any]):
        return {"yaw": self.yaw, "pitch": self.pitch}, None

    def _take_photo(self, args: dict[str, Any]):
        frame = self._frame_at(self.yaw)
        if frame is None:
            raise Refused({"error": "fake gateway: no frame has been pushed (POST /mock/table or /mock/frame)"})
        small = cv2.resize(frame, (PHOTO_W, PHOTO_H), interpolation=cv2.INTER_AREA)
        ok, jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise Refused({"error": "fake gateway: JPEG encoding failed"})
        data = jpeg.tobytes()
        path = self.captures / f"capture_{int(time.time() * 1000)}_{self.seq}.jpg"
        path.write_bytes(data)
        return {"image_path": str(path), "size_bytes": len(data), "question": args["question"]}, data

    def _frame_at(self, yaw: float) -> np.ndarray | None:
        if self.scene is not None:
            return table.render(yaw, self.scene)
        if self.frames:
            return self.frames[min(self.frames, key=lambda pan: (abs(pan - yaw), pan))]
        return self.default_frame

    def _set_avatar(self, args: dict[str, Any]):
        self.face = args["face"]
        return {"ok": True, "face": self.face}, None

    def _set_mouth(self, args: dict[str, Any]):
        self.mouth = args["mouth"]
        return {"ok": True, "mouth": self.mouth}, None

    def _set_blink(self, args: dict[str, Any]):
        self.blink = bool(args["enabled"])
        return {"ok": True, "enabled": self.blink}, None

    def _set_led(self, args: dict[str, Any]):
        self.leds[args["index"]] = [args["r"], args["g"], args["b"]]
        return {"ok": True}, None

    def _set_all_leds(self, args: dict[str, Any]):
        self.leds = [[args["r"], args["g"], args["b"]] for _ in range(12)]
        return {"ok": True}, None

    def _set_leds(self, args: dict[str, Any]):
        for i, rgb in enumerate(args["colors"]):
            self.leds[i] = list(rgb)
        return {"ok": True}, None

    def _clear_leds(self, _: dict[str, Any]):
        self.leds = [[0, 0, 0] for _ in range(12)]
        return {"ok": True}, None

    def _get_touch_state(self, _: dict[str, Any]):
        t = self.touching  # the real robot's shape (stackchan-mcp 0.18)
        return {"available": True, "zone0": t, "zone1": False, "zone2": False, "raw": int(t), "last_event": "idle", "last_event_age_ms": -1}, None

    def _say(self, args: dict[str, Any]):
        # Present because the gateway has it; the brain speaks through /pcm instead.
        return {"engine": args.get("voice", "voicevox"), "text": args["text"], "spoke": True, "sample_rate": 16000}, None

    def _listen(self, args: dict[str, Any]):
        text = " ".join(t for t in self.heard if t)
        self.heard = []
        ms = args.get("duration_ms", 5000)
        return {
            "engine": args.get("engine", "faster-whisper"),
            "text": text,
            "language": args.get("language", "ja"),
            "duration_ms": ms,
            "frame_count": ms // 60,
            "sample_rate": 16000,
        }, None

    def _load_avatar_set(self, args: dict[str, Any]):
        path, mode = args.get("archive_path", ""), args.get("mode", "")
        if not path:
            raise Refused({"ok": False, "error": "archive_path is required"})
        if not Path(path).exists():
            raise Refused({"ok": False, "error": f"archive_not_found: {path}"})
        payload = Path(path).read_bytes()
        expected = {"layered": LAYERED_BYTES, "matrix": MATRIX_BYTES}[mode]
        if len(payload) != expected:
            raise Refused({"ok": False, "error": f"size_mismatch: got={len(payload)} expected={expected} (mode={mode})"})
        try:
            self.manifest = cards.read_manifest(Path(path))
        except (OSError, ValueError):
            self.manifest = None  # a set with no manifest: the fake cannot say what a slot shows
        self.set_path = path
        digest = hashlib.sha256(payload).hexdigest()
        return {"type": "avatar_set_loaded", "ok": True, "checksum": f"sha256:{digest}", "bytes_transferred": len(payload)}, None

    # --- the test side -------------------------------------------------------------

    def screen(self) -> dict[str, Any]:
        with self.lock:
            card = cards.card_in(self.manifest, self.face) if self.manifest else None
            return {
                "face": self.face,
                "blink": self.blink,
                "showing": None if card is None else {"text": card.text, "sub": card.sub},
                "set": self.set_path,
            }

    def push_frame(self, data: bytes, pan: float | None) -> None:
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("the frame is not a PNG or JPEG")
        with self.lock:
            self.scene = None
            if pan is None:
                self.frames = {}
                self.default_frame = image
            else:
                self.frames[pan] = image

    def set_table(self, faces: list[dict[str, Any]]) -> None:
        """The synthetic table: faces at bearings, rendered wherever the head faces."""
        if not isinstance(faces, list) or not all(isinstance(f, dict) for f in faces):
            raise ValueError('expected {"faces": [{"bearing": deg, "pose": "frontal"|"down", "close": bool}, ...]}')
        scene = []
        for f in faces:
            b = f.get("bearing")
            if isinstance(b, bool) or not isinstance(b, (int, float)) or not isinstance(f.get("close", False), bool):
                raise ValueError(f"a face needs a numeric bearing and a boolean close: {f}")
            scene.append(table.Face(float(b), f.get("pose", "frontal"), f.get("close", False)))
        with self.lock:
            self.frames, self.default_frame, self.scene = {}, None, scene


def build_app(device: Device):
    async def list_tools(_ctx: Any, _params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[types.Tool(name=n, description=f"fake {n}", inputSchema=s) for n, s in SCHEMAS.items()])

    async def call_tool(_ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        name, args = params.name, dict(params.arguments or {})
        entry = device.record(name, args)
        if name not in SCHEMAS:
            payload = {"error": f"Unknown tool: {name}"}
            entry["answer"], entry["error"] = payload, payload["error"]
            return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(payload))], isError=False)
        try:
            jsonschema.validate(instance=args, schema=SCHEMAS[name])
        except jsonschema.ValidationError as e:
            entry["error"] = f"Input validation error: {e.message}"
            return types.CallToolResult(content=[types.TextContent(type="text", text=entry["error"])], isError=True)
        try:
            payload, jpeg = device.tool(name, args)
        except Refused as e:
            entry["answer"], entry["error"] = e.payload, e.payload.get("error")
            return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(e.payload))], isError=False)
        entry["answer"] = payload
        content: list[Any] = [types.TextContent(type="text", text=json.dumps(payload))]
        if jpeg is not None:
            content.append(types.ImageContent(type="image", data=base64.b64encode(jpeg).decode(), mimeType="image/jpeg"))
        return types.CallToolResult(content=content, isError=False)

    async def pcm(request: Request) -> Response:
        raw = await request.body()
        rate = request.headers.get("x-sample-rate")
        channels = request.headers.get("x-channels", "1")
        entry = device.record("pcm", {"sample_rate": rate, "channels": channels, "bytes": len(raw)})
        if not rate or not rate.isdigit():
            entry["error"] = "X-Sample-Rate is required"
            return JSONResponse({"error": entry["error"]}, status_code=400)
        entry["line"] = voice.decode_test_pcm(raw)
        frames = max(1, len(raw) // (int(rate) * 2 * 60 // 1000 or 1))
        answer = {"source": "pcm", "frame_count": frames, "sample_rate": 16000, "frame_duration_ms": 60, "duration_ms": frames * 60}
        entry["answer"] = answer
        return JSONResponse(answer)

    async def mock_reset(_request: Request) -> Response:
        device.reset()
        return JSONResponse({"ok": True})

    async def mock_frame(request: Request) -> Response:
        pan_q = request.query_params.get("pan")
        try:
            pan = None if pan_q is None else float(pan_q)
            device.push_frame(await request.body(), pan)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return JSONResponse({"ok": True, "pan": pan})

    async def mock_table(request: Request) -> Response:
        try:
            body = json.loads(await request.body() or b"null")
            device.set_table(body.get("faces") if isinstance(body, dict) else None)
        except (json.JSONDecodeError, ValueError) as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return JSONResponse({"ok": True, "faces": len(device.scene or [])})

    async def mock_hear(request: Request) -> Response:
        try:
            body = json.loads(await request.body() or b"null")
        except json.JSONDecodeError:
            body = None
        if not isinstance(body, dict) or not isinstance(body.get("text"), str):
            return JSONResponse({"error": 'expected {"text": "..."}'}, status_code=400)
        with device.lock:
            device.heard.append(body["text"])
            queued = len(device.heard)
        return JSONResponse({"ok": True, "queued": queued})

    async def mock_calls(_request: Request) -> Response:
        with device.lock:
            return JSONResponse([dict(c) for c in device.calls])

    async def mock_screen(_request: Request) -> Response:
        return JSONResponse(device.screen())

    async def mock_head(_request: Request) -> Response:
        with device.lock:
            return JSONResponse({"yaw": device.yaw, "pitch": device.pitch})

    async def healthz(_request: Request) -> Response:
        return JSONResponse({"ok": True})

    server = Server("stackchan-mcp", on_list_tools=list_tools, on_call_tool=call_tool)
    routes = [
        Route("/pcm", pcm, methods=["POST"]),
        Route("/healthz", healthz, methods=["GET"]),
        Route("/mock/reset", mock_reset, methods=["POST"]),
        Route("/mock/table", mock_table, methods=["POST"]),
        Route("/mock/frame", mock_frame, methods=["POST"]),
        Route("/mock/hear", mock_hear, methods=["POST"]),
        Route("/mock/calls", mock_calls, methods=["GET"]),
        Route("/mock/screen", mock_screen, methods=["GET"]),
        Route("/mock/head", mock_head, methods=["GET"]),
    ]
    return server.streamable_http_app(json_response=True, custom_starlette_routes=routes, host="127.0.0.1")


class FakeGateway:
    """The fake gateway on a background thread (the Python tests) or the main one (CLI)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.device = Device()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(64)
        self.host, self.port = host, self.sock.getsockname()[1]
        self.url = f"http://{host}:{self.port}"
        config = uvicorn.Config(build_app(self.device), log_level="warning", access_log=False, lifespan="on")
        self.server = uvicorn.Server(config)
        self._thread: threading.Thread | None = None

    @property
    def mcp_url(self) -> str:
        return self.url + "/mcp"

    @property
    def pcm_url(self) -> str:
        return self.url + "/pcm"

    def run(self) -> None:
        self.server.run(sockets=[self.sock])

    def start(self) -> FakeGateway:
        self._thread = threading.Thread(target=self.run, name="fake-gateway", daemon=True)
        self._thread.start()
        give_up = time.monotonic() + 15
        while not self.server.started:
            if time.monotonic() > give_up or not self._thread.is_alive():
                raise RuntimeError("the fake gateway did not start")
            time.sleep(0.01)
        return self

    def stop(self) -> None:
        self.server.should_exit = True
        if self._thread:
            self._thread.join(5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fake_gateway.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)
    fake = FakeGateway(args.host, args.port)
    print(f"fake gateway: listening on {fake.url}", flush=True)
    try:
        fake.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
