"""The talk's request shapes, error reporting and Test button (brain/talk.py), with the
HTTP stubbed: no call leaves the process."""

import io
import json
import urllib.error

import pytest

from brain import settings, talk


@pytest.fixture
def anthropic(monkeypatch):
    """Settings on Anthropic's default model at low effort, a fake key, .env.local unread."""
    monkeypatch.setattr(settings, "current", settings.Settings(talk="anthropic"))
    monkeypatch.setattr(talk, "_env_loaded", True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-123456")


@pytest.mark.parametrize(
    ("model", "thinking"),
    [
        ("claude-haiku-5-5", {"type": "disabled"}),
        ("claude-sonnet-5-5", {"type": "between_tools"}),
        ("claude-opus-5-5", None),  # thinking cannot be turned off: it gets room instead
    ],
)
def test_claude_5_5_bodies_send_no_temperature_and_turn_thinking_off_where_allowed(model, thinking):
    body = talk.anthropic_body(model, "low", "system", "prompt", 80, 0.9)
    assert "temperature" not in body
    assert body["output_config"] == {"effort": "low"}
    assert body.get("thinking") == thinking
    assert body["max_tokens"] == (80 if thinking else 80 + 1024)
    at_max = talk.anthropic_body(model, "max", "system", "prompt", 80, 0.9)
    assert "thinking" not in at_max and at_max["max_tokens"] >= 1024  # no model turns it off at max


def test_an_http_400_ends_in_none_and_the_message_reaches_the_log_and_status(anthropic, monkeypatch):
    message = "temperature: this model takes only the default"

    def refuse(req, timeout):
        sent = json.loads(req.data)
        assert "temperature" not in sent and timeout >= 6
        body = io.BytesIO(json.dumps({"type": "error", "error": {"type": "invalid_request_error", "message": message}}).encode())
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, body)

    monkeypatch.setattr(talk.urllib.request, "urlopen", refuse)
    logs: list[str] = []
    t = talk.Talk(log=logs.append)
    assert t.status()["ok"] is None and t.status()["key_set"] is True
    assert t.reply("welcome", "hi ROB", {}) is None
    assert f"talk: anthropic answered HTTP 400: {message}" in logs
    status = t.status()
    assert status["ok"] is False and status["error"] == f"HTTP 400: {message}" and status["ms"] is not None
    assert not any("sk-ant-test" in line for line in logs)
    settings.current.talk_model = "claude-sonnet-5-5"  # another choice: not tried yet
    assert t.status()["ok"] is None


def test_the_test_button_answers_a_line_or_a_plain_reason(anthropic, monkeypatch):
    sent = []

    def answer(self, url, body, headers, timeout=None):
        sent.append(body)
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Evening, table. Ready to lose?"}]}

    monkeypatch.setattr(talk.Talk, "_post", answer)
    t = talk.Talk(log=lambda msg: None)
    result = t.test()
    assert result["ok"] is True and result["line"] == "Evening, table. Ready to lose?" and result["error"] is None
    assert result["provider"] == "anthropic" and result["model"] == "claude-haiku-5-5"
    assert sent[0]["messages"][0]["content"] == talk.TEST_PROMPT and t.status()["ok"] is True

    monkeypatch.delenv("ANTHROPIC_API_KEY")
    result = t.test()
    assert result == {"ok": False, "provider": "anthropic", "model": "claude-haiku-5-5", "line": None, "error": "no ANTHROPIC_API_KEY set", "ms": 0}
    assert len(sent) == 1 and t.status()["key_set"] is False
    settings.current.talk = "off"
    assert t.test()["error"] == "the talk is off"


def test_load_ignores_a_saved_value_of_the_wrong_type(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "current", settings.Settings())
    monkeypatch.setattr(settings, "file", None)
    saved = tmp_path / "rob.json"
    saved.write_text(json.dumps({"persona": "pirate", "effort": 3, "speaker": "mac", "talk": "skynet", "talk_model": None}))
    settings.load(saved)
    s = settings.current
    assert (s.persona, s.effort, s.speaker, s.talk, s.talk_model) == ("pirate", "low", "mac", "anthropic", None)
