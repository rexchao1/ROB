# Plan: ROB does what he is told, right away

Rex, 2026-10-18. Make ROB obey hard commands at any moment, hear people while he talks, and fix the rough edges seen at the table.

## Goal

At the table, "stop the game", "go to sleep", "reset" and "pause" work the moment they are said or pressed, even mid-sentence, and nothing waits in a queue. ROB never freezes mid-game, his full face is always on the screen, the welcome is friendly and names the games, and Wavelength plays the new way.

## Constraints

- The robot's firmware beeps every time its microphone opens and cannot be changed from here (see the head-tap commit). Listening while talking must not make more beeps.
- The QNX referee shares `brain/lobby.py` and `brain/games/`: standard library only there.
- Another session is editing `brain/body.py`, `brain/dash/index.html`, `brain/dashboard.py`, `brain/settings.py`, `scripts/gateway.py` (the Mac microphone). Commit only our own hunks.

## Done when

Each step below is checked off with a focused test, and the full `npm run pytest` passes.

## Steps

1. [done] Head tap puts ROB to sleep between games.
2. [done] Dashboard Pause and Stop act before ROB's next line; a stopped game goes back to the game list awake.
3. [done] Find why ROB froze mid-game (gateway and brain logs), fix it.
4. [done] Hard commands at any moment: stop, sleep, reset, pause cut the current line off and act at once, by voice or button. Needs step 8 for voice mid-line.
5. [done] Head count: the camera sweep still runs, but a number someone says ("we're five") wins over the sweep at any point in the count.
6. [done] Welcome: warmer greeting that lists every game we play, and says Mafia needs at least four people.
7. [done] Wavelength, new version: everyone but one guesser sees the number (1 to 10) on a scale. The guesser calls on each player in turn with a category; that player names something in the category whose value fits the number; the guesser then says the number. Scoring: ten minus the distance, as now.
8. [done] Listen while talking (barge-in): ROB hears a command while his line plays and stops talking.
9. [done] Pi status light checks more often (`qnx/led/status-led.py`, POLL 3 s).
10. [done] ROB's full face always shows, from the first second (not a small yellow dot at start).

## Notes

- The yellow dot: until a game loaded its cards, the robot showed its stock face; the host now uploads ROB's face set (no cards) at startup on the real robot (`Host._setup`). Not checked on the robot yet.
- The welcome now says a greeting, then `lines.games_menu()` (every game, "Mafia needs at least four of you", the question). The talk model's greeting is told to ask nothing.
- Status light: POLL 1 s, address sweep every 10 s.
- The freeze (brain and gateway logs, 08:04 to 08:24): no hang in the brain; the robot dropped off Wi-Fi three times (keepalive ping timeouts) and the Mac's address changed networks mid-game. The same game also ignored "let's end this game please" and "go to sleep": both are hard commands now (`ears.hard_command`).
- On reconnect the gateway "auto-renders the idle avatar": the robot may show its stock face again until ROB's set is reloaded. Not handled yet.
- Barge-in works only on the Mac's microphone (now the default on a Mac). While a line plays, `Host._overhear` listens in 2 s pieces; a hard command not in ROB's own line cuts the line (`Body.play(abort=)`, the robot's line streamed at its pace, 1 s ahead) and waits at the front of the typed queue. Not tried on the robot yet.
- Wavelength (D117): the card is the number over "out of ten"; the spectrum list (`lines.SPECTRA`, editable on the dashboard's content tab) is no longer used by the game. ROB does not judge categories or answers, he gives each its listen.
