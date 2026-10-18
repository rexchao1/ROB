"""The welcome (brain/games/welcome.py): it greets and listens straight away, takes a
headcount at its word, and sweeps the table only when asked."""

import random

from fake_table import FakeTable

from brain import agent, lines
from brain.games.common import Options
from brain.games.welcome import Choice, Welcome


def _welcome(table):
    return Welcome(table, random.Random(3), Options(), listen_window=4.0)


def _kinds(table):
    return [kind for _, kind, _ in table.log]


def test_the_greeting_asks_and_listens_with_no_sweep():
    table = FakeTable().hear("let's play imposter")
    w = _welcome(table)
    w.greet()
    choice = w.converse()
    assert table.said[0] in lines.GREETINGS and table.said[1] == lines.games_menu()
    assert "count" not in _kinds(table)
    assert choice == Choice("imposter", "let's play imposter", None, False)


def test_a_headcount_is_taken_at_its_word_and_gets_a_suggestion():
    table = FakeTable().hear("there are three of us", "sure")
    w = _welcome(table)
    w.greet()
    choice = w.converse()
    assert "count" not in _kinds(table)
    assert ("seated", 3) in [(k, v) for _, k, v in table.log]
    assert "Imposter" in table.said[1]
    assert choice == Choice("imposter", "sure", 3, False)


def test_just_me_is_one_player():
    table = FakeTable().hear("just me")
    w = _welcome(table)
    w.greet()
    assert w.converse() is None  # silence after: nudges, then a nap
    assert w.seats == 1 and lines.suggested(1) == w.suggestion


def test_count_us_sweeps_says_hello_and_suggests():
    table = FakeTable(seats=5).hear("count us", "let's play mafia")
    w = _welcome(table)
    w.greet()
    choice = w.converse()
    assert table.said[2] in lines.LOOKING  # after the greeting and the games
    assert "count" in _kinds(table)
    assert any(line.startswith(("Hi,", "You're")) for line in table.said)
    assert choice == Choice("mafia", "let's play mafia", 5, True)


def test_what_should_we_play_with_no_count_asks_how_many():
    table = FakeTable().hear("what should we play", "four of us")
    w = _welcome(table)
    w.greet()
    assert w.converse() is None
    assert lines.HOW_MANY in table.said
    assert w.seats == 4


def test_seeing_nobody_never_loops_and_a_number_is_taken():
    table = FakeTable(seats=0).hear("count us", "there are four of us", "sure")
    w = _welcome(table)
    w.greet()
    choice = w.converse()
    assert _kinds(table).count("count") == 1
    assert choice == Choice("imposter", "sure", 4, False)


def test_a_number_said_after_the_sweep_wins_with_no_second_look():
    table = FakeTable(counts=[3]).hear("count us", "five of us", "sure")
    w = _welcome(table)
    w.greet()
    choice = w.converse()
    assert _kinds(table).count("count") == 1  # the sweep asked for, and no second look
    assert choice is not None and choice.counted == 5


class ChattyTable(FakeTable):
    """A FakeTable whose talk model answers from `lines` by situation (None: no line),
    and keeps every call's (situation, heard, facts)."""

    def __init__(self, **lines_by_situation):
        super().__init__()
        self.lines = {k: list(v) for k, v in lines_by_situation.items()}
        self.calls = []

    def chat(self, situation, heard="", **facts):
        self.calls.append((situation, heard, facts))
        queue = self.lines.get(situation.replace(".", "_"))
        return queue.pop(0) if queue else None


def test_the_greeting_is_scripted_then_an_open_question_when_the_talk_is_on():
    table = ChattyTable(welcome_greeting=["Evening, legends! I'm ROB, so glad you came."])
    table.talk_settings = lambda: {"talk": "anthropic"}
    w = _welcome(table)
    w.greet()
    assert table.said[0] in lines.GREETINGS and table.said[1] in lines.OPENERS
    assert table.calls == [] and w.offered_at == float("-inf")  # no model greeting; "yeah" picks nothing


def _turns(monkeypatch, *outcomes):
    """agent.run_turn answers with `outcomes` in order (each said by the stub as the agent
    would), then None; every call kept as (situation, heard, facts)."""
    queue, calls = list(outcomes), []

    def run_turn(table, situation, heard, facts, allowed=agent.LOBBY):
        calls.append((situation, heard, facts))
        outcome = queue.pop(0) if queue else None
        if outcome is not None and outcome.said:
            table.say(outcome.said)
        return outcome

    monkeypatch.setattr(agent, "run_turn", run_turn)
    return calls


def test_the_models_line_is_said_and_remembered(monkeypatch):
    calls = _turns(monkeypatch, agent.Outcome(said="The beach! Who got the worst sunburn?"))
    table = FakeTable()
    w = _welcome(table)
    w.greet()
    assert w._hear("we just got back from the beach", 1) is None
    assert table.said[-1] == "The beach! Who got the worst sunburn?"
    assert list(w.memory)[-2:] == [("them", "we just got back from the beach"), ("ROB", "The beach! Who got the worst sunburn?")]
    situation, heard, facts = calls[0]
    assert situation == "lobby" and heard == "we just got back from the beach"
    assert facts["transcript"] == [["ROB", table.said[0]], ["ROB", table.said[1]]] and facts["memory"] is w.facts
    assert w.asked_at == table.now()  # a question: a short answer counts


def test_the_model_starts_a_game_or_naps(monkeypatch):
    _turns(monkeypatch, agent.Outcome(said="Imposter it is.", game="imposter"), agent.Outcome(said="Night, all.", nap=True))
    w = _welcome(FakeTable())
    assert w._hear("I think we should do the word one", 1) == Choice("imposter", "I think we should do the word one", None, False)
    assert w._hear("honestly we are all pretty tired", 2) == ""


