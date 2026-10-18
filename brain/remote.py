"""The Table (brain/table.py) over the network: the rules run on the referee (the QNX
Pi, `python3 -m brain.referee`), the body, the camera, the voice, the ears and the
clock stay with the Host on the Mac. Standard library only: the referee imports this.

TableServer, on the Mac, runs every Table call a referee sends on the table it wraps
(the Host), one at a time, in the order they arrive. RemoteTable, on the referee, is a
Table whose every method is one of those calls.

  POST /table/hello  {"session"}   -> {"epoch", "calls", ...}: the epoch to call with,
                                      how many calls ran in it, and what the brain adds
                                      (the games' options, the listening window, the
                                      recovery line, the seed, whether to welcome)
  POST /table/call   {"session", "id", "epoch", "method", "args", "kwargs"}
                                   -> {"ok": true, "result": ...}
                                      {"ok": false, "kind": "error", "type", "message"}
                                      {"ok": false, "kind": "reset", "epoch"}
                                      {"ok": false, "kind": "replaced"}
                                      {"pending": true}: still running, ask again
  POST /table/rig    {"game"}      -> {"rig": {...} | null}: the next game's rig
  GET  /table/attached             -> {"attached", "epoch"}

A Card travels as {"text", "sub", "kind", "style"}. A GameStopped the host raises (a stop said during
the deal) reaches the referee as GameStopped, so its game ends as at any listen. A call is named by (session, id): RemoteTable sends
the same call again after a dropped connection or a "pending" answer, and the server
runs it once and answers the repeat from it. With a token, every request carries
"Authorization: Bearer <token>".

The clock. One worker thread runs every call. On a VirtualClock (test mode) it is
registered while a referee is attached, so advance() waits for it: asleep on the clock
inside a call (a listen, a wait, the photo poll) it is quiet; between calls, while the
referee decides what to do next and the request is on the wire, it is not, so the clock
never runs ahead of the referee and a test's record is the same as with the rules in
the brain's own process. A referee is attached from its first request until `lease`
seconds of real time pass with none; then the worker unregisters and the clock moves
freely (no referee yet, or one that died). The worker is registered for the setup too.

The epoch. reset() (a test's /test/reset) starts the table over: the call running is
cancelled at its next sleep on the clock, the calls waiting are dropped, and every call
of the old epoch is answered "reset", which RemoteTable raises as TableReset; the
referee says hello again and goes back to idle-listening. The epoch names the server's
run too, so a referee that outlives a restarted brain hears "reset" as well.

One referee at a time: a hello from a new session takes the table, and the old
session's next call is answered "replaced" (TableRefused: that referee stops).
"""

from __future__ import annotations

import hmac
import http.client
import json
import secrets
import sys
import threading
import time
import traceback
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from brain.clock import Clock, ClockCancelled, VirtualClock
from brain.games.common import GameStopped
from brain.table import Card

PORT = 8090
LEASE = 5.0  # real seconds without a request before the referee counts as gone
HOLD = 15.0  # real seconds a /table/call waits for its answer before answering "pending"
PATIENCE = 60.0  # real seconds RemoteTable keeps retrying an unreachable server
METHODS = ("now", "wait", "say", "look", "count", "seated", "prepare", "show_private", "reveal", "listen", "faces_up", "mood", "report", "quip", "chat", "sleep", "talk_settings")


class RemoteError(Exception):
    """The host raised doing a call; its exception's type name and message."""

    def __init__(self, type_name: str, message: str) -> None:
        super().__init__(f"{type_name}: {message}")
        self.type_name = type_name


class TableReset(BaseException):
    """The table started over (a test's reset, or the brain restarted): drop the game.
    A BaseException, so no game's error handling catches it."""


class TableUnreachable(BaseException):
    """The brain did not answer for longer than the referee keeps trying."""


class TableRefused(BaseException):
    """The brain will not take this referee's calls: a wrong token, or another referee
    took the table."""


def _wire(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"{type(value).__name__} does not travel to the table")


def _dumps(value: Any) -> bytes:
    return json.dumps(value, default=_wire).encode("utf-8")


