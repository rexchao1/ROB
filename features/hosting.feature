Feature: Hosting the table
  The behaviors every game shares: counting the table, the private screen,
  heads down, and votes by voice. The host is the only non-player; its
  rulings stand. Serves N1.

  Background:
    Given five friends are seated around a table with the host in the middle

  @D5 @D1
  Scenario: The host counts the table and numbers the seats
    When someone says "let's play Mafia"
    Then the players see the host turn a full circle
    And the players hear the host say "Five of you. Player one is on my left, then two, three, four, five going clockwise."

  @D6
  Scenario: A spoken count that disagrees with the host's count stops the start
    Given the host has counted five faces
    When someone says "there are six of us"
    Then the players hear the host say "I only see five. Who's hiding?"
    And no game has started

  @D7
  Scenario: Leaning in shows one player their private screen
    Given a game has started and Player two is owed a role
    When the host turns to Player two and says "Player two, lean in."
    And only Player two's face is close to the host and facing it
    Then Player two sees their role on the host's screen

  @D8
  Scenario: A second face blanks the private screen
    Given the host's screen is showing Player two their role
    When a second face appears close beside Player two's
    Then within one second Player two sees a blank screen
    And the players hear the host say "One at a time."

  @D8
  Scenario: The private screen returns when the second face leaves
    Given the host's screen went blank because a second face appeared
    When only Player two's face is close to the host and facing it again
    Then Player two sees their role on the host's screen again

  @D9
  Scenario: A face up during heads down is warned by seat
    Given a night phase has begun and the host said "Everyone, heads down."
    And Player three has their head up
    When the host sweeps the table
    Then the players hear the host say "Player three, heads down means heads DOWN."
    And Player three has one warning this night

  @D10
  Scenario: Every head down means no warning
    Given a night phase has begun and the host said "Everyone, heads down."
    And every player has their head down
    When the host sweeps the table
    Then the players hear no player named
    And no player has a warning this night

  @D11
  Scenario: A second peek in the same night sits the player out for the round
    Given a night phase has begun and Player three has one warning this night
    When the host finds Player three's face up again
    Then the players hear the host say "Player three, you're sitting this round out."
    And Player three cannot whisper or vote until the next round begins

  @D12
  Scenario: A majority vote by voice eliminates a seat
    Given a day phase vote has begun with five living players
    When the host turns to each living player in turn and asks "who?"
    And Players one, two and three say "four" and Players four and five say "one"
    Then the players hear the host say "Three for Player four, two for Player one."
    And the players hear the host say "Player four, you're out."

  @D13
  Scenario: A tied vote eliminates nobody
    Given a day phase vote has begun with four living players
    When the host turns to each living player in turn and asks "who?"
    And two players say "two" and two players say "four"
    Then the players hear the host say "Two for Player two, two for Player four. It's a tie. Nobody leaves."
    And every living player is still in
