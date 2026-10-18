"""Parsing what was heard: lower-cased Whisper output, punctuation and all. Every parser
answers None rather than guess."""

import pytest

from brain import ears


@pytest.mark.parametrize(
    "text, game",
    [
        ("let's play mafia.", "mafia"),
        ("Let's play Mafia!", "mafia"),
        ("can we play werewolf", "mafia"),
        ("let's play impostor", "imposter"),
        ("let's play in poster", "imposter"),
        ("wavelength please", "wavelength"),
        ("let's play wave length", "wavelength"),
        ("let's play a game", None),
        ("", None),
    ],
)
def test_game_named(text, game):
    assert ears.game_named(text) == game


@pytest.mark.parametrize(
    "text, n",
    [
        ("there are six of us", 6),
        ("there are six of us.", 6),
        ("six of us", 6),
        ("we're six", 6),
        ("we are six.", 6),
        ("6 players", 6),
        ("six people", 6),
        ("we have six", 6),
        ("let's play mafia, there are six of us", 6),
        ("let's play mafia", None),
        ("player four", None),
        ("there are two mafia", None),
        ("four", None),
        ("", None),
    ],
)
def test_count_said(text, n):
    assert ears.count_said(text) == n


@pytest.mark.parametrize(
    "text, seat",
    [
        ("player four", 4),
        ("player four.", 4),
        ("Player Four.", 4),
        ("four", 4),
        ("4", 4),
        ("4.", 4),
        ("number four", 4),
        ("i vote for four", 4),
        ("i vote for player two", 2),
        ("player for", 4),
        ("for.", 4),
        ("too", 2),
        ("won", 1),
        ("player-three", 3),
        ("i want to go home", None),  # "to" in a sentence is not a seat
        ("two or four", None),  # two seats named: ask again
        ("player six", None),  # no such seat at five
        ("no one", None),
        ("", None),
        ("um", None),
    ],
)
def test_seat_said_at_five_seats(text, seat):
    assert ears.seat_said(text, 5) == seat


@pytest.mark.parametrize(
    "text, n",
    [("six", 6), ("i think seven", 7), ("7", 7), ("ten", 10), ("one", 1), ("eleven", None), ("six or seven", None), ("", None)],
)
def test_number_said(text, n):
    assert ears.number_said(text) == n


def test_bare_number_is_only_a_number():
    assert ears.bare_number("six.") == 6
    assert ears.bare_number("uh, six") == 6
    assert ears.bare_number("player six") == 6
    assert ears.bare_number("i think there might be six") is None


def test_agreeing_stopping_and_voting_early():
    assert ears.agrees("okay")
    assert ears.agrees("yeah, fine, start")
    assert not ears.agrees("there are six of us")
    assert ears.wants_to_stop("let's stop the game")
    assert ears.wants_to_stop("can we start over")
    assert not ears.wants_to_stop("stop it, player two")
    assert ears.wants_to_vote("okay let's vote")
    assert not ears.wants_to_vote("i think it's player two")


@pytest.mark.parametrize("text", ["Pause.", "can you pause the game", "pause please"])
def test_pause_is_heard(text):
    assert ears.wants_pause(text)


@pytest.mark.parametrize("text", ["Resume.", "okay unpause", "we're back", "keep going", "continue"])
def test_resume_is_heard_and_is_not_a_pause(text):
    assert ears.wants_resume(text) and not ears.wants_pause(text)


@pytest.mark.parametrize("text", ["player two", "applause", "let's vote", ""])
def test_other_words_are_neither(text):
    assert not ears.wants_pause(text) and not ears.wants_resume(text)


@pytest.mark.parametrize("text", ["Shut up.", "be quiet", "stop", "Stop, stop.", "okay stop", "wait", "rob, stop", "hush"])
def test_a_bare_stop_or_shut_up_is_a_pause(text):
    assert ears.wants_pause(text)


@pytest.mark.parametrize("text", ["stop the game", "end the game", "reset", "stop it, player two", "hold on", "wait, player three did it"])
def test_stopping_the_game_and_sentences_are_not_a_pause(text):
    assert not ears.wants_pause(text)


