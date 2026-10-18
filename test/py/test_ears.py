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
        ("player for", 4),  # a soundalike right after "player" counts (D91)
        ("seat too", 2),
        ("number won", 1),
        ("player-three", 3),
        ("for.", None),  # a soundalike on its own does not (D91)
        ("too", None),
        ("won", None),
        ("me too", None),
        ("i want to go home", None),  # "to" in a sentence is not a seat
        ("two or four", None),  # two seats named: ask again
        ("players three and four", None),
        ("anyone but four", None),  # a negation: ask again
        ("everyone except player four", None),
        ("not four", None),
        ("player four, no wait, two", 2),  # a correction takes the last number
        ("three, actually four", 4),
        ("sorry, i mean player one", 1),
        ("player six", None),  # no such seat at five
        ("no one", None),
        ("", None),
        ("um", None),
    ],
)
def test_d91_seat_said_at_five_seats(text, seat):
    assert ears.seat_said(text, 5) == seat


@pytest.mark.parametrize(
    "text, n",
    [
        ("six", 6), ("i think seven", 7), ("7", 7), ("ten", 10), ("one", 1), ("eleven", None), ("six or seven", None),
        ("", None),
        ("i'd say six", 6),  # D95
        ("seven out of ten", 7),
        ("seven out of 10", 7),
        ("six on the scale", 6),
        ("nine, no, eight", 8),
        ("eight, actually seven", 7),
        ("it's definitely hot, like an eight, or maybe more", None),
        ("sex", None),
        ("ate", None),
    ],
)
def test_d95_number_said(text, n):
    assert ears.number_said(text) == n


def test_bare_number_is_only_a_number():
    assert ears.bare_number("six.") == 6
    assert ears.bare_number("uh, six") == 6
    assert ears.bare_number("player six") == 6
    assert ears.bare_number("i think there might be six") is None


@pytest.mark.parametrize("text", ["you two", "me too", "one sec", "sex", "i ate", "for"])
def test_d91_a_soundalike_or_a_pointer_at_people_is_no_count(text):
    assert ears.bare_number(text) is None


def test_d89_agreeing_rejects_a_negation():
    assert ears.agrees("okay")
    assert ears.agrees("yeah, fine, start")
    assert ears.agrees("that's right")
    assert not ears.agrees("there are six of us")
    for said in ("no that's not right", "don't start", "no", "nope", "that's wrong", "never mind, not yet"):
        assert not ears.agrees(said), said


@pytest.mark.parametrize("text", ["reset", "let's reset", "okay restart", "start over", "can we start over",
                                  "restart the game", "Reset!", "i want to reset"])
def test_d87_a_short_plain_reset_resets(text):
    assert ears.wants_to_reset(text) and ears.wants_to_stop(text)


@pytest.mark.parametrize("text", ["stop the game", "let's stop the game", "stop the game please", "end the game",
                                  "stop playing", "quit the game"])
def test_d87_a_short_plain_stop_stops(text):
    assert ears.wants_to_stop(text) and not ears.wants_to_reset(text)


@pytest.mark.parametrize("text", [
    "i think we should start over with the accusations", "don't reset", "no reset", "stop playing dumb, player two",
    "stop it, player two", "my clue is restart", "restart, like a computer restart", "we never reset",
    "let's not stop the game", "", "player two",
])
def test_d87_a_sentence_that_contains_the_word_is_talk(text):
    assert not ears.wants_to_stop(text) and not ears.wants_to_reset(text) and not ears.wants_round_restart(text)


@pytest.mark.parametrize("text", ["restart the round", "redo the round", "this round again", "let's redo this round",
                                  "okay restart the round"])
def test_d88_a_round_restart_is_not_a_reset(text):
    assert ears.wants_round_restart(text)
    assert ears.wants_to_stop(text) and not ears.wants_to_reset(text)


def test_d88_a_reset_is_not_a_round_restart():
    assert not ears.wants_round_restart("reset") and not ears.wants_round_restart("restart the game")


@pytest.mark.parametrize("text", ["let's vote", "okay let's vote", "we're ready to vote", "vote now", "time to vote",
                                  "okay we're ready, let's vote", "can we vote"])
def test_d92_a_short_plain_vote_votes_early(text):
    assert ears.wants_to_vote(text)


@pytest.mark.parametrize("text", ["i'm not ready to vote", "we're ready to hear from player two", "don't vote now",
                                  "i think it's player two", "i want to vote for player two, not four", ""])
def test_d92_a_longer_or_negated_sentence_is_talk(text):
    assert not ears.wants_to_vote(text)


@pytest.mark.parametrize(
    "text, game",
    [
        ("mafia", "mafia"),
        ("Mafia!", "mafia"),
        ("hot seat", "hotseat"),
        ("wordle please", "wordle"),
        ("we want hot seat", "hotseat"),
        ("how about imposter", "imposter"),
        ("imposter with six people", "imposter"),
        ("can we play wavelength", "wavelength"),
        ("start mafia", "mafia"),
        ("mafia time", "mafia"),
        ("twenty questions", "twenty"),
        ("let's play twenty questions", "twenty"),
        ("that was a hot seat yesterday", None),
        ("i have twenty questions about this", None),
        ("put it in poster form", None),
        ("the word game was fun", None),
        ("my cousin is in the mafia", None),
    ],
)
def test_d94_a_game_starts_on_its_name_as_a_request_or_the_whole_utterance(text, game):
    assert ears.game_named(text) == game


def test_d94_a_name_inside_other_talk_is_a_mention():
    assert ears.game_mentioned("that was a hot seat yesterday") == "hotseat"
    assert ears.game_mentioned("put it in poster form") == "imposter"
    assert ears.game_mentioned("let's play mafia") == "mafia"
    assert ears.game_mentioned("let's play a game") is None
    assert ears.asks_rules("how do you play imposter?") == "imposter"
    assert ears.asks_rules("what are the rules of mafia") == "mafia"


@pytest.mark.parametrize("text", ["Pause.", "can you pause the game", "pause please"])
def test_pause_is_heard(text):
    assert ears.wants_pause(text)


@pytest.mark.parametrize("text", ["Resume.", "okay unpause", "we're back", "keep going", "continue", "carry on"])
def test_resume_is_heard_and_is_not_a_pause(text):
    assert ears.wants_resume(text) and not ears.wants_pause(text)


@pytest.mark.parametrize("text", ["let's go", "lets go", "go on", "okay let's go"])
def test_d93_lets_go_is_a_yes_not_a_resume(text):
    assert not ears.wants_resume(text)
    assert ears.says_yes(text) or ears.agrees(text)


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
