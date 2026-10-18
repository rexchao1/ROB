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
#   gm-net.sh uplink trial [SECONDS]    the access point on bcm1 beside bcm0's hotspot link, on its
#                                       channel, so the Pi keeps its internet; ends like a trial
#   gm-net.sh uplink persist            back up post_startup.sh, then make that the boot setup, on
#                                       probation; a boot that finds no hotspot within UPLINK_WAIT
#                                       seconds runs the access point alone on bcm0 instead
#   gm-net.sh confirm                   keep what runs: a trial until reboot, the boot setup for good
#   gm-net.sh revert                    back to the hotspot: end a trial, or restore and reboot
#   gm-net.sh referee-restart           start the boot referee again (after qnx/deploy.sh)
#   gm-net.sh boot | uplink boot        from post_startup.sh, in the background
#
# Files it changes (persist), each backed up to ~/gmnet/backup first:
# /data/var/etc/settings/wpa_supplicant.conf (the AP setup) and
# /system/etc/startup/post_startup.sh (one line that runs `gm-net.sh boot`).
# `uplink persist` changes post_startup.sh only (one line that runs `gm-net.sh uplink
# boot`; backed up to ~/gmnet/backup/uplink first): bcm0 keeps the hotspot setup.
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
# Not "gm-net.sh boot..." on purpose: has_hook must not find this line, nor has_uplink_hook that one.
HOOK_UPLINK="[ -x $DIR/gm-net.sh ] && $DIR/gm-net.sh uplink boot >/dev/null 2>&1 &  # gamemaster beside the hotspot link, so the Pi keeps its internet (qnx/README.md)"
UPLINK_WAIT=${UPLINK_WAIT:-60}
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
has_uplink_hook() { grep -q "$DIR/gm-net.sh uplink boot" "$POST"; }
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
      on -u qnxuser sh -c 'cd /data/home/qnxuser/gm && exec python3 -m brain.referee --table "$0"' "$table" >> "$LOG/referee.log" 2>&1
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

# The uplink: bcm0 stays the hotspot's station (start_net.sh starts it from $WPA_CONF, and
# dhcpcd gives it the phone's address, default route and DNS), and the access point runs on
# bcm1 beside it. The driver runs the two on one channel only, so the access point takes
# the hotspot's, and the robot (ESP32) needs that to be 2.4 GHz.

hotspot_addr() {  # bcm0's address on the hotspot; fails while bcm0 is not on it
  [ "$(wpa_get bcm0 mode)" = station ] && [ "$(wpa_get bcm0 wpa_state)" = COMPLETED ] || return 1
  for h in $(ipv4_of bcm0); do
    case "$h" in "$PI_ADDR"|169.254.*) ;; *) echo "$h"; return 0 ;; esac
  done
  return 1
}

wait_hotspot() {  # SECONDS: until bcm0 is on the hotspot with an address
  w=0
  while [ "$w" -lt "$1" ]; do
    hotspot_addr > /dev/null && return 0
    sleep 2; w=$((w + 2))
  done
  return 1
}

is_24ghz() { case "$1" in 24[0-9][0-9]) return 0 ;; esac; return 1; }

uplink_ap() {  # the access point on bcm1 on the hotspot's channel, its address and dhcpd; UPLINK_WHY says why not
  UPLINK_WHY=""
  hf=$(wpa_get bcm0 freq)
  if ! is_24ghz "$hf"; then
    UPLINK_WHY="the hotspot is on ${hf:-an unknown} MHz, not 2.4 GHz (the iPhone's Maximize Compatibility is off)"
    return 1
  fi
  (umask 077; sed "s/^\([[:space:]]*frequency=\).*/\1$hf/" "$DIR/ap.conf" > "$RUN/ap-bcm1.conf")
  if ! start_ap bcm1 "$RUN/ap-bcm1.conf"; then
    kill_pidfile wpa-bcm1
    UPLINK_WHY="the access point did not come up on bcm1 (see $LOG/wpa-bcm1.log)"
    return 1
  fi
  dhcpcd -x bcm1 > /dev/null 2>&1  # dhcpcd is for the hotspot (bcm0 only); this network's address is fixed
  set_addr bcm1
  start_dhcpd bcm1
}

