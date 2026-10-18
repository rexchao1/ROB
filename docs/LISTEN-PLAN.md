# Plan: ROB hears the table while he talks, and understands it

Rex, 2026-10-18. ROB has a hard time understanding the table, and only hears in turns. Make him hear people while he talks, stop when someone starts talking over him, and get the words right.

## What the logs showed (gateway log, 10:51 to 10:53, Mac mic and Mac speaker)

- ROB hears himself. Lines like "Here on the table with a screen for a face" and "Right on time for a ghost story" were ROB's own words, coming out of the Mac's speaker into the Mac's microphone. Nothing takes his voice out of the microphone.
- Words get cut. Every listen starts a new ffmpeg and records a fixed window (4 s, or 2 s pieces while ROB talks): the first word is lost while ffmpeg starts, speech between windows is lost, and a sentence that runs past the window is cut ("Ready, say a game's name and I'll").
- While ROB talks, only a hard command found in a 2 s piece can stop him.

## Goal

On the Mac's microphone and speaker: ROB never hears his own voice; when someone starts talking over him he stops within about half a second and hears the whole thing they said; anything said while he talks or thinks is heard, not lost between windows; and no word is cut at the start or end of what someone says.

## Constraints

- The robot's microphone stays as it is: it cannot hear while its speaker plays, and beeps each time it opens.
- The QNX referee shares `brain/lobby.py` and `brain/games/`: nothing there may need numpy or audio.
- Another session has uncommitted work in the main checkout (`brain/host.py` near line 940, `brain/ears.py`, `brain/games/`, `brain/talk.py`). This work is on the branch `rob/full-duplex` in `../ROB-duplex`, and touches `brain/host.py` only around `say`, `_speak`, `_overhear` and `listen`.
- macOS gives the microphone only to an app allowed to use it: ROB started from T3 Code hears silence (T3 Code lacks the audio-input entitlement). Start ROB from Terminal for the Mac mic.

## Design

- `scripts/rob-audio.swift`, built by `npm start` into `.cache/bin/rob-audio`: one AVAudioEngine with Apple's voice processing on (echo cancellation, noise suppression, gain control). ROB's lines play through it, so it knows exactly what to take out of the microphone. It serves two Unix sockets in `.cache/audio/`: `mic.sock` streams the cleaned microphone (16 kHz 16-bit mono) to whoever connects, `play.sock` plays a line and answers when it has played, or cuts it off.
- The gateway (`scripts/gateway.py`) keeps one microphone stream open the whole time (`MicStream`): the last 30 s in memory, with the voice detector run on every frame. A listen takes what was said since the last listen (at most 12 s back), starts 0.3 s before the voice did, and ends when the talker stops. A small HTTP endpoint on port 8769 answers "has someone started talking since T", outside the gateway's one-at-a-time command queue.
- The brain (`brain/body.py`, `brain/host.py`): ROB's lines go to `play.sock` when the helper runs (afplay otherwise). While a line plays on the Mac with the Mac mic, the host waits on the gateway for a voice; at about 0.3 s of voice the line is cut, the host listens for the rest of what was said, and then: a hard command acts as now; in the lobby it is heard like any answer; in a game ROB says the cut line again once they are done (a host waits for quiet), and the words wait for the game's next listen only if they are a command.
- A last check in `Host.listen`: words that are mostly ROB's own last line are dropped as his echo (for the robot's speaker, which the helper cannot cancel).
- Robot speaker with the Mac mic: no voice barge-in (his voice would trigger it), hard commands only, as now, but from the stream with no gaps.

## Done when

Each step is checked off with its check, the gateway and host tests pass, and a recording through the helper shows ROB's line taken out of the microphone.

## Steps

1. [built, echo not yet measured] `rob-audio`: the Swift helper, built by `scripts/rob.sh`, started before the gateway, stopped with the rest. Check: play a recorded line through it while recording `mic.sock` and plain ffmpeg side by side (from Terminal); the line is at least 20 dB quieter in `mic.sock`, and Whisper hears nothing of it there.
2. [done, smoke-tested; no unit tests yet] `MicStream` in the gateway: the stream, the backlog, the listen from the stream, the voice endpoint; ffmpeg windows stay as the fallback when the helper is not running. Check: unit tests with synthetic frames (backlog, preroll, end of speech, the voice wait).
3. [done; no unit test yet] Playback through `play.sock` in `Body._play_here`, cut-off included. Check: unit test against a fake socket.
4. [done; existing host tests pass, no new ones] Barge-in on a voice in `Host`, the follow-up listen, the lobby and game rules, the echo check in `listen`. Check: host tests with a fake body.
5. [not started] Try it at the table (Rex): talk over ROB in the lobby and in a game; read the "heard" lines in `.cache/game/gateway.log`.

## Notes

- The echo check (step 1) cannot run from T3 Code: its child processes get a silent microphone, Terminal opened from it too. Run `/tmp`-free: start ROB from Terminal, talk over a line, and read `.cache/game/gateway.log` ("listen (Mac mic stream)", "heard") and `.cache/game/brain.log` ("someone talked over my line", "heard my own line, dropped").
- AVAudioEngine's voice processing fails to start (-10875) unless the output node exists before it is turned on; the input comes as 9 channels at 48 kHz, channel 0 is the processed one.
- Played through rob-audio, a 5.3 s line took 5.4 s to answer "played".
