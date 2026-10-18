#!/bin/sh
# The game's own Wi-Fi network on the QNX Pi: the Wi-Fi as a WPA2 access point (the
# AP mode of the image's wpa_supplicant; QNX has no hostapd), a fixed address,
# dhcpd.py, and the referee at boot. qnx/ap.sh on the Mac installs this to ~/gmnet
# and runs it; the commands it takes (as root):
#
#   gm-net.sh status
#   gm-net.sh trial [SECONDS] [IFACE]   the access point now, by hand, nothing written; back to
#                                       the hotspot after SECONDS (net.conf TRIAL) unless confirmed.
#                                       IFACE bcm1 runs it beside the hotspot link instead of on it.
#   gm-net.sh persist                   back up, then make the access point the boot setup, on
#                                       probation: a boot not confirmed within PROBATION seconds
#                                       puts the backups back and reboots
#   gm-net.sh confirm                   keep what runs: a trial until reboot, the boot setup for good
#   gm-net.sh revert                    back to the hotspot: end a trial, or restore and reboot
#   gm-net.sh referee-restart           start the boot referee again (after qnx/deploy.sh)
#   gm-net.sh boot                      from post_startup.sh, in the background
#
# Files it changes (persist), each backed up to ~/gmnet/backup first:
# /data/var/etc/settings/wpa_supplicant.conf (the AP setup) and
# /system/etc/startup/post_startup.sh (one line that runs `gm-net.sh boot`).
set -u
DIR=$(cd "$(dirname "$0")" && pwd)
[ "$(id -u)" = 0 ] || exec sudo -n "$DIR/gm-net.sh" "$@"
. "$DIR/net.conf"
RUN=$DIR/run
LOG=$DIR/log
BAK=$DIR/backup
WPA_CONF=/data/var/etc/settings/wpa_supplicant.conf
POST=/system/etc/startup/post_startup.sh
HOOK="[ -x $DIR/gm-net.sh ] && $DIR/gm-net.sh boot >/dev/null 2>&1 &  # gamemaster: the Pi's own Wi-Fi network (qnx/README.md)"
STATION="wpa_supplicant-2.11 -Dqwdi -t -Z100 -i bcm0 -c $WPA_CONF"  # as start_net.sh starts it
mkdir -p "$RUN" "$LOG"

