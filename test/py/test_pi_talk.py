"""The Pi follows live Mac choices and falls back without repeated offline waits."""
import urllib.error

import pytest

from brain import settings
from brain.pi_talk import PiTable, PiTalk


@pytest.fixture(autouse=True)
def picks(monkeypatch):
    monkeypatch.setattr(settings, "current", settings.Settings())
    monkeypatch.setattr(settings, "file", None)


class Remote:
    def __init__(self):
        self.choices = {"talk": "anthropic", "talk_model": "claude-haiku-5-5", "effort": "low", "persona": "host"}
        self.chats = []
        self.quips = []
        self.said = []

    def talk_settings(self):
        return dict(self.choices)

    def hello(self):
        return {"epoch": "one", "talk_settings": self.talk_settings()}

    def chat(self, situation, heard, **facts):
        self.chats.append((situation, heard, facts))
        return "Mac reply."

    def quip(self, slot, **context):
        self.quips.append((slot, context))

    def say(self, line):
        self.said.append(line)


class TalkStub:
    def __init__(self):
        self.prepared = 0
        self.replies = []
        self.line = "Pi reply."

    def active(self):
        return settings.current.talk != "off"

    def prepare(self):
        self.prepared += 1

    def reply(self, situation, heard, facts):
        self.replies.append((situation, heard, facts, settings.snapshot()))
        return self.line

    def quip(self, slot, context, recap=None):
        return self.line


def test_choices_follow_dashboard_mid_game_without_writing_settings(tmp_path, monkeypatch):
    path = tmp_path / "must-not-exist.json"
    monkeypatch.setattr(settings, "file", path)
    remote, talk = Remote(), TalkStub()
    table = PiTable(remote, talk)
    assert table.hello()["epoch"] == "one"
    assert talk.prepared == 1
    assert table.chat("welcome", "hello", remembered=["we hate Wordle"]) == "Pi reply."
    remote.choices.update(talk="gemini", talk_model="gemini-2.5-flash", effort="high", persona="spooky")
    table.chat("welcome", "how are you")
    assert {k: talk.replies[-1][3][k] for k in settings.TALK} == remote.choices
    assert not path.exists()
    assert not remote.chats


def test_none_off_and_local_quip_fall_back_to_mac():
    remote, talk = Remote(), TalkStub()
    table = PiTable(remote, talk)
    talk.line = None
    assert table.chat("welcome", "hello", remembered=["we like games"]) == "Mac reply."
    assert remote.chats[-1][2] == {"remembered": ["we like games"]}
    table.quip("win", game="mafia")
    assert remote.quips == [("win", {"game": "mafia"})]
    talk.line = "Pi quip."
    table.quip("win", game="mafia")
    assert remote.said == ["Pi quip."]
    remote.choices["talk"] = "off"
    assert table.chat("welcome", "hello") == "Mac reply."
    assert len(talk.replies) == 1


def test_offline_failure_blocks_preparation_and_calls_for_one_minute(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("brain.pi_talk.time.monotonic", lambda: now[0])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    talk = PiTalk(log=lambda message: None)
    calls = []
    def unavailable(*args):
        calls.append(1)
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(talk, "_anthropic", unavailable)
    assert talk.reply("welcome", "hello", {}) is None
    assert talk.unavailable_until == 160.0
    for _ in range(3):
        talk.prepare()
        assert talk.reply("welcome", "hello", {}) is None
    assert len(calls) == 1
    now[0] = 160.1
    assert talk.active()
    talk.reply("welcome", "hello", {})
    assert len(calls) == 2


def test_no_key_falls_back_without_local_requests(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    remote = Remote()
    talk = PiTalk(log=lambda message: None)
    monkeypatch.setattr(talk, "_post", lambda *args: pytest.fail("missing key made a request"))
    table = PiTable(remote, talk)
    assert table.chat("welcome", "hello") == "Mac reply."
