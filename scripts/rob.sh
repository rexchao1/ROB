#!/bin/sh
# ROB in one step (docs/STARTUP-PLAN.md): it checks what is missing, finds what is
# already running, picks the network, starts the gateway, the OTA stub and the brain in
# the background, waits for the robot, and opens the dashboard.
#
#   scripts/rob.sh start [-y] [brain flags...]   npm start (-- --speaker mac ...)
#   scripts/rob.sh stop                          npm run stop
#   scripts/rob.sh restart [-y] [brain flags...] npm run restart
#   scripts/rob.sh status                        npm run status
#
# -y answers yes to every question (stop another copy). Start and restart first catch
# this folder up with GitHub (sync_check). The games run on the Pi's referee when the Pi
# answers at PI_ADDR, else here on the Mac. Logs and the process IDs go to .cache/game/.
# The Wi-Fi is left as it is by stop; scripts/wifi.sh back.
set -eu
cd "$(dirname "$0")/.."
ROOT=$(pwd -P)
. qnx/ap/net.conf
LOGS=.cache/game
PIDS=$LOGS/pids
PORTS="8080 8766 8767 8768 $TABLE_PORT"
PIPER_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
PIPER_VOICE=en_US-lessac-medium
DEV=$(networksetup -listallhardwareports | awk '/Hardware Port: Wi-Fi/ { getline; print $2 }')
YES=""

