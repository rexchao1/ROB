Feature: Hosting the table
  The behaviors every game shares: counting the table, the private screen,
  heads down, and votes by voice. The host is the only non-player; its
  rulings stand. Serves N1.

  Background:
    Given five friends are seated around a table with the host in the middle

  @D96 @D5 @D1
  Scenario: The host counts the table and numbers the seats
    When someone says "let's play Mafia"
    Then the players see the host sweep the whole table, far left to far right
    And the players hear the host say "Five of you. Player one is on my left, then two, three, four, five going clockwise."

  @D6
  Scenario: A spoken count that disagrees with the host's count stops the start
    Given the host has counted five faces
    When someone says "there are six of us"
    Then the players hear the host say "I only see five. Who's hiding?"
    And no game has started

  @D89 @D6
  Scenario: A disagreement without a number gets a second sweep
    Given the host has counted five faces
    When someone says "there are six of us" and then "no, that's not right"
    Then the players hear the host say "I only see five. Who's hiding?"
    And the players see the host sweep the whole table again
    And no game has started

  @D89
  Scenario: After three disagreements the host gives up
    Given the host has counted five faces
    When someone says "there are six of us" three times over
    Then the players hear the host say "Let's try again when everyone's ready."
    And no game has started

  @D90
  Scenario: A count below the host's gets a second sweep
    Given the host has counted five faces
    When someone says "we're four"
    Then the players hear the host say "I see five. Is someone just watching?"
    And the players see the host sweep the whole table again

  @D98
  Scenario Outline: Each game has a smallest table
    Given <players> friends are seated around a table with the host in the middle
    When someone says "let's play <game>"
    Then the players hear the host say "<line>" and offer another game

    Examples:
      | players | game       | line                                      |
      | three   | Mafia      | Mafia needs at least four players.        |
      | two     | Imposter   | Imposter needs at least three players.    |
      | one     | Wavelength | Wavelength needs at least two players.    |
      | one     | Hot Seat   | Hot Seat needs at least two players.      |

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

  @D91
  Scenario: A vote that names two seats is asked for again
    Given a day phase vote has begun with five living players
    When the host asks "Player one, who?" and Player one says "players three and four"
    Then the players hear the host say "Player one, I didn't catch that. Who?"

  @D91
  Scenario: Me too is not a vote
    Given a day phase vote has begun with five living players
    When the host asks "Player two, who?" and Player two says "me too"
    Then the players hear the host say "Player two, I didn't catch that. Who?"

  @D97
  Scenario: A top seat short of a majority eliminates nobody
    Given a day phase vote has begun with four living players
    When the host turns to each living player in turn and asks "who?"
    And Players one and two say "four", Player three says "one" and Player four says "two"
    Then the players hear the host say "Two for Player four, one for Player one, one for Player two. Nobody has a majority. Nobody leaves."
    And every living player is still in

  @D97 @D11
  Scenario: Players sitting out do not count toward the majority
    Given a day phase vote has begun with five living players and Players four and five sitting out
    When the host turns to each player who may vote in turn and asks "who?"
    And Players one and two say "three" and Player three says "one"
    Then the players hear the host say "Two for Player three, one for Player one."
    And the players hear the host say "Player three, you're out."

  @D13
  Scenario: A tied vote eliminates nobody
    Given a day phase vote has begun with four living players
    When the host turns to each living player in turn and asks "who?"
    And two players say "two" and two players say "four"
    Then the players hear the host say "Two for Player two, two for Player four. It's a tie. Nobody leaves."
    And every living player is still in
