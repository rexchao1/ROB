"""Only selected facts and public aggregates may survive a referee restart."""
import json
import os

import pytest

from brain.facts import Facts, LIMIT, WIDTH, for_table
from fake_table import FakeTable


def test_limits_deduplication_and_only_changed_sets_write(tmp_path, monkeypatch):
    path = tmp_path / "memory" / "facts.json"
    store = Facts(path)
    replacements = []
    replace = os.replace
    monkeypatch.setattr(os, "replace", lambda src, dst: (replacements.append(dst), replace(src, dst))[1])
    assert store.remember("we  hate Wordle") == "saved"
    assert store.remember(" WE hate wordle ") == "duplicate"
    assert store.remember("x" * (WIDTH + 1)) == "invalid"
    assert len(replacements) == 1
    for n in range(LIMIT - 1):
        assert store.remember(f"group preference {n}") == "saved"
    assert store.remember("one more") == "full"
    store.played("mafia", "village")
    assert len(replacements) == LIMIT
    assert Facts(path).remembered() == store.remembered()
    assert not list(path.parent.glob(".facts-*"))


def test_history_is_one_bounded_entry_per_game_and_filters_private_winners(tmp_path):
    path = tmp_path / "facts.json"
    store = Facts(path)
    store.played("mafia", "village")
    store.played("mafia", "mafia")
    store.played("hotseat", "Alice at seat 4")
    store.played("twenty", "robot")
    store.played("someone's private game", "doctor")
    assert store.size == 3
    assert "mafia: played 2; village won 1; mafia won 1." in store.remembered()
    assert "hotseat: played 1." in store.remembered()
    assert "twenty: played 1; robot won 1." in store.remembered()
    assert "Alice" not in path.read_text() and "doctor" not in path.read_text()
    assert all(len(f) <= WIDTH for f in store.remembered())
    assert Facts(path).remembered() == store.remembered()


def test_forget_last_selected_fact_and_everything(tmp_path):
    store = Facts(tmp_path / "facts.json")
    store.remember("we love games")
    store.played("mafia", "mafia")
    assert store.forget_last()
    assert store.remembered() == ["mafia: played 1; mafia won 1."]
    assert not store.forget_last()
    assert store.forget_all()
    assert not store.forget_all()
    assert Facts(store.path).remembered() == []


def test_atomic_failure_keeps_previous_memory_and_cleans_temporary(tmp_path, monkeypatch):
    path = tmp_path / "facts.json"
    store = Facts(path)
    store.remember("we love games")
    before = path.read_bytes()
    def fail(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        store.remember("we hate Wordle")
    assert store.remembered() == ["we love games"]
    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".facts-*"))


@pytest.mark.parametrize("content", ["no json", "[]", '{"facts": null}', '{"facts": [5]}', "x" * 32769])
def test_corrupt_memory_is_safe(tmp_path, content):
    path = tmp_path / "facts.json"
    path.write_text(content)
    assert Facts(path).remembered() == []


def test_load_validates_limits_and_filters_unknown_history(tmp_path):
    path = tmp_path / "facts.json"
    path.write_text(json.dumps({"facts": ["we like games", "WE like games", "x" * 101],
                                "history": {"hotseat": {"played": 2, "wins": {"Alice": 2}},
                                            "private": {"played": 3}}}))
    assert Facts(path).remembered() == ["we like games", "hotseat: played 2."]


def test_mac_store_is_per_table_and_ram_only(monkeypatch):
    monkeypatch.setattr(os, "replace", lambda *args: pytest.fail("RAM memory wrote a file"))
    table = FakeTable()
    for_table(table).remember("we love games")
    assert for_table(table).remembered() == ["we love games"]
    assert for_table(FakeTable()).remembered() == []
    assert for_table(table).path is None


@pytest.mark.parametrize("fact", ["player two is mafia", "my name is Rex", "I am the doctor"])
def test_memory_rejects_identity_and_private_assignments(fact):
    assert Facts().remember(fact) == "invalid"
