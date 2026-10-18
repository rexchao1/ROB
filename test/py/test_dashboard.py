"""The /dashboard routes (brain/dashboard.py) on a stub host: the state carries the talk's
catalog and status, a setting is checked before it applies, the speaker goes through the
host, and the test call answers even with no talk. Never writes ROB's saved picks."""

import json
import threading
from types import SimpleNamespace

import pytest

from brain import dashboard, settings, talk


class StubHost:
    def __init__(self, talk=None):
        self._lock = threading.Lock()
        self.state = None
        self.feed = []
        self.robot_ok = True
        self.talk = talk
        self.body = SimpleNamespace(speaker="robot")
        self.speakers = []

    def set_speaker(self, speaker):
        self.speakers.append(speaker)
        self.body.speaker = speaker
        settings.update(speaker=speaker)


@pytest.fixture(autouse=True)
def fresh_settings(monkeypatch):
    monkeypatch.setattr(settings, "file", None)
    monkeypatch.setattr(settings, "current", settings.Settings())


def _post(host, path, body):
    return dashboard.handle(host, "POST", path, json.dumps(body).encode())


def test_the_state_carries_the_catalog_the_speakers_and_the_talk_status():
    status = {"provider": "anthropic", "model": "claude-haiku-5-5", "ok": True, "ms": 820}
    code, d = dashboard.handle(StubHost(SimpleNamespace(status=lambda: status)), "GET", "/dashboard/state", b"")
    assert code == 200
    assert d["talk_models"] == talk.MODELS and d["efforts"] == list(talk.EFFORTS)
    assert [s["key"] for s in d["speakers"]] == ["robot", "mac"]
    assert d["talk_status"] == status
    assert d["settings"]["effort"] == "low" and d["settings"]["speaker"] == "robot"
    assert dashboard.handle(StubHost(), "GET", "/dashboard/state", b"")[1]["talk_status"] is None
    json.dumps(d)  # the page reads it as JSON


def test_effort_applies_and_a_wrong_one_is_a_400():
    host = StubHost()
    assert _post(host, "/dashboard/settings", {"effort": "high"}) == (200, settings.snapshot())
    assert settings.current.effort == "high"
    code, answer = _post(host, "/dashboard/settings", {"effort": "nope", "persona": "sarcastic"})
    assert code == 400 and "effort" in answer["error"]
    assert settings.current.effort == "high" and settings.current.persona == "friendly"  # nothing half applied


def test_the_speaker_goes_through_the_host():
    host = StubHost()
    code, snap = _post(host, "/dashboard/settings", {"speaker": "mac"})
    assert code == 200 and snap["speaker"] == "mac"
    assert host.speakers == ["mac"] and host.body.speaker == "mac"
    assert _post(host, "/dashboard/settings", {"speaker": "tv"})[0] == 400
    assert host.speakers == ["mac"]


def test_a_new_provider_drops_a_model_it_cannot_run():
    host = StubHost()
    _post(host, "/dashboard/settings", {"talk_model": "claude-opus-5-5"})
    assert _post(host, "/dashboard/settings", {"talk": "anthropic"})[1]["talk_model"] == "claude-opus-5-5"
    assert _post(host, "/dashboard/settings", {"talk": "gemini"})[1]["talk_model"] is None


def test_the_talk_test_answers_without_a_talk():
    code, answer = dashboard.handle(StubHost(), "POST", "/dashboard/talk-test", b"")
    assert code == 200 and answer["ok"] is False and answer["error"] == "the talk is not set up"
    line = {"ok": True, "provider": "anthropic", "model": "claude-haiku-5-5", "line": "Hi.", "error": None, "ms": 5}
    assert dashboard.handle(StubHost(SimpleNamespace(test=lambda: line)), "POST", "/dashboard/talk-test", b"") == (200, line)
