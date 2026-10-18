docket: 1

# Game master scoping interview. Visionary: linus (two builders). Interviewer: Claude (scope 5.1.1, gnt 0.11.0, docketry 0.1.0). Started 2026-10-18 ~01:30; build target 07:00-08:00, hard deadline 12:00. Compressed at the visionary's request.

N1 2026-10-18 [V] user 5
  need: I need my friends to be able to play games like Mafia, Imposter and Wavelength without allocating one person the role of game master and forcing them to sit out, so everyone is involved in the game, with human-like narration and banter [V]
# the visionary's words at Phase 0: "this is for friends to play games without having to allocate a single person the role of 'Gamemaster' and thus forcing them to sit out. This is allowing everyone to be involved in the game while integrating 'human-like' narration and banter." Beneficiary "user" = the group of friends at the table.

# Hardware stated in the invocation and quarantined for Phase 5½ (rule 3): a StackChan CoreS3 (camera, head, screen, mic, speaker) and a Raspberry Pi 5 as the brain, fully offline (the Pi as its own access point; local STT/TTS/LLM; ElevenLabs for pre-generated fixed lines). Pi RAM (4 GB vs 8 GB) unknown at this point.

D1 2026-10-18 [I>V]
  pre:   friends are seated around a table with the host in the middle or at one end [I>V]
  trig:  someone says which game to play [I+V]
  resp:  the host turns a full circle to see and count the players and numbers their seats in the order it finds them; a player may instead, or as well, say how many there are; when the host's count and the spoken number differ, the host says how many it saw and asks the group to confirm before the game starts [I+V]
  sib:   none -- failure case probed at readback
  serves: N1
  touches: none
# the visionary's words: "The host can 360 spin to view all the players and count, but someone can also say there are n amount of us." The conflict rule is the interviewer's, to be confirmed at readback.

D2 2026-10-18 [I+V]
  resp: three games are in scope, built in this order: Mafia/Werewolf first (night phase, private roles, day discussion, votes, eliminations, win check), then Imposter (one shared word, one player without it, one-word clues, a vote, a reveal), then Wavelength (a target number shown privately to the psychic, a clue, a group guess, a score); each game is its own behavior area and feature file [I+V]
  -> boundary
  serves: N1
  touches: D1
# the visionary selected all three with Mafia first; the forfeit layer was not selected pending the visionary's question "what does forfeit mean?"

D3 2026-10-18 [V]
  resp: no forfeit or drinking-game layer; the host never assigns penalties for losing a round [V]
  -> fence-declined forfeits
  serves: N1
  touches: D2

# Compressed Phase 2 + 3: the readback of common behaviors and three games with the interviewer's numbers was accepted ("All games should be there"); the demo game ruled as Mafia with Imposter as the short fallback. Entries below are interviewer-drafted and accepted, hence I>V; numbers carry why slots.

D4 2026-10-18 [I>V]
  resp: the demo for judges is one round of Mafia with the judges seated as players; Imposter is the fallback when a judge has only a minute; Wavelength is built last and shown only if asked [I>V]
  -> boundary
  serves: N1
  touches: D2

D5 2026-10-18 [I>V]
  pre:   five friends are seated around a table with the host in the middle [I>V]
  trig:  someone says `let's play Mafia` [I>V]
  resp:  the host turns a full circle, finds five faces, and says `Five of you. Player one is on my left, then two, three, four, five going clockwise.`; the seat numbers are what the host uses for the rest of the game [I>V]
  sib:   D6
  serves: N1
  touches: D1

D6 2026-10-18 [I>V] !
  pre:   five friends are seated; the host has counted five faces [I>V]
  trig:  someone says `there are six of us` [I>V]
  resp:  the game does not start: the host says `I only see five. Who's hiding?` and waits until the spoken number and its count agree [I>V]
  serves: N1
  touches: D1 D5

D7 2026-10-18 [I>V]
  pre:   a game has started and a player is owed something private: a role, a word, or a number [I>V]
  trig:  the host turns its head to that player and says `Player two, lean in.` and exactly one face is close to the host and facing it [I>V]
  resp:  the screen shows the private thing to that player and keeps showing it while exactly one close, facing face is in view [I>V]
  sib:   D8
  serves: N1
  touches: D5

D8 2026-10-18 [I>V] !
  pre:   the screen is showing Player two their role [I>V]
  trig:  a second face appears close beside the first [I>V]
  resp:  nothing private stays visible: the screen goes blank within one second and the host says `One at a time.`; the role returns when only one close face is in view again [I>V]
  why:   one second is the interviewer's number, accepted at readback; long enough to detect, short enough that nothing can be read [I>V]
  serves: N1
  touches: D7

D9 2026-10-18 [I>V]
  pre:   a night phase has begun and the host has said `Everyone, heads down.` [I>V]
  trig:  the host sweeps the table and finds a frontal face at seat three [I>V]
  resp:  the host says `Player three, heads down means heads DOWN.` and counts one warning for Player three [I>V]
  sib:   D10
  serves: N1
  touches: D5

D10 2026-10-18 [I>V] !
  pre:   a night phase has begun and every player has their head down [I>V]
  trig:  the host sweeps the table [I>V]
  resp:  nothing of the warning kind: no player is named and no warning is counted [I>V]
  serves: N1
  touches: D9

D11 2026-10-18 [I>V]
  pre:   Player three has already been warned once in this night phase [I>V]
  trig:  the host finds Player three's face up again in the same night phase [I>V]
  resp:  Player three sits out the rest of this round of play, not the game: they neither whisper nor vote until the next round begins, and the host says so [I>V]
  sib:   D10
  serves: N1
  touches: D9

D12 2026-10-18 [I>V]
  pre:   a day phase vote has begun with five living players [I>V]
  trig:  the host turns to each living player in turn, says `Player one, who?`, and each says a seat number [I>V]
  resp:  the host repeats the tally out loud, and a seat named by a majority of the living players is eliminated; the host announces it [I>V]
  sib:   D13
  serves: N1
  touches: D5

D13 2026-10-18 [I>V] !
  pre:   a day phase vote has begun with four living players [I>V]
  trig:  two players name seat two and two name seat four [I>V]
  resp:  nobody is eliminated: the host says the tally and `It's a tie. Nobody leaves.` [I>V]
  serves: N1
  touches: D12

D14 2026-10-18 [I>V]
  resp: every host line carries flavor from a scripted set with variations, and a local model may add a quip; nothing the host says changes the rules or the state of a game, which are fixed in code [I>V]
  -> structural
  serves: N1
  touches: none

D15 2026-10-18 [I>V]
  pre:   Mafia with five players: one Mafia, one Doctor, three Villagers; with seven or more players, two Mafia [I>V]
  trig:  roles are dealt [I>V]
  resp:  each player receives their role through the private screen, one at a time, in seat order [I>V]
  why:   the role counts are the interviewer's, from the common five-player rule set, accepted at readback [I>V]
  sib:   none -- dealing has no failure case beyond D8
  serves: N1
  touches: D7

D16 2026-10-18 [I>V]
  pre:   Mafia, night, heads down; Player one is the Mafia and Player five is the Doctor [I>V]
  trig:  the host says `Mafia, whisper your target.` and Player one quietly says `Player four`; the host says `Doctor, whisper who you save.` and Player five quietly says `Player two` [I>V]
  resp:  at morning the host says `Player four was killed in the night.`; Player four is out and stays silent for the rest of the game [I>V]
  sib:   D17
  serves: N1
  touches: D9 D15

D17 2026-10-18 [I>V] !
  pre:   Mafia, night, as in D16 [I>V]
  trig:  the Mafia whispers `Player four` and the Doctor whispers `Player four` [I>V]
  resp:  nothing of the killing kind: at morning the host says `Nobody died last night.` and every player is still in [I>V]
  serves: N1
  touches: D16

