"""The API keys: set from the dashboard, written to .env owner-only, never read back.
No route answers a value; a page from another site cannot write one."""

import json
import os
import stat
import urllib.error
import urllib.request

import pytest
from calls import call

from brain import keys
from brain.keys import Keys, KeysError

SECRET = "sk-test-0123456789abcdef"


def test_a_test_brain_reports_set_or_not_and_never_the_value(brain):
    status, got = call(brain.url, "GET", "/dash/api/keys")
    assert status == 200 and {k["key"] for k in got["keys"]} == {k.key for k in keys.KEYS}
    assert not any(k["set"] for k in got["keys"])
    status, got = call(brain.url, "POST", "/dash/api/keys", {"ELEVENLABS_API_KEY": SECRET})
    assert status == 200 and SECRET not in json.dumps(got)
    assert next(k for k in got["keys"] if k["key"] == "ELEVENLABS_API_KEY")["set"] is True
    for path in ("/dash/api/keys", "/dash/api/events?since=0", "/dash/api/settings", "/dash/api/state"):
        assert SECRET not in json.dumps(call(brain.url, "GET", path)[1])
    assert os.environ.get("ELEVENLABS_API_KEY") != SECRET  # a test brain keeps keys in memory
    status, got = call(brain.url, "POST", "/dash/api/keys", {"ELEVENLABS_API_KEY": None})
    assert next(k for k in got["keys"] if k["key"] == "ELEVENLABS_API_KEY")["set"] is False


def test_bad_keys_and_values_are_refused(brain):
    assert call(brain.url, "POST", "/dash/api/keys", {"PATH": "/tmp"})[0] == 400
    assert call(brain.url, "POST", "/dash/api/keys", {"STACKCHAN_TOKEN": "two words"})[0] == 400
    assert call(brain.url, "POST", "/dash/api/keys", {"STACKCHAN_TOKEN": "a\nB=c"})[0] == 400


def test_another_site_cannot_write_a_key(brain):
    req = urllib.request.Request(
        brain.url + "/dash/api/keys", data=json.dumps({"STACKCHAN_TOKEN": "x"}).encode(), method="POST",
        headers={"Content-Type": "text/plain", "Origin": "https://evil.example"},
    )
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=5)
    assert e.value.code == 403
    origin = brain.url.removesuffix("/")
    req.headers["Origin"] = origin  # the dashboard's own page
    with urllib.request.urlopen(req, timeout=5) as res:
        assert res.status == 200


def test_the_gateway_token_applies_at_once(brain):
    call(brain.url, "POST", "/dash/api/keys", {"STACKCHAN_TOKEN": "tok123"})
    assert brain.host.body.token == "tok123" and brain.host.body.gateway.token == "tok123"
    call(brain.url, "POST", "/dash/api/keys", {"STACKCHAN_TOKEN": None})
    assert brain.host.body.token is None and brain.host.body.gateway.token is None


def test_the_env_file_keeps_other_lines_is_owner_only_and_fills_in_the_environment(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# mine\nOTHER=1\nSTACKCHAN_TOKEN=old\n")
    for k in keys.KEYS:
        monkeypatch.delenv(k.key, raising=False)
    k = Keys(env)
    k.set({"STACKCHAN_TOKEN": "new", "ELEVENLABS_VOICE_ID": "voice1"})
    assert env.read_text() == "# mine\nOTHER=1\nSTACKCHAN_TOKEN=new\nELEVENLABS_VOICE_ID=voice1\n"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert os.environ["STACKCHAN_TOKEN"] == "new"
    k.set({"STACKCHAN_TOKEN": None})
    assert "STACKCHAN_TOKEN" not in env.read_text() and "STACKCHAN_TOKEN" not in os.environ
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "from-shell")
    keys.load_env(env)
    assert os.environ["ELEVENLABS_VOICE_ID"] == "from-shell"  # the environment wins
    with pytest.raises(KeysError):
        k.set({"HOME": "x"})
