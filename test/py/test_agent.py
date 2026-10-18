"""brain/agent.py run_turn: the model's line and tools, each checked before it runs."""

from brain import agent, lines
from brain.facts import Facts
from fake_table import FakeTable


def turn(table, *answers, facts=None, allowed=agent.LOBBY):
    table.acts.extend(answers)
    return agent.run_turn(table, "lobby", "hey rob", facts or {}, allowed)


def test_no_answer_is_none_and_says_nothing():
    table = FakeTable()
    assert turn(table) is None and table.said == []


def test_the_line_is_said_after_the_moves():
    table = FakeTable()
    out = turn(table, {"line": "Evening, folks.", "actions": [{"name": "gesture", "args": {"name": "nod"}}, {"name": "look", "args": {"seat": 2}}]},
               facts={"seats": 3})
    assert out.said == "Evening, folks." and table.said == ["Evening, folks."]
    assert out.ran == ["gesture", "look"] and out.dropped == []
    kinds = [k for _, k, _ in table.log if k in ("gesture", "look", "say")]
    assert kinds == ["gesture", "look", "say"]
    situation, heard, facts = table.act_calls[0]
    assert (situation, heard) == ("lobby", "hey rob") and facts["tools"] == list(agent.LOBBY)


def test_a_bad_argument_is_dropped_never_run():
    table = FakeTable()
    out = turn(table, {"line": "Sure.", "actions": [
        {"name": "look", "args": {"seat": 9}}, {"name": "gesture", "args": {"name": "dance"}},
        {"name": "start_game", "args": {"game": "chess"}}, {"name": "remember", "args": {"fact": "Sam hates mimes"}},
    ]}, facts={"seats": 3})
    assert out.ran == [] and out.game is None and len(out.dropped) == 4
    assert out.dropped[0] == "look: no seat 9" and out.dropped[3] == "remember: no memory here"
    assert not any(k in ("look", "gesture") for _, k, _ in table.log)


def test_a_tool_not_offered_is_dropped():
    table = FakeTable()
    out = turn(table, {"line": "Nice.", "actions": [{"name": "start_game", "args": {"game": "mafia"}}, {"name": "gesture", "args": {"name": "tilt"}}]},
               allowed=agent.GAME)
    assert out.game is None and out.dropped == ["start_game: not offered"] and out.ran == ["gesture"]


def test_start_game_nap_and_remember():
    table = FakeTable()
    memory = Facts()
    out = turn(table, {"line": "Mafia it is.", "actions": [
        {"name": "start_game", "args": {"game": "mafia"}}, {"name": "nap", "args": {}},
        {"name": "remember", "args": {"fact": "Sam hates mimes"}}, {"name": "setting", "args": {"name": "volume", "value": 60}},
    ]}, facts={"memory": memory})
    assert out.game == "mafia" and out.nap and out.said == "Mafia it is."
    assert memory.remembered() == ["Sam hates mimes"] and ("setting", ("volume", 60)) in [(k, v) for _, k, v in table.log]
    assert "memory" not in table.act_calls[0][2]  # the store never travels


def test_an_information_tool_gets_one_follow_up_turn():
    table = FakeTable(counts=[4])
    out = turn(table,
               {"line": "Let me look.", "actions": [{"name": "count_table", "args": {}}, {"name": "rules", "args": {"game": "imposter"}}]},
               {"line": "Four of you. Imposter's perfect.", "actions": [{"name": "look", "args": {"seat": 4}}, {"name": "count_table", "args": {}}]})
    assert table.said == [lines.rules("imposter"), "Four of you. Imposter's perfect."]
    assert out.ran == ["count_table", "rules", "look"] and out.dropped == ["count_table: not offered"]
    follow = table.act_calls[1][2]
    assert "count_table" not in follow["tools"] and follow["seats"] == 4
    assert follow["results"][0].startswith("count_table: you counted 4 people")
    assert len(table.act_calls) == 2
