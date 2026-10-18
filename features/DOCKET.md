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
  resp: every host line carries flavor from a scripted set with variations, and a model may add a quip or a line of small talk; a model only writes words, and nothing the host says changes the rules, the count or the state of a game, which are fixed in code; the host sounds like a person running game night, not an assistant: one or two short spoken sentences, casual and playful, never revealing a secret role or word, never inventing a rule, always in character as the robot host [V]
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
