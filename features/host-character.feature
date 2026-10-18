Feature: The host's character
  ROB sounds like a person running game night: every line a talk model writes
  passes the house rules or is replaced by a scripted one, and the operator
  picks one of five personalities and five voices. The model only writes
  words (D14, D42). Built in workstreams W and X without tests; binding this
  file needs a fake talk model in test mode, which does not exist yet.
  Serves N1.

  Background:
    Given five friends are seated around a table with the host in the middle
    And a fake talk model answers the host

  @D74
  Scenario Outline: A model line that breaks the house rules is replaced by a scripted one
    Given the welcome has suggested Mafia and asked
    And the fake talk model will answer "<line>"
    When someone says "we just got back from the beach"
    Then the players hear a scripted reply, not "<line>"

    Examples:
      | line                                                                                                              |
      | Great question! I'd be happy to help you pick a game.                                                             |
      | Player three looks like they already know the rules.                                                              |
      | Wow, the beach, that sounds absolutely wonderful and relaxing, I hope the water was warm and the sand was soft too. |

  @D74
  Scenario: A model line that fits is said
    Given the welcome has suggested Mafia and asked
    And the fake talk model will answer "Beach day, nice. So, Mafia?"
    When someone says "we just got back from the beach"
    Then the players hear the host say "Beach day, nice. So, Mafia?"

  @D74
  Scenario: A slow model answer gets a scripted line
    Given the welcome has suggested Mafia and asked
    And the fake talk model will take six seconds to answer
    When someone says "we just got back from the beach"
    Then the players hear a scripted reply within five seconds

  @D75
  Scenario: Switching the personality applies to the next line and changes no ruled line
    Given a game of Mafia is in its night phase
    When the operator picks the spooky narrator on the dashboard
    Then the next line the model writes is asked for in the spooky narrator's style
    And the ring rests in the spooky narrator's colour
    And the players still hear the host say "Everyone, heads down." word for word

  @D77
  Scenario: Picking a voice turns the live voice on when a key is set
    Given an ElevenLabs key is set
    When the operator picks the voice Brian on the dashboard
    Then the lines not recorded are asked of ElevenLabs in Brian's voice
    And the pick is kept across a restart of the brain

  @D77
  Scenario: Without a key the pick is kept and the local voice speaks
    Given no ElevenLabs key is set
    When the operator picks the voice Brian on the dashboard
    Then the lines not recorded are spoken by the local voice
    And the pick is kept across a restart of the brain
