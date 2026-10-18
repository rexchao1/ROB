#!/bin/sh
# Copy the referee to the QNX Pi (~/gm, replaced whole) and check it starts there.
# It ships exactly the modules `python3 -S -m brain.referee` imports, found on this
# machine, so a new rules module is never left behind: the rules, the ears, the lines
# and the Table over the network, standard library only. Then the Table's token (D85),
# GM_TABLE_TOKEN in .env.local (the brain generates one at its first --referee remote
# start), goes to ~/.gm-table-token on the Pi (mode 600) over ssh's stdin: it is on no
# command line and in no process list; qnx/referee.sh and the boot referee read it there.
#
#   qnx/deploy.sh [user@host]     default $GM_PI, else the Pi on its own network when this
#                                 Mac is on it (qnx/ap/net.conf), else qnxuser@172.20.10.14
#
# Extra ssh options go in $GM_SSH_OPTS (word-split). The Pi needs Python 3 and tar.
set -eu
cd "$(dirname "$0")/.."
. qnx/ap/net.conf
DEFAULT=qnxuser@172.20.10.14  # the phone hotspot
if ifconfig 2>/dev/null | grep -q "inet $MAC_ADDR "; then DEFAULT=qnxuser@$PI_ADDR; fi
PI="${1:-${GM_PI:-$DEFAULT}}"

FILES=$(python3 -S -c '
import os, sys
import brain.referee
root = os.getcwd()
print(" ".join(sorted(os.path.relpath(m.__file__, root) for n, m in sys.modules.items() if n == "brain" or n.startswith("brain."))))
')
echo "deploy: $FILES" | fold -s -w 100

# ustar and no AppleDouble files: nothing a non-Mac tar warns about.
# shellcheck disable=SC2086
COPYFILE_DISABLE=1 tar --format ustar -cf - $FILES | ssh ${GM_SSH_OPTS:-} "$PI" '
  set -e
  rm -rf gm.new && mkdir gm.new && tar -C gm.new -xf -
  cd gm.new && python3 -S -m brain.referee --help > /dev/null
  cd .. && rm -rf gm && mv gm.new gm
  echo "deploy: the referee is in ~/gm on $(hostname) ($(python3 --version))"
'
TOKEN=$(python3 -S -c 'import brain.keys as k; print(k.read_env().get("GM_TABLE_TOKEN", ""))')
if [ -n "$TOKEN" ]; then
  # shellcheck disable=SC2086
  printf '%s\n' "$TOKEN" | ssh ${GM_SSH_OPTS:-} "$PI" '
    umask 077 && cat > .gm-table-token.new && mv .gm-table-token.new .gm-table-token
    echo "deploy: the table token is in ~/.gm-table-token (mode 600)"
  '
else
  echo "deploy: no GM_TABLE_TOKEN in .env.local yet: start the brain once with --referee remote (it generates one), then deploy again"
fi
echo "deploy: run it with qnx/referee.sh http://<this machine>:8090 $PI"
