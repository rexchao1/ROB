"""Every Python test runs with the network refused: a socket may connect to loopback only;
and the shared fixtures: the fake gateway, the brain's Body on it, and a test-mode brain.
GM_REAL_NET=1, set by hand, lifts the guard (as in test/setup/no-network.ts)."""

import ipaddress
import os
import socket
import threading

import pytest


def _loopback(address) -> bool:
    if not isinstance(address, tuple):
        return True  # a Unix socket path
    host = address[0]
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False  # a DNS name: never resolved here


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    if os.environ.get("GM_REAL_NET") == "1":
        return
    connect = socket.socket.connect

    def guarded(self, address):
        if not _loopback(address):
            raise OSError(f"a test tried to reach {address!r} over the network; the lanes never do")
        return connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)


def _start(server):
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}"


@pytest.fixture
def fake():
    """The fake gateway on a free loopback port, in this process (test/fake_gateway.py)."""
    from fake_gateway import FakeGateway

    gateway = FakeGateway().start()
    yield gateway
    gateway.stop()


@pytest.fixture
def body(fake):
    """The brain's Body against the fake gateway."""
    from brain.body import Body, Gateway

    return Body(Gateway(fake.mcp_url), fake.pcm_url)


@pytest.fixture
def brain(fake, tmp_path):
    """A test-mode brain against the fake gateway, serving on a free port: the TestBrain
    (url, host, clock, reset) with its host idle-listening, plus the fake."""
    from brain.__main__ import make_test_brain

    tb = make_test_brain(fake.mcp_url, sets_dir=tmp_path / "sets")
    _start(tb.server)
    tb.clock.settle()
    yield tb
    tb.host.stop()
    tb.server.shutdown()
    tb.server.server_close()
