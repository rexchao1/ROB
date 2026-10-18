"""The script: every line the feature files quote comes out character for character,
flavor never names a player, and fixed_lines() covers what the voice cache records."""

import random
import re

import pytest

from brain import lines


@pytest.mark.parametrize(
    "line, expected",
    [
        (lines.count_line(5), "Five of you. Player one is on my left, then two, three, four, five going clockwise."),
        (lines.only_see(5), "I only see five. Who's hiding?"),
        (lines.lean_in(2), "Player two, lean in."),
        (lines.ONE_AT_A_TIME, "One at a time."),
        (lines.HEADS_DOWN, "Everyone, heads down."),
        (lines.warn(3), "Player three, heads down means heads DOWN."),
        (lines.sit_out(3), "Player three, you're sitting this round out."),
        (lines.who(1), "Player one, who?"),
        (lines.tally([(4, 3), (1, 2)]), "Three for Player four, two for Player one."),
        (lines.voted_out(4), "Player four, you're out."),
        (lines.tie([(2, 2), (4, 2)]), "Two for Player two, two for Player four. It's a tie. Nobody leaves."),
        (lines.MAFIA_WHISPER, "Mafia, whisper your target."),
        (lines.DOCTOR_WHISPER, "Doctor, whisper who you save."),
        (lines.killed(4), "Player four was killed in the night."),
        (lines.NOBODY_DIED, "Nobody died last night."),
        (lines.time_left(60), "One minute left."),
        (lines.TIME_VOTE, "Time. Let's vote."),
        (lines.was(4, lines.VILLAGER), "Player four was a Villager."),
        (lines.village_wins(1), "Player one was the Mafia. The village wins."),
        (lines.MAFIA_WIN, "The Mafia win."),
        (lines.was_imposter(3), "Player three was the Imposter."),
        (lines.imposter_survives(3), "The Imposter survives. It was Player three."),
        (lines.points(9), "Nine points."),
        (lines.points(10), "Ten points."),
        (lines.points(4), "Four points."),
        (lines.points(7), "Seven points."),
        (lines.total(23), "Twenty-three points. Nice work."),
    ],
)
def test_the_ruled_lines_are_exact(line, expected):
    assert line == expected


def test_number_words():
    assert [lines.number_word(n) for n in (0, 1, 13, 20, 23, 40, 99, 100)] == [
        "zero", "one", "thirteen", "twenty", "twenty-three", "forty", "ninety-nine", "one hundred"
    ]
    with pytest.raises(ValueError):
        lines.number_word(101)
    assert lines.player(10) == "Player ten"
    assert lines.points(1) == "One point."


def test_count_lines_for_other_tables():
    assert lines.count_line(4) == "Four of you. Player one is on my left, then two, three, four going clockwise."
    assert lines.count_line(2) == "Two of you. Player one is on my left, then two going clockwise."


def test_halfway_and_discussion_lines_follow_the_day_length():
    assert lines.discussion(120) == "You have two minutes. Talk it out."
    assert lines.discussion(30) == "You have thirty seconds. Talk it out."
    assert lines.time_left(15) == "Fifteen seconds left."
    assert lines.time_left(120) == "Two minutes left."


def test_flavor_never_names_a_player_or_a_seat():
    seat = re.compile(r"\b(player|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b", re.I)
    for moment, variations in lines.FLAVOR.items():
        for line in variations:
            assert not seat.search(line), f"{moment}: {line!r}"
    rng = random.Random(3)
    assert lines.flavor("night", rng) in lines.FLAVOR["night"]


def test_fixed_lines_cover_the_per_seat_lines_once_each():
    fixed = lines.fixed_lines()
    assert len(fixed) == len(set(fixed))
    for line in [
        lines.count_line(5), lines.only_see(5), lines.lean_in(10), lines.warn(3), lines.sit_out(3),
        lines.who(7), lines.killed(4), lines.was(4, lines.VILLAGER), lines.village_wins(1), lines.MAFIA_WIN,
        lines.points(9), lines.total(23), lines.ONE_AT_A_TIME, lines.time_left(60), lines.TIME_VOTE,
        lines.imposter_survives(3), lines.clue(5), lines.guesser_turn(2), lines.ask_category(2, 4),
    ]:
        assert line in fixed, line
    assert lines.tally([(4, 3), (1, 2)]) not in fixed  # composed at play time
    assert lines.lean_in(11) not in fixed
    assert lines.lean_in(11) in lines.fixed_lines(12)


def test_the_welcome_greets_as_rob_and_every_game_says_what_it_is():
    assert all("ROB" in line for line in lines.GREETINGS)
    fixed = lines.fixed_lines()
    assert len(lines.GREETINGS) == 6 and all(line in fixed for line in (*lines.GREETINGS, *lines.OPENERS))
    menu = lines.games_menu()
    assert all(lines.game_name(g) in menu for g in lines.MINIMUM) and "Mafia needs at least four" in menu
    assert all(game in lines.RULES for game in lines.MINIMUM)
    assert "Easier to show you" not in lines.games_about() and "Want to play it?" not in lines.games_about()


def test_a_scripted_reply_answers_the_small_talk_and_skips_lines_just_said():
    rng = random.Random(1)
    assert lines.chat_fallback("mafia", rng, "who").startswith(("I'm ROB", "Name's ROB"))
    assert lines.chat_fallback(None, rng, "joke").endswith("What are we playing?")
    said = list(lines._chat_fallbacks("mafia")[:-1])  # noqa: SLF001
    assert lines.chat_fallback("mafia", rng, None, said) == lines._chat_fallbacks("mafia")[-1]  # noqa: SLF001
    assert "Noted. Now, which game?" not in lines.fixed_lines()
    assert lines.chat_fallback("mafia", rng, "hello") in lines.fixed_lines()