D18 2026-10-18 [I>V]
  pre:   Mafia, morning, after the night's result [I>V]
  trig:  the day phase begins [I>V]
  resp:  the host times {2 minutes} of discussion, says `One minute left.` at the halfway point, then runs the vote; the eliminated player's role is revealed out loud [I>V]
  why:   {2 minutes} is the interviewer's number, accepted at readback; long enough to argue, short enough for a table demo [I>V]
  sib:   none -- the timer has no failure case
  spread: Discussion time runs by the clock
  serves: N1
  touches: D12

D19 2026-10-18 [I>V]
  pre:   Mafia in progress [I>V]
  trig:  after any elimination the number of Mafia equals the number of non-Mafia players still in, or no Mafia is left [I>V]
  resp:  the host announces `The Mafia win.` in the first case and `The village wins.` in the second, and the game ends [I>V]
  sib:   none -- the win check has no failure case
  serves: N1
  touches: D12 D16

D20 2026-10-18 [I>V]
  pre:   Imposter with five players; the word is `beach`; Player three is the Imposter [I>V]
  trig:  words are dealt through the private screen, then each player in seat order gives one word as a clue with the host turning to them, then a vote runs [I>V]
  resp:  every player but Player three saw `beach` and Player three saw `IMPOSTER`; if Player three is voted out the host says `Player three was the Imposter.`; if anyone else is voted out the host says `The Imposter survives. It was Player three.` [I>V]
  sib:   none -- failure cases are D8 and D13
  serves: N1
  touches: D7 D12

D21 2026-10-18 [I>V]
  pre:   Wavelength with five players; Player two is the psychic for this round; the spectrum is `cold - hot` [I>V]
  trig:  Player two leans in and sees the target `7` on a scale of one to ten, gives a clue, the group discusses, and someone says `six` [I>V]
  resp:  the host scores the round as ten minus the distance between the target and the guess, says `Nine points.`, keeps a running total, rotates the psychic, and after three rounds announces the total [I>V]
  why:   the one-to-ten scale, the scoring rule and three rounds are the interviewer's, accepted at readback [I>V]
  sib:   none -- failure cases are D8 and an unparsed guess probed by outline
  spread: A spoken guess scores by distance from the target
  serves: N1
  touches: D7

D22 2026-10-18 [V]
  resp: the checklist sweep was declined to keep the interview short; every checklist category is declined in bulk, unprobed [V]
  -> fence-declined checklist-sweep
  serves: N1
  touches: none

D23 2026-10-18 [V]
  resp: the adversarial pushback pass was declined to keep the interview short [V]
  -> fence-declined adversarial-pass
  serves: N1
  touches: D22

D24 2026-10-18 [V]
  resp: the boundary question was not put; the visionary asked for the shortest interview, so no assumptions were offered by the visionary [V]
  -> boundary
  serves: N1
  touches: none

# Named assumptions the interviewer can see, tagged I until ratified at the read.

D25 2026-10-18 [I]
  pre:   players stay in their seats for the whole game and the table is lit well enough for faces to be found at a metre or so [I]
  trig:  a player changes seats, or the room is too dark to find faces [I]
  resp:  seat numbers stop matching people and the host may miscount or mis-address; reopens if the demo table needs a lamp or players move [I]
  -> fence-assumption seats-and-light
  serves: N1
  touches: D5 D9

D26 2026-10-18 [I]
  pre:   a whisper at night reaches the host's microphone and not the other players [I]
  trig:  a whisper is overheard, or the host cannot make it out [I]
  resp:  if overheard the night action is no longer secret; if not made out the host asks once more, quietly; reopens if either happens at the demo table [I]
  -> fence-assumption whispers-are-private
  serves: N1
  touches: D16

D27 2026-10-18 [I]
  pre:   the host is the only non-player and nobody disputes what it saw [I]
  trig:  a player disputes a warning or a tally [I]
  resp:  the host repeats what it saw and the tally and does not change its ruling; the group may restart the round by saying so; reopens if disputes are frequent at the demo [I]
  -> fence-assumption host-rulings-stand
  serves: N1
  touches: D9 D12

D28 2026-10-18 [I>V]
  resp: the host runs fully offline: the brain is its own wireless network, speech-to-text, text-to-speech and the banter model all run on the brain, and nothing in a game needs the internet [I>V]
  -> structural
  serves: N1
  touches: D14

D29 2026-10-18 [V]
  resp: the body is the StackChan `CoreS3` (camera, turning head, screen, microphone, speaker) and the brain is a `Raspberry Pi 5`; no laptop, no other camera and no other device is part of the product [V]
  -> means N1
  serves: N1
  touches: D28

D30 2026-10-18 [I>V]
  resp: the host's fixed lines are generated once with ElevenLabs and cached on the brain so that the voice at play time is ElevenLabs while the box is offline; lines that must be composed live use a local text-to-speech voice [I>V]
  -> means N1
  serves: N1
  touches: D14 D28

D31 2026-10-18 [I>V]
  resp: the brain runs Raspberry Pi OS, not QNX: the offline speech and language pieces exist for it and not for QNX, and the QNX prize is the accepted price [I>V]
  -> structural
  serves: N1
  touches: D28 D29

D32 2026-10-18 [I>V]
  resp: when the build runs short the cut order is: Wavelength, then the local banter model (scripted lines only), then Imposter; Mafia with the private screen, heads-down catching and voice votes is never cut [I>V]
  -> structural
  serves: N1
  touches: D2 D4 D14

D33 2026-10-18 [I>V]
  resp: Wavelength, the live banter model and Imposter are deferred in that order when the build runs short, per the cut order of D32; each reopens as time allows and anything unbuilt at the deadline stays recorded on the fence [I>V]
  -> fence-deferred cut-order
  serves: N1
  touches: D32

# Handoff read, 2026-10-18 ~02:40. The visionary read the contract and answered "yes ratify". Ratifications under [V], then the signature naming the last entry in effect.

D34 2026-10-18 [V] ratifies D25
  resp: players stay seated and the table is lit enough to find faces at about a metre [V]
  -> boundary
  serves: N1
  touches: D25

D35 2026-10-18 [V] ratifies D26
  resp: a night whisper reaches the host's microphone and not the other players [V]
  -> boundary
  serves: N1
  touches: D26

D36 2026-10-18 [V] ratifies D27
  resp: the host's rulings on warnings and tallies stand; the group may restart a round by saying so [V]
  -> boundary
  serves: N1
  touches: D27

D37 2026-10-18 [V] signs D36
  resp: the visionary read the contract (USER-NEEDS.md, the four feature files, OUT-OF-SCOPE.md) and signed it with no corrections [V]
  -> boundary
  serves: N1
  touches: none

# Workstream W, 2026-10-18 ~04:00. Rex took the build over and is the visionary from here. He asked for a welcome ("if we say reset, it'll start this welcome again and it'll say hey, what's up everyone, and then it'll count the people and it'll look at them and then it'll say, you know, since there's like four people, I recommend this game. But they could always say like yeah, no, we wanna play imposter with six people"), and answered: keep seat numbers, no names; cloud talk with an Anthropic key and a Gemini option; make it sound human, not AI; head pats and other commands later. The entries below record those answers as relayed in the session; the lines and timings are the build's (DESIGN.md, brain/games/welcome.py). Tests for this workstream were skipped at Rex's request: he is trying it by hand.

D38 2026-10-18 [V]
  resp: the host welcomes the table when it starts and whenever someone says `reset`, `start over` or `restart`, which also ends a game in progress: it greets everyone and says it is looking, counts with the full turn, turns to each seat and greets it by number, and suggests a game for the headcount, Wavelength for two, Imposter for three or four, Mafia for five or more, asking whether they want it or another [V]
  -> structural
  serves: N1
  touches: D5 D27

