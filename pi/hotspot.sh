#!/usr/bin/env bash
# The brain's own network (D28): the Pi's Wi-Fi becomes an access point named
# "gamemaster" at 10.42.0.1, and the StackChan joins it. 2.4 GHz only (band bg),
# because the CoreS3's ESP32-S3 has no 5 GHz radio. Comes back on every boot.
#
#   sudo pi/hotspot.sh <password>          # or GM_HOTSPOT_PASSWORD=... sudo pi/hotspot.sh
#   sudo pi/hotspot.sh --off               # back to an ordinary Wi-Fi client
#
# The Pi has no internet over Wi-Fi while this is on (plug in Ethernet for installs).
set -euo pipefail

SSID="${GM_HOTSPOT_SSID:-gamemaster}"
CON="gamemaster-hotspot"
IFACE="${GM_HOTSPOT_IFACE:-wlan0}"

if [[ "${1:-}" == "--off" ]]; then
  nmcli connection down "$CON" 2>/dev/null || true
  nmcli connection delete "$CON" 2>/dev/null || true
  echo "hotspot: off"
  exit 0
fi

PASSWORD="${1:-${GM_HOTSPOT_PASSWORD:-}}"
if [[ ${#PASSWORD} -lt 8 ]]; then
  echo "usage: sudo $0 <password of 8 or more characters>   (or set GM_HOTSPOT_PASSWORD)" >&2
  exit 2
fi
if ! command -v nmcli >/dev/null; then
  echo "hotspot: nmcli not found; Raspberry Pi OS Bookworm and later use NetworkManager" >&2
  exit 1
fi

nmcli connection delete "$CON" 2>/dev/null || true
nmcli connection add type wifi ifname "$IFACE" con-name "$CON" autoconnect yes ssid "$SSID" \
  802-11-wireless.mode ap 802-11-wireless.band bg \
  ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv6.method disabled \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASSWORD" \
  connection.autoconnect-priority 100
nmcli connection up "$CON"

echo "hotspot: \"$SSID\" is up on $IFACE; the brain is 10.42.0.1"
