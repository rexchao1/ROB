Feature: Wavelength
  The psychic sees a target number on the private screen and gives a clue;
  the group guesses; the host scores by distance. Three rounds, the psychic
  rotates. Serves N1.

  Background:
    Given five friends are playing Wavelength with the host in the middle

  @D21
  Scenario: The psychic alone sees the target
    Given Player two is the psychic this round and the spectrum is "cold - hot"
    And the target is 7 on a scale of one to ten
    When the host turns to Player two and says "Player two, lean in."
    And only Player two's face is close to the host and facing it
    Then Player two sees "7" and "cold - hot" on the host's screen

  @D21 @D103
  Scenario Outline: A spoken guess scores by distance from the target
    Given Player two is the psychic this round and the spectrum is "cold - hot"
    And the target is 7 on a scale of one to ten
    And Player two has given a clue
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
    Given Player two is the psychic this round and the spectrum is "cold - hot"
    And the target is 7 on a scale of one to ten
    And Player two has given a clue
    When someone answers "<said>"
    Then the players hear the host say "<score>"

    Examples:
      | said              | score        |
      | seven out of ten  | Ten points.  |
      | nine, no, eight   | Nine points. |
      | i'd say six       | Nine points. |

  @D95
  Scenario: A number inside a longer sentence is talk
    Given Player two is the psychic this round and the spectrum is "cold - hot"
    And the target is 7 on a scale of one to ten
    And Player two has given a clue
    When someone says "it's definitely hot, like an eight, or maybe more"
    Then the players hear the host say "What's your number?" before any points

  @D100
  Scenario: No guess the host can read scores zero
    Given Player two is the psychic this round and the spectrum is "cold - hot"
    And the target is 7 on a scale of one to ten
    And Player two has given a clue
    When nobody says a number for eight listens
    Then the players hear the host say "No guess. Zero points."
    And the players hear the host say "It was seven."

  @D103 @D21
  Scenario: The psychic rotates and the total is announced after three rounds
    Given Player five was the psychic in the first round and the spectrum is "cold - hot"
    And three rounds have been played scoring nine, ten and four
    Then the players hear the host say "Twenty-three points. Nice work."
    And the psychic for the next round would be Player three
