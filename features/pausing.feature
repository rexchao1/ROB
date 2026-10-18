Feature: Pausing a game
  "Pause" at any listen holds the game and its clock until "resume", a tap on
  the host's head or the page's Resume; the interrupted listen runs again. The
  lobby listens in longer windows once the table has been quiet. Built in the
  second commit without tests; this file describes what was built and binds
  nothing yet. Serves N1.

  Background:
    Given five friends are seated around a table with the host in the middle

  @D72
  Scenario: Pause holds the game's clock
    Given a game of Mafia is in its day phase, which began thirty seconds ago
    When someone says "pause"
    Then the players hear the host say "Paused. Say resume or tap my head when you're ready."
    And the players see the ring dim
    When one hundred seconds pass and someone says "resume"
    Then the players hear the host say "Okay, back to it."
    And the players hear the host say "One minute left." thirty seconds later

  @D110 @D72
  Scenario: Shut up and a bare stop pause the game too
    Given a game of Mafia is in its day phase
    When someone says "shut up"
    Then the players hear the host say "Paused. Say resume or tap my head when you're ready."
    When someone says "we're back"
    Then the players hear the host say "Okay, back to it."
    When someone says "okay stop"
    Then the players hear the host say "Paused. Say resume or tap my head when you're ready."

  @D110 @D93
  Scenario: Let's go is a yes, not a resume
    Given a game of Mafia is paused
    When someone says "let's go"
    Then the game stays paused
    When someone says "resume"
    Then the players hear the host say "Okay, back to it."

  @D72
  Scenario: A tap on the head resumes
    Given a game of Mafia is paused
    When someone taps the host's head
    Then the players hear the host say "Okay, back to it."

  @D72
  Scenario: The interrupted listen runs again
    Given a day phase vote has begun and the host has asked "Player one, who?"
    When Player one says "pause" and then "resume"
    Then the host listens for Player one's vote again

  @D72
  Scenario: Stop while paused stops the game
    Given a game of Mafia is paused
    When someone says "stop the game"
    Then the players hear the host say "Okay, stopping the game."
    And the game is over

  @D73
  Scenario: The lobby listens in longer windows after thirty quiet seconds
    Given no game is in progress and the host is listening for a game's name
    When thirty seconds pass with nothing heard
    Then the host's next listen lasts ten seconds
    When the microphone hears "hello there everyone"
    Then the host's next listen lasts four seconds
