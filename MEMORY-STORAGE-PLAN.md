# Memory and storage

Goal: keep conversation ephemeral and stop unnecessary disk writes.

Constraints: no durable conversation memory or recognition; no changes to the other
agents' files except ElevenVoice.pcm; no live process changes, deployment or push.

Done when: session logs are cleared at start and removed at stop by default, only
scripted speech uses the disk cache, unchanged settings and keys cause no writes,
focused tests pass, and the remaining writes and Pi storage requirements are reported.

Steps:
- [done] Bound session logs and inspect Mac and Pi output paths.
- [done] Restrict ElevenLabs disk caching to the existing fixed-line catalog.
- [done] Skip unchanged writes for ROB settings, dashboard tuning and keys.
- [done] Run focused tests, inspect the diff, inventory writes and commit.

The lobby transcript lifecycle is a second round after the other branches merge.


Findings and handoff:
- ROB's talk and conversation memory run in the Mac brain. QNX runs the network
  and referee. No durable conversation store or person recognition was added.
- The dashboard's 500-event ring is RAM; opt-in --keep-photos remains unchanged.
- brain/settings.py writes gamemaster.rob.json only when a saved pick changes.
  brain/dash.py writes gamemaster.settings.json (tuning and deliberately edited
  game word/spectrum lists) only when its saved data differs. brain/keys.py writes
  .env.local through an owner-only temporary file only when stored key values
  change. Applying an unchanged key can still update the live environment.
- brain/voice.py writes .cache/eleven/<hash>.pcm through a .tmp file on a miss
  only for the fixed script from brain.lines.fixed_lines(), the same catalog used
  by scripts/make-voice.py. All other speech uses only the existing bounded RAM
  memo. Legacy conversational cache entries are ignored, not deleted.
- brain/cards.py still writes .cache/sets/<hash>.bin and .bin.json when a card
  set is missing. These contain generic role labels, Imposter words and
  Wavelength targets/spectra, not seat-to-role assignments. Private round content
  can remain there. Lifecycle cleanup needs a follow-up coordinated with Host;
  this round does not change Host or card rendering/loading.
- brain/body.py writes temporary gm-line-*.wav files for Mac playback and removes
  them in finally after each line; a hard kill can leave a temporary file.
- brain/host.py writes annotated JPG photos only with --keep-photos.
- Shell-managed .cache/game/*.log files hold current-run output, not brain memory.
  Start clears them even with GM_KEEP_LOGS=1; stop removes them unless that flag is
  set. scripts/game.sh does the same on start/exit. These scripts still write PID
  bookkeeping; no shutdown hooks were added to individually launched processes.
- QNX's ~/gmnet/log/referee.log previously appended rules/errors, including rigs
  and possible exception text. The supervisor now discards referee output by
  default and removes the old referee log when its loop starts. GM_KEEP_LOGS=1 in
  the Pi supervisor environment opts into a log truncated at each referee launch.
  No deployment or removal of existing Pi logs was performed. qnx/referee.sh
  writes to the SSH terminal, not a file; referee.py itself has no disk writes.
- QNX network, DHCP and LED logs hold network/device status, not speech. DHCP
  leases.json holds network MAC/IP/hostname leases, not person recognition. Those
  paths and persistent AP configuration/backups are unchanged.
- Legacy pi/*.service units send brain/gateway stdout and stderr to journald;
  whether they reach disk depends on the machine's journal settings. They remain
  a transcript-retention risk if that old Linux deployment is used. No changes
  were made to that deployment or its existing journal.
- Existing cache inventory, metadata only: 0 PCM files in this worktree, 29 in
  /Users/rexchao/Projects/ROB/.cache/eleven. No cache was deleted. To clear that
  existing cache deliberately: rm -rf /Users/rexchao/Projects/ROB/.cache/eleven
- A future deliberately selected lasting-facts store could live at
  /data/home/qnxuser/gm-memory/facts.json on QNX. First the owner must choose
  byte/count limits and what may be saved. brain/remote.py currently serves the
  Mac's Table to a Pi client, so it needs an explicit store protocol: authenticated
  Pi service requests from the Mac, or a Pi-polling request/reply extension to the
  current Table connection. Reads and deduplication stay in RAM, with bounded,
  validated updates written atomically only on actual change. No periodic dialogue
  flushes. Limit writes and avoid chatty SQLite journals/fsync loops on the SD
  card. No store, endpoints or schema were built in this round.

Validation:
- Focused settings, keys, voice, dashboard and shell-lifecycle tests use the repo
  interpreter and loopback fixtures. Shell lifecycle tests stub process/network
  functions and operate only in temporary directories.
- sh -n checks scripts/rob.sh, scripts/game.sh and qnx/ap/gm-net.sh.
- No live start/stop/restart, hardware run, Pi deployment, full test suite or
  lobby-memory lifecycle integration was performed.

Final checks: 46 focused tests passed; one Piper synthesis test skipped because
the model is absent. Shell syntax and git diff --check passed.
