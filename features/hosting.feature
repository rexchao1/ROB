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

  @D116 @D6
  Scenario: A spoken count that disagrees with the host's count wins
    Given the host has counted five faces
    When someone says "there are six of us"
    Then the game starts with six players

  @D116 @D90
  Scenario: A count below the host's wins too
    Given the host has counted five faces
    When someone says "we're four"
    Then the game starts with four players

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

  @D109 @D7
  Scenario: Show me puts the card up for a few seconds without a close face
    Given a game has started and Player two is owed a role
    When the host turns to Player two and says "Player two, lean in."
    And nobody comes close and Player two says "show me"
    Then Player two sees their role on the host's screen for about four seconds
    And the screen is blank again afterwards

  @D109
  Scenario: Got it moves the deal on
    Given the host's screen is showing Player two their role
    When Player two says "got it"
    Then the players hear the host say "Player three, lean in."

  @D109
  Scenario: A lean-in nobody answers is asked again with the way round the camera
    Given a game has started and Player two is owed a role
    When the host turns to Player two and says "Player two, lean in."
    And ten seconds pass with nobody close and nothing said
    Then the players hear the host say "Player two, lean in close, or say show me."

  @D111
  Scenario: The speaker moves to the Mac and back by voice
    Given the host is listening between games
    When someone says "change your speaker to the Mac"
    Then the players hear the host say "Okay, I'll talk through the Mac." from the Mac
    When someone says "speaker robot"
    Then the players hear the host say "Okay, back to my own speaker." from the robot

  @D114
  Scenario: Say that again repeats the last line
    Given the host has just said "Everyone, heads down."
    When someone says "say that again"
    Then the players hear the host say "Everyone, heads down." once more