ap_alone() {  # what `boot` runs: the access point alone on bcm0 on net.conf's channel; no hotspot, no internet
  kill_pidfile wpa-bcm1; clear_addr bcm1
  for p in $(pids_of "wpa_supplicant-2.11 .*-i bcm0 "); do kill "$p"; done
  dhcpcd -x bcm0 2>/dev/null
  sleep 2
  (umask 077; cp "$DIR/ap.conf" "$RUN/ap-bcm0.conf")
  start_ap bcm0 "$RUN/ap-bcm0.conf" || say "the access point is not up on bcm0 after 40 s (see $LOG/wpa-bcm0.log)"
  set_addr bcm0
  start_dhcpd bcm0
}

uplink_unhook() {  # the uplink's line out of post_startup.sh; the rest of the file stays as it is
  grep -v "$DIR/gm-net.sh uplink boot" "$POST" > "$POST.gm" && chmod 0555 "$POST.gm" && mv "$POST.gm" "$POST" \
    && rm -f "$DIR/uplink-confirmed" "$RUN/uplink"
}

default_route() {  # "GATEWAY on IFACE", empty without a default route
  r=$(route -n get default 2>/dev/null | awk '$1 == "gateway:" { g = $2 } $1 == "interface:" { i = $2 } END { if (g != "") print g " on " i }')
  [ -n "$r" ] || r=$(netstat -rn 2>/dev/null | awk '$1 == "default" { print $2 " on " $NF; exit }')
  echo "$r"
}

route_iface() { route -n get "$1" 2>/dev/null | awk '$1 == "interface:" { print $2 }'; }

internet() {  # one line: whether this Pi reaches the Anthropic API (DNS, then HTTPS); standard library only
  python3 - <<'EOF' 2>&1
import os, socket, sys, threading, time

HOST = "api.anthropic.com"


def check() -> str:
    found = []

    def look() -> None:
        try:
            found.append(socket.getaddrinfo(HOST, 443, socket.AF_INET, socket.SOCK_STREAM)[0][4][0])
        except OSError as e:
            found.append(e)

    t = threading.Thread(target=look, daemon=True)
    t.start()
    t.join(6)
    addr = found[0] if found else "no DNS answer in 6 s"
    if not isinstance(addr, str) or not found:
        try:
            socket.create_connection(("1.1.1.1", 443), timeout=4).close()
            return f"no: 1.1.1.1 answers, but {HOST} has no address ({addr}): no DNS from the phone"
        except OSError as e:
            return f"no: {HOST} has no address ({addr}) and 1.1.1.1 does not answer ({e})"
    try:
        import http.client
        import ssl
    except ImportError as e:
        return f"partly: {HOST} is {addr}, but this Python has no TLS ({e})"
    t0 = time.monotonic()
    try:
        c = http.client.HTTPSConnection(HOST, 443, timeout=8, context=ssl.create_default_context())
        c.request("HEAD", "/")
        status = c.getresponse().status
        return f"yes: https://{HOST} ({addr}) answers {status} in {time.monotonic() - t0:.1f} s"
    except ssl.SSLCertVerificationError as e:
        return f"partly: {HOST} answers, but its certificate cannot be checked ({e.verify_message}): Python here needs CA certificates"
    except (OSError, http.client.HTTPException) as e:
        return f"no: {HOST} is {addr}, but HTTPS to it fails ({e})"


print(check(), flush=True)
os._exit(0)  # a DNS lookup still stuck in its thread must not hold the exit
EOF
}

