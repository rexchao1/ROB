"""Reveal cards: the big moments of each game on the host's screen while the host says
them (Table.reveal). The rules on the fake table: which card goes with which line, and
that every card is prepared before it is needed. The host on the fake gateway: the card
is up while the line plays, the face comes back after, and a card it cannot show
leaves the line said without it."""

import random

from fake_table import FakeTable
from test_host import Worker, _calls, _faces, _said, clock, host  # noqa: F401 - the fixtures

from brain import games, lines
from brain.games import hotseat, mafia, wavelength
from brain.games.common import Options
from brain.host import REVEAL_HOLD
from brain.table import REVEALS, Card


def _revealed(t: FakeTable) -> dict[str, Card]:
    """The line said -> the card that was up for it."""
    return {line: card for card, line in t.revealed}


def _prepared_before_each_reveal(t: FakeTable) -> None:
    """Every reveal's card was in the set prepared last before it."""
    current: list[Card] = []
    for _, kind, value in t.log:
        if kind == "prepare":
            current = value
        elif kind == "reveal":
            assert value in current, f"{value} revealed from a set without it ({current})"
            assert value.kind in REVEALS


# --- Mafia --------------------------------------------------------------------------------


def _mafia(t: FakeTable, rig=None, **options) -> FakeTable:
    games.play("mafia", t, random.Random(7), rig=rig or {"mafia": [1], "doctor": 5}, options=Options(**options))
    return t


def test_mafia_the_kill_the_vote_and_the_village_win_show_on_the_screen():
    t = FakeTable(5)
    t.reply(lines.MAFIA_WHISPER, "player two", "player four")
    t.reply(lines.DOCTOR_WHISPER, "player five", "player four")
    for seat, answer in {1: "three", 3: "one", 4: "three", 5: "three"}.items():
        t.reply(lines.who(seat), answer)
    t.reply(lines.who(1), "four")
    t.reply(lines.who(4), "one")
    t.reply(lines.who(5), "one")
    _mafia(t)
    shown = _revealed(t)
    assert shown[lines.killed(2)] == Card("PLAYER 2", "killed in the night", "out")
    assert shown[lines.was(3, mafia.VILLAGER)] == Card("VILLAGER", "voted out", "out")
    assert shown[lines.NOBODY_DIED] == Card("NOBODY", "died last night", "safe")
    assert shown[lines.village_wins(1)] == Card("VILLAGE", "wins", "win")
    _prepared_before_each_reveal(t)


def test_mafia_the_mafia_win_shows_on_the_screen():
    t = FakeTable(5)
    t.reply(lines.MAFIA_WHISPER, "player two", "player four")
    t.reply(lines.DOCTOR_WHISPER, "player five", "player five")
    for seat, answer in {1: "three", 3: "one", 4: "three", 5: "three"}.items():
        t.reply(lines.who(seat), answer)
    _mafia(t)
    assert _revealed(t)[lines.MAFIA_WIN] == Card("MAFIA", "win", "win")
    _prepared_before_each_reveal(t)


def test_mafia_a_doctor_sitting_out_turns_the_save_into_a_kill_with_its_card_ready():
    # The Doctor saves four, then is caught heads up twice in the night and sits out:
    # the save has no effect, and the kill's card was in the night's set all along.
    t = FakeTable(5)
    t.reply(lines.MAFIA_WHISPER, "player four")
    t.reply(lines.DOCTOR_WHISPER, "player four")
    t.sweep([], [5], [5])
    _mafia(t, max_rounds=1)
    assert _revealed(t)[lines.killed(4)] == mafia.killed_card(4)
    _prepared_before_each_reveal(t)


def test_mafia_the_role_cards_are_dealt_before_the_reveals_replace_them():
    t = _mafia(FakeTable(5), max_rounds=1)
    prepares = [value for _, kind, value in t.log if kind == "prepare"]
    assert prepares[0] == [Card("MAFIA"), Card("DOCTOR"), Card("VILLAGER")]
    last_show = max(i for i, e in enumerate(t.log) if e[1] == "show")
    second = [i for i, e in enumerate(t.log) if e[1] == "prepare"][1]
    assert last_show < second
    assert all(len(p) <= 5 for p in prepares)


# --- Imposter -----------------------------------------------------------------------------


def _imposter(answer: str) -> FakeTable:
    t = FakeTable(5)
    for seat in range(1, 6):
        t.reply(lines.who(seat), answer)
    games.play("imposter", t, random.Random(5), rig={"word": "beach", "imposter": 3})
    return t


def test_imposter_caught_shows_their_seat_then_the_word():
    t = _imposter("three")
    assert t.revealed == [
        (Card("PLAYER 3", "was the Imposter", "out"), lines.was_imposter(3)),
        (Card("beach", "was the word", "word"), lines.word_was("beach")),
    ]
    _prepared_before_each_reveal(t)


def test_imposter_surviving_shows_their_seat_then_the_word():
    t = _imposter("two")
    assert t.revealed[0] == (Card("PLAYER 3", "Imposter survives", "win"), lines.imposter_survives(3))
    assert t.revealed[1][1] == lines.word_was("beach")
    # One set for the whole game: the words and both endings, uploaded before the deal.
    assert len([e for e in t.log if e[1] == "prepare"]) == 1


# --- Wavelength ---------------------------------------------------------------------------

ROUNDS = [{"spectrum": "cold - hot", "target": 7}, {"spectrum": "bad - good", "target": 3}, {"spectrum": "quiet - loud", "target": 9}]