@pytest.mark.parametrize("text", ["I'm leaning in.", "i'm looking", "show me", "show my card", "I can't see it.", "let me see", "okay I'm here"])
def test_a_player_at_the_screen_asks_for_the_card(text):
    assert ears.wants_card(text) and not ears.saw_card(text)


@pytest.mark.parametrize("text", ["Got it.", "i saw it", "I've seen it", "done", "next", "okay next", "next player", "move on", "skip"])
def test_a_player_has_seen_the_card(text):
    assert ears.saw_card(text)


@pytest.mark.parametrize("text", ["the next morning", "I haven't seen it", "i think the next one is going to be player two for sure", "show me what you've got this time around"])
def test_table_talk_is_not_an_answer_at_the_screen(text):
    assert not ears.saw_card(text) and not ears.wants_card(text)


@pytest.mark.parametrize(
    "text, place",
    [
        ("change your speaker to the Mac.", "mac"),
        ("change your speaker to the back", "mac"),  # Whisper's "Mac"
        ("speaker mac", "mac"),
        ("play the sound through the laptop", "mac"),
        ("switch from the robot speaker to the macbook", "mac"),
        ("speaker robot", "robot"),
        ("go back to your own speaker", "robot"),
        ("use your speaker", "robot"),
        ("take your speakers", None),
        ("is it a computer speaker", None),
        ("sound like a robot", None),
        ("let's play mafia", None),
    ],
)
def test_speaker_said(text, place):
    assert ears.speaker_said(text) == place


def test_say_that_again():
    assert ears.wants_repeat("Can you say that again?") and ears.wants_repeat("what did you say")
    assert not ears.wants_repeat("player two")


def test_restarted_said_in_passing_is_not_a_reset():
    assert not ears.wants_to_reset("in the background. yeah. you never really restarted? well, no.")
    assert ears.wants_to_reset("restart") and ears.wants_to_reset("let's start over")


def test_what_else_asks_for_the_games():
    assert ears.asks_games("what else do you got?")
    assert ears.asks_games("any other games?")


@pytest.mark.parametrize("text", ["hi", "hello.", "hey rob", "what's up?", "how are you?", "who are you?", "yo",
                                  "rob", "a joke?", "are you there?"])
def test_a_greeting_a_question_to_the_host_or_its_name_counts_unasked(text):
    assert ears.meaningful(text)


@pytest.mark.parametrize("text", ["thank you", "you", "oh", "the name. the name. the name.", "ha ha ha ha",
                                  " ".join(["so", "then"] * 21)])
def test_phantoms_and_transcription_junk_never_count(text):
    assert not ears.meaningful(text) and not ears.meaningful(text, answering=True)


def test_a_short_mumble_counts_only_as_an_answer():
    assert not ears.meaningful("i want...") and ears.meaningful("i want...", answering=True)


def test_small_talk_kinds():
    assert [ears.small_talk(t) for t in ("hey rob", "how's it going?", "who are you", "tell us a joke", "pass the chips")] == [
        "hello", "how", "who", "joke", None]


@pytest.mark.parametrize("text, expected", [
    ("ROB, remember that we hate Wordle", ("remember", "we hate Wordle")),
    ("remember we love Mafia", ("remember", "we love Mafia")),
    ("forget that", ("forget", "")),
    ("ROB, forget everything!", ("clear", "")),
    ("what do you remember?", ("recall", "")),
    ("do you remember Mafia?", None),
    ("I remember the last game", None),
])
def test_memory_commands(text, expected):
    assert ears.memory_command(text) == expected


@pytest.mark.parametrize("text", ["let's end this game please.", "okay, exit the game", "we're done", "stop this game"])
def test_more_ways_to_end_the_game_are_heard(text):
    assert ears.wants_to_stop(text) and not ears.wants_sleep(text)


@pytest.mark.parametrize("text", ["go to sleep.", "rob, take a nap", "okay go to bed"])
def test_go_to_sleep_ends_any_game_and_naps(text):
    assert ears.wants_to_stop(text) and ears.wants_sleep(text) and not ears.wants_to_reset(text)


def test_a_stop_phrase_inside_another_word_is_not_a_stop():
    assert not ears.wants_to_stop("we had a great weekend games night")
