#!/bin/sh
# Run the referee on the QNX Pi against the brain's Table, in the foreground over ssh
# (Ctrl-C stops it). The brain must be running with --referee remote.
#
#   qnx/referee.sh http://<mac>:8090 [user@host]     the Pi as in qnx/deploy.sh
#
# $GM_TABLE_TOKEN, when set, is passed on (the brain's --table-token); otherwise the
# referee reads ~/.gm-table-token on the Pi, put there by qnx/deploy.sh. Extra ssh
# options go in $GM_SSH_OPTS. On the Pi's own network a referee already runs from
# boot; this one takes the table from it, and `qnx/ap.sh referee-restart` gives it back.
set -eu
TABLE="${1:?usage: qnx/referee.sh http://<mac>:8090 [user@host]}"
. "$(dirname "$0")/ap/net.conf"
DEFAULT=qnxuser@172.20.10.14  # the phone hotspot
if ifconfig 2>/dev/null | grep -q "inet $MAC_ADDR "; then DEFAULT=qnxuser@$PI_ADDR; fi
PI="${2:-${GM_PI:-$DEFAULT}}"
TOKEN=""
if [ -n "${GM_TABLE_TOKEN:-}" ]; then TOKEN="GM_TABLE_TOKEN='$GM_TABLE_TOKEN' "; fi
# shellcheck disable=SC2086
exec ssh -t ${GM_SSH_OPTS:-} "$PI" "cd gm && ${TOKEN}exec python3 -m brain.referee --table '$TABLE'"
