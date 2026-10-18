# Build plan — Game master

The reviewed contract is `features/`: four feature files (22 scenarios, 2 outlines), `OUT-OF-SCOPE.md`, `USER-NEEDS.md`, `DESIGN.md` and `DOCKET.md` (D1–D33; signature pending the visionary's read). The feature files bind, `DESIGN.md` bounds. Written 2026-10-18 ~02:00; **one human builder; build target 07:00, hard deadline 12:00.** Every agent that runs a phase reads this file itself.

## Build run 2 (from Sat 2026-10-17 23:45 PDT, in the team repo) — read this first

Rex took the build over from the snapshot (P0 done). This section supersedes the phase process and the body contract below wherever they disagree; the rest stays as background.

**Goal.** Everything in the contract built (all four feature files bound and green, Wavelength and the quip slot included), then tested and tuned on the real StackChan, which is here and already flashed with stackchan-mcp.

**Constraints.** Hard deadline Sun 12:00, submit by 11:30. Builders work in parallel in this checkout on disjoint files; nobody commits but the main session. Reserved files as before (`features/*`, every `[ruled: …]` line). Tests never reach past loopback.

**Done when.** `npm test` is green with an empty wip register; the brain runs for real against the gateway (`python -m brain --gateway …`); one full Mafia round plays on the real robot with four people; README says how to run it.

**What changed from the plan below, and why** (facts from reading stackchan-mcp 0.18.0 and its firmware source):

- The brain talks to the gateway daemon (`stackchan-mcp serve --transport streamable-http`, MCP at `:8767/mcp`) with a small synchronous JSON-RPC client, no `mcp` package on the brain side. The daemon runs **one command at a time**: a `say` blocks `move_head` for its whole length, `listen` blocks for its window plus transcription, `load_avatar_set` blocks until the device adopts the set.
- **The voice is the brain's.** The gateway plays raw PCM at `POST :8766/pcm` (headers `X-Sample-Rate`, `X-Channels: 1`, optional bearer token) outside the command queue, so the head can move while the host talks. The brain turns each line into 16 kHz mono PCM itself (`brain/voice.py`: the ElevenLabs cache for fixed lines, Piper for composed ones) and never uses the gateway's TTS engines, so no gateway plugin is needed.
- **Ears:** `listen(duration_ms 100..30000, engine="faster-whisper", language="en")` returns `{text}`. Always pass `language: "en"` (omitting it means Japanese).
- **Camera:** `take_photo(question)` (question is required) returns JSON `{image_path, size_bytes}` plus a base64 JPEG ImageContent; no stream exists, so vision polls. Resolution and latency are unknown until P3 (the fake serves 320×240). Captures pile up in `~/.stackchan/captures`; the brain deletes each one it reads when the path is local.
- **The private screen** is a layered avatar set: 14 full frames of 160×120 RGB565 little-endian (faces idle, happy, thinking, sad, surprised, embarrassed; eyes open, half, closed; mouths closed, half, open, e, u), 537,600 bytes. The device has **no compositor**: a blink or mouth change swaps in the whole eyes or mouth frame, so blinking is turned off while a card shows, and the host never talks over a card. Card slots are happy..embarrassed; `idle` is the host's face; `set_avatar("off")` blanks. A load can take 20 s or more with the device's Wi-Fi in power save, so a game's cards load while the host is talking, before the deal.
- **Head:** `move_head(yaw -90..90, pitch 5..85, speed)`; pitch 45 is neutral. Which way positive yaw turns is unknown until P3 (`--flip-yaw`). The head covers 180° plus the camera's view, not a full circle, so the host sits at the end of the table and "a full circle" binds to a sweep of the whole head range.
- **Vision:** OpenCV's YuNet (`cv2.FaceDetectorYN`, model in `brain/models/`) finds the synthetic table's frontal faces and ignores bowed heads; a close face is found on a downscaled copy of the frame. OpenCV is pinned to 4.x.
- **Process:** one builder per workstream, then one cold review of the whole and a fix round, instead of the per-phase builder, two reviewers and head reviewer.

**Rex's decisions, 2026-10-18 00:15** (these reverse D29 and D31; Linus to be told):

- **Three boxes: the robot, the Mac and a QNX Pi.** The Pi already runs QNX and stays on it. It is the **referee**: the rules and the game state (`brain/games`, `lines`, `ears`, `table`, all standard library only) run there in `python3 -m brain.referee`, calling the Table over HTTP. The Mac runs the gateway, speech recognition, the voice, vision and the Host, and serves the Table to the referee. QNX cannot be the whole brain: CTranslate2 (faster-whisper) and ONNX Runtime (Piper) have no QNX ports (numpy and OpenCV do). Every robot test runs through the Pi from the start; the feature tests run the referee in-process, and one integration test runs it as a separate process over loopback.
- **Voice:** Piper for everything for now; ElevenLabs recordings later (needs a key and a chosen voice).
- **Votes:** a majority of the living players, as signed (D12).
- **Network:** the robot, the Mac and the Pi on one network the team controls; venue Wi-Fi isolates clients. First a phone hotspot; **from 2026-10-18 ~02:50 (Rex) the Pi's own network:** the QNX Pi hosts `gamemaster` itself (2.4 GHz WPA2, 10.77.0.0/24, no router or DNS) and stays on QNX, and the robot, the Mac and the Pi all join it; the Mac keeps its internet over the iPhone's USB link (workstream N, `qnx/README.md`). The hotspot hid itself unless the phone's hotspot screen was open, and the Mac only reached it through Apple's Instant Hotspot.

**Measured on the robot, 2026-10-18 01:30** (firmware 2.2.6, gateway 0.18.0 on the Mac, phone hotspot; these replace the unknowns above):

- **Joining:** the robot needs the OTA stub and the gateway URL set on its setup page (README, "Setting up the robot"). It reconnects to a restarted gateway by itself within 20 s.
- **Camera:** 320×240 JPEG. A photo takes 0.55 s, 1.2 to 1.5 s as the first after the head moves. Field of view about 62 to 70° (a 30° turn moved the scene 137 to 154 px); HFOV_DEG stays 60 until a table test.
- **Head:** positive yaw turns toward the right of the camera image, which is what `vision.bearing` assumes: no `--flip-yaw`. Lower pitch looks down. At 45 the camera sees the ceiling; a player leaning in was framed best at 25, so the default pitch is now 25. The pitch for a seated table is still to be found.
- **Faces:** YuNet found a real face at 0.91 to 0.94 and a face in the background at 0.81, and took a hand for a face at 0.52 (not frontal). SCORE_MIN stays 0.5 because the synthetic fixture faces score 0.5 to 0.9; raising it for the robot (about 0.7) needs either better fixture faces or a separate real-mode floor.
- **Sweeping (03:30):** the robot runs one tool at a time, so the head cannot be steered while a photo is taken, and the camera fires within about 0.1 s of `take_photo` (the rest of the call is the upload), so a photo taken while the head still moves comes out about a quarter as sharp and several degrees behind. `move_head`'s speed is a spring, not a rate: a long move always settles in about 2 s, so one slow turn with photos on the way is not possible (the pose stream is no better). Small eased steps with the photo after the settle work: 12° at 24°/s and 0.3 s is as sharp as a still head and within about 2° of the target (`host.glide_seconds`); the count sweep is 16 such steps, about 1 s each, 17 s in all, more where the Wi-Fi is weak (photos took 1.5 to 3 s with the head turned left, away from the phone). A full circle is out of reach: yaw stops at ±90 in the firmware, so the camera covers about 240°, and the host belongs at the edge of the circle, facing in. Faces nearer than about 50 cm are "close" (CLOSE_WIDTH) and are not counted as seats.
- **Cards:** a full card set loads in 1.8 s (not 20 s); switching cards takes under 0.12 s.
- **Voice:** Piper makes 6 s of speech in 0.1 s on the Mac; `/pcm` returns when playback ends.
- **Ears:** `listen` works with faster-whisper (base), about 1 s after the window closes; "let's play Mafia" came back as "Oh no, I want to- Let's play Mafia" and `ears.game_named` read it. The first listen downloads the model (needs internet once). The gateway's faster-whisper 1.2.1 passes `metadata_errors` to `av.open`, which PyAV 19 rejects; until either side is fixed, drop that argument in the installed `faster_whisper/audio.py` (README).

**Interfaces** (fixed before the workstreams start): `brain/table.py` (what a game asks of the host), and the module surfaces named in each workstream below.

**Workstreams and state**

| # | Workstream | Owns | State |
|---|---|---|---|
| A | Vision: faces, bearings, seats from a sweep, close faces, heads up | `brain/vision.py`, `brain/models/`, `test/py/test_vision.py` | done (56 tests; 6 ms a 320x240 frame; tune HFOV_DEG, CLOSE_WIDTH, SCORE_MIN at P3) |
| B | Rules: the script of lines, parsing what was heard, Mafia, Imposter, Wavelength and the shared hosting rules (count, vote, heads down) | `brain/lines.py`, `brain/ears.py`, `brain/games/`, `test/py/test_lines.py`, `test/py/test_ears.py`, `test/py/test_games_*.py` | done (148 tests; the three probes turn red; majority means more than half of the living) |
| C | Screen and voice assets: cards and avatar sets, the voice (cache, Piper, test encoding), `scripts/make-voice.py`, `pi/` | `brain/cards.py`, `brain/voice.py`, `scripts/make-voice.py`, `pi/`, `voice/`, `test/py/test_cards.py`, `test/py/test_voice.py` | done (44 tests; Piper works on the Mac; 330 lines to record once there is an ElevenLabs key; pi/ not yet run on a Pi) |
| F | The body and the host: gateway client, fake gateway, virtual-time clock, the host loop implementing Table, test endpoints, real mode, the TypeScript harness | `brain/body.py`, `brain/clock.py`, `brain/host.py`, `brain/server.py`, `brain/__main__.py`, `test/fake_gateway.py` (replaces `test/mock_body.py`), `test/harness/`, `test/integration/`, the other `test/py/` files | done (76 tests of its own, 324 Python tests in all; 8 integration tests) |
| Q | The QNX referee: a Table server on the Mac (one registered worker thread runs every call, so the virtual clock still sees it), a RemoteTable client and the referee loop on the Pi, standard library only, plus deploying to the Pi | `brain/remote.py`, `brain/referee.py`, the `--referee` flag in `brain/__main__.py`, `test/py/test_remote.py`, `test/integration/referee.test.ts`, `qnx/` | built (21 Python tests, 4 integration tests; in-brain, loopback and separate-process games match call for call); left: `qnx/deploy.sh` and one game from the Pi (`scripts/pi-game.py remote`), blocked when the Mac left the hotspot |
| N | The Pi's own network: the QNX Pi as the `gamemaster` access point (wpa_supplicant's AP mode; QNX has no hostapd), a standard-library DHCP server with no router or DNS, the referee started at boot, the Mac's switch to the network and back, one command that starts a game | `qnx/ap.sh`, `qnx/ap/`, `scripts/game.sh`, `scripts/wifi.sh`, `test/py/test_dhcpd.py` | built, not yet run on the Pi: the driver reports AP mode (`DRIVER_FLAGS` AP; modes AP; WPA-PSK, CCMP); dhcpd has 9 tests, one over a real socket; persist and revert rehearsed on copies of the Pi's boot files; install and `status` ran on the Pi in a scratch folder. Left: a trial on the Pi (held while the hotspot game ran), then the changeover (`qnx/README.md`) |
| G | Bind all four feature files; empty the wip register | `test/steps/`, `test/features.test.ts` | done (28 scenarios bound, wip empty; no brain change needed) |
| R | Cold review of the whole, then one fix round | — | next (G and Q are in) |
| P3 | The real robot: gateway on the Mac; tune yaw sign, pitch, field of view, close-face size, listen windows | — | started: the robot is on the Mac's gateway; yaw sign, card loads, voice and ears measured (above); left: a seated table, the close-face size, listen windows, a full game |
| W | The welcome and the host's talk: a greeting, a count and a hello to each seat, a suggested game, a short conversation, "reset" to start it again; the ring while listening; cloud talk (Anthropic, or Gemini) that only writes words; a live ElevenLabs voice; the two referee fixes | `brain/lobby.py`, `brain/games/welcome.py`, `brain/talk.py`, the welcome's lines in `brain/lines.py`, the reset and noise parsing in `brain/ears.py`, `brain/voice.py` (ElevenLabs) | built 2026-10-18 ~04:45 without tests (Rex tests by hand); not yet tried on the robot (see "Workstream W" below) |
| X | More games and the host's character: 20 Questions (both ways), Hot Seat, spoken Wordle; house rules for every line; personalities picked on a dashboard page | `brain/games/twenty.py`, `brain/games/hotseat.py`, `brain/games/wordle.py`, `brain/personas.py`, `brain/settings.py`, `brain/dashboard.py` | built in parallel with W, 2026-10-18 ~04:45, without tests; not yet tried on the robot (see "Workstream X" below) |

