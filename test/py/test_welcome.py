"""The welcome (brain/games/welcome.py): it greets and listens straight away, takes a
headcount at its word, and sweeps the table only when asked."""

import random

from fake_table import FakeTable

from brain import lines
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
    assert table.said[0] in lines.GREETINGS
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
    assert table.said[1] in lines.LOOKING
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


def test_insisting_on_a_bigger_number_than_seen_wins_after_the_second_look():
    table = FakeTable(counts=[3]).hear("count us", "five of us", "five of us", "five of us", "five of us", "sure")
    w = _welcome(table)
    w.greet()
    choice = w.converse()
    assert _kinds(table).count("count") == 2  # the sweep asked for, one second look
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


def test_the_greeting_is_the_models_when_it_names_rob_and_asks():
    table = ChattyTable(welcome_greeting=["Evening, legends! I'm ROB. What are we playing?"])
    _welcome(table).greet()
    assert table.said == ["Evening, legends! I'm ROB. What are we playing?"]
    table = ChattyTable(welcome_greeting=["Evening, legends. Let the games begin."])  # no name, no question
    _welcome(table).greet()
    assert table.said[0] in lines.GREETINGS


def test_a_hello_and_how_are_you_get_answers_with_the_talk_so_far():
    table = ChattyTable(welcome=["Hey yourself! What are we playing?", "Doing great, just itching to host. You?"])
    table.hear("", "", "", "", "", "", "hello.", "uh, how are you?")
    w = _welcome(table)
    w.greet()
    w.converse()
    assert table.said[1:3] == ["Hey yourself! What are we playing?", "Doing great, just itching to host. You?"]
    (_, heard, facts) = table.calls[-1]
    assert heard == "uh, how are you?" and facts["answering"] is True
    assert facts["transcript"][-3:] == [["ROB", table.said[0]], ["them", "hello."], ["ROB", "Hey yourself! What are we playing?"]]


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
    replies = table.said[1:5]
    assert replies[0].startswith(("I'm ROB", "Name's ROB"))
    assert len(set(replies[1:])) == 3


def test_junk_from_the_transcriber_gets_nothing():
    table = FakeTable().hear("the name. the name. the name. the name.")
    w = _welcome(table)
    w.greet()
    w.converse()
    assert table.said[1] not in lines._chat_fallbacks(None)  # noqa: SLF001 - a nudge, not a reply
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
    assert ("them", "we just got back from the beach") not in woken.memory and len(woken.memory) == 1
