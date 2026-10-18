# Dashboard plan

Branch `gamemaster-dashboard`, in its own worktree, merged back into `gamemaster` after any finished panel. Started 2026-10-18 03:05 PDT.

**Goal.** A page beside the table, on a laptop or phone, that shows what the host is doing, lets the operator rescue a game when the ears or the eyes fail, and changes the tuning numbers and game content without restarting the brain.

**Constraints.**

- Served by the brain itself at `GET /dash` on its port (8080): one static HTML file plus JSON endpoints in `brain/server.py`. No build step, no new dependency, standard library on the Python side. One exception: the seat avatars' DiceBear bundle (`brain/dash/vendor/dicebear.js`), built once with `npm run build:avatars` and committed, so the page still needs no build.
- The contract (`features/`) and the rules (`brain/games/`) do not change. The dashboard reads state, feeds the same inputs a voice would, and changes settings. `npm test` stays green.
- Works the same with `--referee local` and `--referee remote` (the referee reports state through the Mac's host either way).
- Hard deadline Sun 12:00, submit by 11:30, and the robot test session in `BUILD-PLAN.md` still has to happen.

**Done when.** Each finished panel has a Python test for its endpoints, has been driven in a browser against the fake gateway, and `npm test` is green on the branch.

## Panels, in build order

| # | Panel | What it does | State |
|---|---|---|---|
| 1 | Live view | Phase, round, seats, living, out, warnings, winner; a log of the host's lines and what the microphone heard; the latest photo with face boxes and the head's angle | built |
| 2 | Controls | Type what the table said (the next listen hears it instead of the microphone); start a game, stop the game; make the host say a line; nudge the head, run a sweep | built |
| 3 | Tuning | Head pitch, field of view, face score floor, close-face width, Mafia discussion time, listen windows, quips on or off; applied live, saved to `gamemaster.settings.json` and read at start | built |
| 4 | Content | Imposter words and Wavelength spectrums, editable; rig the next game (Mafia, doctor, word, target) | built |

## Design notes

- The log and the photo come from the host: `say`, `listen` and each photo are recorded in a small ring buffer under the host's lock, served at `GET /dash/events?since=N` and `GET /dash/photo`. The page polls about once a second.
- Typed hearing is a queue in the host that `listen` drains before asking the gateway, so the rules see the same text either way.
- Face crops of the seats are kept in memory only (replaced at the next count, dropped by a reset or `host.clear()`), served only to the dashboard's page, and never leave the Mac: no file, no network. The avatar colours are read from them locally (`brain/portraits.py`).
- The robot's face on the page is drawn in the colours `brain/cards.py` draws it on the robot (`face_style`); the host tells the Dash when it speaks, its mood and ring, and whether the screen shows its face, a card or nothing.
- Settings are module constants today (`vision.HFOV_DEG`, `vision.SCORE_MIN`, `vision.CLOSE_WIDTH`, `host.LISTEN_WINDOW`, the `--pitch` and `--day-seconds` flags). One `brain/settings.py` owns the names, ranges and the file, and applies a change by setting them.

## Rex's answers (03:20)

Build all four now, quickly, in parallel; more features later. Look: clean and polished like Apple, gamified, high contrast; a dark game UI that does not look AI-made.

## The API (fixed before the two builders start)

Everything is JSON unless said. All paths work in real and test mode. Errors are `{"error": "..."}` with 400 or 404.

| Route | Answer |
|---|---|
| `GET /dash` | `brain/dash/index.html` (the page; one file, no external fonts, scripts or CDNs: the table's network is offline) |
| `GET /dash/api/state` | `{"game": {...the reported state, or {"game": null}}, "yaw": deg, "pitch": deg, "seats": [bearing, ...], "mode": "real"\|"test", "referee": "local"\|"remote", "photo": {"id": n, "t": epoch_s, "yaw": deg, "faces": [{"cx","cy","w","h","score","close"}]} or null, "typed_pending": n, "robot": {...}, "face_style": {...}, "seats_info": [...]}`; the last three below |
| `robot` (in state) | `{"face": "idle"\|"card"\|"off", "mood": "idle"\|"listening"\|"night"\|"day"\|"tense"\|"win", "led": [r, g, b], "speaking": bool, "line": the line being spoken or null, "speaking_since": epoch_s or null, "volume": 0..100 or null}`; `face` is "card" while a private card is up and "off" while the screen is blanked; `volume` is read once from the robot at start (null until known) and after each set |
| `face_style` (in state) | `{"bg", "ink", "cheek", "mouth"}` as `#rrggbb`: the robot's face colours from `brain/cards.py` |
| `seats_info` (in state) | `[{"seat": n, "bearing": deg, "face": bool, "avatar": {"style": "lorelei", "seed": "seat-<n>-<count id>", "skin": hex or null, "hair": hex or "none", "options": {"seed", "skinColor"?: [hex], "hairColor"?: [hex]}} or null}]`; hex has no `#`. `face` and `avatar` fill in shortly after a count (cropped on the dash's own thread). Draw an avatar with `createAvatar(style, avatar.options).toString()` (an SVG string) from `/dash/vendor/dicebear.js`; a colour that could not be read is left out of `options` |
| `GET /dash/api/robot` | `{"robot": {...}, "face_style": {...}}`, the same as in state |
| `GET /dash/api/seat/<n>.jpg` | `image/jpeg`, 160x160, seat n's face from the last count; 404 until it is ready |
| `POST /dash/api/volume` | body `{"volume": 0..100}` (a whole number); sets the robot's speaker now through the gateway's `set_volume`, not saved; answers `{"volume": n}`; 400 on a bad value or when the robot refuses |
| `GET /dash/vendor/dicebear.js` | `text/javascript`: DiceBear 9 core and the Lorelei style (artwork CC0) as one ES module exporting `createAvatar` and `style`; built by `npm run build:avatars`, licenses in `brain/dash/vendor/LICENSES.md` |
| `GET /dash/api/events?since=N` | `{"next": N2, "events": [{"id": n, "t": epoch_s, "kind": "say"\|"heard"\|"typed"\|"log"\|"game", "text": "..."}]}`; a ring of the last 500; `next` is the last id given, to pass back as `since` |
| `GET /dash/api/photo` | `image/jpeg`, the latest camera frame with face boxes drawn (green close, white others); 404 before the first photo |
| `POST /dash/api/hear` | body `{"text": "..."}`; the host's next listen hears it instead of the microphone; `{"ok": true, "pending": n}` |
| `POST /dash/api/game` | body `{"name": "mafia"\|"imposter"\|"wavelength"\|"stop"}`; queues "let's play <name>" or "stop the game" as typed hearing |
| `POST /dash/api/say` | body `{"text": "..."}`; the host speaks it now (in a background thread, through the voice and the body) |
| `POST /dash/api/head` | body `{"yaw"?: -90..90, "pitch"?: 5..85}`; moves the head; answers the new `{"yaw", "pitch"}` |
| `GET /dash/api/settings` | `{"values": {key: value}, "schema": [{"key", "label", "group", "kind": "number"\|"bool", "min", "max", "step", "unit", "help"}]}` |
| `POST /dash/api/settings` | body `{key: value, ...}`; applied live, saved to `gamemaster.settings.json` beside `package.json`; answers like GET |
| `GET /dash/api/content` | `{"imposter_words": [...], "spectra": ["cold - hot", ...]}` |
| `POST /dash/api/content` | same shape (either key); applied live (`lines.IMPOSTER_WORDS`, `lines.SPECTRA`), saved in the settings file; answers like GET |
| `GET /dash/api/keys` / `POST /dash/api/keys` | write-only API keys (`brain/keys.py`): GET answers `{"keys": [{"key", "label", "applies", "help", "set"}]}`, never a value; POST `{"KEY": "value"}` sets, `{"KEY": null}` clears; saved to `.env.local` (gitignored, mode 600; `brain/voice.py` and `brain/talk.py` read it too), read at start; refused (403) from another site's page |
| `GET /dash/api/rig` / `POST /dash/api/rig` | the pending rigs, `{"<game>": {...}}` as `/test/rig` takes them (keys in `brain/games/__init__.py`) |

Settings keys: `pitch` (head, 5..85), `hfov` (20..120), `sweep_step` (Camera, "Scan step", 10..45 degrees between the counting scan's photos; the scan takes ceil(180 / step) + 1 photos, reported as `"photos": n` beside `values` and `schema`; unset it is `vision.SWEEP_DEFAULT_DEG`, 15, or a third of the field of view if that is smaller), `sweep_speed` (Camera, "Scan speed", 10..90 degrees per second the head glides between those photos, default `host.SWEEP_SPEED`, 40), `score_min` (0.3..0.99), `close_width` (0.05..0.6), `listen_window` (1..15 s), `day_seconds` (10..300), `vote_seconds`, `whisper_seconds`, `clue_seconds` (1..20), `banter` (bool, quips on or off). Groups: "Camera", "Head", "Timing", "Voice".

Options reach a remote referee only at its hello, so timing changes apply to the next referee start under `--referee remote`.

## Two screens (Rex, 03:55)

The robot runs the game by voice; the page stays out of the way. **The rule: every button during play is a phrase the robot already understands, sent as typed hearing.** If the table could say it, the screen can say it for them when the ears fail; if the robot cannot understand it by voice, it is not a button (it goes in "Product fixes" below instead). Head, tuning, word lists and rigs move behind a gear.

- **Lobby** (no game): full-screen backdrop, three game cards (tap = "let's play mafia"), the hint "Say 'let's play Mafia' or tap a game", and ready checks: robot, camera ("sees N people" from the last photo), voice.
- **In game:** the game's backdrop (Mafia day and night, Imposter, Wavelength; photos in `brain/dash/art/`, credits in `art/CREDITS.md`), phase in big type, the seat ring, the host's last line as a subtitle, and the phase's buttons:

| Phase | Buttons (what they send) |
|---|---|
| count | Yes ("yes"); a number stepper ("there are N of us") |
| day | Vote now ("let's vote") |
| vote, night, clue | tap a seat ("player N") |
| guess (Wavelength) | 1 to 10 ("N") |
| any | Stop, with a confirm ("stop the game"); "Say it for them" (the typed box, folded) |

## Product fixes (the robot should do these by voice; the page leaves them out until it can)

- "Say that again": the host repeats its last line.
- "Count again" / "look again": a recount when the count is wrong, instead of only correcting the number.
- "More time" during the day, and a deadline in the reported state so the page can show a countdown.
- A wrong heads-up warning cannot be taken back (vision misread a face); a spoken "I was down" or an operator undo.
- The reported state does not say what the host is listening for right now; the page guesses from the phase. A `listening_for` field ("count", "agree", "vote", "whisper", "guess", "game") would make the buttons exact.

## Pause, a quieter lobby, simpler settings (Rex, 05:10)

Rex: the settings have too much in them; "pause" should hold the game until he says so or taps the robot; the robot chimes every few seconds while it waits; drop "I'm just gonna sit here looking cute until someone picks a game".

Why it chimes: the firmware plays a sound each time the gateway opens its microphone (`listen` sends listen.start, then listen.stop), and the lobby listens in back-to-back 4 s windows. There is no setting to silence it, so the lobby opens the microphone less often once the table has been quiet.

| Step | What | State |
|---|---|---|
| P1 | Pause: "pause" (or "hold on") at any listen holds the game; the ring dims, the host says it is paused; "resume", "unpause", "we're back", a tap on the robot's head or the page's Resume button carries on, and the listen that was interrupted runs again. The game's clock (`host.now()`) stops while paused, so the day timer does not run out. `paused` in `/dash/api/state` | done |
| P2 | Quieter lobby: idle listens grow from `listen_window` to 10 s after 30 s with nothing heard, and back on the next word; paused listens are 10 s | done |
| P3 | The "sit here looking cute" nudge removed | done |
| P4 | Settings drawer: one short panel instead of four tabs. Host (personality, voice, talk, from `/dashboard/state`), Volume, Camera (head pitch, scan step), Keys; the rest of the tuning, the log and the camera photo folded under "More". Content, rigs, head nudge and the duplicate typing boxes leave the page (their APIs stay). Pause/Resume on the in-game screen | done |
| P5 | Merge to `gamemaster` and into the ROB repo; restart the game | done (tests stopped at Rex's word after P3: the Python tests passed then; the ROB name, the five voices and Customize ROB ran untested) |

**ROB (Rex, 05:20).** The robot is named ROB: the greetings and the talk's house rules say so. "Customize ROB" on the lobby picks one of five personalities (`brain/personas.py` PERSONAS) and five ElevenLabs voices (`personas.VOICES`; `settings.eleven_voice`, which turns ElevenLabs on when the key is set); both are kept in `gamemaster.rob.json` (gitignored) across starts.

## Voice control, the talk fixed, tabbed settings (Rex, 05:30)

Rex, after a test game: ROB waits for exactly one response (the lean-in above all); "pause", "stop" and "shut up" went unheard while it waited for a lean-in; the settings are confusing; he does not think the Anthropic key is used; he wants to say "change your speaker to the Mac" and have a speaker setting; and more choices: provider, model, effort, voice, personality. Fast, parallel, few tests.

What the log showed: the key loads, but every Anthropic call answered HTTP 400 (the talk sends `temperature`, which Claude Haiku 5.5 refuses at a non-default value), so every line was scripted. `show_private` only takes photos; it never listens, so nothing said during a lean-in is heard.

**Done when.** A lean-in can be answered by voice ("I'm looking" or "show me" shows the card, "got it" or "next" moves on), a head tap or the page; "pause", "shut up", a bare "stop", "stop the game" and "reset" work during a lean-in; "change your speaker to the Mac" switches the speaker live, and so does the page; the talk reaches Claude (Haiku, Sonnet or Opus 5.5, with an effort) and the page can test it and shows the last error; the settings are tabs. Targeted tests pass, then `npm run test:fast`.

| Step | What | State |
|---|---|---|
| V1 | Talk: the Anthropic request shape per model (no temperature on Claude 4.7 and later, effort, thinking off where the model allows it), the error's message in the log and on the page, a test call, a model and effort catalog; `effort` and `speaker` in `brain/settings.py`, saved with the rest of ROB's picks | done (stubbed HTTP only: no real call to Anthropic or Gemini yet) |
| V2 | Host: commands at every listen (pause by "shut up" or a bare "stop", the speaker, "say that again"); `show_private` listens for "show me", "got it", pause and stop, takes typed lines and a head tap; a stop during the deal ends the game, over the remote Table too | done (not tried on the robot) |
| V3 | `/dashboard`: tabs, the provider, model, effort, speaker and a test button; `POST /dashboard/talk-test` | done |
| V4 | `/dash`: the settings drawer in tabs (ROB, AI, Keys, Game, Camera, Log), Customize ROB opens the ROB tab, the deal's buttons ("Show the card", "They've seen it") | done (the Working and No key cards and a real Test answer not seen yet: test mode has no talk) |
| V5 | Review, `npm run test:fast`, restart the brain | done: the live game now runs from this checkout (`npm run brain`, log in `.cache/game/brain.log`), so no copy into the hackathon one |
| V6 | Tap to wake (Rex, 06:10): after a game or once the talk dies down ROB says it is napping and stops listening (`Table.sleep()`, the ring dim, the head read once a second); a tap, the page's Wake ROB or a typed line wakes it, and it says it is up, counts and suggests. Also "restarted" in passing is no reset, "what else" lists the real games, the talk is told the games and its length limit, and the tests read an empty key file (`GM_ENV_FILE`) | done, `npm run test:fast` green (471 Python, 40 feature); brain restarted 06:17; not yet tried with a tap on the robot |
