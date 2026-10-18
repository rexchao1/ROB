#!/bin/sh
# Everything a game needs on the Mac, in one terminal: the stackchan-mcp gateway (with
# VISION_HOST, so the robot can send its photos here), the OTA stub the robot checks in
# with, and the brain serving the Table to the referee on the QNX Pi. Ctrl-C stops what
# this started. A gateway or stub already running is left alone and used.
#
#   scripts/game.sh [brain flags...]      e.g. --speaker mac --banter none --day-seconds 60
#
# The Mac's address is MAC_ADDR in qnx/ap/net.conf ($GM_MAC_IP overrides it); the
# referee on the Pi starts at boot and attaches by itself (qnx/README.md). Logs of the
# gateway and the stub go to .cache/game/.
set -eu
cd "$(dirname "$0")/.."
. qnx/ap/net.conf
IP=${GM_MAC_IP:-$MAC_ADDR}
LOGS=.cache/game
mkdir -p "$LOGS"
listening() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1; }
STARTED=""
stop() {
  for p in $STARTED; do kill "$p" 2>/dev/null || true; done
}
trap stop EXIT
trap 'exit 130' INT TERM

if ! ifconfig | grep -q "inet $IP "; then
  echo "game: this Mac does not have $IP (scripts/wifi.sh game puts it on the $SSID network); going on anyway"
fi
for port in 8080 "$TABLE_PORT"; do
  p=$(listening "$port")
  if [ -n "$p" ]; then echo "game: port $port is taken (pid $p, $(ps -p "$p" -o comm=)); is a brain already running?" >&2; exit 1; fi
done

p=$(listening 8767)
if [ -n "$p" ]; then
  host=$(ps -E -p "$p" -o command= | tr ' ' '\n' | sed -n 's/^VISION_HOST=//p' | head -1)
  if [ "$host" != "$IP" ]; then
    echo "game: the gateway running now (pid $p) has VISION_HOST=${host:-unset}, so the robot's photos would not reach $IP; stop it and run this again" >&2
    exit 1
  fi
  echo "game: the gateway is already running (pid $p), VISION_HOST=$host"
else
  VISION_HOST=$IP stackchan-mcp serve --transport streamable-http >> "$LOGS/gateway.log" 2>&1 &
  STARTED="$STARTED $!"
  echo "game: gateway started (pid $!, VISION_HOST=$IP, log $LOGS/gateway.log)"
fi

p=$(listening 8768)
if [ -n "$p" ]; then
  echo "game: the OTA stub is already running (pid $p)"
else
  python3 scripts/ota-stub.py --port 8768 >> "$LOGS/ota-stub.log" 2>&1 &
  STARTED="$STARTED $!"
  echo "game: OTA stub started (pid $!, log $LOGS/ota-stub.log)"
fi

n=0
until [ -n "$(listening 8767)" ]; do
  n=$((n + 1))
  if [ "$n" -ge 30 ]; then echo "game: the gateway did not open :8767 in 30 s ($LOGS/gateway.log)" >&2; exit 1; fi
  sleep 1
done

if [ -e voice/piper/en_US-lessac-medium.onnx ]; then set -- --piper-model voice/piper/en_US-lessac-medium.onnx "$@"; fi
set -- --referee remote --voice-dir voice "$@"  # flags given here come last and win
echo "game: the robot joins the gateway within 20 s; the Pi's referee attaches to http://$IP:$TABLE_PORT by itself (qnx/ap.sh status)"
echo "game: brain $*"
node scripts/py.mjs -m brain "$@"
