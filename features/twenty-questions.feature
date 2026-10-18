Feature: Twenty Questions
  One player, or a group playing as one, against the host. The host asks which
  way round. Guessing, it asks yes-or-no questions and may guess at any point;
  thinking of the secret, it answers from its built-in table and a hint costs a
  question. Built in workstream X without tests; this file describes what was
  built and binds nothing yet. Serves N2.

  Background:
    Given one friend is seated in front of the host
    And no talk model answers the host

  @D61
  Scenario: The host asks which way round
    When Twenty Questions begins
    Then the players hear the host say "Twenty Questions. Want me to guess yours, or you guess mine?"

  @D61
  Scenario: Left to the host, it picks a way round and says which
    Given Twenty Questions has begun
    When the player says "whatever"
    Then the players hear the host say which way round it picked

  @D62
  Scenario: The host wins on a right guess
    Given the host is guessing and the player is thinking of a dog
    When the player answers every question truthfully about a dog
    Then the host guesses the dog within twenty questions
    And the players hear the host claim the win
    And the game is over with the host the winner

  @D62
  Scenario: Twenty questions used up without a right guess is the player's win
    Given the host is guessing
    When the player answers "no" to twenty questions
    Then the players hear the host say "Twenty's up. You win. What was it?"
    And the game is over with the player the winner

  @D63
  Scenario: A question about a trait the table knows is answered from the table
    Given the host is thinking of a toaster
    When the player asks "is it electronic?"
    Then the players hear the host answer yes
    And one question has been used

  @D63
  Scenario: A question the host cannot answer does not count
    Given the host is thinking of a toaster
    When the player asks "when did you get it?"
    Then the players hear the host say "Can't answer that one. Try another way."
    And no question has been used

  @D63
  Scenario: A hint costs a question
    Given the host is thinking of a toaster
    When the player says "hint"
    Then the players hear the host say a line beginning "Hint:"
    And one question has been used

  @D63
  Scenario: A right guess wins
    Given the host is thinking of a toaster
    When the player asks "is it a toaster?"
    Then the players hear the host say it was a toaster
    And the game is over with the player the winner

  @D63
  Scenario: Giving up reveals the secret
    Given the host is thinking of a toaster
    When the player says "i give up"
    Then the players hear the host say it was a toaster
    And the game is over with the host the winner

  @D64
  Scenario Outline: The host counts out loud only at the moments that matter
    Given the host is thinking of a toaster
    When the player has asked <count> counted questions
    Then the players hear the host say "<line>"

    Examples:
      | count    | line                      |
      | ten      | That's ten. Halfway.      |
      | fifteen  | Five left.                |
      | nineteen | Last one. Make it count.  |

  @D65
  Scenario: Silence gets a nudge, then take your time, then quiet
    Given the host is thinking of a toaster
    When eight seconds pass with nothing said
    Then the players hear the host say "Got a question for me?"
    When twelve more seconds pass with nothing said
    Then the players hear the host say "Take your time. Want a hint? Just say hint."
    When a minute more passes with nothing said
    Then the players hear the host say nothing

  @D65
  Scenario: Three minutes of silence ends the game
    Given the host is thinking of a toaster
    When three minutes pass with nothing said
    Then the players hear the host say "I'll be here when you're back."
    And the game is over with no winner
