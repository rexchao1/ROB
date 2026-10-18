#!/bin/sh
# Copy the referee to the QNX Pi (~/gm, replaced whole) and check it starts there.
# It ships exactly the modules `python3 -S -m brain.referee` imports, found on this
# machine, so a new rules module is never left behind: the rules, the ears, the lines
# and the Table over the network, standard library only.
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
echo "deploy: run it with qnx/referee.sh http://<this machine>:8090 $PI"