cmd="${1:-status}"
[ $# -gt 0 ] && shift
case "$cmd" in
status)
  if is_ap_boot; then
    if [ -e "$DIR/confirmed" ]; then echo "boot setup: the $SSID access point (confirmed)"; else echo "boot setup: the $SSID access point (on probation)"; fi
  elif has_uplink_hook; then
    echo "boot setup: the uplink: bcm0 on the hotspot, the $SSID access point beside it on bcm1 ($([ -e "$DIR/uplink-confirmed" ] && echo confirmed || echo on probation))"
  else
    echo "boot setup: the hotspot client"
  fi
  has_hook && echo "post_startup.sh: runs gm-net.sh boot"
  has_uplink_hook && echo "post_startup.sh: runs gm-net.sh uplink boot"
  has_uplink_hook && [ -s "$RUN/uplink" ] && echo "this boot: $(cat "$RUN/uplink")"
  [ -e "$RUN/trial" ] && echo "trial: running on $(cat "$RUN/trial")$([ -e "$RUN/trial-confirmed" ] && echo ', confirmed')"
  for i in bcm0 bcm1; do
    echo "$i: $(ipv4_of $i | tr '\n' ' ')$(wpa_get $i mode) $(wpa_get $i wpa_state) $(wpa_get $i ssid) $(wpa_get $i freq)"
    [ "$(wpa_get $i mode)" = AP ] && echo "  clients: $(python3 "$DIR/wpactl.py" $i stations | tr '\n' ' ')"
  done
  echo "dhcpd: $(pids_of "python3 $DIR/dhcpd.py" | tr '\n' ' ')"
  echo "referee: $(pids_of 'brain.referee --table' | tr '\n' ' ')"
  if a=$(hotspot_addr); then
    hf=$(wpa_get bcm0 freq)
    echo "uplink: up: bcm0 at $a on $(wpa_get bcm0 ssid), $hf MHz$(is_24ghz "$hf" || echo ' (not 2.4 GHz: the robot cannot join an access point beside it)')"
  else
    echo "uplink: down (bcm0 is not on the hotspot)"
  fi
  dr=$(default_route)
  echo "default route: ${dr:-none}"
  to=$(route_iface "$MAC_ADDR")
  echo "to the Mac ($MAC_ADDR): ${to:-no route}$([ -n "$to" ] && [ "$(wpa_get "$to" mode)" = station ] && echo ' (through the phone, not gamemaster)')"
  echo "internet: $(internet)"
  [ -s "$DIR/leases.json" ] && { echo "leases:"; cat "$DIR/leases.json"; }
  exit 0
  ;;
trial)
  [ -s "$DIR/ap.conf" ] || die "no $DIR/ap.conf: run qnx/ap.sh install on the Mac"
  is_ap_boot && die "the boot setup is already the access point"
  has_uplink_hook && die "the boot setup is the uplink, which runs the access point already; gm-net.sh revert first"
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
  has_uplink_hook && die "the boot setup is the uplink; gm-net.sh revert first (one boot setup at a time)"
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
  elif has_uplink_hook; then
    touch "$DIR/uplink-confirmed"; kill_pidfile uplink-probation
    say "confirm: the uplink is the boot setup for good"
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
  elif has_uplink_hook; then
    uplink_unhook || die "could not take the uplink's line out of $POST (the backup is in $BAK/uplink)"
    say "revert: the uplink's boot line is out of $POST; rebooting into the hotspot client"
    shutdown -S reboot
  else
    say "revert: already the hotspot client"
  fi
  ;;