def test_wavelength_each_target_and_the_total_show_on_the_screen():
    t = FakeTable(5)
    t.reply(lines.WAVELENGTH_TALK, "six", "three", "five")
    games.play("wavelength", t, random.Random(2), rig={"psychic": 2, "rounds": ROUNDS})
    shown = _revealed(t)
    assert shown[lines.target_was(7)] == Card("7", "cold - hot", "target")
    assert shown[lines.target_was(9)] == Card("9", "quiet - loud", "target")
    assert shown[lines.total(9 + 10 + 6)] == Card("25", "points", "score")
    _prepared_before_each_reveal(t)


def test_wavelength_the_total_is_prepared_as_soon_as_the_last_guess_is_in():
    t = FakeTable(5)
    t.reply(lines.WAVELENGTH_TALK, "six", "three", "five")
    games.play("wavelength", t, random.Random(2), rig={"psychic": 2, "rounds": ROUNDS})
    entries = [(kind, value) for _, kind, value in t.log]
    last = max(i for i, (kind, _) in enumerate(entries) if kind == "prepare")
    assert entries[last][1] == [Card("9", "quiet - loud", "target"), wavelength.total_card(25)]
    # Before the round's points line, so the upload runs while it is said.
    assert entries[last + 1] == ("say", "Six points.")


# --- Wordle -------------------------------------------------------------------------------


def _wordle(*heard: str) -> FakeTable:
    t = FakeTable(1)
    t.reply(lines.count_line(1), "")
    t.hear(*heard)
    games.play("wordle", t, random.Random(1), rig={"word": "crane"})
    return t


def test_wordle_solved_shows_the_word():
    t = _wordle("crane")
    assert [card for card, _ in t.revealed] == [Card("CRANE", "solved", "win")]
    assert t.revealed[0][1].startswith("Crane. That's it!")
    _prepared_before_each_reveal(t)


def test_wordle_given_up_shows_the_word():
    t = _wordle("i give up")
    assert t.revealed == [(Card("CRANE", "was the word", "word"), "Fine. The word was crane.")]


# --- Hot Seat -----------------------------------------------------------------------------


def test_hot_seat_the_winner_shows_on_the_screen_once_five_are_left():
    t = FakeTable(6)
    for seat, answer in zip(range(1, 6), ("apple", "banana", "grape", "mango", "lemon")):
        t.reply(f"{lines.player(seat)}, go!", answer)
    games.play("hotseat", t, random.Random(3), rig={"categories": ["fruits"]})
    prepares = [value for _, kind, value in t.log if kind == "prepare"]
    assert prepares == [[hotseat.win_card(s) for s in range(1, 6)]]  # once six became five
    assert t.revealed == [(hotseat.win_card(5), "Player five wins Hot Seat!")]
    _prepared_before_each_reveal(t)


def test_hot_seat_stages_the_winners_mid_round_when_most_go_out_at_once():
    t = FakeTable(7)
    t.reply("Player one, go!", "apple")
    games.play("hotseat", t, random.Random(3), rig={"categories": ["fruits"]})
    prepares = [value for _, kind, value in t.log if kind == "prepare"]
    assert prepares == [[hotseat.win_card(s) for s in (1, 4, 5, 6, 7)]]  # right after Player three went out
    assert t.revealed == [(hotseat.win_card(1), "Player one wins Hot Seat!")]


# --- The host -----------------------------------------------------------------------------

WIN = Card("VILLAGE", "wins", "win")


def test_the_card_is_up_while_the_line_plays_then_the_face_comes_back(host, fake, clock):
    Worker(clock, host.prepare, [Card("MAFIA"), WIN])
    w = Worker(clock, host.reveal, WIN, lines.VILLAGE_WINS)
    assert not w.done  # held after the line
    clock.advance(REVEAL_HOLD)
    assert w.done and w.error is None
    pcm = _calls(fake, "pcm")
    assert [(c["line"], c["showing"]) for c in pcm] == [(lines.VILLAGE_WINS, {"text": "VILLAGE", "sub": "wins", "kind": "win"})]
    assert _faces(fake) == ["thinking", "idle"]
    screen = fake.device.screen()
    assert (screen["face"], screen["blink"], screen["showing"]) == ("idle", True, None)
    blinks = [c["args"]["enabled"] for c in _calls(fake, "set_blink")]
    assert blinks == [False, True]
    assert host.last_line == lines.VILLAGE_WINS  # "say that again" repeats it


def test_a_card_not_prepared_leaves_the_line_said_without_it(host, fake, clock):
    w = Worker(clock, host.reveal, WIN, lines.VILLAGE_WINS)  # nothing prepared at all
    assert w.done and w.error is None
    assert _said(fake) == [lines.VILLAGE_WINS] and _faces(fake) == []
    Worker(clock, host.prepare, [Card("MAFIA")])
    w = Worker(clock, host.reveal, WIN, lines.VILLAGE_WINS)  # a set without it
    assert w.done and w.error is None
    assert _said(fake) == [lines.VILLAGE_WINS] * 2 and _faces(fake) == []


def test_on_the_macs_speaker_the_mouth_stays_still_under_the_card(host, fake, clock, monkeypatch):
    played = []
    monkeypatch.setattr(host.body, "_play_here", lambda pcm, mouth=True: played.append(mouth))
    host.body.speaker = "mac"
    Worker(clock, host.prepare, [WIN])
    Worker(clock, host.say, "Hello.")
    Worker(clock, host.reveal, WIN, lines.VILLAGE_WINS)
    clock.advance(REVEAL_HOLD)
    assert played == [True, False]