say() { echo "gm-net: $*"; echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG/gm-net.log"; }
die() { say "$*"; exit 1; }
pids_of() { pidin -f aen ar 2>/dev/null | awk -v re="$1" '$0 ~ re && $0 !~ /awk/ { print $1 }'; }
kill_pidfile() { [ -s "$RUN/$1.pid" ] && kill "$(cat "$RUN/$1.pid")" 2>/dev/null; rm -f "$RUN/$1.pid"; }
mac_of() { ifconfig "$1" | awk '/ether/ { print $2 }'; }
wpa_get() { python3 "$DIR/wpactl.py" "$1" get "$2" 2>/dev/null; }
is_ap_boot() { grep -q '^[[:space:]]*mode=2' "$WPA_CONF" 2>/dev/null; }
has_hook() { grep -q "$DIR/gm-net.sh boot" "$POST"; }
ipv4_of() { ifconfig "$1" | awk '$1 == "inet" { print $2 }'; }

wait_ap() {  # IFACE SECONDS: until wpa_supplicant there reports the access point running
  n=0
  while [ "$n" -lt "$2" ]; do
    [ "$(wpa_get "$1" wpa_state)" = COMPLETED ] && [ "$(wpa_get "$1" mode)" = AP ] && return 0
    sleep 2; n=$((n + 2))
  done
  return 1
}

start_ap() {  # IFACE CONF
  wpa_supplicant-2.11 -Dqwdi -t -Z100 -i "$1" -c "$2" >> "$LOG/wpa-$1.log" 2>&1 &
  echo $! > "$RUN/wpa-$1.pid"
  wait_ap "$1" 40
}

set_addr() { ifconfig "$1" inet "$PI_ADDR" netmask "$NETMASK"; }
clear_addr() { ifconfig "$1" inet "$PI_ADDR" -alias 2>/dev/null; }

dhcpd_loop() {  # IFACE: dhcpd.py, started again if it stops
  while [ ! -e "$RUN/dhcpd-off" ]; do
    python3 "$DIR/dhcpd.py" --iface "$1" --server "$PI_ADDR" --netmask "$NETMASK" --pool "$POOL" \
      --leases "$DIR/leases.json" --ignore "$(mac_of "$1")" >> "$LOG/dhcpd.log" 2>&1
    say "dhcpd stopped ($?); again in 2 s"
    sleep 2
  done
}

start_dhcpd() { rm -f "$RUN/dhcpd-off"; dhcpd_loop "$1" & echo $! > "$RUN/dhcpd-loop.pid"; }
stop_dhcpd() {
  touch "$RUN/dhcpd-off"; kill_pidfile dhcpd-loop
  for p in $(pids_of "python3 $DIR/dhcpd.py"); do kill "$p" 2>/dev/null; done
}

referee_loop() {  # the referee as qnxuser against the Mac's Table, until another referee takes the table
  table="http://$MAC_ADDR:$TABLE_PORT"
  while [ ! -e "$RUN/referee-off" ]; do
    if [ -d /data/home/qnxuser/gm/brain ]; then
      on -u qnxuser sh -c 'cd /data/home/qnxuser/gm && exec python3 -m brain.referee --table "$0" --token-file /data/home/qnxuser/.gm-table-token' "$table" >> "$LOG/referee.log" 2>&1  # the token qnx/deploy.sh put there (D85)
      rc=$?
      if [ "$rc" = 3 ]; then
        say "referee: another referee took the table; this one stays off (gm-net.sh referee-restart)"
        break
      fi
      say "referee stopped ($rc); again in 5 s"
    fi
    sleep 5
  done
  rm -f "$RUN/referee-loop.pid"
}

start_referee() {
  rm -f "$RUN/referee-off"
  if [ -s "$RUN/referee-loop.pid" ] && kill -0 "$(cat "$RUN/referee-loop.pid")" 2>/dev/null; then
    for p in $(pids_of "brain.referee --table http://$MAC_ADDR:"); do kill "$p"; done  # the loop starts it again
  else
    nohup "$DIR/gm-net.sh" _referee < /dev/null > /dev/null 2>&1 &
  fi
}

back_to_station() {  # bcm0 to the hotspot as at boot; a reboot if it does not get an address
  $STATION >> "$LOG/wpa-bcm0.log" 2>&1 &
  sleep 3
  dhcpcd -n bcm0 >> "$LOG/gm-net.log" 2>&1
  n=0
  while [ "$n" -lt 90 ]; do
    a=$(ipv4_of bcm0)
    if [ -n "$a" ] && [ "$a" != "$PI_ADDR" ]; then say "bcm0 is back on the hotspot at $a"; return 0; fi
    sleep 3; n=$((n + 3))
  done
  say "bcm0 has no hotspot address after 90 s: rebooting (nothing was written, so the boot setup is the hotspot)"
  shutdown -S reboot
}

restore() {  # the backed-up files back in place; the backups move aside so the next persist takes fresh ones
  [ -e "$BAK/wpa_supplicant.conf" ] || [ -e "$BAK/post_startup.sh" ] || die "no backups in $BAK"
  if [ -e "$BAK/wpa_supplicant.conf" ]; then
    cp -p "$BAK/wpa_supplicant.conf" "$WPA_CONF.gm" && chown root:root "$WPA_CONF.gm" && chmod 0640 "$WPA_CONF.gm" && mv "$WPA_CONF.gm" "$WPA_CONF"
  fi
  if [ -e "$BAK/post_startup.sh" ]; then
    cp -p "$BAK/post_startup.sh" "$POST.gm" && chmod 0555 "$POST.gm" && mv "$POST.gm" "$POST"
  fi
  rm -f "$DIR/confirmed"
  old="$BAK/restored-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$old" && mv "$BAK"/wpa_supplicant.conf "$BAK"/post_startup.sh "$old"/ 2>/dev/null
  say "restored $WPA_CONF and $POST (the backups are now in $old)"
}

cmd="${1:-status}"
[ $# -gt 0 ] && shift
case "$cmd" in
status)
  if is_ap_boot; then
    if [ -e "$DIR/confirmed" ]; then echo "boot setup: the $SSID access point (confirmed)"; else echo "boot setup: the $SSID access point (on probation)"; fi
  else
    echo "boot setup: the hotspot client"
  fi
  has_hook && echo "post_startup.sh: runs gm-net.sh boot"
  [ -e "$RUN/trial" ] && echo "trial: running on $(cat "$RUN/trial")$([ -e "$RUN/trial-confirmed" ] && echo ', confirmed')"
  for i in bcm0 bcm1; do
    echo "$i: $(ipv4_of $i | tr '\n' ' ')$(wpa_get $i mode) $(wpa_get $i wpa_state) $(wpa_get $i ssid) $(wpa_get $i freq)"
    [ "$(wpa_get $i mode)" = AP ] && echo "  clients: $(python3 "$DIR/wpactl.py" $i stations | tr '\n' ' ')"
  done
  echo "dhcpd: $(pids_of "python3 $DIR/dhcpd.py" | tr '\n' ' ')"
  echo "referee: $(pids_of 'brain.referee --table' | tr '\n' ' ')"
  [ -s "$DIR/leases.json" ] && { echo "leases:"; cat "$DIR/leases.json"; }
  exit 0
  ;;
trial)
  [ -s "$DIR/ap.conf" ] || die "no $DIR/ap.conf: run qnx/ap.sh install on the Mac"
  is_ap_boot && die "the boot setup is already the access point"
  [ -e "$RUN/trial" ] && die "a trial is running ($(cat "$RUN/trial")); gm-net.sh revert ends it"
  secs="${1:-$TRIAL}"; ifc="${2:-$IFACE}"
  echo "$ifc" > "$RUN/trial"
  rm -f "$RUN/trial-confirmed"
  # Detached from this ssh session: on bcm0 the session ends as soon as the hotspot link goes.
  nohup "$DIR/gm-net.sh" _trial "$secs" "$ifc" < /dev/null >> "$LOG/trial.log" 2>&1 &
  say "trial: $SSID on $ifc for $secs s unless confirmed (log: $LOG/trial.log)"
  ;;
