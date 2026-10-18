Feature: Wavelength
  Everyone but the guesser sees a secret number from one to ten on the private
  screen. The guesser gives each of them a category and each names something in
  it that fits the number (one the least, ten the most); then the guesser says the
  number and the host scores by distance. Three rounds, the guesser rotates.
  Serves N1.

  Background:
    Given five friends are playing Wavelength with the host in the middle

  @D117
  Scenario: Everyone but the guesser sees the number
    Given Player two is the guesser this round and the number is 7
    When the round's number is dealt
    Then Players three, four, five and one each saw "7" and "out of ten" alone on the host's screen
    And Player two was not called to lean in

  @D117
  Scenario: The guesser gives each player a category
    Given Player two is the guesser this round and the number is 7
    When the round's number is dealt
    Then the players hear the host say "Player two, give Player three a category."
    And the players hear the host say "Player three, name something that fits the number."

  @D21 @D103 @D117
  Scenario Outline: The guesser's number scores by distance from the secret number
    Given Player two is the guesser this round and the number is 7
    And every player has named something for Player two
    When someone says "<guess>"
    Then the players hear the host say "<score>"

    Examples:
      | guess | score         |
      | six   | Nine points.  |
      | seven | Ten points.   |
      | one   | Four points.  |
      | ten   | Seven points. |

  @D95
  Scenario Outline: A guess is read from a short answer
    Given Player two is the guesser this round and the number is 7
    And every player has named something for Player two
    When someone answers "<said>"
    Then the players hear the host say "<score>"

    Examples:
      | said              | score        |
      | seven out of ten  | Ten points.  |
      | nine, no, eight   | Nine points. |
      | i'd say six       | Nine points. |

  @D95
  Scenario: A number inside a longer sentence is talk
    Given Player two is the guesser this round and the number is 7
    And every player has named something for Player two
    When someone says "it's definitely big, like an eight, or maybe more"
    Then the players hear the host say "What's your number?" before any points

  @D100
  Scenario: No guess the host can read scores zero
    Given Player two is the guesser this round and the number is 7
    And every player has named something for Player two
    When nobody says a number for eight listens
    Then the players hear the host say "No guess. Zero points."
    And the players hear the host say "It was seven."

  @D103 @D21 @D117
  Scenario: The guesser rotates and the total is announced after three rounds
    Given Player two is the guesser this round and the number is 7
    And three rounds have been played scoring nine, ten and four
    Then the players hear the host say "Twenty-three points. Nice work."
    And the guesser for the next round would be Player three
