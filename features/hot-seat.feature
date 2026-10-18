Feature: Hot Seat
  The host names a category and turns to each player in turn: name something
  in it before the time runs out. Freeze, repeat or miss, and you are out; the
  last one in wins. Built in workstream X without tests; this file describes
  what was built and binds nothing yet. Serves N1 and N2.

  Background:
    Given three friends are seated around a table with the host in the middle
    And no talk model answers the host
    And Hot Seat has been picked with fruits as the first category

  @D66
  Scenario: The host names a category and turns to each player saying go
    When the first round begins
    Then the players hear the host say "Hot Seat! I say a category, you name one, fast. Freeze, repeat or miss, and you're out."
    And the players hear the host name the category Fruits
    And the players hear the host say "Player one, go!" with its head turned to Player one

  @D66
  Scenario Outline: The clock tightens each round
    Given every player has answered in time until round <round>
    When round <round> begins and the host says "Player one, go!"
    Then Player one has <seconds> seconds to answer

    Examples:
      | round | seconds |
      | one   | five    |
      | two   | four    |
      | three | three   |
      | four  | three   |

  @D66
  Scenario: Silence puts a player out
    Given Player one has said "apple"
    When Player two says nothing in time
    Then the players hear the host put Player two out
    And Player two is out for the rest of the game

  @D66
  Scenario: The last player in wins
    Given Players two and three are out
    Then the players hear the host say "Player one wins Hot Seat!"
    And the game is over with Player one the winner

  @D67
  Scenario: A repeat puts a player out
    Given Player one has said "apple"
    When Player two says "apple"
    Then the players hear the host put Player two out for a repeat

  @D67
  Scenario: An answer from another category's list is out offline
    Given Player one has said "apple"
    When Player two says "dog"
    Then the players hear the host put Player two out for an answer that does not count

  @D67
  Scenario: An answer on no list counts offline
    Given Player one has said "apple"
    When Player two says "rambutan"
    Then Player two is still in
    And the players hear the host say "Player three, go!"

  @D68
  Scenario: Twelve rounds with two still in is a tie
    Given Player three is out and Players one and two have answered in time for twelve rounds
    Then the players hear the host say "You're all too good at this. I'm calling it a tie."
    And the game is over with no winner

  @D106 @D104
  Scenario: A model's no makes the host ask the table
    Given a fake talk model answers the host with "no"
    And Player one has said "apple"
    When Player two says "rambutan"
    Then the players hear the host say "Rambutan? Does that count?"
    When the table says "yes"
    Then Player two is still in