uplink)
  sub="${1:-}"
  [ $# -gt 0 ] && shift
  case "$sub" in
  trial)
    [ -s "$DIR/ap.conf" ] || die "no $DIR/ap.conf: run qnx/ap.sh install on the Mac"
    is_ap_boot && die "the boot setup is the access point on bcm0, so bcm0 is not on the hotspot: gm-net.sh revert first (it reboots onto the hotspot)"
    has_uplink_hook && die "the uplink is the boot setup already"
    [ -e "$RUN/trial" ] && die "a trial is running ($(cat "$RUN/trial")); gm-net.sh revert ends it"
    hotspot_addr > /dev/null || die "bcm0 is not on the hotspot: turn on the iPhone's Personal Hotspot and wait for the Pi to join it"
    hf=$(wpa_get bcm0 freq)
    is_24ghz "$hf" || die "the hotspot is on $hf MHz and the robot needs 2.4 GHz: turn on Maximize Compatibility on the iPhone, then let the Pi join again"
    secs="${1:-$TRIAL}"
    echo bcm1 > "$RUN/trial"  # an ordinary trial on bcm1 from here: confirm, revert and the watchdog end it as one
    rm -f "$RUN/trial-confirmed"
    nohup "$DIR/gm-net.sh" _uplink-trial "$secs" < /dev/null >> "$LOG/trial.log" 2>&1 &
    say "uplink trial: $SSID on bcm1 beside the hotspot ($hf MHz) for $secs s unless confirmed (log: $LOG/trial.log)"
    ;;
  persist)
    [ -s "$DIR/ap.conf" ] || die "no $DIR/ap.conf: run qnx/ap.sh install on the Mac"
    [ -e "$RUN/trial" ] && die "a trial is running; gm-net.sh revert ends it first"
    { is_ap_boot || has_hook; } && die "the boot setup is the access point on bcm0: gm-net.sh revert first (it reboots onto the hotspot), then this"
    has_uplink_hook && die "the uplink is the boot setup already ($([ -e "$DIR/uplink-confirmed" ] && echo confirmed || echo on probation))"
    hotspot_addr > /dev/null || die "bcm0 is not on the hotspot now; the uplink needs its hotspot setup to work (gm-net.sh uplink trial proves it)"
    hf=$(wpa_get bcm0 freq)
    is_24ghz "$hf" || die "the hotspot is on $hf MHz and the robot needs 2.4 GHz: turn on Maximize Compatibility on the iPhone first"
    mkdir -p "$BAK/uplink" && chmod 700 "$BAK" "$BAK/uplink"
    saved="$BAK/uplink/post_startup.sh.$(date +%Y%m%d-%H%M%S)"
    cp -p "$POST" "$saved" || die "could not back up $POST"
    n=$(grep -n '^exit 0' "$POST" | tail -1 | cut -d: -f1)
    awk -v n="${n:-0}" -v hook="$HOOK_UPLINK" 'NR == n { print hook } { print } END { if (n == 0) print hook }' "$POST" > "$POST.gm" \
      && chmod 0555 "$POST.gm" && mv "$POST.gm" "$POST" || die "could not add the boot line to $POST"
    rm -f "$DIR/uplink-confirmed"
    say "uplink persist: at boot $SSID runs on bcm1 beside the hotspot, or alone on bcm0 without it after $UPLINK_WAIT s; on probation for $PROBATION s after each boot until confirmed; $POST backed up to $saved"
    ;;
  boot)
    # One boot setup at a time: the access point on bcm0 (`boot`) wins, and this does nothing.
    if is_ap_boot || has_hook; then say "uplink boot: the boot setup is the access point on bcm0; nothing to do"; exit 0; fi
    has_uplink_hook || { say "uplink boot: the uplink is not the boot setup; nothing to do"; exit 0; }
    rm -f "$RUN"/*.pid "$RUN"/*-off "$RUN"/trial "$RUN"/trial-confirmed "$RUN"/uplink
    if [ ! -e "$DIR/uplink-confirmed" ]; then
      nohup "$DIR/gm-net.sh" _uplink-probation < /dev/null > /dev/null 2>&1 &
      echo $! > "$RUN/uplink-probation.pid"
    fi
    if ! wait_hotspot "$UPLINK_WAIT"; then
      why="no hotspot after $UPLINK_WAIT s"
    elif ! uplink_ap; then
      why=$UPLINK_WHY
    else
      why=""
    fi
    if [ -z "$why" ]; then
      echo "the uplink: $SSID on bcm1 ($(wpa_get bcm1 freq) MHz) beside the hotspot, internet through bcm0 at $(hotspot_addr)" > "$RUN/uplink"
    else
      say "uplink boot: $why: $SSID alone on bcm0 instead, without internet"
      ap_alone
      echo "the fallback: $SSID alone on bcm0 ($(wpa_get bcm0 freq) MHz), no internet; $why" > "$RUN/uplink"
    fi
    start_referee
    say "uplink boot: $(cat "$RUN/uplink"); dhcpd and the referee started$([ -e "$DIR/uplink-confirmed" ] || echo ", on probation for $PROBATION s")"
    ;;
  *)
    die "uplink takes trial [SECONDS], persist or boot (qnx/README.md, \"The uplink\")"
    ;;
  esac
  ;;
_uplink-trial)
  nohup "$DIR/gm-net.sh" _watchdog "$1" < /dev/null > /dev/null 2>&1 &
  echo $! > "$RUN/watchdog.pid"
  if uplink_ap; then
    say "uplink trial: $SSID is up on bcm1 ($(wpa_get bcm1 freq) MHz) at $PI_ADDR, bcm0 on the hotspot at $(hotspot_addr || echo nothing); internet: $(internet)"
  else
    say "uplink trial: $UPLINK_WHY; going back"
    "$DIR/gm-net.sh" revert
  fi
  ;;
_uplink-probation)
  sleep "$PROBATION"
  if [ ! -e "$DIR/uplink-confirmed" ] && has_uplink_hook; then
    say "uplink probation: $PROBATION s and no confirm: the boot line comes out and the Pi reboots into the hotspot client"
    uplink_unhook && shutdown -S reboot
  fi
  ;;
referee-restart)
  is_ap_boot || [ -e "$RUN/trial" ] || has_uplink_hook || die "the referee starts at boot only on the $SSID network; use qnx/referee.sh"
  start_referee
  say "referee: (re)started against http://$MAC_ADDR:$TABLE_PORT (log: $LOG/referee.log)"
  ;;
*)
  sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
  ;;
esac
