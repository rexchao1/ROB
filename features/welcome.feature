Feature: The welcome
  At its start, and whenever someone says "reset", the host greets the table
  as ROB and asks what they want to play or how many they are, listening
  straight away; it sweeps and says hello to each seat only when asked ("count
  us"), and suggests a game for a headcount it heard or saw, then talks with the
  group until they pick one (D38 to D43, revised 2026-10-18: no sweep on its
  own). Built in workstream W without tests; the scenarios below still describe
  the first build and bind nothing yet. Serves N1.

  Background:
    Given no talk model answers the host

  @D47 @D38 @D76
  Scenario: The welcome greets the table as ROB, counts, says hello to each seat and suggests Mafia
    Given five friends are seated around a table with the host in the middle
    When the host starts with the welcome
    Then the players hear the host greet them, name itself ROB and say it is looking
    And the players see the host sweep the whole table
    And the players hear the host say hello to Players one, two, three, four and five in turn, its head turned to each
    And the players hear the host suggest Mafia and end on a question

  @D48 @D38
  Scenario Outline: The suggestion follows the headcount
    Given <players> friends are seated around a table with the host in the middle
    When the host starts with the welcome
    Then the players hear the host suggest <game>

    Examples:
      | players | game             |
      | one     | Twenty Questions |
      | two     | Wavelength       |
      | three   | Imposter         |
      | four    | Imposter         |
      | five    | Mafia            |
      | six     | Mafia            |

  @D48
  Scenario: Nobody seen is asked to sit where the host can see them
    Given nobody is seated in front of the host
    When the host starts with the welcome
    Then the players hear the host say "I don't see anyone yet. Sit where I can see you and say reset."

  @D49 @D39
  Scenario: A yes within twenty seconds starts the suggested game on the welcome's count
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When someone says "sure" ten seconds later
    Then the players hear the host say "Let's play Mafia. One of you is the Mafia, one of you is the Doctor, and everyone else is a Villager."
    And the players see no second sweep and hear no count line

  @D49 @D39
  Scenario: Naming a game starts it at any time
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When someone says "let's play imposter"
    Then the players hear the host say "Let's play Imposter. Everyone gets the same secret word, except one of you: the Imposter."

  @D50 @D6
  Scenario: A game named with a headcount that disagrees waits for the count to agree
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When someone says "imposter with six people"
    Then the players hear the host say "I only see five. Who's hiding?"
    And no game has started

  @D94
  Scenario: A game's name inside other talk does not start it
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When someone says "that was a hot seat yesterday"
    Then no game has started
    And the players hear the host say "Hot Seat? Say yes to play it."

  @D51
  Scenario: A no gets the other games the count can play
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When someone says "nah, something else" ten seconds later
    Then the players hear the host offer Imposter, Wavelength, Hot Seat, Wordle and Twenty Questions and ask which

  @D52
  Scenario: Asking how a game goes gets its rules from the script
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When someone says "how do you play imposter?"
    Then the players hear the host say "In Imposter, everyone gets the same secret word except one person, the Imposter. You each give a one-word clue, then vote on who's faking it. Want to play it?"

  @D53
  Scenario: Asking what games there are lists the games built
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When someone says "what games do you have?"
    Then the players hear the host say "I've got Mafia, Imposter, Wavelength, Hot Seat, Wordle and Twenty Questions. With five of you I'd pick Mafia. Which one?"

  @D54
  Scenario: Room noise gets nothing
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When the microphone hears "thank you" thirty seconds later
    Then the players hear the host say nothing

  @D55
  Scenario: Small talk gets one short reply that steers back to the game
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When someone says "we just got back from the beach"
    Then the players hear one short reply from the host that names Mafia

  @D56
  Scenario: Silence gets two nudges, then a nap
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When twenty-five seconds pass with nothing said
    Then the players hear the host nudge them once
    When another twenty-five seconds pass with nothing said
    Then the players hear the host nudge them once more
    When another twenty-five seconds pass with nothing said
    Then the players hear the host say "I'll take a nap. Tap my head when you want me."
    And the host does not listen again until someone taps its head

  Scenario: A tap on the head wakes the napping host, which counts and suggests a game
    Given five friends are seated around a table with the host in the middle
    And the host is napping
    When someone taps the host's head
    Then the players hear the host say it is up
    And the players see the host sweep the whole table
    And the players hear the host suggest Mafia and end on a question

  @D57 @D38
  Scenario: Reset in the middle of a game ends it and the welcome comes again
    Given five friends are seated around a table with the host in the middle
    And a game of Mafia has started
    When someone says "reset"
    Then the players hear the host say "Okay, starting over."
    And the players hear the host greet them, name itself ROB and say it is looking

  @D58
  Scenario: Not now gets a line and the host naps
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When someone says "not now"
    Then the players hear the host say to tap its head when they are ready
    And the players hear no nudge in the next two minutes
    And the host does not listen again until someone taps its head

  @D59 @D6
  Scenario: A headcount above the host's gets a second look
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When someone says "there are six of us"
    Then the players hear the host say "I only see five. Who's hiding?"
    And the players see the host sweep the whole table again
    And the players hear the host say "Hmm, still five."

  @D59
  Scenario: A headcount below the host's gets no second look
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When someone says "we're four"
    Then the players hear the host say "I see five. Is someone just watching?"
    And the players see no second sweep

  @D60 @D43
  Scenario: The ring shows the listening colour while the host listens
    Given five friends are seated around a table with the host in the middle
    And the welcome has suggested Mafia and asked
    When the host listens
    Then the players see the ring in the listening colour
    When the host speaks
    Then the players see the ring in the mood's colour
