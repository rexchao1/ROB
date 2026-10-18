# Sound cues for ROB: research (review R, 2026-10-18)

Rex asked for sound effects to enhance the experience. This is the research for it: what to play, where to get it legally, how it would sit in the code, and what the contract would say. Nothing here is built; the proposed ruling is D108 in `features/DOCKET.md` and it reopens D44 ("sound and mood … for later").

**Recommendation.** Add a `Table.sound(cue)` call, the sibling of `mood()` and `quip()`: cosmetic, blocking, never deciding anything (D14). Ship about fifteen short cues as 16 kHz mono WAVs under `voice/sfx/`, every one CC0 (Kenney first, Freesound's CC0 filter second) or generated once with the team's ElevenLabs key by a `scripts/make-sfx.py` in the mould of `scripts/make-voice.py` (D30's pattern: made once, cached, offline at play time). Keep stingers under 1.5 s and the ambiences under 3 s, and never play one under speech: `/pcm` is serial and returns when playback ends (`brain/body.py`, `Body.play`), so a cue that is a Table call cannot overlap a line. Pair every cue with the mood the script already sets at that moment (`MOOD_LEDS` in `brain/host.py`), so the ring and the speaker change together. The zero-dependency fallback is a synthesized set written with `wave`, `math` and `struct`, which also runs on the QNX referee's standard-library Python (note `audioop` is gone since 3.13: https://docs.python.org/3/whatsnew/3.13.html).

The team's earlier note `ideas/sound-cues.md` ("Behind You") is about a different product, sound awareness on glasses; what carries over is its quiet rules (one cue at a time, a cooldown per kind, nothing for a sound that merely continues), its "CC0 libraries; data, not code" sourcing, and its hour-one kill test, which here becomes a speaker test in the hall.

## Why these moments, and what the precedents say

Game shows use three classes: a bright ding around 2 to 4 kHz for a right answer, an abrasive low buzzer for a strike, and timed think music (Jeopardy's "Think!" is 136 BPM, 17 bars, exactly 30 s, so it is the timer) (https://tvtropes.org/pmwiki/pmwiki.php/Main/JeopardyThinkingMusic, https://soundboardmax.com/family-feud-soundboard/). Board-game companions do the same in miniature: the Codenames Companion app's timer has sound alerts and spoken announcements (https://apps.apple.com/us/app/codenames-companion/id1032754439); generic turn timers tick for the last 5 s and buzz at time-out (https://apps.apple.com/us/app/-/id6472882122); Bezier's One Night app plays night narration over an optional background such as "Crickets", and its reviewers complain when a music bed overpowers the narrator (https://play.google.com/store/apps/details?id=com.mobieos.karan.Wolf_Android14_11_13); the Werewolf Narrator app has "more than 150 sound effects specifically designed for the scenes" (https://apps.apple.com/us/app/werewolf-narrator/id1505233252). Jackbox's audio leads do sound effects and music together because "the sound and music go a long way in differentiating the tone for each game" (https://www.jackboxgames.com/blog/behind-the-scenes-of-pp10-audio).

UI sound guidance converges on durations: taps 80 to 150 ms, notifications 200 to 600 ms, stingers 1 to 3 s, with UI sounds mixed quieter than the main audio and slight variation to avoid fatigue (https://sfxengine.com/blog/best-practices-for-game-ui-sounds). Earcon studies find 0.5 to 1 s preferred and 2 s less preferred (https://arxiv.org/pdf/2507.04238); sounds of 60 to 150 ms are still recognized (https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10101377/). Two constraints from ROB itself: the robot already chimes whenever its microphone opens (`brain/lobby.py`, D73), so no "listening" cue; and `listen()` holds the microphone, so nothing can tick during Hot Seat's window without the microphone hearing it. Hot Seat gets a "go" cue before and a buzzer after, not a tick during.

## Cue list

| Moment (where in the script) | Cue | Length | Feel / source option |
|---|---|---|---|
| Any game starts (`welcome.py` hands over) | host sting | 0.8 s | two-note brand tag; Kenney Music Jingles or synth |
| Mafia deal (`mafia.py` before `DEAL_ROLES`) | card riffle | 0.6 s | paper; Freesound CC0 |
| Card shown on screen (`show_private`, host) | soft tick | 0.15 s | UI confirm; Kenney Interface Sounds |
| Night falls (`mood("night")` + flavor night) | wind + one owl | 2.5 s, then silence | ambience, ends before `HEADS_DOWN`; Freesound CC0 or ElevenLabs |
| Morning (`mood("day")` + `MORNING`) | birds / rooster | 1.5 s | ambience; Freesound CC0 |
| Death (`killed()`) | low minor stinger | 1.2 s | dark; ElevenLabs "short low orchestral stinger, minor" |
| Saved (`NOBODY_DIED`) | light relief chime | 0.8 s | warm; Kenney jingle |
| Vote called (`TIME_VOTE` / `EARLY_VOTE`, mood tense) | drum roll / pulse | 1.5 s | tension; ElevenLabs or synth |
| Tie (`flavor("tie")`) | flat "wah" | 0.7 s | a softened Family-Feud buzzer; synth |
| Reveal (Mafia `was()`, Imposter `was_imposter`) | reveal hit | 1.0 s | one accent; Kenney jingle |
| Win, any game (`finish()`, mood win) | fanfare | 2.0 s | shared across games; Kenney Music Jingles |
| Imposter: clues begin (`CLUES`) | light ping | 0.3 s | UI; Kenney |
| Wavelength: target revealed (`target_was`) | dial sweep whoosh | 0.9 s | rising; ElevenLabs |
| Wavelength: points / no points | bell / soft thud | 0.5 s | Kenney Interface Sounds |
| Hot Seat: "Player N, go!" | short buzzer-in | 0.4 s | start gun; synth |
| Hot Seat: out (time, repeat, wrong) | strike buzzer | 0.7 s | low, abrasive but quiet; synth |
| Wordle: all gray / some green / solved | blip / ding / fanfare | 0.3 / 0.3 / 2.0 s | the ding bright, 2 to 4 kHz; Kenney |
| Pause / resume (`host._pause`) | two notes down / up | 0.5 s | the same cue inverted; synth |

Seventeen cues, three ambiences at most; "tense" moments in Twenty Questions and Wordle's last guess reuse the vote pulse.

## Sources and licenses

| Source | License | Attribution | Redistribute in a public repo? | Notes |
|---|---|---|---|---|
| Kenney Interface Sounds (100 files), Music Jingles (85) | CC0 1.0 | none | yes | https://kenney.nl/assets/interface-sounds, https://kenney.nl/assets/music-jingles; OGG, convert once |
| OpenGameArt, per-item license filter | CC0 items only | none | yes | e.g. GUI Sound Effects (Lokif), 100 CC0 SFX: https://opengameart.org/content/gui-sound-effects, https://opengameart.org/content/100-cc0-sfx |
| Freesound, filter `license:"Creative Commons 0"` | CC0 | none (CC-BY items need a credit; BY-NC excluded) | yes for CC0 | https://freesound.org/search/?q=stinger&f=license:%22Creative+Commons+0%22; licenses FAQ https://freesound.org/help/faq/ |
| Pixabay | Pixabay Content License | none | doubtful: no distribution "on a Standalone basis" in substantially original form | https://pixabay.com/service/license-summary/; treat as not repo-clean |
| Mixkit | Mixkit Free License | none | no: may not "sublicense ... or make any item available to any third party" | https://mixkit.co/license/ |
| Zapsplat | Standard License | credit "ZapSplat" required on the free tier; MP3 only | no: "must not be redistributed outside of your project" | https://www.zapsplat.com/license-type/standard-license/ |
| ElevenLabs Sound Effects API | plan terms; commercial license from Starter ($6) up, not Free | none | yes, as the team's own generated output | `POST /v1/sound-generation`, `duration_seconds` 0.5 to 30, `output_format=pcm_16000`, `loop` for ambiences; 200 credits per generation, or 40 credits per second when a duration is given: https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert, https://elevenlabs.io/docs/capabilities/sound-effects, https://elevenlabs.io/pricing |
| Local synthesis | the team's own | none | yes | `wave` + `math` + `struct` only; https://docs.python.org/3/library/wave.html |

Record every file's origin in a `voice/sfx/CREDITS.md`, the way `brain/dash/art/CREDITS.md` already does for the backdrops.

## Integration sketch

- `brain/table.py`: `sound(cue: str) -> None`, "a short sound for a moment the script marks; cosmetic only, blocks until played"; a `CUES` tuple beside `MOODS` so a bad name fails fast like `mood()` does.
- `brain/remote.py`: add `"sound"` to `METHODS`, the client stub and the server dispatch, so the QNX referee's games can call it; the audio still plays on the Mac.
- `brain/sfx.py` (new): a `Sounds` class like `CachedVoice`: `voice/sfx/<cue>.wav` loaded through the existing `wav_to_pcm`, a `_Memo`, and a `TestSounds` whose clip carries `sound:<cue>` through `encode_test_pcm`, so the fake gateway's `/mock/calls` records it with `line` and the harness gets a `sounds()` beside `said()`.
- `brain/host.py`: `sound()` = `_check_stop`, `_note("sound", cue)`, `dash.record`, `body.play(pcm)`; a per-cue cooldown and one at a time; `--sfx off` and a dashboard toggle like the voice picker.
- `brain/games/*.py`: one `table.sound(...)` beside each `mood()`/`flavor()` named in the table above; the fake Table in `test/py` gains a no-op `sound`.
- `scripts/make-sfx.py`: fetch or generate, then normalise with ffmpeg two-pass `loudnorm` (measure a Piper line and a recorded ElevenLabs line, aim cues 3 to 6 LU under them, `TP=-1.5`, then `-ar 16000 -ac 1 -sample_fmt s16` because loudnorm leaves audio at 192 kHz: https://k.ylo.ph/2016/04/04/loudnorm.html). Gain is baked into the file; nothing is scaled at play time.
- Visual pairing: the ring already changes in `mood()`; the three ambiences (night, morning, win) are issued right after the matching `mood()` so light and sound land together.

## The contract

Reopens D44 (reopening condition in `OUT-OF-SCOPE.md`: when Rex picks one up after trying the welcome on the robot) and touches D14 (a sound decides nothing) and D30 (made once, cached, offline). Proposed as D108. A `sound-cues.feature` would hold: (1) night falls: the host plays the night cue, then says the night line, and the fake gateway's record shows the cue strictly before the line, never interleaved; (2) a win ends with the fanfare after the winning line and the ring in the win colour; (3) with `--sfx off` the same game plays with no cue recorded and the said lines unchanged; (4) a missing or unreadable cue file is logged and the game goes on.

## Risks

- The CoreS3 speaker is 1 W through an AW88298 amplifier (https://docs.m5stack.com/en/core/CoreS3); the gateway exposes `set_volume` 0 to 100. Low rumbles will vanish; keep cues in the 400 Hz to 4 kHz band and test in the hall first. `--speaker mac` sidesteps this for the demo.
- Cue fatigue: at most one cue per script moment, cooldowns, no cue under 150 ms repeated per turn (Wordle's per-guess ding is the one to watch).
- The judge's attention: cues add seconds; a Mafia night already has four lines. Cap the added time per round at about 5 s.
- Test mode: cues must go through `encode_test_pcm` so `/mock/calls` records them; otherwise the harness cannot assert them and the virtual clock would wait real time on nothing.
- Licensing: only CC0 and self-generated files in the repo; Pixabay, Mixkit and Zapsplat stay out even though they are free to use.
