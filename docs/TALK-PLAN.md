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
4. Merge the three, run the focused tests, restart ROB and try it: not started.

Done when: the three are merged on the branch, focused tests pass, and the log shows ROB answering "hello" and a question in his own words, music producing no words, and talk calls timed.