D39 2026-10-18 [V]
  resp: after the suggestion a yes starts the suggested game and a game's name starts that game; a headcount said with it goes through the count check of D6, because the host cannot deal secret cards to people it has not seen; questions and small talk get a short playful reply, background noise gets none, and silence gets a nudge or two before the host waits quietly [V]
  -> structural
  serves: N1
  touches: D6 D38

D40 2026-10-18 [V] amends D28
  resp: every game runs without the internet: the brain is its own wireless network, speech-to-text and a local text-to-speech voice run on the brain, and nothing in a game needs the internet; only the host's talk may use it: its small-talk replies and quips come from a cloud model when one is set up, Anthropic's Claude by default with Google's Gemini as the option, and with no key, no internet or a slow answer the host says scripted lines [V]
  -> structural
  serves: N1
  touches: D14 D28 D39

D41 2026-10-18 [V] amends D30
  resp: the host's fixed lines are generated once with ElevenLabs and cached on the brain; a line composed at play time is spoken live by ElevenLabs when a key and the internet are there, and by the local voice otherwise [V]
  -> means N1
  serves: N1
  touches: D30 D40

D42 2026-10-18 [V] amends D14
  resp: every host line carries flavor from a scripted set with variations, and a model may add a quip or a line of small talk; a model only writes words, and nothing the host says changes the rules, the count or the state of a game, which are fixed in code; the host sounds like a person running game night, not an assistant: one to three short spoken sentences, casual and playful, answering what was said before steering back to a game, never revealing a secret role or word, never inventing a rule, always in character as the robot host [V]
  -> structural
  serves: N1
  touches: D14 D40

D43 2026-10-18 [V]
  resp: seats keep their numbers and the host uses no names; while the host listens its light ring shows a steady listening colour, back to the mood's colour when it speaks [V]
  -> structural
  serves: N1
  touches: D5 D38

D44 2026-10-18 [V]
  resp: head pats, `louder` and `quieter`, sound and mood, playing again with scores, and players' names are for later, not this build [V]
  -> fence-deferred welcome-extras
  serves: N1
  touches: D38 D43

# Review R, 2026-10-18 ~06:00 PDT (Linus, a cold review of the ROB repo on a branch). Workstreams Q, N, W, X and the pause work were built ahead of the docket: BUILD-PLAN.md recorded Rex's rulings for them and said they would be docketed from D46 when X1 ran; X1 was skipped. The entries below transcribe those recorded rulings ([I>V]: Rex's words as the build wrote them down, built as written; the source section is named in each note) and, where no ruling was recorded, what the code does ([I]: inferred from the code, unratified; the strict lint lists every one of these as a finding until Rex ratifies or vetoes it). Nothing here changes code. The feature files added with these entries (welcome, twenty-questions, hot-seat, wordle, pausing, host-character, operator-dashboard) describe the built behaviour and bind nothing yet: they sit in the wip register.

N2 2026-10-18 [I] user 3
  need: I need the host to be worth playing with when there are only one or two of us, not only when there are enough for Mafia [I]
# Inferred from Rex's X rulings (BUILD-PLAN.md, Workstream X: 20 Questions for one player, Wordle for one or more, Hot Seat for two or more) and the welcome's suggestion of Twenty Questions for one player. Rex has not stated this need in his own words.

N3 2026-10-18 [I] operator 3
  need: I need to see what the host is doing and rescue a game from beside the table when its ears or its eyes fail, without restarting the brain [I]
# Inferred from DASHBOARD-PLAN.md's goal line ("lets the operator rescue a game when the ears or the eyes fail, and changes the tuning numbers ... without restarting the brain") and Rex's answers at 03:20 and 03:55. The operator is Rex or a teammate at the demo, not a player.

D45 2026-10-18 [I>V] amends D29
  resp: the body is the StackChan K151 running the stackchan-mcp firmware and gateway; the brain is two boxes: a Mac that runs the gateway, speech-to-text, the voice, vision and the host, and a Raspberry Pi running QNX that runs the rules as the referee and hosts the game's own Wi-Fi network; no phone and no second camera are part of the product [I>V]
  -> means N1
  serves: N1
  touches: D28 D29
# BUILD-PLAN.md, "Rex's decisions, 2026-10-18 00:15 (these reverse D29 and D31; Linus to be told)". D29 was Linus's [V] ruling; this records Rex's reversal as the build carried it out. Linus is the reviewer here and has not yet ratified it.

D46 2026-10-18 [I>V] amends D31
  resp: the Pi runs QNX and stays on it: it is the referee (the games, the lines, the parsing and the lobby, standard library Python only) and the access point; speech-to-text, the voice and vision, which have no QNX port, run on the Mac and serve the Table to the referee over HTTP [I>V]
  -> structural
  serves: N1
  touches: D31 D45
# BUILD-PLAN.md, the same decision; the QNX prize is back in reach, which D31 had given up.

# The welcome (D38 to D43 rule it; the lines and timings below are the build's, brain/games/welcome.py and brain/lines.py).

D47 2026-10-18 [I]
  pre:   five friends are seated and the host has just started, or someone has said `reset` [I]
  trig:  the welcome begins [I]
  resp:  the host says one of its greetings naming itself ROB and saying it is looking, counts with the full sweep, turns to each seat in order and greets it by number, then suggests Mafia for five and ends on a question [I]
  sib:   D56
  serves: N1
  touches: D5 D38 D43

D48 2026-10-18 [I>V]
  pre:   the welcome has counted the table [I>V]
  trig:  the host suggests a game for the headcount of {one | two | three or four | five or more} [I>V]
  resp:  one player is offered Twenty Questions, two Wavelength, three or four Imposter, five or more Mafia; a game not yet built gives way to the first built one the count can play; nobody seen gets `I don't see anyone yet. Sit where I can see you and say reset.` [I>V]
  spread: The suggestion follows the headcount
  sib:   none -- a count below every minimum is answered with a line, not a failure
  serves: N1 N2
  touches: D38 D47
# D38 (Rex) rules the three table sizes; Twenty Questions for one player is from Workstream X's "Suggestions and minimums"; the nobody-seen line is the build's.

D49 2026-10-18 [I]
  pre:   the welcome has suggested a game and asked [I>V]
  trig:  someone says yes within twenty seconds of the question, or names any game at any time [I>V]
  resp:  that game starts on the welcome's count when the count is less than two minutes old: no second sweep and no count line; a game named later is counted again [I>V]
  why:   twenty seconds for a short answer and two minutes for a fresh count are the build's numbers (brain/games/common.py Options), not Rex's [I]
  sib:   D50
  serves: N1
  touches: D39 D47

D50 2026-10-18 [I>V] !
  pre:   the welcome has counted five [I>V]
  trig:  someone names a game with a headcount that disagrees, `imposter with six people` [I>V]
  resp:  no game starts: the count check of D6 runs, the host says `I only see five. Who's hiding?` and the game waits until the spoken number and its count agree [I>V]
  serves: N1
  touches: D6 D39 D49
# D39 (Rex): "the host cannot deal secret cards to people it has not seen".

D51 2026-10-18 [I]
  pre:   the welcome has suggested a game and asked [I]
  trig:  someone says no, or asks for something else, within twenty seconds [I]
  resp:  the host names the other games the count can play and asks which; when the count can play only the suggested game it says so [I]
  sib:   none -- a no has no failure case; silence is D56
  serves: N1
  touches: D39 D48

D52 2026-10-18 [I]
  pre:   the welcome is listening [I]
  trig:  someone asks how a game is played, naming it [I]
  resp:  the host says that game's rules from the script, never from a model, and asks `Want to play it?`; a game registered without a rules line gets a line that states no rule [I]
  sib:   none -- the rules come from a fixed script, there is no wrong answer to probe
  serves: N1
  touches: D14 D39 D42