**Next test session** (everything on the phone hotspot; the Mac at 172.20.10.13, which the robot's saved URLs name; the Mac's Wi-Fi has IPv6 off for the hotspot, `networksetup -setv6automatic Wi-Fi` undoes it):

1. Start the gateway and the OTA stub on the Mac (README, "Setting up the robot"); the robot joins within 20 s of either restarting.
2. The Pi: `qnx/deploy.sh`, then `scripts/pi-game.py remote OUT.json` must match `scripts/pi-game.py local OUT.json` (only the `mode` field differs).
3. Seated table: players sitting back, find the pitch that frames them, then the close-face width for the private screen (CLOSE_WIDTH), and the face floor (SCORE_MIN, see above).
4. The first real three-box game: `npm run brain -- --referee remote --voice-dir voice --piper-model voice/piper/en_US-lessac-medium.onnx` on the Mac, `qnx/referee.sh http://172.20.10.13:8090` on the Pi.

## Workstream W: the welcome, the host's talk, a human voice (Rex, 2026-10-18 ~04:00)

**Goal.** The host feels like a person running game night: when it starts, and whenever someone says "reset", "start over" or "restart", it greets the table, counts, turns to each player with their number, suggests a game for the headcount (two: Wavelength; three or four: Imposter; five or more: Mafia) and talks with the group until they pick one. Its words sound human, not like an assistant, and so does its voice.