_trial)
  secs="$1"; ifc="$2"
  nohup "$DIR/gm-net.sh" _watchdog "$secs" < /dev/null > /dev/null 2>&1 &
  echo $! > "$RUN/watchdog.pid"
  conf="$RUN/ap-$ifc.conf"
  cp "$DIR/ap.conf" "$conf" && chmod 600 "$conf"
  if [ "$ifc" = bcm0 ]; then
    for p in $(pids_of "wpa_supplicant-2.11 .*-i bcm0 "); do kill "$p"; done
    dhcpcd -x bcm0 2>/dev/null
    sleep 2
  else
    f=$(wpa_get bcm0 freq)  # beside a station link the access point must share its channel
    if [ -n "$f" ]; then sed "s/^\([[:space:]]*frequency=\).*/\1$f/" "$DIR/ap.conf" > "$conf"; fi
  fi
  if start_ap "$ifc" "$conf"; then
    set_addr "$ifc"
    start_dhcpd "$ifc"
    say "trial: $SSID is up on $ifc ($(wpa_get "$ifc" freq) MHz) at $PI_ADDR"
  else
    say "trial: the access point did not come up on $ifc (see $LOG/wpa-$ifc.log); going back"
    "$DIR/gm-net.sh" revert
  fi
  ;;
_watchdog)
  sleep "$1"
  if [ -e "$RUN/trial" ] && [ ! -e "$RUN/trial-confirmed" ]; then
    say "trial: $1 s and no confirm: going back to the hotspot"
    "$DIR/gm-net.sh" revert
  fi
  ;;
