#!/bin/sh
# This Mac on the Pi's gamemaster Wi-Fi network at its fixed address, and back again
# (qnx/README.md has the whole changeover). The gamemaster network has no router, so
# the Mac keeps its internet on another interface: the iPhone over USB.
#
#   scripts/wifi.sh game      Wi-Fi to MAC_ADDR by hand (qnx/ap/net.conf), then join gamemaster
#                             with the password in .env.local; asks for the Mac's password (sudo)
#   scripts/wifi.sh back      Wi-Fi to DHCP again and forget gamemaster; it rejoins your usual network
#   scripts/wifi.sh status    the Wi-Fi setup, its address and where the internet goes
#
# The address is set by hand because the Mac's Wi-Fi uses a private MAC address per
# network, which a DHCP reservation could not follow.
set -eu
cd "$(dirname "$0")/.."
. qnx/ap/net.conf
SERVICE=Wi-Fi
DEV=$(networksetup -listallhardwareports | awk '/Hardware Port: Wi-Fi/ { getline; print $2 }')
[ -n "$DEV" ] || { echo "wifi: this Mac has no Wi-Fi port" >&2; exit 1; }
internet() { route -n get default 2>/dev/null | awk '/interface:/ { print $2 }'; }

case "${1:-status}" in
game)
  pw=$(sed -n 's/^GM_WIFI_PASSWORD=//p' .env.local 2>/dev/null | tail -1)
  [ -n "$pw" ] || { echo "wifi: no GM_WIFI_PASSWORD in .env.local (qnx/ap.sh install makes one)" >&2; exit 1; }
  if [ "$(internet)" = "$DEV" ]; then
    echo "wifi: the internet goes over Wi-Fi ($DEV) now and stops when it joins $SSID; plug the iPhone in by USB first (Ctrl-C to stop, Enter to go on)"
    read -r _
  fi
  # No router: the default route stays on the USB link. If this macOS insists on a
  # router, the manual address takes the mask from the Pi's DHCP server instead.
  if ! sudo networksetup -setmanual "$SERVICE" "$MAC_ADDR" "$NETMASK" 2>/dev/null; then
    sudo networksetup -setmanualwithdhcprouter "$SERVICE" "$MAC_ADDR"
  fi
  networksetup -setairportnetwork "$DEV" "$SSID" "$pw"
  n=0
  until ping -c 1 -t 1 "$PI_ADDR" > /dev/null 2>&1; do
    n=$((n + 1))
    if [ "$n" -ge 30 ]; then echo "wifi: no answer from the Pi at $PI_ADDR after 30 s (scripts/wifi.sh status)" >&2; exit 1; fi
    sleep 1
  done
  echo "wifi: on $SSID as $MAC_ADDR, the Pi answers at $PI_ADDR; internet over $(internet || echo nothing)"
  ;;
back)
  sudo networksetup -setdhcp "$SERVICE"
  sudo networksetup -removepreferredwirelessnetwork "$DEV" "$SSID" > /dev/null 2>&1 || true
  networksetup -setairportpower "$DEV" off
  networksetup -setairportpower "$DEV" on
  echo "wifi: Wi-Fi is on DHCP again and has forgotten $SSID; it rejoins your usual network (or pick one from the Wi-Fi menu)"
  ;;
status)
  networksetup -getinfo "$SERVICE" | grep -E '^(Manual|DHCP|IP address|Subnet mask|Router)' || true
  echo "Wi-Fi address: $(ifconfig "$DEV" | awk '$1 == "inet" { print $2 }' | tr '\n' ' ')"
  echo "internet over: $(internet || echo nothing)"
  ;;
*)
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
  ;;
esac
