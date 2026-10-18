"""Kept-alive HTTPS for the brain's cloud calls: the talk's model (brain/talk.py) and the
ElevenLabs voice (brain/voice.py).

urllib opened a new connection for every call: a lookup, a TCP connect and a TLS
handshake, 70 to 260 ms over the iPhone's hotspot (measured October 2026), paid twice a
reply, once for the line and once for its voice, and now and then far more (one new
connection in 14 hung 10 s on its TCP connect). Here each host keeps its connection
open between calls, so a call costs only the request and the provider's own time.

  request()  one call over the host's kept connection. An HTTP error raises
             urllib.error.HTTPError (its body readable) and a connection that will not
             open raises urllib.error.URLError, as urllib's urlopen does, so the callers
             handle errors as before. A kept connection the server has closed is noticed
             before the call, or retried once on a fresh one.
  warm()     open a host's connection ahead of its first call with a cheap GET, or
             freshen one that has sat idle for REWARM seconds, before the server drops it

New connections try every address of the host side by side, IPv6 and IPv4 taking turns,
the next one started when the last has not answered in a quarter second, so a dead IPv6
path on the phone's link costs 250 ms rather than the whole timeout.
"""

from __future__ import annotations

import http.client
import io
import os
import select
import socket
import ssl
import threading
import time
import urllib.error
from collections.abc import Callable
from typing import Any, Protocol
from urllib.parse import urlsplit

ATTEMPT_DELAY = 0.25  # seconds before the next address is tried alongside the last (RFC 8305)
KEEP = 2  # idle connections kept per host; a call while another is out opens a second
MAX_IDLE = 300.0  # a connection idle this long is closed, not reused: Anthropic's closes at 400 s idle (ElevenLabs' outlived 600 s)
REWARM = 180.0  # warm() freshens a host's connection once it has sat idle this long, well before either closes
WARM_TIMEOUT = 5.0
STALE = (  # a kept connection the server or the network dropped while it sat idle
    http.client.RemoteDisconnected,
    http.client.CannotSendRequest,
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
    ssl.SSLZeroReturnError,
    ssl.SSLEOFError,
)

_context: ssl.SSLContext | None = None


def _tls() -> ssl.SSLContext:
    """One TLS context for every connection (urllib built and loaded a new one per call)."""
    global _context
    if _context is None:
        _context = ssl.create_default_context()
    return _context