D53 2026-10-18 [I]
  pre:   the welcome is listening [I]
  trig:  someone asks what games the host has [I]
  resp:  the host lists every game built and names its pick for the count [I]
  sib:   none -- a fixed list, no failure case
  serves: N1
  touches: D39 D48

D54 2026-10-18 [I] !
  pre:   the welcome is listening [I]
  trig:  the microphone hears room noise: fewer than three real words with no question pending, unless it is a greeting, a short question to the host or its name (`hi`, `what's up`, `how are you`, `hey rob`); or one of the transcriber's phantoms such as `thank you` or `you`; or transcription junk, one short phrase over and over or a run-on past forty words [I]
  resp:  nothing of the reply kind: the host says nothing and keeps listening [I]
  serves: N1
  touches: D39
# D39 (Rex): "background noise gets none"; the three-word floor and the phantom list are the build's (DESIGN.md, chosen).

D55 2026-10-18 [I]
  pre:   the welcome is listening and no talk model answers [I>V]
  trig:  someone says something to the host that is neither a game, a count, a yes, a no nor a question about the games [I>V]
  resp:  the host answers what was said (a hello, a question, a joke asked for) and steers back to picking a game when it fits, from the script when no model answers; at most one reply a second, with no cap, since the nap after two unanswered nudges ends idle talk [I>V]
  why:   the gap is the build's number (brain/games/common.py Options), not Rex's [I]
  sib:   D54
  serves: N1
  touches: D39 D40 D42

D56 2026-10-18 [I] !
  pre:   the welcome has asked its question [I>V]
  trig:  nobody says anything to the host for twenty-five seconds, twice [I>V]
  resp:  nothing of the chatter kind: one nudge after each quiet stretch, two in all, then the host waits quietly for a game's name and says nothing more [I>V]
  why:   twenty-five seconds and two nudges are the build's numbers (brain/games/common.py Options), not Rex's [I]
  serves: N1
  touches: D39 D47

D57 2026-10-18 [I>V]
  pre:   a game is in progress [I>V]
  trig:  someone says `reset`, `start over` or `restart` at any listen [I>V]
  resp:  the game ends where it is with `Okay, starting over.` and the welcome begins again [I>V]
  sib:   none -- D27 already allows the group to restart by saying so
  serves: N1
  touches: D27 D38 D47

D58 2026-10-18 [I]
  pre:   the welcome has asked its question [I]
  trig:  someone says `not now`, `give us a minute` or asks to stop [I]
  resp:  the host says it will be there and waits quietly for a game's name [I]
  sib:   none -- a wait has no failure case
  serves: N1
  touches: D39 D56

D59 2026-10-18 [I]
  pre:   the welcome has counted five [I]
  trig:  someone says a headcount above it, `there are six of us` [I]
  resp:  the host says `I only see five. Who's hiding?`, waits a moment and counts again, says what it sees now, greets any new seat and suggests again; a count below the host's gets `I see five. Is someone just watching?` and no second look; a count that agrees gets `Yep, five.` [I]
  sib:   none -- the mismatch itself is the failure case, D6
  serves: N1
  touches: D6 D39 D47

D60 2026-10-18 [I]
  pre:   the host is awake [I]
  trig:  the host listens, and then speaks [I]
  resp:  the ring shows the steady listening colour for the whole listen, and the mood's colour again as soon as the host speaks or the mood changes [I]
  sib:   none -- the ring is cosmetic, D43 rules it, this binds it
  serves: N1
  touches: D43

# Workstream X (BUILD-PLAN.md, "Rex's rulings" and "House rules for the host"): three more games and the host's character, built 2026-10-18 ~04:45 without tests.

D61 2026-10-18 [I>V]
  pre:   one player, or a group playing as one, has picked Twenty Questions [I>V]
  trig:  the game begins [I>V]
  resp:  the host asks which way round, `Twenty Questions. Want me to guess yours, or you guess mine?`, and either works; left to the host it picks one and says which [I>V]
  sib:   none -- either answer is a valid way round; silence is D65
  serves: N2
  touches: D48

D62 2026-10-18 [I>V]
  pre:   Twenty Questions with the host guessing; the player has thought of something and said ready [I>V]
  trig:  the host asks yes-or-no questions, counting each, and may guess at any point, a guess using a question [I>V]
  resp:  a right guess ends the game with the host the winner; the twentieth question used up without one ends it with the player the winner, and the host asks what it was [I>V]
  sib:   none -- a wrong guess is a used question, not a failure case
  serves: N2
  touches: D61

D63 2026-10-18 [I>V]
  pre:   Twenty Questions with the player guessing; code picked the secret from the built-in table before the first question and it never changes [I>V]
  trig:  the player asks a yes-or-no question, asks for a hint, guesses, or gives up [I>V]
  resp:  a question about a trait the table knows is answered from the table, `yes`, `no` or `sort of`, and counts; a question the host cannot answer gets `Can't answer that one. Try another way.` and does not count; a hint costs a question; a right guess wins; `I give up`, or the twentieth question used, reveals the secret [I>V]
  sib:   none -- the uncounted answer is the only failure case and is in resp
  serves: N2
  touches: D14 D42 D61

D64 2026-10-18 [I]
  pre:   Twenty Questions is being played [I>V]
  trig:  the question count reaches {ten | fifteen | nineteen} [I>V]
  resp:  the host counts out loud only at those moments: halfway, five left, the last one, and the mood turns tense for the last five [I>V]
  why:   Rex's house rule ("counts out loud only at the moments that matter: halfway, five left, the last one"); the exact lines are the build's [I]
  spread: The host counts out loud only at the moments that matter
  sib:   none -- no count line at any other moment is the rule itself
  serves: N2
  touches: D42 D62 D63

D65 2026-10-18 [I]
  pre:   Twenty Questions is waiting for the player [I>V]
  trig:  nobody says anything for eight seconds, then twenty, then three minutes [I>V]
  resp:  a nudge at eight seconds, `Take your time.` at twenty (an offer of a hint instead when the host holds the secret), then quiet; `hold on` or `wait` holds the nudges; after three minutes of silence the host says `I'll be here when you're back.` and the game ends with no winner [I>V]
  why:   eight and twenty seconds are Rex's house rule ("Reads the room"); three minutes is the build's number [I]
  sib:   none -- silence handling is itself the failure case
  serves: N2
  touches: D39 D61

D66 2026-10-18 [I>V]
  pre:   two or more players have picked Hot Seat [I>V]
  trig:  each round the host names a category and turns to each player still in, left to right, saying `Player two, go!` [I>V]
  resp:  the player names something in the category before the time runs out, {5 seconds} in the first round, a second less each round, never under {3 seconds}; silence, a pass, a repeat or an answer that does not count puts that player out; the last one in wins; a new category comes each round [I>V]
  why:   the five seconds, the second less each round and the floor of three are Rex's numbers (BUILD-PLAN.md, Workstream X) [I>V]
  spread: The clock tightens each round
  sib:   D67
  serves: N1 N2
  touches: D12 D48

D67 2026-10-18 [I] !
  pre:   Hot Seat, the category is fruits [I]
  trig:  a player says a word from another category's list, or repeats one already said this round [I]
  resp:  nothing of the point kind: `Already taken.` or `Nope, doesn't count.`, and that player is out; offline an answer on no list counts unless it is on another category's list; with a talk model the model judges yes or no [I]
  serves: N2
  touches: D14 D42 D66
# The build's judging rule (brain/games/hotseat.py). The model judging an elimination is in tension with D14 and D42 (a model never decides a rule); flagged for Rex in the review.

D68 2026-10-18 [I]
  pre:   Hot Seat with two or more still in [I]
  trig:  twelve rounds have been played [I]
  resp:  the host calls it a tie and the game ends with no winner [I]
  sib:   none -- a cap on rounds has no failure case
  serves: N2
  touches: D66

