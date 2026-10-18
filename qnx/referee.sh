#!/bin/sh
# Run the referee on the QNX Pi against the brain's Table, in the foreground over ssh
# (Ctrl-C stops it). The brain must be running with --referee remote.
#
#   qnx/referee.sh http://<mac>:8090 [user@host]     the Pi as in qnx/deploy.sh
#
# The Table's token (D85) is read by the referee itself from ~/.gm-table-token on the
# Pi, where qnx/deploy.sh put it: it is on no command line and in no process list.
# Extra ssh options go in $GM_SSH_OPTS. On the Pi's own network a referee already runs
# from boot; this one takes the table from it, and `qnx/ap.sh referee-restart` gives it
# back.
set -eu
TABLE="${1:?usage: qnx/referee.sh http://<mac>:8090 [user@host]}"
. "$(dirname "$0")/ap/net.conf"
DEFAULT=qnxuser@172.20.10.14  # the phone hotspot
if ifconfig 2>/dev/null | grep -q "inet $MAC_ADDR "; then DEFAULT=qnxuser@$PI_ADDR; fi
PI="${2:-${GM_PI:-$DEFAULT}}"
# shellcheck disable=SC2086
exec ssh -t ${GM_SSH_OPTS:-} "$PI" "cd gm && exec python3 -m brain.referee --table '$TABLE' --token-file \"\$HOME/.gm-table-token\""