say() { echo "rob: $*"; }
listening() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1; }
folder() { lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1; }
ask() {  # ask "question": yes with -y, or when there is no one to ask
  [ -n "$YES" ] && return 0
  [ -t 0 ] || return 0
  printf 'rob: %s [Y/n] ' "$1"
  read -r a
  case "$a" in [nN]*) return 1 ;; *) return 0 ;; esac
}
python() {
  if [ -n "${GM_PYTHON:-}" ]; then echo "$GM_PYTHON"; elif [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi
}
robot_joined() {
  auth=""
  [ -n "${STACKCHAN_TOKEN:-}" ] && auth="Authorization: Bearer $STACKCHAN_TOKEN"
  curl -s -m 2 ${auth:+-H "$auth"} http://127.0.0.1:8767/status 2>/dev/null | grep -q '"connected": *true'
}
wifi_addr() { [ -n "$DEV" ] && ipconfig getifaddr "$DEV" 2>/dev/null || true; }
pi_up() { ping -c 1 -t 1 "$PI_ADDR" > /dev/null 2>&1; }
# The Pi as a client of the iPhone hotspot (no gamemaster, so no referee from boot):
# start runs one over ssh, and stop ends it, since a referee alone retries forever.
HOTSPOT_PI=qnxuser@172.20.10.14
# Up to three pings: on the hotspot the Pi's Wi-Fi dozes and often misses the first.
hotspot_pi_up() { ping -c 3 -o -t 3 "${HOTSPOT_PI#*@}" > /dev/null 2>&1; }
pi_ssh() { ssh -o BatchMode=yes -o ConnectTimeout=5 ${GM_SSH_OPTS:-} "$HOTSPOT_PI" "$@"; }
stop_hotspot_referee() {
  pi_ssh 'for p in $(pidin -f aen ar 2>/dev/null | awk "/brain.referee/ && !/awk/ { print \$1 }"); do kill $p; done' 2>/dev/null || true
}
# Every process on ROB's ports, one "pid port folder" a line.
running() {
  for port in $PORTS; do
    p=$(listening "$port")
    [ -n "$p" ] && echo "$p $port $(folder "$p")"
  done
  return 0
}

status() {
  r=$(running)
  if [ -z "$r" ]; then
    say "nothing is running"
  else
    echo "$r" | while read -r p port dir; do
      say "port $port: $(ps -p "$p" -o comm= | xargs basename) (pid $p) from $dir"
    done
  fi
  if pi_up; then say "the Pi answers at $PI_ADDR"
  elif hotspot_pi_up; then say "the Pi answers on the iPhone hotspot at ${HOTSPOT_PI#*@}"
  else say "the Pi does not answer"; fi
  say "this Mac's Wi-Fi address: $(wifi_addr)"
  if [ -n "$(listening 8767)" ]; then
    if robot_joined; then say "the robot is connected"; else say "the robot is not connected"; fi
  fi
  [ -s "$LOGS/brain.log" ] && { say "the brain's last lines:"; tail -5 "$LOGS/brain.log" | sed 's/^/  /'; }
  next_step
  return 0
}

# One "rob: next:" line: what a person has to do now, so whoever started ROB (or an
# agent) can pass it on as is. The robot keeps its own Wi-Fi and the Mac's address from
# its setup page; once the game network exists it is set for gamemaster, which only
# the Pi hosts, so a Mac on any other Wi-Fi never sees it (a no-cloud symbol on its face).
next_step() {
  g=$(listening 8767)
  vh=""
  [ -n "$g" ] && vh=$(ps -E -p "$g" -o command= | tr ' ' '\n' | sed -n 's/^VISION_HOST=//p' | head -1)
  if [ -z "$(listening 8080)" ]; then
    say "next: ROB is not running; npm start"
  elif [ -n "$vh" ] && [ -n "$(wifi_addr)" ] && [ "$vh" != "$(wifi_addr)" ]; then
    say "next: the Mac's Wi-Fi changed since ROB started (it was $vh, now $(wifi_addr)), so the robot's photos and face go nowhere; npm run restart"
  elif robot_joined; then
    say "next: ready. Say \"let's play Mafia\" (or any game's name); the dashboard is http://127.0.0.1:8080/dash"
  elif [ "$(wifi_addr)" != "$MAC_ADDR" ] && grep -q '^GM_WIFI_PASSWORD=.' .env.local 2>/dev/null; then
    net=""
    [ "$(route -n get default 2>/dev/null | awk '/interface:/ { print $2 }')" = "$DEV" ] &&
      net=" First plug the iPhone in by USB with Personal Hotspot on: $SSID has no internet, and the Mac's internet goes over Wi-Fi now."
    say "next: the robot is set up for the Pi's $SSID Wi-Fi and this Mac is not on it. With the Pi powered (a minute after its green light), run scripts/wifi.sh game in Terminal (it asks for the Mac's password), then npm run restart.$net"
  else
    say "next: turn the robot on; it joins within 20 s when it is on the same Wi-Fi as this Mac ($(wifi_addr)). A no-cloud symbol on its face means it cannot reach the Mac: README, Setting up the robot"
  fi
}

stop() {
  if [ -s "$PIDS" ]; then
    for p in $(cat "$PIDS"); do kill "$p" 2>/dev/null || true; done
  fi
  # Anything else on ROB's ports from this folder (started by hand, or by game.sh).
  for port in $PORTS; do
    p=$(listening "$port")
    [ -n "$p" ] && [ "$(folder "$p")" = "$ROOT" ] && kill "$p" 2>/dev/null || true
  done
  rm -f "$PIDS"
  pkill -f "$ROOT/.cache/bin/rob-audio" 2>/dev/null || true
  rm -f .cache/audio/*.sock
  [ -f "$LOGS/hotspot-referee" ] && { stop_hotspot_referee; rm -f "$LOGS/hotspot-referee"; }
  # Logs can contain speech and private game details. Keep only by explicit opt-in.
  if [ "${GM_KEEP_LOGS:-}" != 1 ]; then rm -f "$LOGS/"*.log; fi
  n=0
  while [ -n "$(running)" ] && [ "$n" -lt 10 ]; do n=$((n + 1)); sleep 0.5; done
  left=$(running)
  if [ -n "$left" ]; then
    say "still running, not from this folder (rob.sh start offers to stop it):"
    echo "$left" | sed 's/^/  pid, port, folder: /'
  else
    say "stopped"
  fi
  if [ -n "$(wifi_addr)" ] && [ "$(wifi_addr)" = "$MAC_ADDR" ]; then
    say "the Mac is still on $SSID; scripts/wifi.sh back gives it your usual Wi-Fi"
  fi
}

# This folder against GitHub, since ROB runs whatever is on disk: a folder that fell
# behind once served a dashboard from hours before. Behind with nothing local, it
# catches up and starts again from the new rob.sh; anything else is only said. Off the
# internet (gamemaster has none) the fetch gives up after 10 s and the start goes on.
sync_check() {
  [ "${GM_NO_SYNC:-}" = 1 ] && return 0
  git rev-parse --git-dir > /dev/null 2>&1 || return 0
  up=$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null) || return 0
  GIT_TERMINAL_PROMPT=0 git fetch -q 2>/dev/null &
  f=$!
  n=0
  while kill -0 "$f" 2>/dev/null; do
    n=$((n + 1))
    if [ "$n" -ge 20 ]; then kill "$f" 2>/dev/null; say "could not reach GitHub; not checked whether this folder is up to date"; return 0; fi
    sleep 0.5
  done
  wait "$f" || { say "could not reach GitHub; not checked whether this folder is up to date"; return 0; }
  behind=$(git rev-list --count "HEAD..$up")
  ahead=$(git rev-list --count "$up..HEAD")
  [ "$behind" = 0 ] && { [ "$ahead" = 0 ] || say "this folder has $ahead commit(s) not on $up yet; git push"; return 0; }
  if [ "$ahead" = 0 ] && [ -z "$(git status --porcelain --untracked-files=no)" ]; then
    say "this folder was $behind commit(s) behind $up; catching up"
    git merge -q --ff-only "$up"
    GM_NO_SYNC=1 exec sh "$0" "$@"
  fi
  say "WARNING: this folder is $behind commit(s) behind $up and has local changes or commits, so ROB runs old code."
  say "  git status, then git pull --rebase (or commit and push first)"
  ask "Start the old code anyway?" || exit 1
}

preflight() {
  mkdir -p "$LOGS"
  if [ ! -x .venv/bin/python ] && [ -z "${GM_PYTHON:-}" ]; then
    say "no .venv here; setting it up (npm run setup:py)"
    npm run setup:py
  fi
  if [ ! -s "voice/piper/$PIPER_VOICE.onnx" ]; then
    say "no Piper voice; downloading it (about 61 MB)"
    mkdir -p voice/piper
    for f in "$PIPER_VOICE.onnx.json" "$PIPER_VOICE.onnx"; do
      [ -s "voice/piper/$f" ] && continue
      curl -fL --progress-bar -o "voice/piper/$f.part" "$PIPER_URL/$f"
      mv "voice/piper/$f.part" "voice/piper/$f"
    done
  fi
  if ! grep -qE '^(ANTHROPIC_API_KEY|GEMINI_API_KEY)=.' .env.local 2>/dev/null; then
    say "no AI key in .env.local: ROB uses its scripted lines (the dashboard's Keys tab can add one)"
  fi
  # rob-audio: ROB's voice and the Mac's microphone with his voice taken out (docs/LISTEN-PLAN.md)
  if [ ! -x .cache/bin/rob-audio ] || [ scripts/rob-audio.swift -nt .cache/bin/rob-audio ]; then
    mkdir -p .cache/bin
    say "building rob-audio (echo cancellation for the Mac's microphone)"
    swiftc -O -swift-version 5 scripts/rob-audio.swift -o .cache/bin/rob-audio 2> "$LOGS/rob-audio-build.log" ||
      say "rob-audio did not build ($LOGS/rob-audio-build.log): the Mac's microphone will hear ROB's own voice"
  fi
  command -v stackchan-mcp > /dev/null || { say "stackchan-mcp is not installed (uv tool install stackchan-mcp)" >&2; exit 1; }
  # the gateway's ears: Whisper large-v3-turbo on the Mac's GPU (scripts/gateway.py)
  gp="$(uv tool dir)/stackchan-mcp/bin/python"
  if [ "$(uname -m)" = arm64 ] && ! "$gp" -c "import mlx_whisper" 2> /dev/null; then
    say "installing mlx-whisper into the gateway (better speech recognition)"
    uv pip install -q --python "$gp" mlx-whisper
  fi
}

# Stops whatever holds ROB's ports from another folder, after asking; 0 when this
# folder's ROB is already up and nothing has to start.
clear_ports() {
  others=$(running | while read -r p port dir; do [ "$dir" != "$ROOT" ] && echo "$p $port $dir"; done)
  if [ -n "$others" ]; then
    say "something else holds ROB's ports:"
    echo "$others" | while read -r p port dir; do echo "  port $port: pid $p from $dir"; done
    if ! ask "Stop it and start this folder's ROB?"; then say "left it running"; exit 1; fi
    for p in $(echo "$others" | awk '{ print $1 }' | sort -u); do kill "$p" 2>/dev/null || true; done
    n=0
    while [ -n "$(running | while read -r p port dir; do [ "$dir" != "$ROOT" ] && echo x; done)" ]; do
      n=$((n + 1)); [ "$n" -ge 20 ] && { say "it did not stop; try again or kill it by hand" >&2; exit 1; }
      sleep 0.5
    done
  fi
  [ -n "$(listening 8080)" ]
}

# Sets IP (the Mac's address for the robot's photos) and REFEREE.
pick_network() {
  if pi_up; then
    IP=$MAC_ADDR; REFEREE=remote
    say "the Pi answers: the games run on its referee, the Mac at $IP"
    return
  fi
  IP=$(wifi_addr)
  [ -n "$IP" ] || { say "this Mac has no Wi-Fi address; join the network the robot uses and run this again" >&2; exit 1; }
  if hotspot_pi_up && pi_ssh true 2>/dev/null; then
    REFEREE=remote
    say "the Pi answers on the hotspot: the games run on its referee, the Mac at $IP"
    return
  fi
  REFEREE=local
  say "no Pi: the games run on this Mac, at $IP on the current Wi-Fi; the robot has to be on the same network"
}

# The rules as they are in this folder go to the Pi (qnx/deploy.sh, with the table token
# the brain just made), then a referee runs there against this Mac's Table.
start_hotspot_referee() {
  stop_hotspot_referee
  if ! GM_PI=$HOTSPOT_PI sh qnx/deploy.sh > "$LOGS/deploy.log" 2>&1; then
    say "could not copy the rules to the Pi ($LOGS/deploy.log); the games will not start until a referee runs" >&2
    return 0
  fi
  nohup ssh -o BatchMode=yes -o ServerAliveInterval=10 ${GM_SSH_OPTS:-} "$HOTSPOT_PI" \
    "cd gm && exec python3 -u -m brain.referee --table 'http://$IP:$TABLE_PORT'" > "$LOGS/referee.log" 2>&1 &
  echo $! >> "$PIDS"
  : > "$LOGS/hotspot-referee"
  n=0
  until grep -q 'referee: playing' "$LOGS/referee.log" 2>/dev/null || [ "$n" -ge 15 ]; do n=$((n + 1)); sleep 1; done
  if grep -q 'referee: playing' "$LOGS/referee.log"; then say "the Pi's referee is playing"
  else say "the Pi's referee did not report in ($LOGS/referee.log)" >&2; fi
}

start() {
  preflight
  if clear_ports; then
    say "this folder's ROB is already running (npm run restart starts it over)"
    open "http://127.0.0.1:8080/dash"
    return
  fi
  pick_network
  # Starting a new run always discards the previous run, even in debug mode.
  for log in "$LOGS/"*.log; do [ ! -f "$log" ] || : > "$log"; done
  : > "$PIDS"

  p=$(listening 8767)
  if [ -n "$p" ]; then
    host=$(ps -E -p "$p" -o command= | tr ' ' '\n' | sed -n 's/^VISION_HOST=//p' | head -1)
    if [ "$host" != "$IP" ]; then
      say "the gateway has VISION_HOST=${host:-unset}, not $IP; restarting it"
      kill "$p"; sleep 1
      p=""
    fi
  fi
  if [ -x .cache/bin/rob-audio ]; then
    pkill -f "$ROOT/.cache/bin/rob-audio" 2>/dev/null || true
    rm -f .cache/audio/*.sock
    nohup "$ROOT/.cache/bin/rob-audio" "$ROOT/.cache/audio" > "$LOGS/rob-audio.log" 2>&1 &
    echo $! >> "$PIDS"
  fi
  if [ -z "$p" ]; then
    # scripts/gateway.py: the same gateway, with each listen ending when the talker stops
    VISION_HOST=$IP nohup "$(uv tool dir)/stackchan-mcp/bin/python" scripts/gateway.py serve --transport streamable-http > "$LOGS/gateway.log" 2>&1 &
    echo $! >> "$PIDS"
  fi
  [ -n "$(listening 8768)" ] || { nohup python3 scripts/ota-stub.py --port 8768 > "$LOGS/ota-stub.log" 2>&1 & echo $! >> "$PIDS"; }
  n=0
  until [ -n "$(listening 8767)" ]; do
    n=$((n + 1)); [ "$n" -ge 30 ] && { say "the gateway did not start ($LOGS/gateway.log)" >&2; exit 1; }
    sleep 1
  done

  : > "$LOGS/brain.log"
  nohup "$(python)" -m brain --referee "$REFEREE" --voice-dir voice --piper-model "voice/piper/$PIPER_VOICE.onnx" "$@" >> "$LOGS/brain.log" 2>&1 &
  echo $! >> "$PIDS"
  brain=$!
  n=0
  until curl -s -m 1 http://127.0.0.1:8080/state > /dev/null 2>&1; do
    n=$((n + 1))
    if ! kill -0 "$brain" 2>/dev/null || [ "$n" -ge 60 ]; then
      say "the brain did not start; its log:" >&2; tail -10 "$LOGS/brain.log" >&2; exit 1
    fi
    sleep 1
  done
  [ "$REFEREE" = remote ] && ! pi_up && start_hotspot_referee

  # A robot that is already on rejoins within a few seconds; one still booting shows up
  # on the dashboard when it joins, so there is no point holding the terminal for it.
  n=0
  until robot_joined || [ "$n" -ge 8 ]; do n=$((n + 1)); sleep 1; done
  robot_joined && say "the robot is connected"

  dash=$(sed -n 's/^gamemaster: dashboard at //p' "$LOGS/brain.log" | tail -1)
  echo
  say "ROB is running. Say \"let's play Mafia\" (or any game's name)."
  say "  dashboard:   ${dash:-http://127.0.0.1:8080/dash}"
  say "  games run:   $([ "$REFEREE" = remote ] && echo "on the Pi" || echo "on this Mac")"
  say "  logs:        $LOGS/"
  say "  stop:        npm run stop    restart: npm run restart"
  next_step
  open "http://127.0.0.1:8080/dash"
}

cmd=${1:-start}
[ $# -gt 0 ] && shift
if [ "${1:-}" = "-y" ]; then YES=1; shift; fi
case "$cmd" in
start) sync_check start ${YES:+-y} "$@"; start "$@" ;;
stop) stop ;;
restart) sync_check restart ${YES:+-y} "$@"; stop; start "$@" ;;
status) status ;;
*) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