D69 2026-10-18 [I>V]
  pre:   one or more players have picked Wordle [I>V]
  trig:  the host picks a secret five-letter word from its built-in list and the table says or spells guesses, six at most [I>V]
  resp:  a guess the host knows is scored and the feedback is spoken short, the heard word first, then which letters are spot on and which are in there somewhere; a word not on the host's list, or not five letters, uses no guess; `no` right after the feedback undoes a misheard guess for free; the sixth guess is confirmed before it counts; the word guessed wins, six used reveals it [I>V]
  sib:   D70
  serves: N2
  touches: D48
# Rex's ruling (Workstream X, "Wordle") as built, except the grid: Rex asked for it on the robot's screen; the build puts it on the dashboard only (D84).

D70 2026-10-18 [I] !
  pre:   Wordle, one guess already made [I]
  trig:  someone says a word that is not five letters, or a five-letter word the host does not know, or repeats a word already tried [I]
  resp:  nothing of the scoring kind: `Not in my dictionary. Try another.`, `Didn't catch that. Spell it?` or `Already tried crane.`, and the guess count does not move [I]
  serves: N2
  touches: D69

D71 2026-10-18 [I]
  pre:   Wordle with three players [I]
  trig:  a guess is scored [I]
  resp:  the seats take turns in order, the host turning to the next seat and saying whose turn it is, though anyone may say the guess; `what do we know` gets a recap of the board in a few short sentences; `I give up` reveals the word [I]
  sib:   none -- turn order is a default Rex can change, not a failure case
  serves: N2
  touches: D69

# Pause, a quieter lobby and ROB (DASHBOARD-PLAN.md, "Pause, a quieter lobby, simpler settings (Rex, 05:10)" and "ROB (Rex, 05:20)"), built in the second commit, untested.

D72 2026-10-18 [I>V]
  pre:   a game is in progress [I>V]
  trig:  someone says `pause` or `hold the game` at any listen [I>V]
  resp:  the host holds the game: it says `Paused. Say resume or put your hand on top of my head when you're ready.`, the ring dims, the game's clock stops so a day timer does not run out, and it listens in ten-second windows; `resume`, `we're back`, `keep going`, a tap on its head or the page's Resume carries on with `Okay, back to it.` and the listen that was interrupted runs again; `stop the game` or `reset` said while paused is heard by the game [I>V]
  sib:   none -- a stop or reset while paused is handled in resp
  serves: N1
  touches: D27 D57
# Rex, 05:10: "pause should hold the game until he says so or taps the robot". The ten-second window is the build's (the robot chimes each time its microphone opens).

D73 2026-10-18 [I]
  pre:   no game is in progress and the host is listening for a game's name [I>V]
  trig:  thirty seconds pass with nothing heard [I>V]
  resp:  the lobby listens in ten-second windows instead of four-second ones, so the robot's microphone chime comes less often, and goes back to short windows at the next word [I>V]
  why:   thirty seconds and ten seconds are the build's numbers (brain/lobby.py) [I]
  sib:   none -- a longer listen has no failure case
  serves: N1
  touches: D39

# The host's character (BUILD-PLAN.md, Workstream X, "House rules for the host" and "Personalities"; DASHBOARD-PLAN.md, "ROB").

D74 2026-10-18 [I>V]
  pre:   a talk model is set up and the host asks it for a line [I>V]
  trig:  the model's line comes back [I>V]
  resp:  the line is said only if it fits the house rules: one line, two sentences at most, about fifteen words, no assistant phrases (`great question`, `I'd be happy to`, `certainly`, `absolutely`, `as an AI`, `let's dive in`, `feel free`), no emoji, no stage directions, at most one exclamation mark, and no seat named; a line that does not fit is replaced by a scripted one, and so is a slow answer [I>V]
  sib:   none -- the replacement is the failure case and is in resp
  serves: N1
  touches: D14 D40 D42
# Rex's house rules as the build enforces them in brain/talk.py fit(). "Teases the move, never the person" and "stays quiet while the group talks among themselves" are prompt instructions, not checks.

D75 2026-10-18 [I>V]
  pre:   the host is running [I>V]
  trig:  the operator picks one of six personalities (friendly, sarcastic, energetic, calm, dramatic, grumpy) on the dashboard [I>V]
  resp:  the personality changes how the talk model writes, the ring's resting colour and which voice speaks, from the next line on; it never changes a rule or a line the feature files assert; friendly is the default [I>V]
  sib:   none -- a pick from a fixed list has no failure case
  serves: N1 N3
  touches: D42 D74

D76 2026-10-18 [I>V]
  pre:   the host is running [I>V]
  trig:  the welcome greets the table, or someone asks who the host is [I>V]
  resp:  the host is named ROB: its greetings say so and its talk says it only when asked [I>V]
  sib:   none -- a name has no failure case
  serves: N1
  touches: D38 D47

D77 2026-10-18 [I>V]
  pre:   the host is running with an ElevenLabs key set [I>V]
  trig:  the operator picks one of five voices (Chris, Jessica, George, Charlie, Brian) on the dashboard [I>V]
  resp:  the lines not recorded are spoken live in that voice, and picking one turns the live voice on; the personality and the voice are kept across starts in a file beside the brain [I>V]
  sib:   none -- without a key the pick is kept and Piper speaks, which resp allows
  serves: N1 N3
  touches: D41 D75

# The operator dashboard (DASHBOARD-PLAN.md: Rex's answers 03:20, "Two screens" 03:55, "simpler settings" 05:10).

D78 2026-10-18 [I>V]
  pre:   the brain is running and a laptop or phone on the same network opens its page [I>V]
  trig:  the operator looks at the page during a game [I>V]
  resp:  the page shows the game as it happens: the phase, the seats, who is in and out, the warnings, the last line said and heard, the Wordle board and the Twenty Questions count; it polls about once a second and needs nothing from the internet [I>V]
  sib:   none -- a read-only view has no failure case
  serves: N3
  touches: D45

D79 2026-10-18 [I>V]
  pre:   the operator's page is open during a game [I>V]
  trig:  the operator taps a button or types what the table said [I>V]
  resp:  every in-game button is a phrase the robot already understands by voice, sent as typed hearing; typed hearing is heard at the host's next listen in place of the microphone, so the rules see the same text either way; a phrase the robot cannot understand by voice is not a button [I>V]
  sib:   none -- the button set is the rule; a missing phrase is on the fence (D83)
  serves: N3
  touches: D14 D78

D80 2026-10-18 [I>V]
  pre:   the operator's page is open [I>V]
  trig:  the operator enters an API key or token [I>V]
  resp:  the key is written to the brain's local environment file, owner-readable only, takes effect where it can, and is never shown again: no page, route, log line or event carries its value; the request is refused when it comes from another site's page [I>V]
  sib:   none -- the refusal is in resp; what else a LAN peer may do is a review finding, not a ruling
  serves: N3
  touches: D40 D78

D81 2026-10-18 [I>V]
  pre:   the operator's page is open [I>V]
  trig:  the operator changes a tuning number (head pitch, scan step, field of view, face floor, close-face width, listen windows, discussion time) or the volume [I>V]
  resp:  the change applies live, is saved beside the brain and read at the next start, where a saved setting overrides the matching flag; the volume is set on the robot and never saved [I>V]
  sib:   none -- a value outside its range is refused with a reason, which is in the API, not a game behaviour
  serves: N3
  touches: D78

D82 2026-10-18 [I>V]
  resp: scripted lines per personality, the one callback to a moment from earlier in the game, and switching the personality by voice (`be spooky`) are not in this build [I>V]
  -> fence-deferred character-extras
  serves: N1
  touches: D44 D75
# BUILD-PLAN.md, X2 "Left".

D83 2026-10-18 [I>V]
  resp: `say that again`, `count again`, `more time` during the day with a deadline the page can show, taking back a wrong heads-up warning, and a `listening_for` field in the reported state are for the robot to do by voice first; the page leaves them out until it can [I>V]
  -> fence-deferred product-fixes
  serves: N3
  touches: D9 D18 D79
# DASHBOARD-PLAN.md, "Product fixes".

D84 2026-10-18 [I]
  resp: the Wordle grid on the robot's own screen (Rex asked for it in green, yellow and gray) is not in this build; the grid is reported to the dashboard only [I]
  -> fence-deferred wordle-grid
  serves: N2
  touches: D69
# BUILD-PLAN.md, X5 "done without show_board".

# Review R, proposals (Linus, 2026-10-18 ~08:00). Each entry below is a ruling the review proposes after reading the code against the contract (docs/REVIEW-2026-10-18.md names the finding behind each). All are [I]: proposed, unratified; Rex rules. Where an entry amends a signed ruling the amendment is the proposal, and the signed text stands until he does. The scenarios that cite them are held in the wip register; the code that would make them green is on the branch abdd/3-src.

D85 2026-10-18 [I]
  resp: the referee's Table takes calls only from a referee that holds the shared token; the token is required, generated at the brain's first start and carried to the Pi by the deploy script, never optional; a call that could hold the Table for long (a wait or a listen) is capped at the longest listen the gateway allows [I]
  -> structural
  serves: N1
  touches: D45 D46
# REVIEW A1: brain/remote.py binds 0.0.0.0 with no token by default; any phone on the game's Wi-Fi can take the Table over, turn the boot referee off, speak through the robot and park the worker thread.

D86 2026-10-18 [I]
  resp: a write from the operator's page (a key, a setting, typed hearing, a game, the head, the volume, content, a rig) carries a secret the brain minted at this start and printed with the page's address; a write without it is refused, whatever its origin, and the page's answers are readable by the page's own origin only; rigging a game is possible in test mode only [I]
  -> structural
  serves: N3
  touches: D78 D79 D80 D81
# REVIEW A2, A3: the keys route's guard compares Origin with Host and nothing else; every other write route has no check at all and answers any origin; a page the operator has open, or any phone on the network under --host 0.0.0.0, can set the robot's token, rig the Mafia, speak and read the camera.

D87 2026-10-18 [I]
  pre:   a game is in progress and the host is listening, during the day's discussion or a clue or a vote [I]
  trig:  someone says a sentence that merely contains `start over`, `reset`, `restart` or `stop playing`, such as `i think we should start over with the accusations` or `don't reset` [I]
  resp:  the game goes on: a stop or a reset is heard only as a short plain command, at most five words with no negation, said on its own; a sentence that contains the word is talk [I]
  sib:   none -- the rule names its own negative; D57 is the wanted command
  serves: N1
  touches: D18 D27 D38 D57
