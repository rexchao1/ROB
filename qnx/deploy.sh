#!/bin/sh
# Copy the referee to the QNX Pi (~/gm, replaced whole) and check it starts there.
# It ships exactly the modules `python3 -S -m brain.referee` imports, found on this
# machine, so a new rules module is never left behind: the rules, the ears, the lines
# and the Table over the network, standard library only.
#
#   qnx/deploy.sh [--with-key] [user@host]     default $GM_PI, else the Pi on its own network when this
#                                 Mac is on it (qnx/ap/net.conf), else qnxuser@172.20.10.14
#
# Extra ssh options go in $GM_SSH_OPTS (word-split). The Pi needs Python 3 and tar.
set -eu
cd "$(dirname "$0")/.."
. qnx/ap/net.conf
DEFAULT=qnxuser@172.20.10.14  # the phone hotspot
if ifconfig 2>/dev/null | grep -q "inet $MAC_ADDR "; then DEFAULT=qnxuser@$PI_ADDR; fi
WITH_KEY=0
TARGET=""
for arg in "$@"; do
  case "$arg" in
    --with-key) WITH_KEY=1 ;;
    -*) echo "usage: qnx/deploy.sh [--with-key] [user@host]" >&2; exit 2 ;;
    *) if [ -n "$TARGET" ]; then echo "deploy: only one Pi target allowed" >&2; exit 2; fi; TARGET="$arg" ;;
  esac
done
PI="${TARGET:-${GM_PI:-$DEFAULT}}"
KEY_FILE=""
trap 'if [ -n "$KEY_FILE" ]; then rm -f "$KEY_FILE"; fi' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [ "$WITH_KEY" = 1 ]; then
  # Prepare before connecting. Neither keys nor their values go into shell arguments.
  KEY_FILE=$(mktemp)
  chmod 600 "$KEY_FILE"
  python3 qnx/deploy_key.py .env.local > "$KEY_FILE"
fi

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
if [ "$WITH_KEY" = 1 ]; then
  # Deliberate opt-in only; ~/gm is replaced on deploy, ~/gm-memory is not.
  # shellcheck disable=SC2086
  ssh ${GM_SSH_OPTS:-} "$PI" '
    set -e
    umask 077
    mkdir -p gm-memory
    chmod 700 gm-memory
    cat > gm-memory/talk.env.new
    chmod 600 gm-memory/talk.env.new
    mv -f gm-memory/talk.env.new gm-memory/talk.env
  ' < "$KEY_FILE"
  echo "deploy: Pi talk key installed in ~/gm-memory/talk.env (mode 600)"
fi
echo "deploy: run it with qnx/referee.sh http://<this machine>:8090 $PI"
