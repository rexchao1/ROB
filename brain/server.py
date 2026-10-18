"""The brain's one HTTP server.

Always: GET /state, the game state the host last published ({"game": null} before
any), for watching a real game from a laptop; and the dashboard, GET /dashboard and
its routes (brain/dashboard.py).

Under --test only, the endpoints a test drives the brain with. None seeds game state:
a test rigs the random choices (who is the Mafia, the word, the targets) and pushes
what the camera sees and what the microphone hears; the brain does the rest, on its
virtual clock.

  POST /test/reset            the host stopped wherever it is, the fake gateway reset
                              (its record, frames, transcripts, head, screen), the
                              clock to zero, the host's memory cleared, and the host
                              started again, idle-listening; answers once it is asleep.
                              Body {"welcome": true}: it starts with the welcome (D38)
                              instead, as the real host does
  POST /test/table            body: {"faces": [{"bearing", "pose", "close"}, ...]};
                              forwarded to the fake gateway's camera, which renders the
                              synthetic table wherever the head faces (/mock/table)
  POST /test/frame[?pan=deg]  body: a PNG or JPEG; forwarded to the fake gateway's
                              camera (see test/fake_gateway.py, /mock/frame)
  POST /test/hear             body: {"text": "..."}; forwarded to the fake gateway's
                              microphone: the host's next listen hears it
  POST /test/advance          body: {"seconds": n}, n >= 0; moves the virtual clock and
                              answers once the host has done everything due by then
  POST /test/rig              body: {"<game>": {...}}; the next game of that name deals
                              from it (brain/games/__init__.py names the keys)
  GET  /test/state            the same as GET /state

In both modes, when a Dash is attached to the host (brain/dash.py), the operator's
dashboard: GET /dash, the page (brain/dash/index.html), and its JSON under /dash/api/*
(docs/DASHBOARD-PLAN.md has the table), its backdrops, GET /dash/art/<name>.jpg, and
its bundled scripts, GET /dash/vendor/<name>.js (the avatars' DiceBear, built by
`npm run build:avatars`). /dash/api answers any origin.
"""

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from brain import dashboard
from brain.clock import ClockStuck, VirtualClock
from brain.dash import FACE_STYLE, DashError
from brain.keys import KeysError
from brain.host import Host

PAGE = Path(__file__).resolve().parent / "dash" / "index.html"
ART = PAGE.parent / "art"  # the page's backdrops, GET /dash/art/<name>.jpg
VENDOR = PAGE.parent / "vendor"  # the page's bundled scripts, GET /dash/vendor/<name>.js


class FakeControl:
    """The fake gateway's test-side endpoints (test/fake_gateway.py, /mock/*). Test mode
    only: the real gateway has none of them."""

    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout

    def post(self, path: str, data: bytes, content_type: str) -> tuple[int, Any]:
        req = urllib.request.Request(self.url + path, data=data, method="POST", headers={"Content-Type": content_type})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                return res.status, json.loads(res.read() or b"null")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"null")
            except json.JSONDecodeError:
                return e.code, {"error": f"the fake gateway answered {e.code}"}
        except (urllib.error.URLError, OSError) as e:
            return 502, {"error": f"the fake gateway at {self.url} did not answer: {e}"}


class _NotFound(Exception):
    pass


class _BadRequest(Exception):
    pass


class _Forbidden(Exception):
    pass