**Rex's rulings** (docket D38 to D44): the welcome as above, with a reset ending any game; seats keep their numbers, no names; the group may take the suggestion, name any game, or name a game with a headcount ("imposter with six people"), which goes through the count check (D6: it cannot deal to people it has not seen); questions and chat get a short playful answer, silence a nudge or two and then quiet, background noise nothing; a cloud model writes the talk (Anthropic by default, Gemini as an option) and only the words, with scripted lines whenever it is slow, missing or offline (reverses D28 for talk only); everything sounds human; the ring shows when the host is listening. Later, not in this workstream: head pats, "louder" and "quieter", sound and mood, play again with scores, names.

**Constraints.** The rules, the welcome and the lobby run on the QNX Pi (standard library only, brain/games and brain/lobby.py); the model call runs on the Mac behind a new Table method, `chat`, so the referee never touches the internet. Code decides the game, the count and every rule (D14); a model line that names a seat, runs long or reads like an assistant is dropped for a scripted one. Every game still plays with no internet. Tests never reach the network (mocked HTTP on loopback). In test mode a reset skips the startup welcome unless the test asks for it (`POST /test/reset {"welcome": true}`), so the existing scenarios keep their meaning; saying a game's name always starts it, from idle or mid-welcome.

**Done when.** `npm test` and the docket lint are green with an empty wip register; the welcome, reset, suggestion, game choice, the count check from the welcome, the listening ring, the noise filter, the scripted fallback and the two fixes each have a test; the talk client and the ElevenLabs voice have mocked tests and a documented way to try them live once the keys are in `.env.local`; the README says how to run it.