def _interleave(infos: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """getaddrinfo's answers with the families taking turns, the first answer's family
    first (RFC 8305), so a dead family never holds up the other for long."""
    if not infos:
        return []
    first = [i for i in infos if i[0] == infos[0][0]]
    other = [i for i in infos if i[0] != infos[0][0]]
    out: list[tuple[Any, ...]] = []
    for n in range(max(len(first), len(other))):
        out += first[n : n + 1] + other[n : n + 1]
    return out


def open_socket(host: str, port: int, timeout: float, delay: float = ATTEMPT_DELAY) -> socket.socket:
    """A connected TCP socket to host:port, with TCP keepalive on so the phone's NAT keeps
    an idle connection and a dead one is noticed. Every address the lookup gives is tried,
    IPv6 and IPv4 taking turns: the next starts when the last has not connected within
    delay seconds or has failed, and the first to connect wins. Raises the last
    address's error, or TimeoutError when none connects within timeout."""
    addrs = _interleave(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
    deadline = time.monotonic() + timeout
    pending: dict[socket.socket, Any] = {}
    error: OSError | None = None
    next_at = 0.0
    try:
        while addrs or pending:
            now = time.monotonic()
            if now >= deadline:
                raise TimeoutError(f"no connection to {host}:{port} in {timeout:g} s")
            if addrs and (now >= next_at or not pending):
                family, kind, proto, _, address = addrs.pop(0)
                s = socket.socket(family, kind, proto)
                s.setblocking(False)
                try:
                    s.connect(address)
                except BlockingIOError:
                    pending[s] = address
                    next_at = now + delay
                except OSError as e:  # refused at once: the next address now
                    s.close()
                    error = e
                else:
                    return _ready(s, timeout)  # connected at once (loopback)
                continue
            wait = (min(deadline, next_at) if addrs else deadline) - now
            _, ready, _ = select.select([], list(pending), [], max(0.0, wait))
            for s in ready:
                del pending[s]
                code = s.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if code == 0:
                    return _ready(s, timeout)
                s.close()
                error = OSError(code, os.strerror(code))
                next_at = 0.0  # a failed attempt starts the next one at once
        raise error or OSError(f"no address for {host}")
    finally:
        for s in pending:
            s.close()


def _ready(s: socket.socket, timeout: float) -> socket.socket:
    s.setblocking(True)
    s.settimeout(timeout)
    for level, option, value in (
        (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
        (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
        (socket.IPPROTO_TCP, getattr(socket, "TCP_KEEPALIVE", getattr(socket, "TCP_KEEPIDLE", None)), 30),
        (socket.IPPROTO_TCP, getattr(socket, "TCP_KEEPINTVL", None), 10),
        (socket.IPPROTO_TCP, getattr(socket, "TCP_KEEPCNT", None), 3),
    ):
        if option is not None:
            try:
                s.setsockopt(level, option, value)
            except OSError:
                pass
    return s


class _HTTPS(http.client.HTTPSConnection):
    def connect(self) -> None:
        sock = open_socket(self.host, self.port, self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


class _HTTP(http.client.HTTPConnection):
    def connect(self) -> None:
        self.sock = open_socket(self.host, self.port, self.timeout)


class Connection(Protocol):  # what Client needs of http.client's connections (tests pass a fake)
    sock: Any
    timeout: float | None

    def connect(self) -> None: ...
    def request(self, method: str, url: str, body: bytes | None = None, headers: dict[str, str] = ...) -> None: ...
    def getresponse(self) -> Any: ...
    def close(self) -> None: ...


def _open(scheme: str, host: str, port: int, timeout: float) -> Connection:
    if scheme == "https":
        return _HTTPS(host, port, timeout=timeout, context=_tls())
    return _HTTP(host, port, timeout=timeout)


def _where(url: str) -> tuple[tuple[str, str, int], str]:
    """((scheme, host, port), path with its query) of a URL."""
    parts = urlsplit(url)
    scheme = parts.scheme or "https"
    key = (scheme, parts.hostname or "", parts.port or (443 if scheme == "https" else 80))
    return key, (parts.path or "/") + (f"?{parts.query}" if parts.query else "")


def _exchange(conn: Connection, method: str, path: str, body: bytes | None, headers: dict[str, str]) -> tuple[Any, bytes]:
    """(response, its whole body) of one call; any failure closes the connection."""
    try:
        conn.request(method, path, body=body, headers=headers)
        res = conn.getresponse()
        return res, res.read()
    except BaseException:
        conn.close()
        raise


def _alive(conn: Connection) -> bool:
    """An idle connection is never readable: readable means the server closed it."""
    sock = conn.sock
    if sock is None:
        return False
    try:
        return not select.select([sock], [], [], 0)[0]
    except (OSError, ValueError, TypeError):
        return False


class Client:
    """Kept connections, per (scheme, host, port), for any thread: a call takes an idle
    one (or opens one), and puts it back when the answer is read."""

    def __init__(self, connection: Callable[[str, str, int, float], Connection] = _open) -> None:
        self._connection = connection
        self._lock = threading.Lock()
        self._idle: dict[tuple[str, str, int], list[tuple[Connection, float]]] = {}
        self._used: dict[tuple[str, str, int], float] = {}  # when each host last answered

    def request(
        self, method: str, url: str, body: bytes | None = None, headers: dict[str, str] | None = None, timeout: float = 10.0
    ) -> bytes:
        """The answer's body to one call. timeout bounds the connect and each wait for the
        server, as urlopen's does. HTTP 400 and up raise urllib.error.HTTPError."""
        key, path = _where(url)
        conn, reused = self._take(key, timeout)
        try:
            res, data = _exchange(conn, method, path, body, headers or {})
        except STALE:
            if not reused:
                raise
            conn = self._new(key, timeout)  # dropped while it sat idle: once more, on a fresh connection
            res, data = _exchange(conn, method, path, body, headers or {})
        self._give(key, conn)
        if res.status >= 400:
            raise urllib.error.HTTPError(url, res.status, res.reason, res.headers, io.BytesIO(data))
        return data

    def warm(self, url: str, headers: dict[str, str] | None = None, timeout: float = WARM_TIMEOUT) -> int | None:
        """GET url to open its host's connection, unless the host answered within REWARM
        seconds; the ms it took (0 when skipped), or None when it could not connect. An
        HTTP error still leaves the connection open, so it counts as warm."""
        key, _ = _where(url)
        with self._lock:
            if time.monotonic() - self._used.get(key, -1e9) < REWARM and self._idle.get(key):
                return 0
        start = time.monotonic()
        try:
            self.request("GET", url, headers=headers, timeout=timeout)
        except urllib.error.HTTPError:
            pass
        except (OSError, http.client.HTTPException):
            return None
        return int((time.monotonic() - start) * 1000)

    def close(self) -> None:
        with self._lock:
            idle, self._idle = self._idle, {}
        for conns in idle.values():
            for conn, _ in conns:
                conn.close()

    def _take(self, key: tuple[str, str, int], timeout: float) -> tuple[Connection, bool]:
        """(connection, reused): a kept one still open, else a new one, connected."""
        with self._lock:
            idle = self._idle.get(key, [])
            while idle:
                conn, since = idle.pop()
                if time.monotonic() - since < MAX_IDLE and _alive(conn):
                    conn.timeout = timeout
                    conn.sock.settimeout(timeout)
                    return conn, True
                conn.close()
        return self._new(key, timeout), False

    def _new(self, key: tuple[str, str, int], timeout: float) -> Connection:
        """A new connection, connected; one that will not open is urllib.error.URLError."""
        conn = self._connection(*key, timeout)
        try:
            conn.connect()
        except OSError as e:
            conn.close()
            raise urllib.error.URLError(e) from e
        return conn

    def _give(self, key: tuple[str, str, int], conn: Connection) -> None:
        """Keep a connection whose answer is read, unless the server said it closes."""
        now = time.monotonic()
        with self._lock:
            self._used[key] = now
            idle = self._idle.setdefault(key, [])
            if conn.sock is not None and len(idle) < KEEP:
                idle.append((conn, now))
                return
        conn.close()


client = Client()  # the brain's one set of kept connections


def request(method: str, url: str, body: bytes | None = None, headers: dict[str, str] | None = None, timeout: float = 10.0) -> bytes:
    return client.request(method, url, body, headers, timeout)


def warm(url: str, headers: dict[str, str] | None = None, timeout: float = WARM_TIMEOUT) -> int | None:
    return client.warm(url, headers, timeout)
