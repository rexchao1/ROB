#!/bin/sh
# The Pi's status light (qnx/led/status-led.py), from the Mac: red once the Pi is on,
# yellow once its Wi-Fi is up, green once the robot (ROBOT_MAC in qnx/ap/net.conf) is
# on the same Wi-Fi. The wiring is in qnx/README.md, "The status light".
#
#   qnx/led.sh install     copy it to ~/gmled on the Pi and (re)start it
#   qnx/led.sh test        each colour for 2 s (stops the running light first; install starts it again)
#   qnx/led.sh status      whether it runs, and its last lines
#   qnx/led.sh stop        stop it and switch the LED off
#   qnx/led.sh boot        start it at every power-on: one line in the Pi's post_startup.sh
#                          (backed up to ~/gmled/post_startup.sh.bak first)
#   qnx/led.sh unboot      take that line out again
#
# The Pi: $GM_PI, else qnxuser@PI_ADDR when this Mac is on the gamemaster network, else
# qnxuser@172.20.10.14 (the hotspot). Extra ssh options go in $GM_SSH_OPTS.
set -eu
cd "$(dirname "$0")/.."
. qnx/ap/net.conf
if [ -n "${GM_PI:-}" ]; then PI=$GM_PI
elif ifconfig 2>/dev/null | grep -q "inet $MAC_ADDR "; then PI=qnxuser@$PI_ADDR
else PI=qnxuser@172.20.10.14; fi
# shellcheck disable=SC2086
pi() { ssh ${GM_SSH_OPTS:-} "$PI" "$@"; }

HOME_PI=/data/home/qnxuser
RUN="python3 $HOME_PI/gmled/status-led.py --robot-mac $ROBOT_MAC --iface $IFACE --leases $HOME_PI/gmnet/leases.json"
POST=/system/etc/startup/post_startup.sh
HOOK="on -u qnxuser sh -c '$RUN >> $HOME_PI/gmled/led.log 2>&1' &  # gamemaster: the status light (qnx/README.md)"

stop_remote='for p in $(pidin -f aen ar 2>/dev/null | awk "/status-led.py/ && !/awk/ { print \$1 }"); do kill $p; done; sleep 1'

case "${1:-}" in
install)
  pi 'mkdir -p gmled' && scp ${GM_SSH_OPTS:-} -q qnx/led/status-led.py "$PI:gmled/status-led.py"
  pi "$stop_remote; nohup $RUN >> gmled/led.log 2>&1 < /dev/null & sleep 2; tail -3 gmled/led.log"
  echo "led: running on $PI"
  ;;
test)
  pi "$stop_remote; python3 gmled/status-led.py --test"
  ;;
status)
  pi 'pidin -f aen ar | grep "[s]tatus-led.py" || echo "led: not running"; tail -5 gmled/led.log 2>/dev/null'
  pi "grep -q 'gmled/status-led.py' $POST && echo 'led: starts at boot' || echo 'led: not started at boot'"
  ;;
stop)
  pi "$stop_remote"
  echo "led: stopped"
  ;;
boot)
  # The line goes before the file's last "exit 0", as qnx/ap/gm-net.sh persist does it.
  pi "sudo -n sh -c '
    set -e
    grep -q gmled/status-led.py $POST && { echo \"led: already in $POST\"; exit 0; }
    cp -p $POST $HOME_PI/gmled/post_startup.sh.bak
    n=\$(grep -n \"^exit 0\" $POST | tail -1 | cut -d: -f1)
    awk -v n=\"\${n:-0}\" -v hook=\"\$1\" \"NR == n { print hook } { print } END { if (n == 0) print hook }\" $POST > $POST.gm
    chmod 0555 $POST.gm && mv $POST.gm $POST
    echo \"led: starts at boot (backup: ~/gmled/post_startup.sh.bak)\"
  ' sh \"$HOOK\""
  ;;
unboot)
  pi "sudo -n sh -c 'grep -v gmled/status-led.py $POST > $POST.gm && chmod 0555 $POST.gm && mv $POST.gm $POST && echo \"led: no longer starts at boot\"'"
  ;;
*)
  sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
  ;;
esac