**Steps**

| Step | What | State |
|---|---|---|
| W1 | Fixes: one lobby loop for the host and the referee that survives the robot dropping off Wi-Fi (the referee exited on a BodyError from an idle listen, 03:2x); a deal that cannot finish ends with its own line, no "Well played." or "Good game." | done: `brain/lobby.py` (a body error is logged, a 3 s pause, listen again), used by `Host.run` and `Referee.idle_loop`; `common.abandon` for Mafia, Imposter and Wavelength |
| W2 | The contract: D38 to D44, the DESIGN.md changelog | done; no `features/welcome.feature` (Rex, ~04:30: skip tests, Rex tests by hand) |
| W3 | The welcome, reset, the conversation, the noise filter, the listening ring | done, no bindings: `brain/games/welcome.py`, `brain/lobby.py`; the suggestion and "what games" read `lines.MINIMUM`, so one player gets Twenty Questions. Never run, may now fail: `test_lines.py` (`test_fixed_lines_cover_the_per_seat_lines_once_each`, `test_flavor_never_names_a_player_or_a_seat`), ring-sequence checks; three ring expectations updated unrun (`test_remote.py`, `referee.test.ts`) |
| W4 | Talk: `brain/talk.py` (Anthropic `claude-haiku-5-5` by default, `claude-sonnet-5-5` allowed; Gemini `gemini-3.8-flash`; Ollama kept), `Table.chat`, the quips through the same client; `--talk`, `--talk-model` | done: Gemini defaults to `gemini-2.5-flash` (3.8 is not a real name); `fit()` drops long, assistant-sounding or seat-naming lines; situations `welcome`, `twenty.guesser`, `twenty.answer`, `hotseat.judge`; reads the personality per call; test mode has no talk. Not tried with a real key |
| W5 | Voice: a live ElevenLabs voice for the lines not recorded (`ELEVENLABS_API_KEY`, `--eleven-voice`), recorded lines first, Piper last | done: `--voice piper|eleven` (eleven when the key is there), `--eleven-model` (default `eleven_flash_v2_5`), stock voice Chris unless the personality names one; cache in `.cache/eleven/`; a failure is Piper for that line and skips ElevenLabs for 30 s. Not tried with a real key |
| W6 | README, this plan | done; the full lane skipped (Rex). `npm run validate` is broken: it calls a helper outside the repo |

Needs the robot or the Pi, not done here: the deal that missed Player one at -33.9°, the real-mode face floor (SCORE_MIN), redeploying the referee (`qnx/deploy.sh`) so the Pi has the fix and the welcome, a first live try of the cloud talk and the ElevenLabs voice.

## Workstream X: more games, the host's character, the dashboard (Rex, 2026-10-18 ~04:15)

**Goal.** Three new games and a host worth playing with: 20 Questions for one player against the robot, Hot Seat for a group, and spoken Wordle for one or more. In every game the host is funny but stays on task, keeps each line short and reads the room. A dashboard page on the Mac lets the group pick the host's personality.

**Rex's rulings** (to be docketed from D46 when X1 starts; W owns D38 to D45):

- **20 Questions.** The robot asks which way round ("Want me to guess yours, or you guess mine?"), and either works.
  - *You think, it guesses:* it asks yes/no questions and may guess at any point; a guess uses a question. It wins on a right guess; you win when all 20 are gone, and it asks what it was.
  - *It thinks, you guess:* code picks the secret from a built-in list before the first question, and the secret never changes. You ask; it answers yes, no, sort of, or "can't answer that" (which does not count). A right guess wins. "I give up", or using all 20, reveals it. A hint on request costs one question.
- **Hot Seat.** The robot names a category, turns to each seat in turn and says "go". You name something in the category before time runs out: 5 s in the first round, a second less each round, never under 3 s. A repeat, a miss or silence puts you out. The last one in wins.
- **Wordle.** A secret five-letter word from a built-in list and six guesses, said aloud or spelled out. The screen shows the grid in green, yellow and gray; the voice gives a short summary. Play it alone, or the seats take turns.
- **Personalities.** The host has several, picked on the dashboard: game-show host (the default), deadpan roaster, hype man, spooky narrator and chill friend. Every one follows the house rules below.
- **Suggestions and minimums.** The welcome suggests 20 Questions for one person (the rest as W); Wordle and Hot Seat are offered when someone asks "what else". Minimums: 20 Questions 1, Wordle 1, Hot Seat 2.
- **Defaults chosen here, which Rex can change:** Hot Seat is out on the first miss (keeps it fast); a group Wordle takes turns; the personality can also be switched by voice ("be spooky").

**House rules for the host** (every game and every personality; code enforces what it can):