def test_nothing_from_the_model_is_the_scripted_reply(monkeypatch):
    calls = _turns(monkeypatch)
    table = FakeTable()
    w = _welcome(table)
    w._hear("who are you?", 1)
    assert len(calls) == 1 and table.said[-1].startswith(("I'm ROB", "Name's ROB"))


def test_commands_and_a_named_game_never_reach_the_model(monkeypatch):
    calls = _turns(monkeypatch)
    w = _welcome(FakeTable())
    assert w._hear("let's play mafia", 0).game == "mafia"
    assert w._hear("ROB, remember that we hate Wordle", 1) is None
    assert w._hear("not now", 2) == ""
    assert w._hear("start over", 3) == "restart"
    assert calls == []


def test_a_headcount_is_still_the_codes_when_the_model_answers(monkeypatch):
    calls = _turns(monkeypatch, agent.Outcome(said="Three! Perfect for Imposter. Want to try it?"))
    table = FakeTable()
    w = _welcome(table)
    w._hear("there are three of us tonight", 1)
    assert calls[0][2]["seats"] == 3 and w.seats == 3 and ("seated", 3) in [(k, v) for _, k, v in table.log]
    assert w.suggestion == "imposter" and w.offered_at == table.now()  # the model named it: a yes takes it


def test_a_quiet_table_hears_the_models_nudges(monkeypatch):
    calls = _turns(monkeypatch, agent.Outcome(said="So quiet. Somebody say something."), agent.Outcome(said="Still here."))
    table = FakeTable()
    w = _welcome(table)
    w.greet()
    assert w.converse() is None
    assert [facts.get("quiet") for _, _, facts in calls] == [True, True]
    assert table.said[2:] == ["So quiet. Somebody say something.", "Still here.", lines.NAP]


def test_a_hello_and_how_are_you_get_answers_with_the_talk_so_far():
    table = ChattyTable(welcome=["Hey yourself! What are we playing?", "Doing great, just itching to host. You?"])
    table.hear("", "", "", "", "", "", "hello.", "uh, how are you?")
    w = _welcome(table)
    w.greet()
    w.converse()
    assert table.said[2:4] == ["Hey yourself! What are we playing?", "Doing great, just itching to host. You?"]
    (_, heard, facts) = table.calls[-1]
    assert heard == "uh, how are you?" and facts["answering"] is True
    assert facts["transcript"][-3:] == [["ROB", table.said[1]], ["them", "hello."], ["ROB", "Hey yourself! What are we playing?"]]


def test_a_yes_to_a_chatty_question_is_talk_but_a_yes_to_the_game_picks_it():
    table = ChattyTable(welcome=["Ooh, the beach. Was it fun?"])
    table.hear("there are three of us", "we just got back from the beach", "yeah, it was great")
    w = _welcome(table)
    w.greet()
    assert w.converse() is None  # the yes answered the beach, not the game: talk, nudges, a nap
    assert table.calls[-1][1] == "yeah, it was great"
    table = ChattyTable(welcome=["Beach day, nice. So, Imposter?"])
    table.hear("there are three of us", "we just got back from the beach", "yeah, it was great")
    w = _welcome(table)
    w.greet()
    assert w.converse() == Choice("imposter", "yeah, it was great", 3, False)


def test_scripted_replies_answer_the_small_talk_and_never_repeat():
    table = FakeTable().hear("who are you?", "we just got back from the beach", "it was so sunny out", "the water was cold")
    w = _welcome(table)
    w.greet()
    w.converse()
    replies = table.said[2:6]
    assert replies[0].startswith(("I'm ROB", "Name's ROB"))
    assert len(set(replies[1:])) == 3


def test_junk_from_the_transcriber_gets_nothing():
    table = FakeTable().hear("the name. the name. the name. the name.")
    w = _welcome(table)
    w.greet()
    w.converse()
    assert table.said[2] not in lines._chat_fallbacks(None)  # noqa: SLF001 - a nudge, not a reply
    assert ["them", "the name. the name. the name. the name."] not in [list(e) for e in w.memory]


def test_a_nap_keeps_the_talk_and_a_greeting_clears_it():
    table = FakeTable().hear("we just got back from the beach")
    w = _welcome(table)
    w.greet()
    w.converse()
    woken = _welcome(table)
    woken.wake()
    assert ("them", "we just got back from the beach") in woken.memory
    _welcome(table).greet()
    assert ("them", "we just got back from the beach") not in woken.memory and len(woken.memory) == 2  # the greeting and the games


def test_explicit_memory_precedes_game_names_and_uses_scripted_confirmation():
    table = FakeTable()
    w = _welcome(table)
    assert w._hear("ROB, remember that we hate Wordle", 0) is None
    assert w.facts.remembered() == ["we hate Wordle"]
    assert table.said == [lines.MEMORY_SAVED]
    assert w._hear("what do you remember?", 1) is None
    assert "we hate Wordle" in table.said[-1]
    w._hear("forget that", 2)
    assert w.facts.remembered() == []
    assert table.said[-1] == lines.MEMORY_FORGOT


def test_remembered_facts_go_to_each_lobby_model_reply_and_survive_reset():
    table = FakeTable()
    calls = []
    table.chat = lambda situation, heard="", **facts: calls.append((situation, facts))
    w = _welcome(table)
    w._hear("remember we love games", 0)
    w.greet()
    w._chat("hello ROB", False, 10, [])
    assert all(f["remembered"] == ["we love games"] for _, f in calls)
    w._hear("reset", 11)
    assert not w.memory
    assert w.facts.remembered() == ["we love games"]
    w._hear("forget everything", 12)
    assert w.facts.remembered() == []
