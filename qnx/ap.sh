#!/bin/sh
# The Pi's own Wi-Fi network (qnx/ap/net.conf), from the Mac. qnx/README.md has the
# order to do this in; nothing but `persist` writes a file outside ~/gmnet on the Pi.
#
#   qnx/ap.sh install            copy qnx/ap and the access point's setup (with the password
#                                from .env.local, made there if missing) to ~/gmnet on the Pi
#   qnx/ap.sh trial [SECONDS] [IFACE]
#                                the access point now, by hand, back to the hotspot by itself
#                                after SECONDS (300) unless confirmed; IFACE bcm1 runs it beside
#                                the hotspot link, so this ssh session survives
#   qnx/ap.sh persist            back up the two boot files and make the access point the boot
#                                setup, on probation (15 min after each boot until confirmed)
#   qnx/ap.sh reboot             reboot the Pi
#   qnx/ap.sh confirm            over the new network: keep it (or keep a trial until reboot)
#   qnx/ap.sh revert             back to the hotspot: end a trial, or restore the files and reboot
#   qnx/ap.sh status             what runs on the Pi: the boot setup, the access point, its clients
#   qnx/ap.sh referee-restart    start the Pi's boot referee again (after qnx/deploy.sh)
#
# The Pi: $GM_PI, else qnxuser@PI_ADDR when this Mac is on the gamemaster network, else
# qnxuser@172.20.10.14 (the hotspot). Extra ssh options go in $GM_SSH_OPTS; $GM_NET_DIR
# moves ~/gmnet (relative to the Pi's home).
set -eu
cd "$(dirname "$0")/.."
. qnx/ap/net.conf
if [ -n "${GM_PI:-}" ]; then PI=$GM_PI
elif ifconfig 2>/dev/null | grep -q "inet $MAC_ADDR "; then PI=qnxuser@$PI_ADDR
else PI=qnxuser@172.20.10.14; fi
DEST=${GM_NET_DIR:-gmnet}
# shellcheck disable=SC2086
pi() { ssh ${GM_SSH_OPTS:-} "$PI" "$@"; }

password() {
  if [ ! -s .env.local ] || ! grep -q '^GM_WIFI_PASSWORD=' .env.local; then
    pw=$(python3 -c 'import secrets; a = "abcdefghjkmnpqrstuvwxyz23456789"; print("-".join("".join(secrets.choice(a) for _ in range(4)) for _ in range(4)))')
    (umask 077; printf '# Local secrets, never committed (.gitignore: .env.*).\nGM_WIFI_PASSWORD=%s\n' "$pw" >> .env.local)
    echo "ap: a new Wi-Fi password is in .env.local" >&2
  fi
  pw=$(sed -n 's/^GM_WIFI_PASSWORD=//p' .env.local | tail -1)
  case "$pw" in *'"'*|*'\'*) echo "ap: GM_WIFI_PASSWORD must not hold quotes or backslashes" >&2; exit 1 ;; esac
  [ "${#pw}" -ge 8 ] && [ "${#pw}" -le 63 ] || { echo "ap: GM_WIFI_PASSWORD must be 8 to 63 characters" >&2; exit 1; }
  printf '%s' "$pw"
}

cmd="${1:-status}"
[ $# -gt 0 ] && shift
case "$cmd" in
install)
  pw=$(password)
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  cp qnx/ap/net.conf qnx/ap/gm-net.sh qnx/ap/dhcpd.py qnx/ap/wpactl.py "$tmp"/
  (umask 077; cat > "$tmp/ap.conf" <<EOF
# The $SSID network: this Pi as a WPA2 access point (wpa_supplicant's AP mode).
# Written by qnx/ap.sh install; the password is GM_WIFI_PASSWORD in the Mac's .env.local.
ctrl_interface=/var/run/wpa_supplicant
ap_scan=1

network={
    ssid="$SSID"
    mode=2
    frequency=$FREQ
    key_mgmt=WPA-PSK
    proto=RSN
    pairwise=CCMP
    group=CCMP
    psk="$pw"
}
EOF
  )
  COPYFILE_DISABLE=1 tar --format ustar -C "$tmp" -cf - net.conf gm-net.sh dhcpd.py wpactl.py ap.conf | pi "
    set -e
    mkdir -p $DEST && tar -C $DEST -xf - && chmod 700 $DEST && chmod 600 $DEST/ap.conf && chmod 755 $DEST/gm-net.sh
    sh -n $DEST/gm-net.sh && python3 -S $DEST/dhcpd.py --help > /dev/null
    echo \"ap: installed in $DEST on \$(hostname); nothing else changed\"
  "
  ;;
trial|persist|confirm|revert|status|referee-restart)
  pi "sudo -n $DEST/gm-net.sh $cmd $*"
  if [ "$cmd" = trial ]; then
    echo "ap: on bcm0 this ssh link goes with the hotspot; the Pi comes back on it by itself when the trial ends"
  fi
  if [ "$cmd" = persist ]; then
    echo "ap: reboot the Pi to start it (qnx/ap.sh reboot); then within $PROBATION s, from the gamemaster network: qnx/ap.sh confirm"
  fi
  ;;
reboot)
  pi 'sudo -n shutdown -S reboot' || true
  echo "ap: the Pi is rebooting (about a minute)"
  ;;
*)
  sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
  ;;
esac
