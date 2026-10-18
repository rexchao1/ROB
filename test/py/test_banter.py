"""brain/banter.py against a fake Ollama on loopback: a clean quip comes back; anything
that names a player, holds a number, runs long, fails or is late comes back as None."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from brain.banter import Banter, NoBanter, clean


class FakeOllama:
    def __init__(self) -> None:
        self.answer: object = {"response": "The night is young and full of secrets."}
        self.status = 200
        self.delay = 0.0
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: ANN002
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append({"path": self.path, **body})
                time.sleep(outer.delay)
                data = outer.answer if isinstance(outer.answer, bytes) else json.dumps(outer.answer).encode()
                self.send_response(outer.status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def ollama():
    fake = FakeOllama()
    yield fake
    fake.close()


def test_a_quip(ollama):
    b = Banter(ollama.url, model="tiny", timeout=2.0)
    assert b.line("night", {"game": "mafia", "seat": 4}) == "The night is young and full of secrets."
    req = ollama.requests[0]
    assert req["path"] == "/api/generate" and req["model"] == "tiny" and req["stream"] is False
    assert "Night falls" in req["prompt"]
    assert '"seat"' not in req["prompt"]  # numbers never go to the model


@pytest.mark.parametrize(
    "said",
    [
        "Player three looks guilty to me.",
        "Seat four, I'm watching you.",
        "Only 2 of you left.",
        "Two of you are lying.",
        "This is a very long quip that just keeps going on and on past the limit we set.",
        "",
    ],
)
def test_bad_quips_are_dropped(ollama, said):
    ollama.answer = {"response": said}
    assert Banter(ollama.url).line("vote", {}) is None


def test_failures_are_silent(ollama):
    b = Banter(ollama.url, timeout=0.3)
    ollama.status = 500
    assert b.line("vote", {}) is None
    ollama.status = 200
    ollama.answer = b"not json"
    assert b.line("vote", {}) is None
    ollama.answer = {"nope": 1}
    assert b.line("vote", {}) is None
    ollama.answer = {"response": "Fine."}
    ollama.delay = 0.6
    assert b.line("vote", {}) is None  # too late
    assert Banter("http://127.0.0.1:9", timeout=0.3).line("vote", {}) is None  # nobody home


def test_clean():
    assert clean('"Ooh, the plot thickens."\nmore text') == "Ooh, the plot thickens."
    assert clean("*grins* Sleep tight, everyone.") == "Sleep tight, everyone."
    assert clean("Someone is nervous.") == "Someone is nervous."
    assert clean("No one saw a thing.") is None  # "one" is a number word; dropping a good line is fine


def test_no_banter():
    assert NoBanter().line("night", {}) is None
