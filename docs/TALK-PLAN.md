# Talk plan: ROB sounds like a person, hears only people, answers fast

Goal: talking to ROB in the lobby feels like talking to a funny friend who hosts game night, not a script. He answers what you asked, can riff and joke a little, and works his way back to a game. Music and room noise never turn into words. A reply starts within about a second of you finishing.

## What the log showed (2026-10-18 session)

- Model lines were thrown away for running past 20 words or two sentences ("how are you?" got a 30-word spooky reply, dropped), and the scripted "Noted. Now, which game?" played instead.
- "what's up?" and "hello." got nothing: under three words is treated as noise unless ROB just asked something.
- Every model call is one turn with no memory; small talk is capped at six replies with eight seconds between them.
- Music came out as "the name. the name. the name..." dozens of times: Whisper hallucinating on non-speech. The only gate is a loudness bar, which music clears, and music keeps the listen window open to its end.
- Each Anthropic and ElevenLabs call opens a fresh TLS connection (urllib), with the Mac's internet over the iPhone's USB while its Wi-Fi is on the Pi's network.

## Constraints

- D14 holds: the model writes words, the code decides rules, counts and winners.
- Everything still works offline and with no keys (scripted fallbacks stay).
- Quick checks only: the focused pytest for each changed module.

## Steps

1. Personality and conversation (brain/talk.py prompts and fit, personas, welcome, lines, ears.meaningful, host chat memory): in progress.
2. Hearing (scripts/gateway.py: speech detection before Whisper, drop hallucinated and repeated text): in progress.
3. Reply speed (measure the network path; keep-alive connections for Anthropic and ElevenLabs, warm-up, per-call timing in the log): in progress.
4. Merge the three, run the focused tests: not started.
5. One ROB character everywhere (second round, after the merge): personas get concrete instincts and a few example exchanges around one default ROB (a tiny robot who takes hosting slightly too seriously, loves suspense, teases overconfident moves, enjoys being teased, makes himself the joke now and then, helps confused players); each moment gets its own freedom (lobby chat, clear instructions, brief reactions in play); non-critical scripted intros, reactions and fallbacks carry the character; quips get a short summary of public game events for callbacks and to avoid repeats, never a secret role; banter length fits the moment: not started.
6. A replay set: a handful of realistic multi-turn lobby conversations run against the real model, read for answering, continuity, too many game redirects and a distinct voice; prompts adjusted from what it shows: not started.
7. One voice: recorded lines play only when they were recorded in the voice now picked, so changing voice or personality does not leave some lines in another voice; turn-taking timing (pauses between lines, how long ROB waits after you stop): not started.
8. Memory and storage (Codex agent, branch rob/memory-storage): the lobby dialogue and public game context live in RAM only, bounded, cleared on game end, reset and exit; logs hold only the current run and `npm run stop` deletes the ones with what people said (GM_KEEP_LOGS=1 keeps them); ElevenLabs keeps only fixed scripted lines on disk; settings are written only when a value changes. No durable conversational memory and no recognizing people across sessions until Rex picks limits. The talk runs in the brain on the Mac, not on the Pi; a lasting-facts store on the Pi would be new work over brain/remote.py. Round one (logs, voice cache, settings writes) in progress; round two (the dialogue and game-event lifecycle) after the merge.
9. Facts on the Pi (Codex, after the merge; Rex chose this): a small file beside the referee on the Pi, written only when a fact changes, at most 30 facts of 100 characters, deduplicated. What goes in: things the group tells ROB on purpose ("remember that...", "forget that", "what do you remember?") and a public game history (games played, which side won). No transcripts, no secret roles, no recognizing people. Without the Pi, ROB remembers within the session only.
10. ROB's words from the Pi (Codex, after the merge; Rex chose "stay on QNX, move what fits"): the referee on the Pi calls the talk model itself when it has internet and a key, and falls back to the Mac's Table.chat otherwise; the Mac's settings (personality, model) reach it over brain/remote.py. The key goes to the Pi only through a deliberate deploy step Rex runs. Hearing, voice, camera and the robot's connection stay on the Mac: QNX has no numpy, OpenCV or ONNX.
11. Internet for the Pi (in progress, branch rob/pi-uplink): the Pi joins the iPhone's Wi-Fi hotspot on one interface while hosting `gamemaster` on the other, as `qnx/ap.sh trial 300 bcm1` already does by hand. Written as an opt-in trial that reverts itself; the boot setup changes only after a test on the Pi.
12. Restart ROB and try it on the robot: not started.

Done when: the three are merged on the branch, focused tests pass, and the log shows ROB answering "hello" and a question in his own words, music producing no words, and talk calls timed.
