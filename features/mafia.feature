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

  @D87
  Scenario: A sentence that mentions starting over is talk, not a reset
    Given it is morning and the day phase has begun
    When someone says "i think we should start over with the accusations"
    Then the game goes on and the players hear the host say "One minute left." sixty seconds after the day began

  @D88
  Scenario: Restart the round starts the night again
    Given it is morning and the day phase has begun
    When someone says "restart the round"
    Then the players hear the host say "Okay, this round again."
    And the players hear the host say "Everyone, heads down."

  @D92
  Scenario: The group may vote early by saying so
    Given it is morning and the day phase has begun
    When thirty seconds have passed and someone says "let's vote"
    Then the players hear the host say "Okay, let's vote."

  @D92
  Scenario: A sentence about not being ready does not end the day
    Given it is morning and the day phase has begun
    When someone says "i'm not ready to vote"
    Then the game goes on and the players hear the host say "One minute left." sixty seconds after the day began

  @D99
  Scenario: Ten rounds without a win is a draw
    Given nine rounds have passed with nobody killed and every vote tied
    When the tenth day's vote ties
    Then the players hear the host say "That's enough rounds for one night. Let's call it a draw."
    And the game is over with no winner

  @D102
  Scenario: The Doctor is asked every night, dead or alive
    Given Player five was killed in the first night
    When the second night comes and nobody whispers
    Then the players hear the host say "Mafia, once more, quietly. Who?"
    And the players hear the host say "Doctor, once more, quietly. Who?"

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