# REVIEW B1: wants_to_stop and wants_to_reset match substrings at every listen; a clue of "restart" ended Wavelength in a trace.

D88 2026-10-18 [I]
  pre:   Mafia, a night or a day in progress [I]
  trig:  someone says `restart the round` on its own [I]
  resp:  the host starts the current round again from its night, with the same roles and nothing undone from earlier rounds, and says so; `reset` alone still goes to the welcome [I]
  sib:   none -- a restart undoes nothing that could fail
  serves: N1
  touches: D27 D36 D57 D87
# REVIEW B2: D27 and D36 (ratified) let the group restart a round; the code reads the phrase as a full reset to the welcome and has no round restart.

D89 2026-10-18 [I] amends D6
  pre:   the host has counted five faces and said so [I]
  trig:  someone says `there are six of us` [I]
  resp:  the game does not start: the host says `I only see five. Who's hiding?` and listens again; a plain go-ahead with no `no` or `not` in it accepts the host's count; a disagreement with no number in it gets a second sweep; after three disagreements the host says `Let's try again when everyone's ready.` and no game starts; silence after the mismatch line is not agreement [I]
  sib:   none -- the mismatch is itself the failure case; its outcomes are in resp
  serves: N1
  touches: D5 D6 D59
# REVIEW B3: agrees() takes "no that's not right" as a go-ahead and the game starts on the host's count; the go-ahead, the give-up after three tries and silence-as-agreement were all unruled though the code and a test (test_games_common.py L29-37, labelled D6) assert them.

D90 2026-10-18 [I]
  pre:   the host has counted five faces and said so [I]
  trig:  someone says a count below it, `we're four` [I]
  resp:  the host says `I see five. Is someone just watching?`, sweeps once more in case a face was a bystander's, and starts on the count the group confirms [I]
  sib:   none -- the mirror of D6, with no failure of its own
  serves: N1
  touches: D6 D89
# REVIEW B3: the line exists (lines.see_more, "not ruled" in its own docstring); the code does not sweep again.

D91 2026-10-18 [I]
  pre:   a day phase vote has begun and the host has asked `Player one, who?` [I]
  trig:  the answer names two seats, negates one, or corrects itself, `players three and four`, `anyone but four`, `player four, no wait, two` [I]
  resp:  the vote is asked for once more; a vote names exactly one living seat; a soundalike (`for`, `too`, `won`) counts only right after `player`, `number` or `seat`; `me too` is not a vote [I]
  sib:   none -- the re-ask is the failure handling and is in resp
  serves: N1
  touches: D12 D26
# REVIEW B4: seat_said reads "me too" as seat two, "everyone except player four" as four and keeps the first number of a correction; test_ears.py asserts the soundalike readings.

D92 2026-10-18 [I]
  pre:   Mafia, the day's discussion is running [I]
  trig:  someone says `let's vote` or `we're ready to vote` on its own, before the time is up [I]
  resp:  the host says `Okay, let's vote.` and runs the vote; a longer or negated sentence (`i'm not ready to vote`, `we're ready to hear from player two`) is talk; the halfway call is still said when the vote comes after the half [I]
  sib:   none -- the negated sentence is in resp
  serves: N1
  touches: D12 D18
# REVIEW B5: wants_to_vote is a substring test, so "we're ready to hear from player two" skips the day and its halfway call; the early vote itself was unruled.

D93 2026-10-18 [I] amends D72
  pre:   a game is in progress [I]
  trig:  someone says `pause`, `hold on`, `hang on`, `one sec` or `wait` on its own at any listen [I]
  resp:  the host holds the game as D72 says; `resume`, `unpause`, `we're back` or `keep going`, a tap on its head or the page's Resume carries on; `let's go` is a yes, never a resume; in Hot Seat a hold word pauses the clock instead of counting as an answer or a miss; a stop or a reset said while paused is heard [I]
  sib:   none -- the pause has no failure case beyond the phrases in resp
  serves: N1
  touches: D66 D72
# REVIEW B6: the plan says "pause (or hold on)" but only "pause" and "hold the game" pause; Hot Seat counts "hold on" as an answer and puts "wait" out; "let's go" is at once a yes, an agree and a resume.

D94 2026-10-18 [I]
  pre:   the host is listening for a game's name, idle or in the welcome [I]
  trig:  a game's name is said inside other talk, `that was a hot seat`, `i have twenty questions about this`, `put it in poster form` [I]
  resp:  no game starts: a game starts on its name said as a request or as the whole utterance (`let's play mafia`, `mafia`, `wordle please`); a doubtful hearing gets `Mafia? Say yes to play it.` and a yes starts it [I]
  sib:   none -- the confirm is the failure handling and is in resp
  serves: N1
  touches: D39 D49 D58
# REVIEW B7: game_named fires on the name anywhere, split forms included, and the welcome starts that game at once.

