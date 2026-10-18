"""ROB only saves a pick when its value changes."""

import json
from pathlib import Path

import pytest

from brain import settings


def test_unchanged_picks_never_write(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "current", settings.Settings())
    monkeypatch.setattr(settings, "file", tmp_path / "rob.json")
    settings.update(speaker="robot")
    assert not settings.file.exists()
    settings.update(speaker="mac")
    assert json.loads(settings.file.read_text())["speaker"] == "mac"
    with monkeypatch.context() as patch:
        patch.setattr(Path, "write_text", lambda *a, **kw: pytest.fail("unchanged pick wrote a file"))
        settings.update(speaker="mac")
        settings.update()
    settings.update(speaker="robot")
    assert json.loads(settings.file.read_text())["speaker"] == "robot"


def test_bad_names_do_not_partly_change_picks(monkeypatch):
    monkeypatch.setattr(settings, "current", settings.Settings())
    with pytest.raises(KeyError):
        settings.update(speaker="mac", unknown="x")
    assert settings.current.speaker == "robot"
