Feature: Imposter
  Everyone sees the same word on the private screen except one player, who
  sees IMPOSTER. One clue each, a vote, a reveal. Serves N1.

  Background:
    Given five friends are playing Imposter with the host in the middle
    And the word is "beach" and Player three is the Imposter

  @D20
  Scenario: Words are dealt and one player sees IMPOSTER
    When words are dealt through the private screen
    Then Players one, two, four and five each saw "beach" alone
    And Player three saw "IMPOSTER" alone

  @D20
  Scenario: Each player gives one clue in seat order
    Given words have been dealt
    When the host turns to each player in seat order and asks for one word
    Then the players hear the host address Player one, then two, three, four and five, each once

  @D20
  Scenario: Voting out the Imposter ends the round with a reveal
    Given clues have been given
    When a vote eliminates Player three
    Then the players hear the host say "Player three was the Imposter."

  @D20
  Scenario: Voting out anyone else lets the Imposter survive
    Given clues have been given
    When a vote eliminates Player two
    Then the players hear the host say "The Imposter survives. It was Player three."

  @D101 @D13
  Scenario: A tied vote lets the Imposter survive
    Given clues have been given
    When a vote ties between Players two and four
    Then the players hear the host say "Two for Player two, two for Player four. It's a tie. Nobody leaves."
    And the players hear the host say "The Imposter survives. It was Player three."

  @D115
  Scenario: The reveal shows on the host's screen while the host says it
    Given clues have been given
    When a vote eliminates Player three
    Then the host's screen shows "PLAYER 3" and "was the Imposter" while it says "Player three was the Imposter."
    And the host's screen shows "beach" and "was the word" while it says "The word was beach."
    And the host's own face is back on its screen afterwards
