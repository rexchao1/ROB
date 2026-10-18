Feature: The operator's dashboard
  A page beside the table on a laptop or phone: the game as it happens, buttons
  that say what the table could have said, keys written once and never shown,
  tuning applied live. Built in workstream X and the dashboard plan without
  feature tests (the Python endpoints have unit tests); this file describes
  what was built and binds nothing yet. Serves N3.

  Background:
    Given five friends are seated around a table with the host in the middle
    And the operator's page is open

  @D78
  Scenario: The page shows the game as it happens
    Given a game of Mafia is in its night phase and Player three has one warning
    Then the page shows Mafia in its night phase with five seats
    And the page shows Player three with one warning
    And the page shows the last line the host said

  @D79
  Scenario: A button sends a phrase the robot understands
    Given a game of Mafia is in its day phase
    When the operator taps Vote now
    Then the host hears "let's vote" at its next listen
    And the players hear the host say "Okay, let's vote."

  @D79
  Scenario: Typed hearing replaces the microphone at the next listen
    Given a day phase vote has begun and the host has asked "Player one, who?"
    When the operator types "player four"
    Then Player one's vote counts for Player four

  @D80
  Scenario: A key entered on the page is never shown again
    When the operator enters an Anthropic API key
    Then the page reports the key as set and shows no value
    And the key is in the brain's environment file, readable by its owner only

  @D80
  Scenario: A key request from another site's page is refused
    When a page on another site posts a key to the brain
    Then the brain refuses it with a 403
    And the brain's environment file is unchanged

  @D81
  Scenario: A tuning change applies live and is saved
    When the operator sets the head pitch to thirty
    Then the robot's head is at pitch thirty
    And the brain reads pitch thirty at its next start

  @D81
  Scenario: The volume is set on the robot and never saved
    When the operator sets the volume to forty
    Then the robot's speaker is at volume forty
    And the saved settings do not hold a volume
