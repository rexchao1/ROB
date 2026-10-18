Feature: Wordle, out loud
  The host picks a secret five-letter word; the table gets six guesses, said
  or spelled. The feedback is spoken short, the heard word first. Built in
  workstream X without tests; this file describes what was built and binds
  nothing yet. Serves N2.

  Background:
    Given one friend is seated in front of the host
    And no talk model answers the host
    And Wordle has been picked with the word "crane"

  @D69
  Scenario: A spoken guess is scored and the feedback names the letters
    When the player says "stare"
    Then the players hear the host say the word it heard, "Stare", first
    And the players hear the host name A and E as spot on and R as in there somewhere
    And one guess has been used

  @D69
  Scenario: A spelled guess is read letter by letter
    When the player says "s t a r e"
    Then the players hear the host say the word it heard, "Stare", first
    And one guess has been used

  @D70
  Scenario: A word the host does not know uses no guess
    Given the player has guessed "stare"
    When the player says "blorp"
    Then the players hear the host say "Blorp? Not in my dictionary. Try another."
    And one guess has been used

  @D70
  Scenario: Something that is not five letters uses no guess
    Given the player has guessed "stare"
    When the player says "is it cat"
    Then the players hear the host say "Didn't catch that. Spell it?"
    And one guess has been used

  @D70
  Scenario: A repeated word uses no guess
    Given the player has guessed "stare"
    When the player says "stare"
    Then the players hear the host say "Already tried stare."
    And one guess has been used

  @D69
  Scenario: A mishearing is undone with no
    Given the player has guessed "stare"
    When the player says "no, I said store"
    Then the players hear the host say the word it heard, "Store", first
    And one guess has been used
    And the board shows only "store"

  @D69
  Scenario: The last guess is confirmed before it counts
    Given the player has guessed "stare", "store", "slate", "snare" and "share"
    When the player says "shard"
    Then the players hear the host say "Shard, final answer?"
    When the player says "yes"
    Then the players hear the host say "Out of guesses. The word was crane." and a consoling line

  @D69
  Scenario: Guessing the word wins
    When the player says "crane"
    Then the players hear the host say "Crane. That's it!" and a congratulating line
    And the game is over with the players the winners

  @D71
  Scenario: Three players take turns
    Given three friends are seated around a table with the host in the middle
    And Wordle has been picked with the word "crane"
    When Player one says "stare"
    Then the players hear the host turn to Player two and say it is their turn

  @D71
  Scenario: What do we know gets a recap
    Given the player has guessed "stare"
    When the player says "what do we know"
    Then the players hear the host say "Here's what we know. A is third and E is last. R is in there somewhere. Ruled out: S, T."

  @D71
  Scenario: I give up reveals the word
    Given the player has guessed "stare"
    When the player says "i give up"
    Then the players hear the host say "Fine. The word was crane."
    And the game is over with no winner
