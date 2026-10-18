# Startup plan

Started 2026-10-18.

**Goal.** Starting ROB takes one step: one command, or a double-click, and ROB is talking with the dashboard open. Stopping takes one step too. Nobody has to know which network the Mac is on, whether the Pi is up, which flags to pass, or what else is already running.

**What goes wrong today** (from starting it on 2026-10-18):

- An old copy of ROB from another folder (`Projects/Hackathon/LAHacks_AI_2026/gamemaster`) was already running. `scripts/game.sh` only says "port 8080 is taken", without saying which copy holds it.
- `scripts/game.sh` assumes the Pi is up (`--referee remote`, Mac at 10.77.0.2). With the Pi off and the Mac on the iPhone hotspot, you have to know to add `--referee local` and to set `VISION_HOST` to the hotspot address yourself.
- A fresh checkout has no voice model (`voice/piper/`) and no `.env.local`, so the brain refuses to start, or starts without its keys, and the error doesn't say how to fix it.
- Stopping means Ctrl-C in the terminal that started it, or knowing which processes to kill. Killing the brain alone also takes down the gateway `game.sh` started, which then has to be restarted by hand.
- Nothing says when the robot has actually joined. "waiting for the robot" repeats in the log until it does.

**Constraints.**

- Wraps what exists (`scripts/game.sh`, `scripts/wifi.sh`, `npm run brain`) instead of replacing them. The brain's flags and the README's manual steps keep working.
- No new dependencies. POSIX shell like the other scripts, and the brain's own `/state` to tell when it's ready.
- Nothing silently changes the Wi-Fi or asks for a password without saying why. Joining `gamemaster` still asks for the Mac's password (sudo), once, and only when the Pi is actually there to join.
- Secrets stay in `.env.local`. The script never prints them and never copies them between folders without asking.

**Done when.** On this Mac, from a cold start, each of these takes one step and ends with ROB greeting the table and the dashboard open in the browser: (a) Pi on, (b) Pi off with the Mac on the iPhone hotspot, (c) an older ROB already running. `npm run stop` leaves nothing running. `npm test` is still green.

## The shape

`scripts/rob.sh`, run as `npm start`, `npm run stop`, `npm run status`, and a `Start ROB.command` file you can double-click (it opens Terminal and runs `npm start`).

`npm start`:

1. **Preflight.** It checks for `.venv`, `voice/piper/en_US-lessac-medium.onnx` and `.env.local`. A missing venv runs `npm run setup:py`. A missing voice model is downloaded, the same file `pi/install.sh` fetches. A missing `.env.local` gets a warning, not a stop ("no keys: ROB uses its scripted lines and the Piper voice"). The dashboard's Keys tab can add keys later.
2. **Something already running?** For each of ports 8080, 8766, 8767, 8768 and 8090, it finds the process and the folder it runs from. If it's this folder's ROB, it says so and just opens the dashboard. If it's another folder, it names that folder and asks "Stop it and start this one? [Y/n]".
3. **Pick the network.** It pings the Pi at 10.77.0.1.
   - The Pi answers: it uses the Pi's referee (`--referee remote`) with the Mac at 10.77.0.2.
   - The Pi doesn't answer: it no longer scans for `gamemaster` (the scan took 18 s and macOS hides network names from it anyway). The closing `rob: next:` line says to run `scripts/wifi.sh game` then `npm run restart` when the robot has not joined and the Mac is off `gamemaster`.
   - Neither: it runs the games on the Mac (`--referee local`) and uses the Mac's current Wi-Fi address as `VISION_HOST`. It says which network the robot must be on to join.
4. **Start in the background.** It starts the gateway, the update stub and the brain with `nohup`, logs to `.cache/game/`, and writes their process IDs to `.cache/game/pids`. It closes Terminal without stopping anything.
5. **Wait and report.** It polls `GET /state` until the brain answers, then gives the robot 8 s to join (it used to wait 60 s; the dashboard shows a later join). Then it prints one block: which network, where the games run, the dashboard and game-screen addresses, and how to stop. It opens the dashboard in the browser. It ends with one `rob: next:` line, what to do now (`npm run status` ends with the same line).

`npm run stop` kills what `.cache/game/pids` lists, plus anything still on those ports from this folder. It doesn't touch the Wi-Fi. `scripts/wifi.sh back` stays a separate step, and stop reminds you of it when the Mac is on `gamemaster`.

`npm run status` reports what's running and from which folder, the network, whether the robot has joined, and the last few log lines.

## Steps

| # | Step | State |
|---|---|---|
| 1 | `scripts/rob.sh` with `status`: finds each port's process and its folder, the network, the Pi, whether the robot has joined | built |
| 2 | `stop`: the PID file plus this folder's processes on the ports; the Wi-Fi reminder | built |
| 3 | `start`: the preflight (venv, voice model download, `.env.local` warning) | built |
| 4 | `start`: the "already running" check and its prompt | built |
| 5 | `start`: the network choice (Pi, offer to join `gamemaster`, or local on the current Wi-Fi) | built |
| 6 | `start`: background launch, waiting for the brain and the robot, the summary, opening the dashboard | built |
| 7 | `npm start` / `npm run stop` / `npm run status` in `package.json`; `Start ROB.command`; the README's "Running a game" leads with them | built |
| 8 | Check the three cold starts in "Done when" on the real robot; `npm test` | checked on 2026-10-18: Pi off on the iPhone hotspot, restart, and another folder holding a port, all on the real robot; `npm run test:fast` green. The Pi-on path and joining `gamemaster` are not checked yet |

## Choices made

`npm start` plus the double-click file, chosen 2026-10-18; `npm run restart` added.

## Later

- A menu-bar app, or starting at login.
- `Start ROB.command` is in the repo root; an alias on the Desktop works too.