D95 2026-10-18 [I]
  pre:   Wavelength, the group has talked it over [I]
  trig:  someone says the guess as {seven | seven out of ten | nine, no, eight} or inside a longer sentence [I]
  resp:  the guess is the one number in a short answer; `out of ten` is dropped; a correction takes the later number; a number inside a longer sentence (`it's definitely hot, like an eight`) is talk and the host waits for the answer [I]
  spread: A guess is read from a short answer
  sib:   none -- an answer the host cannot read is asked for again, D21's outline
  serves: N1
  touches: D21
# REVIEW B8: number_said answers None for "seven out of ten" and scores the first number it hears while the group is still talking.

D96 2026-10-18 [I] amends D5
  pre:   five friends are seated around a table with the host at one end, facing in [I]
  trig:  someone says `let's play Mafia` [I]
  resp:  the host sweeps its head across its whole range, far left to far right, with a photo at each step, finds five faces, and says `Five of you. Player one is on my left, then two, three, four, five going clockwise.`; the seat numbers are what the host uses for the rest of the game; the robot's head stops at ninety degrees each way, so a full circle is out of reach and the host belongs at the end of the table [I]
  sib:   D6
  serves: N1
  touches: D1 D5 D47
# REVIEW C1: "a full circle" is held to the code only by the binding's comment (hosting.steps.ts L52-54); BUILD-PLAN "Sweeping (03:30)" measured the ±90 limit. The sentence in hosting.feature changes with this entry.

D97 2026-10-18 [I] amends D12
  pre:   a day phase vote has begun with five living players, two of them sitting out this round [I]
  trig:  the host turns to each living player not sitting out, says `Player one, who?`, and each says a seat number [I]
  resp:  the host repeats the tally out loud; a seat named by more than half of the players who may vote this round is eliminated and the host announces it; a top seat short of that gets `Nobody has a majority. Nobody leaves.`; players sitting out neither vote nor count toward the half [I]
  sib:   D13
  serves: N1
  touches: D11 D12 D13
# REVIEW C2: the code counts the majority over all living players, sit-outs included, so a 2-1 vote of five living with two sitting out eliminates nobody; no test or scenario fails when the majority becomes a plurality (mutation probe e).

D98 2026-10-18 [I]
  pre:   the welcome has counted the table [I]
  trig:  a game is named for a table of {four | three | two | one} [I]
  resp:  each game has a smallest table: Mafia four (one Mafia and one Doctor up to six, two Mafia from seven), Imposter three, Wavelength two, Hot Seat two, Wordle one, Twenty Questions one; a table below it hears `Mafia needs at least four players.` and the host offers a game the count can play [I]
  spread: Each game has a smallest table
  sib:   none -- the too-few line is the failure handling and is in resp
  serves: N1 N2
  touches: D15 D20 D21 D48 D66 D69
# REVIEW C3: lines.MINIMUM and mafia_count carry these numbers; D15 rules five and seven-plus only, and test_games_mafia.py asserts four and six.

D99 2026-10-18 [I]
  pre:   Mafia, ten rounds played and neither side has won [I]
  trig:  the tenth day ends without a win [I]
  resp:  the host says `That's enough rounds for one night. Let's call it a draw.` and the game ends with no winner [I]
  sib:   none -- a cap on rounds has no failure case
  serves: N1
  touches: D19
# REVIEW C4: Options.max_rounds and lines.DRAW, asserted by a unit test, bound by no scenario.

D100 2026-10-18 [I]
  pre:   Wavelength, the psychic has given a clue [I]
  trig:  nobody says a number the host can read within eight listens, with `What's your number?` asked once halfway [I]
  resp:  the host says `No guess. Zero points.`, then the target, and the round scores zero [I]
  sib:   none -- the zero is the failure handling itself
  serves: N1
  touches: D21 D95
# REVIEW C4: eight listens of six seconds, asserted by test_games_wavelength.py, bound by no scenario.

D101 2026-10-18 [I]
  pre:   Imposter, clues have been given and the vote has run [I]
  trig:  the vote ties, or no seat has a majority [I]
  resp:  nobody is eliminated: the host says the tally and the tie or no-majority line, then `The Imposter survives. It was Player three.` and the word, and the round ends [I]
  sib:   none -- the tie is the failure case of D13 and this names its Imposter outcome
  serves: N1
  touches: D13 D20
# REVIEW C4: D13 says a tie eliminates nobody and stops; D20 names the survive line for "anyone else voted out"; the code says the survive line on a tie too.

D102 2026-10-18 [I] amends D16
  pre:   Mafia, night, heads down; Player one is the Mafia and Player five is the Doctor [I]
  trig:  the host says `Mafia, whisper your target.` and Player one quietly says `Player four`; the host says `Doctor, whisper who you save.` and Player five quietly says `Player two` [I]
  resp:  at morning the host says `Player four was killed in the night.` and Player four is out; every night the host asks each role once and, when it hears nothing, once more, whether or not the role is still in, so the asks give nothing away; a dead player's silence is the table's rule, not the host's, since the host cannot tell voices apart [I]
  sib:   D17
  serves: N1
  touches: D9 D11 D15 D16 D26
# REVIEW C5: the second ask is said only when nothing valid was heard, so "Doctor, once more, quietly" after the Doctor's death tells the table which role is gone; D16's "stays silent for the rest of the game" is unenforceable by the host.

D103 2026-10-18 [I] amends D21
  pre:   Wavelength with five players; Player five is the psychic in the first round; the spectrum is `cold - hot` [I]
  trig:  Player five leans in and sees the target `7` on a scale of one to ten, gives a clue, the group discusses, and someone says `six` [I]
  resp:  the host scores the round as ten minus the distance between the target and the guess, says `Nine points.`, keeps a running total, rotates the psychic in seat order from the first round's psychic (five, one, two), and after three rounds announces the total; the psychic who would lead a fourth round is Player three [I]
  why:   the one-to-ten scale, the scoring rule and three rounds are the interviewer's, accepted at D21; the first-round psychic moves to five so the scenario's words and the code agree without a rig [I]
  sib:   none -- failure cases are D8 and D100
  spread: A spoken guess scores by distance from the target
  serves: N1
  touches: D7 D21
# REVIEW C6: wavelength.feature's Background names Player two as the psychic while its third scenario wants Player three next; the binding rigs psychic five (wavelength.steps.ts L4-7). This entry moves the fact into the text.

D104 2026-10-18 [I]
  resp: a model may advise a yes or a no; code decides: a guess in Twenty Questions wins only when it names the secret or one of its aliases, and a question the table cannot answer and the model answers is `sort of` at most, never a win or a loss; in Hot Seat an answer on no list counts unless it is on another category's list, and a model's `no` makes the host ask the table `Does that count?` and take the group's answer [I]
  -> structural
  serves: N2
  touches: D14 D42 D63 D67
# REVIEW C7, C8: a model "yes" to "is it a kazoo" won a game against a secret dog; a model "no" eliminates a Hot Seat player.

D105 2026-10-18 [I]
  pre:   Twenty Questions with the player guessing; the host is thinking of a dog [I]
  trig:  the player asks `is it a kazoo?` and a talk model answers yes [I]
  resp:  the host says `Nope, not a kazoo.` and one question is used; code compared the guess with the secret and the model's yes decided nothing [I]
  sib:   none -- the wrong guess is itself the failure case, decided by code
  serves: N2
  touches: D63 D104

D106 2026-10-18 [I]
  pre:   Hot Seat, the category is fruits, a talk model answers [I]
  trig:  a player says `rambutan`, which is on no list, and the model answers no [I]
  resp:  the host asks the table `Rambutan? Does that count?` and takes the group's yes or no; the model's no alone puts nobody out [I]
  sib:   D67
  serves: N2
  touches: D66 D67 D104

D107 2026-10-18 [I] amends D33
  resp: nothing was cut: Wavelength, the live talk and Imposter were all built and bound before the deadline, so the deferral of D33 is closed; the cut order of D32 stays as the rule for a future build that runs short [I]
  -> fence-deferred cut-order
  serves: N1
  touches: D32 D33
