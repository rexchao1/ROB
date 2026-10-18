Feature: Mafia
  Five players: one Mafia, one Doctor, three Villagers. Roles through the
  private screen, a night of whispers with heads down, a timed day, a vote,
  a win check. Serves N1.

  Background:
    Given five friends are playing Mafia with the host in the middle
    And Player one is the Mafia and Player five is the Doctor

  @D15
  Scenario: Roles are dealt one at a time through the private screen
    When roles are dealt
    Then each player in seat order has leaned in and seen their role alone
    And Player one saw "MAFIA", Player five saw "DOCTOR", and Players two, three and four saw "VILLAGER"

  @D16
  Scenario: The Mafia's target dies when the Doctor saves someone else
    Given it is night and every head is down
    When the host says "Mafia, whisper your target." and Player one quietly says "Player four"
    And the host says "Doctor, whisper who you save." and Player five quietly says "Player two"
    Then at morning the players hear the host say "Player four was killed in the night."
    And Player four is out for the rest of the game

  @D17
  Scenario: The Doctor saves the Mafia's target
    Given it is night and every head is down
    When the host says "Mafia, whisper your target." and Player one quietly says "Player four"
    And the host says "Doctor, whisper who you save." and Player five quietly says "Player four"
    Then at morning the players hear the host say "Nobody died last night."
    And every player is still in

  @D18
  Scenario Outline: Discussion time runs by the clock
    Given it is morning and the day phase has begun
    When <elapsed> have passed
    Then the players hear the host say "<line>"

    Examples:
      | elapsed              | line                      |
      | sixty seconds        | One minute left.          |
      | one hundred twenty seconds | Time. Let's vote.   |

  @D18
  Scenario: The eliminated player's role is revealed
    Given a day phase vote eliminated Player four
    Then the players hear the host say "Player four was a Villager."

  @D19
  Scenario: The village wins when no Mafia is left
    Given Players two and three are out and Player one is the only Mafia
    When a day phase vote eliminates Player one
    Then the players hear the host say "Player one was the Mafia. The village wins."
    And the game is over

  @D19
  Scenario: The Mafia win when they equal the rest
    Given Players two, three and four are out and Players one and five remain
    When the host checks the win condition
    Then the players hear the host say "The Mafia win."
    And the game is over