def make_handler(host: Host, fake: FakeControl | None, reset: Callable[..., None] | None) -> type[BaseHTTPRequestHandler]:
    test_mode = fake is not None and reset is not None

    class Handler(BaseHTTPRequestHandler):
        server_version = "gamemaster"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
            pass

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def do_OPTIONS(self) -> None:
            if not urlsplit(self.path).path.startswith("/dash/api/"):
                self._send(404, {"error": f"no OPTIONS {self.path}"})
                return
            self.send_response(204)
            self._cors()
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _dispatch(self, method: str) -> None:
            url = urlsplit(self.path)
            body = self._body() if method == "POST" else b""
            try:
                if (method, url.path) == ("GET", "/state"):
                    status, payload = 200, _state(host)
                elif url.path == "/dashboard" or url.path.startswith("/dashboard/"):
                    status, payload = dashboard.handle(host, method, url.path, body)
                elif url.path == "/dash" and method == "GET" and host.dash is not None:
                    if not PAGE.is_file():
                        raise _NotFound
                    self._send_raw(200, PAGE.read_bytes(), "text/html; charset=utf-8")
                    return
                elif url.path.startswith("/dash/art/") and method == "GET" and host.dash is not None:
                    name = url.path.removeprefix("/dash/art/")
                    art = ART / name
                    if not re.fullmatch(r"[a-z0-9-]+\.jpg", name) or not art.is_file():  # one flat folder, no paths
                        raise _NotFound
                    self._send_raw(200, art.read_bytes(), "image/jpeg")
                    return
                elif url.path.startswith("/dash/vendor/") and method == "GET" and host.dash is not None:
                    name = url.path.removeprefix("/dash/vendor/")
                    script = VENDOR / name
                    if not re.fullmatch(r"[a-z0-9-]+\.js", name) or not script.is_file():  # one flat folder, no paths
                        raise _NotFound
                    self._send_raw(200, script.read_bytes(), "text/javascript; charset=utf-8")
                    return
                elif url.path.startswith("/dash/api/") and host.dash is not None:
                    status, payload = self._dash(method, url.path, parse_qs(url.query), body)
                    if isinstance(payload, bytes):
                        self._send_raw(status, payload, "image/jpeg")
                        return
                elif url.path.startswith("/test/") and test_mode:
                    status, payload = self._test(method, url.path, parse_qs(url.query), body)
                else:
                    raise _NotFound
            except _NotFound:
                status, payload = 404, {"error": f"no {method} {url.path}"}
            except _Forbidden:
                status, payload = 403, {"error": "keys are set from the dashboard's own page"}
            except (_BadRequest, DashError, KeysError) as e:
                status, payload = 400, {"error": str(e)}
            except ClockStuck as e:
                status, payload = 500, {"error": f"ClockStuck: {e}"}
            except Exception as e:  # every request gets an answer, never a dropped socket
                status, payload = 500, {"error": f"{type(e).__name__}: {e}"}
            self._send(status, payload)

        def _test(self, method: str, path: str, query: dict[str, list[str]], body: bytes) -> tuple[int, Any]:
            assert fake is not None and reset is not None and isinstance(host.clock, VirtualClock)
            route = (method, path)
            if route == ("POST", "/test/reset"):
                reset(welcome=bool(_json(body).get("welcome")) if body else False)
                return 200, {"ok": True, "now": host.clock.now()}
            if route == ("POST", "/test/frame"):
                suffix = "?" + urlencode({"pan": query["pan"][0]}) if "pan" in query else ""
                return fake.post("/mock/frame" + suffix, body, self.headers.get("Content-Type") or "image/png")
            if route == ("POST", "/test/table"):
                return fake.post("/mock/table", body, "application/json")
            if route == ("POST", "/test/hear"):
                text = _json(body).get("text")
                if not isinstance(text, str):
                    raise _BadRequest('expected {"text": "..."}')
                return fake.post("/mock/hear", json.dumps({"text": text}).encode(), "application/json")
            if route == ("POST", "/test/advance"):
                seconds = _json(body).get("seconds")
                if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
                    raise _BadRequest('expected {"seconds": n} with n >= 0')
                return 200, {"now": host.clock.advance(seconds)}
            if route == ("POST", "/test/rig"):
                rigs = _json(body)
                if not all(isinstance(v, dict) for v in rigs.values()):
                    raise _BadRequest('expected {"<game>": {...}}')
                with host._lock:  # noqa: SLF001 - the server is the host's test side
                    host.rigs.update(rigs)
                return 200, {"ok": True, "rigged": sorted(host.rigs)}
            if route == ("GET", "/test/state"):
                return 200, _state(host)
            raise _NotFound

        def _dash(self, method: str, path: str, query: dict[str, list[str]], body: bytes) -> tuple[int, Any]:
            dash = host.dash
            route = (method, path.removeprefix("/dash/api"))
            if route == ("GET", "/state"):
                return 200, dash.state()
            if route == ("GET", "/events"):
                try:
                    since = int(query.get("since", ["0"])[0])
                except ValueError as e:
                    raise _BadRequest("since must be a whole number") from e
                return 200, dash.events(since)
            if route == ("GET", "/photo"):
                jpeg = dash.photo_jpeg()
                if jpeg is None:
                    raise _NotFound
                return 200, jpeg
            if method == "GET" and (m := re.fullmatch(r"/seat/([1-9][0-9]?)\.jpg", route[1])):
                jpeg = dash.seat_jpeg(int(m.group(1)))
                if jpeg is None:
                    raise _NotFound
                return 200, jpeg
            if route == ("GET", "/robot"):
                return 200, {"robot": dash.robot(), "face_style": FACE_STYLE}
            if route == ("POST", "/volume"):
                return 200, dash.set_volume(_json(body).get("volume"))
            if route == ("POST", "/hear"):
                return 200, {"ok": True, "pending": dash.hear(_text(_json(body)))}
            if route == ("POST", "/game"):
                name = _json(body).get("name")
                if not isinstance(name, str):
                    raise _BadRequest('expected {"name": "mafia" | "imposter" | "wavelength" | "stop"}')
                return 200, {"ok": True, "pending": dash.game(name)}
            if route == ("POST", "/say"):
                dash.say(_text(_json(body)))
                return 200, {"ok": True}
            if route == ("POST", "/head"):
                b = _json(body)
                return 200, dash.head(b.get("yaw"), b.get("pitch"))
            if route == ("GET", "/settings"):
                return 200, dash.settings()
            if route == ("POST", "/settings"):
                return 200, dash.apply(_json(body))
            if route == ("GET", "/content"):
                return 200, dash.content()
            if route == ("POST", "/content"):
                return 200, dash.set_content(_json(body))
            if route == ("GET", "/keys"):
                return 200, dash.keys.status()
            if route == ("POST", "/keys"):
                if not self._same_origin():
                    raise _Forbidden
                return 200, dash.keys.set(_json(body))
            if route == ("GET", "/rig"):
                return 200, dash.rigs()
            if route == ("POST", "/rig"):
                return 200, dash.rig(_json(body))
            raise _NotFound

        def _same_origin(self) -> bool:
            """A browser's request from this page, or one with no Origin (curl, a script on
            this machine); never a page from another site writing keys."""
            origin = self.headers.get("Origin")
            return origin is None or urlsplit(origin).netloc == (self.headers.get("Host") or "")

        def _cors(self) -> None:
            if urlsplit(self.path).path.startswith("/dash/api/"):
                self.send_header("Access-Control-Allow-Origin", "*")

        def _send_raw(self, status: int, data: bytes, content_type: str) -> None:
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> bytes:
            length = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(length) if length > 0 else b""

        def _send(self, status: int, payload: Any) -> None:
            html = isinstance(payload, dashboard.Html)
            data = payload.encode("utf-8") if html else json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", "text/html; charset=utf-8" if html else "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def _state(host: Host) -> dict[str, Any]:
    with host._lock:  # noqa: SLF001
        return dict(host.state) if host.state is not None else {"game": None}


def _text(body: dict[str, Any]) -> str:
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise _BadRequest('expected {"text": "..."}')
    return text


def _json(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body or b"null")
    except json.JSONDecodeError as e:
        raise _BadRequest("body is not JSON") from e
    if not isinstance(value, dict):
        raise _BadRequest("body is not a JSON object")
    return value


def serve(host: Host, address: str, port: int, fake: FakeControl | None = None, reset: Callable[..., None] | None = None) -> ThreadingHTTPServer:
    """Bind the server (port 0 picks a free one); the caller runs serve_forever(). With a
    FakeControl and a reset callable, the /test/* endpoints are open."""
    server = ThreadingHTTPServer((address, port), make_handler(host, fake, reset))
    server.daemon_threads = True
    return server