# AUDIT, rulings: a deferral whose condition is moot stood unrevised on the fence.

D108 2026-10-18 [I] amends D44
  resp: sound cues come into this build, reopening the sound half of D44: a short cue at the moments the script already marks (a game's start, the deal, night, morning, a death, a save, the vote, a tie, a reveal, a win, Hot Seat's go and out, Wordle's feedback, pause and resume), each under two seconds except three ambiences under three, never played under speech, made once from `CC0` libraries or generated with the team's ElevenLabs key and cached beside the recorded lines, off with one flag; a cue decides nothing and a missing cue never stops a game; head pats, `louder` and `quieter`, mood, playing again with scores and players' names stay deferred [I]
  -> fence-deferred welcome-extras
  serves: N1
  touches: D14 D30 D44 D73
# Rex asked for sound effects (relayed by Linus, 2026-10-18); docs/SOUND-CUES.md is the research. Proposed, unratified: Rex picks the cue list.

# Rex's commit 3ae4edc (2026-10-18 ~05:30, "Voice control, the talk fixed, tabbed settings" in DASHBOARD-PLAN.md), pushed after this review began. Transcribed here the same way as D45 to D81: [I>V] where the plan records Rex's words, built as written.

D109 2026-10-18 [I>V]
  pre:   a game has started and the host has said `Player two, lean in.` [I>V]
  trig:  nobody comes close for a few seconds and Player two says `I'm looking` or `show me`, or taps the host's head [I>V]
  resp:  the card shows for about four seconds whether or not the camera sees a close face; `got it`, `next` or `done` moves the deal on; after ten seconds with nobody close the host says `Player two, lean in close, or say show me.`; `stop the game` or `reset` said during a deal ends the game, over the remote Table too [I>V]
  why:   the four seconds and the ten are the build's numbers (brain/host.py TRUST, REPROMPT) [I]
  sib:   none -- D8 stays the private screen's failure case; a spoken show is the player's own choice
  serves: N1
  touches: D7 D8 D72
# Rex: "ROB waits for exactly one response (the lean-in above all)". A spoken show bypasses D7's one-face rule for four seconds; flagged for Rex in the review as a privacy trade-off he chose.

D110 2026-10-18 [I>V] amends D72
  pre:   a game is in progress, a lean-in included [I>V]
  trig:  someone says `pause`, `shut up`, `be quiet`, `hush`, or a bare `stop` or `wait` with at most a word of filler (`okay stop`, `rob, wait`) [I>V]
  resp:  the host holds the game as D72 says; `hold on` is not a pause but the welcome's `not now`; `stop the game` ends the game, never pauses it; the resume words stay those of D72, and the point of D93 that `let's go` is a yes, not a resume, stands [I>V]
  sib:   none -- a stop or reset while paused is handled in D72
  serves: N1
  touches: D58 D72 D93
# Rex, after a test game: "pause", "stop" and "shut up" went unheard while it waited for a lean-in. This replaces the phrase list the review proposed in D93.

D111 2026-10-18 [I>V]
  pre:   the host is running [I>V]
  trig:  someone says `change your speaker to the Mac`, `speaker mac`, or `use your own speaker`, `speaker robot` [I>V]
  resp:  the voice moves live to the Mac's audio output (`Okay, I'll talk through the Mac.`) or back to the robot's speaker (`Okay, back to my own speaker.`) while the robot keeps moving its mouth; the page has the same switch and the pick is kept with ROB's others; a sentence that merely mentions a speaker is not a command [I>V]
  sib:   none -- the non-command sentence is the rule's own negative
  serves: N1 N3
  touches: D75 D77
# Rex: "change your speaker to the Mac" and a speaker setting; the robot's one-watt speaker is quiet in a hall.

D112 2026-10-18 [I>V] amends D83
  resp: `say that again`, `can you repeat`, `what did you say` make the host say its last line again, at any listen, so this leaves the product-fixes deferral; `count again`, `more time` with a deadline the page can show, taking back a wrong heads-up warning and a `listening_for` field stay deferred [I>V]
  -> fence-deferred product-fixes
  serves: N3
  touches: D79 D83

D113 2026-10-18 [I>V]
  resp: the talk reaches the model: the request is shaped per model (no temperature where Claude refuses it, an effort where the model takes one), the page has an AI tab with the provider, the model, the effort, the last call's result and a Test button, and ROB's own tab holds the personality, the voice and the speaker; a key not tied to a workspace needs its workspace id beside it [I>V]
  -> structural
  serves: N1 N3
  touches: D40 D74 D75 D81
# What the log showed Rex: every Anthropic call answered HTTP 400 (temperature), so every line had been scripted. Not yet tried against the real API ("stubbed HTTP only").

D114 2026-10-18 [I>V]
  pre:   the host has just said a line [I>V]
  trig:  someone says `say that again` [I>V]
  resp:  the host says its last line once more [I>V]
  sib:   none -- a repeat has no failure case
  serves: N1
  touches: D112

D115 2026-10-18 [I]
  pre:   a game reaches one of its big moments: a death at night or nobody dying, a player voted out, the Imposter named, a Wavelength target or total, a Wordle ending, a winner [I]
  trig:  the host says the line for it [I]
  resp:  the host's screen shows a card for the moment while it says the line (Imposter: `PLAYER 3` over `was the Imposter` with `Player three was the Imposter.`, then `beach` over `was the word` with `The word was beach.`), keeps it up about two seconds, then shows the host's face again; a card the screen cannot show leaves the line said without it, and no reveal is ever shown while a private card is owed [I]
  why:   the screen holds five cards and a new set takes seconds to upload, so the cards are uploaded while the host is still talking: with the deal's cards when the outcome is known in advance, otherwise as soon as it is [I]
  sib:   none -- a card the screen cannot show is the rule's own fallback
  serves: N1
  touches: D7 D16 D17 D18 D19 D20 D21
# Rex asked for reveal moments on ROB's screen (relayed, 2026-10-18). Proposed, unratified: the cards' words are the build's.

D116 2026-10-18 [I] amends D6 D41 D59 D89 D90
  pre:   the host has counted the table with its camera, in the welcome or at a game's start [I]
  trig:  someone says a number of players that differs from the host's count, `there are six of us` or `we're four` [I]
  resp:  the group's number wins: the host seats that many, spread evenly, and goes on (the game starts, or the welcome suggests a game for it) with no mismatch line and no second sweep [I]
  sib:   none -- the group's word is final, so there is no disagreement left to fail
  serves: N1
  touches: D5 D6 D41 D59 D89 D90
# Rex, 2026-10-18: "Head count can use camera sweep but also accepts a number given by somebody (that overrides stackchan's sweep)".


D117 2026-10-18 [I] amends D21
  pre:   Wavelength with five players; Player two is the guesser for this round; the secret number is `7` [I]
  trig:  the round starts [I]
  resp:  every player but Player two leans in alone and sees `7` over `out of ten`; then for each of them in turn the host says `Player two, give Player three a category.` and `Player three, name something that fits the number.` and listens to each; then the host asks `Player two, what's the number?` and scores ten minus the distance, as D21; the guesser rotates each round [I]
  why:   Rex's version: everybody but one person knows the number; that person calls on each player with a category, and the player names something whose value is closest to the number [I]
  sib:   none -- a player who never leans in is skipped (D8's deal miss); nobody leaning in ends the game on its own line
  serves: N1
  touches: D7 D8 D21 D95 D100 D103
# Rex, 2026-10-18: "Everybody but one person knows the number. Then the person that doesn't know calls individually on each person with a category, and the person called on has to choose a word in that category that's meaning/value is closest (in the person that doesn't know the number opinion) to the number".
