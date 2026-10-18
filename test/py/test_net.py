"""The kept-alive HTTPS client (brain/net.py): connections kept and reused, a dropped one
noticed or retried once, HTTP errors raised as urllib's, and the side-by-side connect.
Fake connections over a local socket pair and loopback listeners: no call leaves the
machine."""

import email.message
import http.client
import socket
import urllib.error

import pytest

from brain import net


class Answer:
    def __init__(self, status, body):
        self.status, self.reason, self.body = status, http.client.responses.get(status, ""), body
        self.headers = email.message.Message()

    def read(self):
        return self.body


class Server:
    """Hands out fake connections; each request is answered by the next of `answers`,
    (status, body) or an exception to raise."""

    def __init__(self, *answers, refuse=False):
        self.answers, self.refuse = list(answers), refuse
        self.conns, self.sent = [], []

    def __call__(self, scheme, host, port, timeout):
        conn = Conn(self, (scheme, host, port), timeout)
        self.conns.append(conn)
        return conn


class Conn:
    def __init__(self, server, where, timeout):
        self.server, self.where, self.timeout = server, where, timeout
        self.sock = self.peer = None

    def connect(self):
        if self.server.refuse:
            raise ConnectionRefusedError(61, "Connection refused")
        self.sock, self.peer = socket.socketpair()

    def request(self, method, url, body=None, headers=None):
        self.server.sent.append((self, method, url, body, headers))

    def getresponse(self):
        answer = self.server.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return Answer(*answer)

    def close(self):
        for s in (self.sock, self.peer):
            if s is not None:
                s.close()
        self.sock = self.peer = None


@pytest.fixture
def client():
    made = []

    def make(server):
        c = net.Client(connection=server)
        made.append(c)
        return c

    yield make
    for c in made:
        c.close()


def test_calls_to_one_host_share_one_connection(client):
    server = Server((200, b'{"a": 1}'), (200, b"pcm"))
    c = client(server)
    assert c.request("POST", "https://api.example.com/v1/messages", b"{}", {"x": "y"}, timeout=6) == b'{"a": 1}'
    assert c.request("GET", "https://api.example.com/v1/models?limit=1", timeout=3) == b"pcm"
    assert len(server.conns) == 1 and server.conns[0].where == ("https", "api.example.com", 443)
    assert [(m, u) for _, m, u, _, _ in server.sent] == [("POST", "/v1/messages"), ("GET", "/v1/models?limit=1")]
    assert server.conns[0].timeout == 3 and server.conns[0].sock.gettimeout() == 3  # each call's own timeout


def test_an_http_error_raises_urllibs_with_the_body_and_keeps_the_connection(client):
    server = Server((400, b'{"error": {"message": "no temperature"}}'), (200, b"ok"))
    c = client(server)
    with pytest.raises(urllib.error.HTTPError) as e:
        c.request("POST", "https://api.example.com/v1/messages", b"{}")
    assert e.value.code == 400 and b"no temperature" in e.value.read()
    assert c.request("POST", "https://api.example.com/v1/messages", b"{}") == b"ok"
    assert len(server.conns) == 1


def test_a_connection_the_server_closed_while_idle_is_not_reused(client):
    server = Server((200, b"one"), (200, b"two"))
    c = client(server)
    c.request("GET", "https://api.example.com/")
    server.conns[0].peer.close()  # the server hangs up: the idle socket reads as closed
    assert c.request("GET", "https://api.example.com/") == b"two"
    assert len(server.conns) == 2 and len(server.sent) == 2  # noticed before sending, nothing retried


def test_a_kept_connection_that_fails_stale_is_retried_once_on_a_fresh_one(client):
    server = Server((200, b"one"), http.client.RemoteDisconnected("closed"), (200, b"again"))
    c = client(server)
    c.request("GET", "https://api.example.com/")
    assert c.request("POST", "https://api.example.com/v1/messages", b"{}") == b"again"
    assert len(server.conns) == 2 and server.conns[0].sock is None  # the stale one closed

    fresh = Server(ConnectionResetError(54, "reset"))  # a new connection failing is not retried
    with pytest.raises(ConnectionResetError):
        client(fresh).request("GET", "https://api.example.com/")
    assert len(fresh.conns) == 1


def test_a_connection_that_will_not_open_is_a_url_error(client):
    with pytest.raises(urllib.error.URLError) as e:
        client(Server(refuse=True)).request("GET", "https://api.example.com/")
    assert isinstance(e.value.reason, ConnectionRefusedError)


def test_warm_opens_the_connection_once_and_counts_an_http_error(client, monkeypatch):
    server = Server((401, b"no key"), (200, b"line"))
    c = client(server)
    assert c.warm("https://api.example.com/v1/models") is not None
    assert c.warm("https://api.example.com/v1/models") == 0  # warm already: nothing sent
    assert c.request("POST", "https://api.example.com/v1/messages", b"{}") == b"line"
    assert len(server.conns) == 1 and len(server.sent) == 2
    monkeypatch.setattr(net, "REWARM", 0.0)  # idle long enough: freshened with another GET
    server.answers.append((200, b"[]"))
    assert c.warm("https://api.example.com/v1/models") is not None and len(server.sent) == 3
    assert client(Server(refuse=True)).warm("https://api.example.com/v1/models") is None


def test_families_take_turns_the_first_answers_first():
    v6 = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", (f"2001:db8::{n}", 443, 0, 0)) for n in (1, 2)]
    v4 = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (f"192.0.2.{n}", 443)) for n in (1, 2, 3)]
    order = [info[4][0] for info in net._interleave(v6 + v4)]  # noqa: SLF001
    assert order == ["2001:db8::1", "192.0.2.1", "2001:db8::2", "192.0.2.2", "192.0.2.3"]


def _listener():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(4)
    return s


def test_a_dead_address_hands_on_to_the_next(monkeypatch):
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    dead_port = closed.getsockname()[1]
    closed.close()  # nobody listens there: refused
    live = _listener()
    infos = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443)),  # off the machine: the test guard refuses it at once
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", dead_port)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", live.getsockname()),
    ]
    monkeypatch.setattr(net.socket, "getaddrinfo", lambda *a, **k: infos)
    s = net.open_socket("api.example.com", 443, timeout=2, delay=0.05)
    try:
        assert s.getpeername() == live.getsockname() and s.gettimeout() == 2
        assert s.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE)
    finally:
        s.close()
        live.close()
    monkeypatch.setattr(net.socket, "getaddrinfo", lambda *a, **k: infos[:2])
    with pytest.raises(OSError):
        net.open_socket("api.example.com", 443, timeout=2, delay=0.05)