def _card(value: Any) -> Card:
    if not isinstance(value, dict) or not isinstance(value.get("text"), str) or not all(
        isinstance(value.get(k), (str, type(None))) for k in ("sub", "kind")
    ):
        raise ValueError(f"not a card: {value!r}")
    style = value.get("style")
    return Card(value["text"], value.get("sub"), value.get("kind"), style if isinstance(style, str) else None)


class _Job:
    __slots__ = ("id", "run", "done", "answer")

    def __init__(self, id: int | None, run: Callable[[], Any]) -> None:  # noqa: A002 - the wire's name
        self.id = id
        self.run = run
        self.done = threading.Event()
        self.answer: dict[str, Any] = {}

    def finish(self, answer: dict[str, Any]) -> None:
        self.answer = answer
        self.done.set()


class TableServer:
    """Serve `table` to a referee on (host, port); port 0 picks a free one.

    setup: run on the worker at start() and after every reset(), before any call (the
    Host's own setup: the screen on, the idle look). rigs: game -> the next rig of that
    game or None (the Host's test rigs). hello: what /table/hello adds to the epoch, or
    a callable asked for it at every hello."""

    def __init__(
        self,
        table: Any,
        clock: Clock,
        host: str = "0.0.0.0",
        port: int = PORT,
        token: str | None = None,
        *,
        setup: Callable[[], None] | None = None,
        rigs: Callable[[str], dict[str, Any] | None] | None = None,
        hello: dict[str, Any] | Callable[[], dict[str, Any]] | None = None,
        lease: float = LEASE,
        hold: float = HOLD,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self.table = table
        self.clock = clock
        self.token = token
        self.setup = setup
        self.rigs = rigs
        self.extra = hello if callable(hello) else dict(hello or {})
        self.lease = lease
        self.hold = hold
        self.virtual = isinstance(clock, VirtualClock)
        self._log = log or (lambda msg: print(msg, file=sys.stderr, flush=True))
        self._run_name = secrets.token_hex(3)
        self._n = 1
        self._cv = threading.Condition()
        self._queue: deque[_Job] = deque()
        self._calls: dict[str, _Job] = {}  # session -> its latest call
        self._owner: str | None = None  # the session of the latest hello
        self._seen = float("-inf")  # time.monotonic() of the referee's last request or answer
        self._ran = 0  # calls run this epoch
        self._registered = False
        self._stopping = False
        self._serving = False
        self._worker = threading.Thread(target=self._work, name="table", daemon=True)
        self.httpd = ThreadingHTTPServer((host, port), _handler(self))
        self.httpd.daemon_threads = True

    @property
    def epoch(self) -> str:
        return f"{self._run_name}-{self._n}"

    @property
    def address(self) -> tuple[str, int]:
        return self.httpd.server_address[0], self.httpd.server_address[1]

    @property
    def url(self) -> str:
        host, port = self.address
        return f"http://{host}:{port}"

    def attached(self) -> bool:
        with self._cv:
            return time.monotonic() - self._seen < self.lease

    def start(self) -> TableServer:
        """The worker (which runs the setup first) and the HTTP server, on daemon threads."""
        with self._cv:
            if self.setup is not None:
                self._queue.append(_Job(None, self.setup))
        self._worker.start()
        self._serving = True
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, name="table-http", daemon=True).start()
        return self

    def stop(self, timeout: float = 5.0) -> None:
        with self._cv:
            self._stopping = True
            self._drop()
            if self.virtual and self._worker.ident is not None:
                self.clock.cancel(self._worker.ident)  # type: ignore[attr-defined]
            self._cv.notify_all()
        if self._serving:
            self.httpd.shutdown()
            self._serving = False
        self.httpd.server_close()
        if self._worker.ident is not None:
            self._worker.join(timeout)

    def reset(self, wipe: Callable[[], None], timeout: float = 10.0) -> None:
        """Start the table over (test mode): cancel the call running, drop the ones
        waiting, answer the old epoch "reset", and on the worker, once nothing runs,
        `wipe()` (the fake gateway, the clock, the host's memory) and the setup. Returns
        once wiped; the setup may still be running (the caller settles the clock)."""

        def wiping() -> None:
            if self.virtual:
                self.clock.unregister()  # type: ignore[attr-defined]  # forgets the cancel below
                self.clock.register()  # type: ignore[attr-defined]
            wipe()

        job = _Job(None, wiping)
        with self._cv:
            if self.virtual and self._worker.ident is not None:
                self.clock.cancel(self._worker.ident)  # type: ignore[attr-defined]
            self._n += 1
            self._ran = 0
            self._drop()
            self._queue.append(job)
            if self.setup is not None:
                self._queue.append(_Job(None, self.setup))
            self._cv.notify_all()
        if not job.done.wait(timeout):
            raise RuntimeError(f"the table did not start over within {timeout} s")
        if not job.answer.get("ok"):
            raise RuntimeError(job.answer.get("message") or "the table did not start over")

    # --- the requests (on the HTTP server's threads) ------------------------------

    def hello(self, session: str) -> dict[str, Any]:
        with self._cv:
            self._seen = time.monotonic()
            if session != self._owner:
                if self._owner is not None:
                    self._log(f"table: referee {session} took over from {self._owner}")
                self._owner = session
            self._cv.notify_all()
            extra = self.extra() if callable(self.extra) else self.extra
            # Settings are a lock-protected snapshot, independent of the body worker.
            # A fresh virtual table may still be finishing setup until its first reset.
            choices = self.table.talk_settings() if hasattr(self.table, "talk_settings") else {"talk": "off"}
            return {**extra, "epoch": self.epoch, "calls": self._ran, "talk_settings": choices}

    def rig(self, game: str) -> dict[str, Any] | None:
        return self.rigs(game) if self.rigs is not None else None

    def call(self, request: dict[str, Any]) -> dict[str, Any]:
        session, call_id, method = request.get("session"), request.get("id"), request.get("method")
        args, kwargs = request.get("args", []), request.get("kwargs", {})
        if not isinstance(session, str) or isinstance(call_id, bool) or not isinstance(call_id, int):
            raise ValueError('a call needs "session" (a string) and "id" (an integer)')
        if method not in METHODS or not isinstance(args, list) or not isinstance(kwargs, dict):
            raise ValueError(f'a call needs "method" (one of {METHODS}), "args" (a list) and "kwargs" (an object)')
        with self._cv:
            self._seen = time.monotonic()
            self._cv.notify_all()
            job = self._calls.get(session)
            if job is None or job.id != call_id:  # a new call, not a repeat
                if request.get("epoch") != self.epoch:
                    return {"ok": False, "kind": "reset", "epoch": self.epoch}
                if session != self._owner:
                    return {"ok": False, "kind": "replaced"}
                if job is not None and job.id is not None and call_id < job.id:
                    raise ValueError(f"call {call_id} is older than call {job.id}")
                job = _Job(call_id, lambda: self._dispatch(method, args, kwargs))
                self._calls[session] = job
                self._queue.append(job)
                self._cv.notify_all()
        if not job.done.wait(self.hold):
            return {"pending": True}
        return job.answer

    # --- the worker ---------------------------------------------------------------

    def _dispatch(self, method: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
        if method == "prepare" and args and isinstance(args[0], list):
            args = [[_card(c) for c in args[0]], *args[1:]]
        elif method == "show_private" and len(args) == 2:
            args = [args[0], _card(args[1])]
        elif method == "reveal" and len(args) == 2:
            args = [_card(args[0]), args[1]]
        with self._cv:
            self._ran += 1
        return getattr(self.table, method)(*args, **kwargs)

    def _drop(self) -> None:
        for job in self._queue:
            job.finish({"ok": False, "kind": "reset", "epoch": self.epoch})
        self._queue.clear()

    def _work(self) -> None:
        while True:
            with self._cv:
                while not self._queue:
                    if self._stopping:
                        self._unregister()
                        return
                    left = self._seen + self.lease - time.monotonic()
                    if left <= 0:
                        self._unregister()  # no referee: the clock moves without waiting for one
                    self._cv.wait(left if left > 0 else None)
                job = self._queue.popleft()
                if self.virtual and not self._registered:
                    self.clock.register()  # type: ignore[attr-defined]
                    self._registered = True
            answer = self._run(job)
            with self._cv:
                if job.id is not None:
                    self._seen = time.monotonic()
                job.finish(answer)

    def _unregister(self) -> None:
        if self._registered:
            self.clock.unregister()  # type: ignore[attr-defined]
            self._registered = False

    def _run(self, job: _Job) -> dict[str, Any]:
        try:
            return {"ok": True, "result": job.run()}
        except ClockCancelled:
            return {"ok": False, "kind": "reset", "epoch": self.epoch}
        except BaseException as e:  # noqa: BLE001 - every call gets an answer
            if job.id is None:
                self._log("table: the setup failed:\n" + traceback.format_exc())
            return {"ok": False, "kind": "error", "type": type(e).__name__, "message": str(e)}


class _BadRequest(Exception):
    pass


def _handler(server: TableServer) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"  # keep-alive: one connection for a referee's calls
        server_version = "gamemaster-table"
        timeout = 120  # an idle connection is closed after this long

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
            pass

        def do_GET(self) -> None:
            self._route("GET")

        def do_POST(self) -> None:
            self._route("POST")

        def _route(self, method: str) -> None:
            path = urlsplit(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else b""
            if server.token is not None and not hmac.compare_digest(
                self.headers.get("Authorization") or "", f"Bearer {server.token}"
            ):
                self._send(401, {"error": "a referee needs the table's token"})
                return
            try:
                if (method, path) == ("POST", "/table/call"):
                    status, payload = 200, server.call(_json(body))
                elif (method, path) == ("POST", "/table/hello"):
                    session = _json(body).get("session")
                    if not isinstance(session, str):
                        raise _BadRequest('expected {"session": "..."}')
                    status, payload = 200, server.hello(session)
                elif (method, path) == ("POST", "/table/rig"):
                    game = _json(body).get("game")
                    if not isinstance(game, str):
                        raise _BadRequest('expected {"game": "..."}')
                    status, payload = 200, {"rig": server.rig(game)}
                elif (method, path) == ("GET", "/table/attached"):
                    status, payload = 200, {"attached": server.attached(), "epoch": server.epoch}
                else:
                    status, payload = 404, {"error": f"no {method} {path}"}
            except (_BadRequest, ValueError) as e:
                status, payload = 400, {"error": str(e)}
            except Exception as e:  # every request gets an answer, never a dropped socket
                status, payload = 500, {"error": f"{type(e).__name__}: {e}"}
            try:
                self._send(status, payload)
            except TypeError as e:  # a result that does not travel
                self._send(500, {"error": f"TypeError: {e}"})

        def _send(self, status: int, payload: Any) -> None:
            data = _dumps(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def _json(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body or b"null")
    except json.JSONDecodeError as e:
        raise _BadRequest("body is not JSON") from e
    if not isinstance(value, dict):
        raise _BadRequest("body is not a JSON object")
    return value


class RemoteTable:
    """A Table whose every method is a call on the TableServer at `url`. Say hello()
    first. A dropped connection is retried, the same call again (run once), for up to
    `patience` seconds; then TableUnreachable."""

    def __init__(
        self,
        url: str,
        token: str | None = None,
        timeout: float = HOLD + 15.0,
        patience: float = PATIENCE,
        log: Callable[[str], None] | None = None,
    ) -> None:
        u = urlsplit(url)
        if u.scheme != "http" or not u.hostname:
            raise ValueError(f"the table's URL is http://HOST:PORT, not {url!r}")
        self.url = url.rstrip("/")
        self._host, self._port = u.hostname, u.port or 80
        self.token = token
        self.timeout = timeout
        self.patience = patience
        self.session = secrets.token_hex(6)
        self.epoch: str | None = None
        self._id = 0
        self._conn: http.client.HTTPConnection | None = None
        self._log = log or (lambda msg: print(msg, file=sys.stderr, flush=True))

    def hello(self) -> dict[str, Any]:
        """Attach to the table: its epoch (kept for every call) and what the brain sends."""
        answer = self._post("/table/hello", {"session": self.session})
        self.epoch = answer["epoch"]
        return answer

    def rig(self, game: str) -> dict[str, Any] | None:
        return self._post("/table/rig", {"game": game}).get("rig")

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # --- the Table ---------------------------------------------------------------

    def now(self) -> float:
        return float(self._call("now"))

    def wait(self, seconds: float) -> None:
        self._call("wait", seconds)

    def say(self, line: str) -> None:
        self._call("say", line)

    def look(self, seat: int | None) -> None:
        self._call("look", seat)

    def count(self) -> int:
        return int(self._call("count"))

    def seated(self, n: int) -> None:
        self._call("seated", n)

    def prepare(self, cards: list[Card]) -> None:
        self._call("prepare", list(cards))

    def show_private(self, seat: int, card: Card) -> bool:
        return bool(self._call("show_private", seat, card))

    def reveal(self, card: Card, line: str) -> None:
        self._call("reveal", card, line)

    def listen(self, seconds: float) -> str:
        return str(self._call("listen", seconds) or "")

    def faces_up(self) -> list[int]:
        return [int(s) for s in self._call("faces_up")]

    def mood(self, name: str) -> None:
        self._call("mood", name)

    def report(self, state: dict[str, Any]) -> None:
        self._call("report", state)

    def quip(self, slot: str, **context: Any) -> None:
        self._call("quip", slot, **context)

    def talk_settings(self) -> dict[str, Any]:
        return self._call("talk_settings")

    def chat(self, situation: str, heard: str = "", **facts: Any) -> str | None:
        line = self._call("chat", situation, heard, **facts)
        return line if isinstance(line, str) else None

    def sleep(self, seconds: float) -> str | None:
        woke = self._call("sleep", seconds)
        return woke if isinstance(woke, str) else None

    # --- the wire -----------------------------------------------------------------

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        self._id += 1
        request = {"session": self.session, "id": self._id, "epoch": self.epoch, "method": method, "args": list(args), "kwargs": kwargs}
        while True:
            answer = self._post("/table/call", request)
            if answer.get("pending"):
                continue  # the call is still running: ask for it again
            if answer.get("ok"):
                return answer.get("result")
            kind = answer.get("kind")
            if kind == "reset":
                raise TableReset(answer.get("epoch"))
            if kind == "replaced":
                raise TableRefused("another referee took the table")
            type_name, message = str(answer.get("type") or "Error"), str(answer.get("message") or "")
            if type_name == "GameStopped":  # a stop said during the deal: the game ends, as at any listen
                raise GameStopped(reset=message == "reset")
            raise RemoteError(type_name, message)

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        data = _dumps(body)
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        give_up = time.monotonic() + self.patience
        delay = 0.25
        failing = False
        while True:
            try:
                if self._conn is None:
                    self._conn = http.client.HTTPConnection(self._host, self._port, timeout=self.timeout)
                self._conn.request("POST", path, body=data, headers=headers)
                res = self._conn.getresponse()
                status, raw = res.status, res.read()
                if res.will_close:
                    self.close()
            except (OSError, http.client.HTTPException) as e:  # refused, dropped, timed out
                self.close()
                if time.monotonic() + delay > give_up:
                    raise TableUnreachable(f"the table at {self.url} did not answer for {self.patience:.0f} s: {e}") from None
                if not failing:
                    self._log(f"referee: the table at {self.url} did not answer ({e}); trying again")
                    failing = True
                time.sleep(delay)
                delay = min(2.0, delay * 2)
                continue
            if failing:
                self._log(f"referee: the table at {self.url} answered again")
            try:
                answer = json.loads(raw or b"null")
            except ValueError:
                answer = raw[:200].decode("utf-8", "replace")
            if status == 401:
                raise TableRefused(f"the table at {self.url} wants its token (--token)")
            if status != 200 or not isinstance(answer, dict):
                raise RemoteError("HTTPError", f"{path} answered {status}: {answer}")
            return answer
