# ROB

A game master for a table of friends, so nobody has to sit out to host: a StackChan (camera, turning head, screen, microphone, speaker) counts the table, deals private roles on its own screen to whoever leans in alone, catches heads-up players at night, takes votes by voice, and runs Mafia (then Imposter, then Wavelength) with a narrator's voice. The brain is a Raspberry Pi that is its own offline network. LA Hacks 2026.

The contract is `features/` (the feature files bind; `DESIGN.md` bounds; `DOCKET.md` holds the rulings). The build plan is `docs/BUILD-PLAN.md`; the operator dashboard has its own, `docs/DASHBOARD-PLAN.md`.

## Layout

- `brain/`: one Python process (`python -m brain`). `host.py` is the Table (`table.py`) made real: it turns the head, reads photos with `vision.py`, puts cards on the screen (`cards.py`), speaks (`voice.py`, `banter.py`) and listens (`ears.py`), and runs the loop that waits for a game's name and plays it (`games/`, with the lines in `lines.py`). `body.py` is the client for the stackchan-mcp gateway (MCP tools at :8767/mcp, PCM audio at :8766/pcm), `clock.py` the real and virtual clocks, `server.py` GET /state and, in test mode, `/test/*`.
- `pi/`: the Pi's hotspot, the gateway and the brain as services (`pi/README.md`), from before the Pi ran QNX.
- `qnx/`: the QNX Pi: the referee (`brain/referee.py` plays the games through the brain's Table over the network, `brain/remote.py`) and the game's own Wi-Fi network, which the Pi hosts (`qnx/ap/`, `qnx/ap.sh`); deploying and running both (`qnx/README.md`).
- `scripts/`: `game.sh` starts a game on the Mac, `wifi.sh` puts the Mac on the Pi's network and back, `ota-stub.py` answers the robot's update check.
- `voice/`: the recorded lines and the Piper voice.
- `test/`: `fake_gateway.py` (the gateway as the brain sees it: the same MCP tools and schemas, `/pcm`, and `/mock/*` for the camera, the microphone and the record of every call), `fixtures/table.py` (the synthetic 640x480 table at any pan angle), gherkin-node-test step bindings in TypeScript driving the brain in `--test` mode (`harness/brain.ts`), Python unit tests in `test/py/`.

## Develop

    npm install
    npm run setup:py          # .venv with Python 3.11, numpy, OpenCV, the mcp SDK, pytest (needs uv)
    npm run test:fast         # oxlint, tsc, pytest, the feature files in FEATURES (all when unset)
    npm test                  # the gate: everything
    npm run validate          # strict feature lint + docket strict
    npm run manifest          # writes and stages run-manifest.ndjson
    npm run fake:gateway -- --port 8081
    npm run brain -- --test --gateway http://127.0.0.1:8081/mcp --port 8080
    npm run fixtures -- --pan=0 --face=-20 --face=10:down --out table.png

In test mode the brain runs on a virtual clock that moves only on `POST /test/advance`, speaks with a test voice whose clips carry each line's text (the fake gateway records what was said), and has no banter. Push a table to the camera with `POST /test/table {"faces": [{"bearing": -30}, {"bearing": 30}]}`, say something with `POST /test/hear {"text": "let's play mafia"}`, then advance; `GET /mock/calls` on the fake shows everything the brain told the robot.

Against the robot: run the gateway (`stackchan-mcp serve --transport streamable-http`), then `npm run brain -- --voice-dir voice --piper-model voice/piper/en_US-lessac-medium.onnx` (flags: `--gateway`, `--pcm`, `--token` or `$STACKCHAN_TOKEN`, `--flip-yaw` if the head turns the wrong way, `--keep-photos DIR` to keep every photo with the faces it found drawn on, `--day-seconds`, `--banter none`). `GET /state` on port 8080 shows the game.

## Running a game

Three boxes on the Pi's own Wi-Fi network, `gamemaster` (2.4 GHz, WPA2, no internet; the password is `GM_WIFI_PASSWORD` in `.env.local`): the QNX Pi at 10.77.0.1 runs the network and the referee, the Mac at 10.77.0.2 runs the gateway, the ears, the voice, vision and the brain, and the robot gets its address from the Pi. The Mac keeps its internet over the iPhone's USB cable. Moving over from the phone hotspot is done once (`qnx/README.md`, "The changeover").

1. Power the Pi from its 27 W supply (a laptop's USB port browns it out). About a minute later its network is up and its referee is waiting for the Mac.
2. Plug the iPhone into the Mac with Personal Hotspot on, then `scripts/wifi.sh game`: the Mac joins `gamemaster` at 10.77.0.2 (it asks for the Mac's password).
3. `scripts/game.sh`, with any brain flags after it (`--speaker mac`, `--banter none`, `--day-seconds 60`): it starts the gateway with `VISION_HOST=10.77.0.2`, the OTA stub and the brain with `--referee remote`, and Ctrl-C stops them. A gateway already running with another `VISION_HOST` is refused, since the robot's photos would go to the wrong address.
4. Turn the robot on; it joins within 20 s. Say "let's play Mafia".

`qnx/ap.sh status` shows the Pi's side: the network, who is on it, the leases, the referee. After a change to the rules, `qnx/deploy.sh` then `qnx/ap.sh referee-restart`. `scripts/wifi.sh back` gives the Mac its usual Wi-Fi again.

## The welcome, the games, the talk and the dashboard

When the brain starts, and whenever someone says "reset", "start over" or "restart", the host greets the table, counts, says hi to each seat, suggests a game for the headcount (one: Twenty Questions; two: Wavelength; three or four: Imposter; five or more: Mafia) and chats until the group picks one. Say a game's name to start it any time: "Mafia", "Imposter", "Wavelength", "Twenty Questions" (one player or more; the host asks who thinks of the secret), "Hot Seat" (two or more; name something in the category before time runs out), "Wordle" (one or more; say or spell five-letter words). "Stop the game" stops; "reset" goes back to the welcome.

Keys go in `.env.local` (gitignored), one `NAME=value` a line. Everything works with none of them:

- `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`: the host's talk (the welcome chat, quips, 20 Questions' guesses and answers, Hot Seat's judging). `--talk anthropic|gemini|ollama|off` (default anthropic, model `claude-haiku-5-5`; `--talk-model claude-sonnet-5-5` or a Gemini model). Without a key the host uses its scripted lines and the games use their built-in tables.
- `ELEVENLABS_API_KEY`: a live ElevenLabs voice for any line not recorded (`--voice eleven|piper`, eleven by default when the key is there; `--eleven-voice ID`, `--eleven-model`). Generated lines are cached in `.cache/eleven/`. A failure falls back to Piper for that line.

The dashboard is at `http://127.0.0.1:8080/dashboard` on the Mac: the game as it happens (the seats, who is still in, the Wordle grid, the 20 Questions count, what was heard and said), buttons to start any game, reset or stop, a box to type what the host should hear, and the pickers for the host's personality (game-show host, deadpan roaster, hype man, spooky narrator, chill friend), the talk and the voice. A change applies to the next line. The game screen is at `/dash` on the same port (`docs/DASHBOARD-PLAN.md`): a lobby with the games, then the game itself over a backdrop, with the robot's face and an avatar for each player, and only the buttons the table could have said out loud. Behind its gear: the camera, the log, the head, tuning saved to `gamemaster.settings.json` (a saved setting overrides the matching flag), word lists, rigs and the keys, which are written to `.env.local` and never shown again. To open it on a phone, start the brain with `--host 0.0.0.0` (with `scripts/game.sh`, add it after the script's name) and open the address it prints, with the phone on the same network.

## Setting up the robot

The robot (stackchan-mcp firmware 2.2.6) keeps three settings from its setup page across restarts: the Wi-Fi network and two addresses on the Mac. For the game that is `gamemaster` with its password, and the Mac at 10.77.0.2. The two servers it checks in with run on the Mac (`scripts/game.sh` starts both):

    VISION_HOST=10.77.0.2 stackchan-mcp serve --transport streamable-http
    python3 scripts/ota-stub.py                        # keep running whenever the robot boots

1. Setup mode: a short tap on the screen (not the head) while the robot is still starting, roughly 5 to 9.5 s after power-on, before it joins Wi-Fi. Outside that window a tap does nothing useful. With nothing saved, or 60 s after its saved network fails, it opens setup mode by itself. Over USB, opening the serial port restarts it, which makes the window easy to time.
2. From a phone, or from the Mac with its Wi-Fi on DHCP (`scripts/wifi.sh back`; the fixed address does not work on the robot's network), join the robot's "Xiaozhi..." network and open http://192.168.4.1 in a real browser. On the first tab pick `gamemaster` and type its password. If the page lists the phone's hotspot as saved, remove it, or the robot may join that instead.
3. On the Advanced tab: Custom OTA URL `http://10.77.0.2:8768/ota/` and WebSocket Gateway URL `ws://10.77.0.2:8765/`; Save.

On the phone hotspot (before the changeover) the Mac was 172.20.10.13 and the steps were the same with those addresses.

Without the OTA stub the robot checks in with api.tenclass.net, which answers an unbound device with an activation code, and the firmware loops on "Activating..." forever without opening the gateway connection (`scripts/ota-stub.py` says more). The serial log (USB, 115200) shows each step: `Ota:`, `WS: Connected to websocket server`, `Activation done`.

The gateway's `listen` downloads faster-whisper's base model on first use (internet needed once). With PyAV 19 it fails with `open() got an unexpected keyword argument 'metadata_errors'`; remove that argument from `av.open(...)` in the gateway's installed `faster_whisper/audio.py` (under `~/.local/share/uv/tools/stackchan-mcp/`) and restart the gateway.

`GM_PYTHON` overrides the interpreter (default `.venv/bin/python`, else `python3`). Tests never reach past loopback; `GM_REAL_NET=1` lifts the guard by hand.