- **Short.** One line, two at most, about 15 words. A model line over the cap is dropped for a scripted one.
- **On task.** Every line moves the game on. Off-topic chat gets one quick joke, then back to the game.
- **Never an assistant.** A blocklist ("great question", "I'd be happy to", "certainly", "absolutely", "as an AI", "let's dive in", "feel free") and no explaining itself. No emoji, at most one exclamation mark.
- **Teases the move, never the person.** Nothing about looks, bodies or identity; roasting stays on bad guesses and slow answers.
- **Reads the room.**
  - It never talks over people: lines are short, so listening starts again fast.
  - It stays quiet while the group talks among themselves (speech with no game word and no question for it).
  - Silence: a nudge after about 8 s, "take your time" after about 20 s, then quiet until someone talks. When the robot holds the secret in 20 Questions, the second step offers a hint instead.
  - "Wait", "hold on" and "one sec" pause the clock.
  - Laughs and big moments (a near miss, a comeback, question 19) get a short reaction, not every time.
  - It keeps one moment from each game (a wild guess, a near miss) and may bring it back once.
  - It looks at whoever it is talking to.
- **Builds tension.** It counts out loud only at the moments that matter (halfway, five left, the last one), not every turn.

**Constraints.** As in W: the rules and the game state run on the Pi (standard library only), and the model only supplies words and answers from a fixed set, through Table methods on the Mac. Every game plays offline from built-in tables (20 Questions both ways, Hot Seat's categories, Wordle's lists). Tests never reach the network. X starts after W lands, since it needs `Table.chat`, `brain/talk.py` and the welcome.

**Design.**

- **New Table methods** (on the Mac; the referee calls them through RemoteTable):
  - `choose(kind, context, options) -> str | None`: the model picks from fixed options. 20 Questions answers use "yes", "no", "sort of" and "unknown"; Hot Seat's "does this count" uses "yes" and "no". It returns None when the model is slow, offline or off the list, and the game falls back to its own table.
  - `ask(kind, context) -> str | None`: the robot's next 20 Questions question or guess when it is the guesser. Code checks it is one question, short and not a repeat.
  - `show_board(rows)`: a public picture on the robot's screen and the dashboard (the Wordle grid, the 20 Questions count), rendered on the Mac. Cards stay private and unchanged.
- **20 Questions offline.** About 150 common things, each with 25 to 40 yes/no traits (alive, an animal, bigger than a microwave, found in a kitchen, electronic, edible).
  - Guessing: ask about the trait that best splits what is left; guess once two or fewer remain, or at question 18.
  - Answering: match the question to a trait by keywords, otherwise "can't answer that", which does not count.
  - Online, the model guesses and answers. The table cross-checks wherever it has the trait and wins on a clash, so the secret never drifts.
  - If the player's answers rule out everything in the table, the robot says so once, as a joke ("A living rock. Bold."), and plays on.
- **Hot Seat.**
  - Categories come with their accepted answers built in (fruits, animals, countries, colors and more).
  - Code checks repeats after normalizing (plurals, "a", "an", "the").
  - An answer not on the list counts offline unless it belongs to another category; online, the model judges.
  - Seats go left to right so the head's turns stay short, and the clock starts when "go" ends.
  - Players who are out are skipped and get a one-line send-off.
- **Wordle.**
  - About 2,300 answer words and about 13,000 allowed guesses, from a word list with a clear license, kept on disk on the Pi (check the size is fine on QNX).
  - A spoken word comes first; spelled letters ("c r a n e", "c as in cat") also work.
  - A word that is not on the list, or not five letters, does not use a guess ("Didn't catch that. Spell it?").
  - The robot says the word it heard back in its feedback, so a mishearing can be undone at once with "no".
  - A 6 by 5 grid fits the 160 by 120 screen; one load takes about 1.8 s per guess, which is fine. The ring flashes the greens and yellows.
- **Personalities.** One small data file each, under `brain/personas/`, holding:
  - a style paragraph for the model;
  - scripted variants of the lines that carry the most personality (greeting, win, loss, nudge, out, near miss);
  - the voice (Piper speaker, ElevenLabs voice, rate), the ring color and the avatar face.

  Lines the feature files assert stay the same in every personality; only the marked lines vary.
- **Dashboard.** A page served by the brain on the Mac (`GET /dashboard`, `GET /dashboard/state`, `POST /dashboard/settings`), opened on the Mac or a phone on the same network.
  - It shows whether the robot is connected, the game and its phase, the seats found, the last thing heard and said, the Wordle grid, the 20 Questions count and the Hot Seat players still in.
  - Its controls: personality, talk (Anthropic, Gemini or offline), voice (Piper, ElevenLabs or Mac), start a game and reset.
  - It never shows or accepts API keys, and it listens on the local network only.

**Done when.** Each new game plays start to finish offline. The house-rules check (length cap, blocklist, a seat named, a rule decided by the model) and the personality switch work. The dashboard changes the personality mid-session, and the next line uses it. The README covers the new games and the dashboard. Rex tests by hand (as for W, tests are skipped unless Rex asks for them). On the real robot: a round of 20 Questions each way, a Hot Seat round with three people and one Wordle.

**Steps**