persist)
  [ -s "$DIR/ap.conf" ] || die "no $DIR/ap.conf: run qnx/ap.sh install on the Mac"
  [ -e "$RUN/trial" ] && die "a trial is running; gm-net.sh revert ends it first"
  is_ap_boot && has_hook && die "already the boot setup ($( [ -e "$DIR/confirmed" ] && echo confirmed || echo on probation))"
  mkdir -p "$BAK" && chmod 700 "$BAK"
  [ -e "$BAK/wpa_supplicant.conf" ] || cp -p "$WPA_CONF" "$BAK/wpa_supplicant.conf" || die "could not back up $WPA_CONF"
  [ -e "$BAK/post_startup.sh" ] || cp -p "$POST" "$BAK/post_startup.sh" || die "could not back up $POST"
  if ! has_hook; then
    n=$(grep -n '^exit 0' "$POST" | tail -1 | cut -d: -f1)
    awk -v n="${n:-0}" -v hook="$HOOK" 'NR == n { print hook } { print } END { if (n == 0) print hook }' "$POST" > "$POST.gm" \
      && chmod 0555 "$POST.gm" && mv "$POST.gm" "$POST" || die "could not add the boot line to $POST"
  fi
  cp "$DIR/ap.conf" "$WPA_CONF.gm" && chown root:root "$WPA_CONF.gm" && chmod 0640 "$WPA_CONF.gm" && mv "$WPA_CONF.gm" "$WPA_CONF" \
    || die "could not write $WPA_CONF"
  rm -f "$DIR/confirmed"
  say "persist: the boot setup is the $SSID access point, on probation for $PROBATION s after each boot until confirmed; backups in $BAK"
  ;;
boot)
  rm -f "$RUN"/*.pid "$RUN"/*-off "$RUN"/trial "$RUN"/trial-confirmed
  if ! is_ap_boot; then say "boot: the boot setup is the hotspot client; nothing to do"; exit 0; fi
  if [ ! -e "$DIR/confirmed" ]; then
    nohup "$DIR/gm-net.sh" _probation < /dev/null > /dev/null 2>&1 &
    echo $! > "$RUN/probation.pid"
  fi
  wait_ap bcm0 60 || say "boot: the access point is not up after 60 s (see $LOG/gm-net.log)"
  dhcpcd -x bcm0 2>/dev/null  # dhcpcd is for the hotspot; this network's address is fixed
  sleep 1
  set_addr bcm0
  start_dhcpd bcm0
  start_referee
  say "boot: $SSID at $PI_ADDR ($(wpa_get bcm0 freq) MHz), dhcpd and the referee started$([ -e "$DIR/confirmed" ] || echo ", on probation for $PROBATION s")"
  ;;
_probation)
  sleep "$PROBATION"
  if [ ! -e "$DIR/confirmed" ] && is_ap_boot; then
    say "probation: $PROBATION s and no confirm: back to the hotspot and reboot"
    restore && shutdown -S reboot
  fi
  ;;
_referee)
  echo $$ > "$RUN/referee-loop.pid"
  referee_loop
  ;;
confirm)
  if [ -e "$RUN/trial" ]; then
    touch "$RUN/trial-confirmed"; kill_pidfile watchdog
    say "confirm: the trial on $(cat "$RUN/trial") stays until a reboot or gm-net.sh revert"
  elif is_ap_boot; then
    touch "$DIR/confirmed"; kill_pidfile probation
    say "confirm: the $SSID access point is the boot setup for good"
  else
    die "nothing to confirm"
  fi
  ;;
revert)
  if [ -e "$RUN/trial" ]; then
    ifc=$(cat "$RUN/trial")
    kill_pidfile watchdog
    stop_dhcpd
    kill_pidfile "wpa-$ifc"
    clear_addr "$ifc"
    rm -f "$RUN/trial" "$RUN/trial-confirmed"
    say "revert: the trial on $ifc is over"
    [ "$ifc" = bcm0 ] && back_to_station
  elif is_ap_boot || has_hook; then
    restore
    say "revert: rebooting into the hotspot client"
    shutdown -S reboot
  else
    say "revert: already the hotspot client"
  fi
  ;;
referee-restart)
  is_ap_boot || [ -e "$RUN/trial" ] || die "the referee starts at boot only on the $SSID network; use qnx/referee.sh"
  start_referee
  say "referee: (re)started against http://$MAC_ADDR:$TABLE_PORT (log: $LOG/referee.log)"
  ;;
*)
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
  ;;
esac