| Step | What | State |
|---|---|---|
| X1 | The contract: the rulings above as D46 onward, the DESIGN.md changelog, short feature files for 20 Questions, Hot Seat, Wordle and the host's character | skipped for now (no tests, Rex) |
| X2 | The host's character: the house-rules check on every model line, the silence steps, chatter and "hold on", reactions and the one callback, the personalities and their lines | partly: the check is `talk.fit`; the five personalities (`brain/personas.py`) change the talk's style and the ElevenLabs voice (no voice ids picked yet); each new game has its own silence steps and "hold on". Left: scripted lines per personality, the callback, switching personality by voice |
| X3 | 20 Questions, both ways, with the offline table and the `ask` and `choose` Table methods | done through `Table.chat` instead of new methods (situations `twenty.guesser`, `twenty.answer`; a model guess is written `GUESS: a toaster`): `brain/games/twenty.py`, about 170 things and 46 traits in `twenty_things.py`; the table wins over the model on what kind of thing it is |
| X4 | Hot Seat | done: `brain/games/hotseat.py`, 14 categories in `hotseat_words.py`; a tie after 12 rounds |
| X5 | Wordle, with `show_board` | done without `show_board`: `brain/games/wordle.py`, 901 answers and about 12,600 guesses in `wordle_words.py` (from /usr/share/dict/words); the grid is in the state for the dashboard, not on the robot's screen |
| X6 | The dashboard | done: `brain/dashboard.py` at `/dashboard` on port 8080 (`--host 0.0.0.0` for phones); typed commands go through `Host.inject`, so they work with the Pi referee too |
| X7 | README and this plan; then the tries on the real robot | README and plan done; the robot tries pending |

## The one-human split

- **The human (operator) does the body and the box:** the StackChan CoreS3 firmware and the Raspberry Pi as an offline access point. Nothing an agent can do in a sandbox.
- **The pipeline builds the brain** against a **mock body** that implements the same HTTP contract, so every brain phase is testable with no hardware present. Integration (P3) is operator-led.
- Models: builder/head/fixer Opus (`claude-opus-5-5`), reviewers/verifier/gate Sonnet (`claude-sonnet-5-5`). Pass the overrides on every run. Reserved files: `features/*.feature`, `features/DOCKET.md`, `features/OUT-OF-SCOPE.md`, `features/USER-NEEDS.md`, every `[ruled: …]` line in `features/DESIGN.md`. The `wip` register only shrinks. The integration branch is `master`.
- **Pre-authorization:** the operator authorizes the pipeline to run P0 → P1 → P2 back to back, stopping at the first block or contract question, while the operator works on the body.

## Process, every phase (as Taken's plan: cold builder → two cold reviewers → head reviewer → one fix round → gate)

Two lanes: `npm run test:fast` (lint, typecheck, Python unit, the `FEATURES` subset) for everyone inside a phase; `npm test` (everything) for the gate only. Integrate: merge to `master`, commit the run manifest, treecontext pointer, report.

## The body contract (superseded 2026-10-18 ~03:00: the body is the stackchan-mcp gateway's MCP tools, see PB; the table below is the original HTTP sketch, kept for the record)

| Endpoint | Body | Meaning |
|---|---|---|
| `GET /stream` | multipart MJPEG, 640×480, ~8 fps | the camera |
| `GET /audio` | 16 kHz mono PCM stream (chunked) | the microphone |
| `POST /say {url}` | plays a WAV the brain serves | the voice |
| `POST /face {state}` | `idle \| listening \| thinking \| talking \| sweeping \| private` | the face |
| `POST /show {text}` / `POST /show {}` | puts text on the screen / blanks it | the private screen |
| `POST /turn {deg}` | pans the head, −90…90, 0 = straight ahead | the head |
| `GET /status` | `{facing, showing}` | far-side read of what the body is doing |

The **mock body** (`test/mock_body.py`) implements all seven over HTTP: `/stream` serves PNG fixtures pushed by tests, `/audio` serves WAV fixtures, and every `POST` is recorded so a test can assert *what the body was told* (far-side), never what the brain thinks it said.

## Acceptance bars

- **Far-side assertions.** "The players hear the host say X" binds to the WAV the body was told to play (the mock records `/say` and the brain's served WAV is decoded to its text id). "Player two sees their role" binds to the mock's recorded `/show`. "The host turns a full circle" binds to the recorded `/turn` sequence. "Player three has one warning" binds to the brain's state read through `/test/state`, which is allowed only for state the feature text names.
- **Fixtures.** Frames: `test/fixtures/table.py` renders a 640×480 synthetic table view per pan angle (N drawn faces at known angles, each flagged frontal or down, one optionally "close") so vision runs for real on synthetic input; a small set of **real photos** of the team at a table, taken tonight, is the second fixture set. Audio: WAV clips of "Player four", "there are six of us", "six", spoken by the team, with a fake STT allowed in the fast lane only when the clip's transcript sidecar says so.
- **Mutation probes, obligatory:** a role shown with two close faces must turn "A second face blanks the private screen" red; a warning issued with every head down must turn "Every head down means no warning" red; a tie that eliminates must turn "A tied vote eliminates nobody" red; a Doctor save that does not cancel the kill must turn "The Doctor saves the Mafia's target" red.
- **No live model in the lane.** STT: Vosk small (offline) is the real path; the lane uses transcript sidecars. TTS: the lane never synthesizes; it asserts the text id of the line. The ElevenLabs cache is generated by `scripts/make-voice.py` by hand, once.
- **Numbers from the rulings** (D8, D15, D18, D21): one second blank, 1/1/3 roles at five, two-minute day with the one-minute call, 1–10 and ten-minus-distance.

## Architecture

- `brain/` — one Python process on the Pi: `body.py` (HTTP client to the body), `vision.py` (MediaPipe face detection on the stream: faces → bearings; close-face lock; frontal-face finder during sweeps), `ears.py` (Vosk on the audio stream; seat-number and count parsing), `voice.py` (line ids → cached WAVs; local TTS fallback), `games/mafia.py`, `games/imposter.py`, `games/wavelength.py` (state machines), `host.py` (the loop: count → deal → phases), `server.py` (serves WAVs to the body; `/test/*` in test mode).
- `body/` — the StackChan firmware (the human's): start from the M5Unified + m5stack-avatar + esp32-camera stack (or AiStackChan2 if it streams); the seven endpoints above.
- `pi/` — the access-point setup script (`nmcli device wifi hotspot ssid gamemaster password …`), systemd unit for the brain.
- `test/` — gherkin-node-test with TypeScript steps driving the brain in test mode and reading the mock body.

## Schedule (one human, five hours)

| Phase | Builds | Binds | Who | Hours |
|---|---|---|---|---|
| **P0** | scaffold, lanes, the mock body, fixtures, brain skeleton with test mode | nothing | pipeline | 0.75 |
| **P1** | vision: count on a sweep, seats, close-face lock, heads-down finder; `hosting.feature` minus votes | hosting.feature except D12/D13 | pipeline | 1.25 |
| **P2** | ears + Mafia: STT parsing, votes, whispers, the state machine, timer, win check | hosting.feature (D12, D13), mafia.feature | pipeline | 1.25 |
| **PB** (parallel with P0–P2) | the body via `stackchan-mcp` (replacement firmware + gateway): avatar-set cards, a cache/Piper TTS engine for the gateway, the ElevenLabs voice cache, a fake MCP server as the mock body, the Pi install and hotspot scripts. Flashing, Wi-Fi provisioning and the physical check (gate B) are the human's | — (gate B is manual) | pipeline, then human | 1.5 + 1 |
| **P3** | integration on the real body: stream → vision, mic → ears, WAVs → speaker; one full Mafia round with four people; tune the close-face distance and the frontal threshold once | — (operator gate) | human + main session | 1 |
| **P4** | Imposter | imposter.feature | pipeline | 0.5, only if P3 is done by 06:00 |
| **PS** | README, video, Devpost | — | human | 0.5 |

Wavelength and the live banter model are deferred by the cut order (D33) unless P4 finishes early. Submit by 11:30.

## Gates

- **P0:** `npm run validate`, `npm test` green on an empty register, the mock body answers all seven endpoints, manifest committed.
- **P1/P2/P4:** `FEATURES=<files> npm run test:fast`, `npm test`, manifest.
- **B (human, by 05:00):** `curl` makes the StackChan say a WAV, show text, blank, turn; `curl /stream` yields frames on the laptop; the Pi's hotspot appears and the StackChan joins it.
- **P3 (operator, by 06:30):** one Mafia round on the real table: the spin count is right, a role shows and blanks on a second face, a heads-up player is named, a whispered target is heard, a vote tallies. Record it on a phone as the video's raw footage.

## Phase briefs

**PB — the body (pipeline phase; runs beside P0–P2; touches only `body/`, `pi/`, `scripts/`, `docs/`). Rewritten 2026-10-18 ~03:00 after the hardware was identified.** The StackChan is M5Stack's official K151 (CoreS3 + two SCS serial-bus servos + GC0308 camera + 12-LED ring + Si12T head touch), shipped with M5Stack's factory firmware (Mooncake 2.3.3), whose MCP tools are only reachable through M5Stack's cloud. **The body is therefore `kisaragi-mochi/stackchan-mcp`:** its replacement firmware (release `firmware-v1.17.0`, `merged-binary.bin`, flashed by the human with esptool; already downloaded to `/tmp/gm/merged-binary.bin`) plus its Python gateway (`stackchan-mcp` 0.18.0, installed with `uv tool install 'stackchan-mcp[tts,tts-elevenlabs,stt-faster-whisper]'`; verified on the laptop; runs on the Pi for the product). The gateway *is* the body contract: it exposes MCP tools `move_head(yaw -90..90, pitch 5..85, speed?)`, `get_head_angles`, `take_photo` (320×240 JPEG posted by the device to the gateway's capture server, needs `VISION_HOST`), `set_avatar(idle|happy|thinking|sad|surprised|embarrassed|off)`, `load_avatar_set(archive_path, mode='layered')` (a raw RGB565 LE file of 14 frames × 160×120 = 537,600 bytes, faces first in the order idle, happy, thinking, sad, surprised, embarrassed, then eyes open/half/closed, then mouths closed/half/open/e/u; staged on the gateway's HTTP server, fetched and SHA256-verified by the device), `say(text, voice, speaker_name)` (gateway-side TTS → Opus → device; engines voicevox, elevenlabs, irodori, edge-tts), `listen(duration_ms, engine='faster-whisper')` (device mic → gateway STT), `set_leds`/`set_all_leds`/`clear_leds`, `get_touch_state`, `get_device_info`. Transport for the brain: run the gateway as a daemon (`stackchan-mcp serve --transport streamable-http`, MCP at `http://127.0.0.1:8767/mcp`) and have `brain/body.py` be an MCP client over HTTP (the `mcp` Python package), one method per tool. The device finds the gateway by mDNS (`_stackchan-mcp._tcp.local.`) on the same network; Wi-Fi is provisioned once through the firmware's captive portal at `192.168.4.1`.

PB builds, in this order: (1) `body/avatar/make_set.py`: renders six 160×120 PNG "faces" with Pillow (idle = the host's face; the other five slots are **cards**: large centred text on a dark background, one set per game — `mafia.bin`: MAFIA / DOCTOR / VILLAGER / blank / blank; `imposter.bin`: IMPOSTER / BEACH / blank / blank / blank; `wavelength.bin`: 1–5 and a second file 6–10), plus neutral eyes and mouths, and packs each into the 537,600-byte layered archive; a unit test asserts the byte size and that frame 0 differs from frame 1. (2) `body/gateway_ext/`: a small package the gateway process imports (`STACKCHAN_MCP_PLUGINS` if the gateway supports it, else a wrapper entry point `gamemaster-gateway` that imports stackchan_mcp, registers engines, then runs its CLI) registering two `TTSEngine`s: `cache` — answers a text whose hash exists under `body/voice/<sha>.wav` with that WAV's 16 kHz mono PCM (how the ElevenLabs lines play offline, D30), raising a clear error for unknown text; and `piper` — local English TTS via the `piper-tts` package for composed lines, if it installs on the Mac and the Pi (if not, `cache` only and say so in the report). Unit tests with a fake registry. (3) `scripts/make-voice.py`: generates the host's fixed lines (collected from the feature files' quoted lines plus `body/voice/lines.txt`) through ElevenLabs into `body/voice/<sha>.wav` with a fake client in tests; two voices (host; "night" variant optional). (4) `test/mock_body.py` is now a **fake MCP server** (streamable HTTP, same tool names and schemas as the gateway's; `take_photo` returns PNG fixtures pushed by tests; every call recorded for far-side assertions) — replace P0's HTTP mock if P0 has merged, else write it here and tell P1 to use it. (5) `pi/`: `hotspot.sh` (`nmcli device wifi hotspot ssid gamemaster password …`), `install.sh` (uv, the gateway with extras, libopus0, faster-whisper `base` model prefetch, Ollama with a 3B model since the Pi has 8 GB), and a systemd unit for the gateway daemon and the brain. **Gate:** `pytest` for (1)–(3) green; the fake MCP server answers every tool and records calls; `pi/*.sh` shell-checked; `npm run validate`. The human's gate B afterwards: flash, provision Wi-Fi, run the gateway on the laptop, and from Claude Code or `curl` to the daemon: `move_head`, `set_avatar('happy')`, `load_avatar_set(mafia.bin)` then `set_avatar('happy')` shows MAFIA, `say('hello', voice='cache')`, `take_photo` returns a JPEG. Second reviewer's focus: the archive byte layout (a wrong frame order shows the wrong card to the wrong player, which is a game-breaking silent failure) and the cache engine never falling back to a cloud engine without being asked.

**P0.** `package.json` (gherkin-node-test, vitest, oxlint, typescript), `pyproject.toml` (brain, pytest), `scripts/lane.mjs`, `test/harness/brain.ts` (spawns `python -m brain --test --body http://localhost:<mock>`), `test/mock_body.py`, `test/fixtures/table.py`, the brain skeleton: `body.py` client, `server.py` with `/test/reset`, `/test/frame` (pushes to the mock's stream), `/test/audio`, `/test/advance`, `/test/state`; every feature file in `wip`; README stub. Second reviewer: harness honesty (the mock records what it was told; nothing in `/test/*` pre-seeds state a later phase could pass with).

**P1.** Vision on the synthetic table: during a sweep (`/turn` through −90…90 in steps) collect face bearings, cluster into seats numbered left to right (D5); count mismatch with a spoken number stops the start (D6, with the fake STT sidecar); close-face lock: a face whose box is wider than a threshold and roughly frontal = close; exactly one → show; a second → blank within one second and the line (D7, D8); heads-down sweep: any frontal face at a seat → warning by seat; second in the same night → sits out (D9, D10, D11). Second reviewer: the lock and the warning must depend on *frames*, not on test hints — probe by feeding a two-face frame with the lock asserting one.

**P2.** `ears.py`: Vosk (real path) with sidecar transcripts in the lane; parse "Player N" / "N" / counts; votes in turn with the head turning to each living seat (D12, D13); the Mafia state machine: deal (D15), night whispers and the Doctor's save (D16, D17), the two-minute day with the one-minute call on the virtual clock (D18), reveal, win checks (D19). Second reviewer: clock honesty and the tie rule; probe the Doctor-save cancellation.

**P4.** Imposter: word deal through the private screen, one-word clue turn-taking, the vote, the two reveal lines (D20).

## The demo (rehearse at 06:30, three times)

Four players (the judge plus three of you). "Let's play Mafia." The host spins and counts. Roles by leaning in — a teammate leans in beside the judge and the screen dies: "One at a time." Night: heads down; a teammate peeks on purpose; "Player three, heads down means heads DOWN." Whispers. Morning: "Player four was killed in the night." Two minutes of accusation (cut to thirty seconds with a dev flag for the table). Votes by voice, the tally out loud, the reveal. Under four minutes. Imposter as the sixty-second version.
