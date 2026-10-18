#!/bin/sh
# ssh to the QNX Pi from anywhere, through the relay on the AWS VM. The Pi keeps an outbound
# connection to wss://$RELAY_NAME (port 443 only), so this works on any network the Pi has
# internet on: the iPhone hotspot, or the uplink beside gamemaster. qnx/relay/ is
# github.com/lancestreuber/qnx-pi-headless-relay at 3fedf7b; the README there explains it.
#
#   qnx/relay.sh setup      make the keys and config once, in .qnx-connect/qnxpi (gitignored)
#   qnx/relay.sh server     build and run the relay on the VM, behind the VM's Caddy
#   qnx/relay.sh install    copy the Pi's side to its boot partition (Pi reachable locally) and start it
#   qnx/relay.sh ssh [CMD]  ssh to the Pi through the relay
#   qnx/relay.sh status     the relay on the VM, and whether the Pi answers through it
#
# The VM: $GM_RELAY_VM (ubuntu@3.23.80.81), its ssh options in $GM_RELAY_VM_OPTS. It also
# serves Tooey; the relay is one extra site in its Caddyfile, which `server` puts back if a
# Tooey deploy rewrote the file. The Pi for `install`: $GM_PI, else qnxuser@172.20.10.14.
set -eu
cd "$(dirname "$0")/.."

VM="${GM_RELAY_VM:-ubuntu@3.23.80.81}"
VM_OPTS="${GM_RELAY_VM_OPTS:--i $HOME/.ssh/tooeymac.pem -o IdentitiesOnly=yes}"
RELAY_NAME="${GM_RELAY_NAME:-qnx.3-23-80-81.sslip.io}"  # sslip.io answers with the IP in the name
RELAY_PORT=8081       # the container's port on the VM's loopback, behind Caddy
DEVICE=qnxpi
BUNDLE=.qnx-connect/$DEVICE
PI="${GM_PI:-qnxuser@172.20.10.14}"

# shellcheck disable=SC2086
vm() { ssh $VM_OPTS "$VM" "$@"; }
need_bundle() { [ -d "$BUNDLE" ] || { echo "relay: no $BUNDLE yet; run qnx/relay.sh setup"; exit 1; }; }
# The Pi's sshd predates post-quantum key exchange; the link is inside the relay's TLS anyway.
through() { ssh -F "$BUNDLE/client/ssh_config" -o WarnWeakCrypto=no "$DEVICE" "$@"; }

case "${1:-}" in
setup)
  if [ -d "$BUNDLE" ]; then echo "relay: $BUNDLE already exists"; exit 0; fi
  python3 qnx/relay/scripts/configure.py --relay-url "wss://$RELAY_NAME" --device-name "$DEVICE" --output "$BUNDLE"
  ;;
server)
  need_bundle
  # shellcheck disable=SC2086
  COPYFILE_DISABLE=1 tar --format ustar -cf - -C qnx/relay relay | vm 'rm -rf qnx-relay/relay && mkdir -p qnx-relay && tar -xf - -C qnx-relay'
  # shellcheck disable=SC2086
  vm 'umask 077 && cat > qnx-relay/relay.env' < "$BUNDLE/relay/relay.env"
  vm "set -e
    cd qnx-relay
    sudo docker build -q -t qnx-relay relay >/dev/null
    sudo docker rm -f qnx-relay >/dev/null 2>&1 || true
    sudo docker run -d --name qnx-relay --restart unless-stopped --env-file relay.env -e PORT=8080 \
      -p 127.0.0.1:$RELAY_PORT:8080 qnx-relay >/dev/null
    if ! grep -q '^$RELAY_NAME ' /etc/caddy/Caddyfile; then
      sudo cp -p /etc/caddy/Caddyfile /etc/caddy/Caddyfile.before-qnx-relay
      printf '\n# ROB: the QNX Pi relay (ROB repo, qnx/relay.sh server). Not part of the Tooey deploy.\n$RELAY_NAME {\n\treverse_proxy 127.0.0.1:$RELAY_PORT\n}\n' | sudo tee -a /etc/caddy/Caddyfile >/dev/null
      sudo sh -c 'set -a; . /etc/caddy/env; caddy validate --config /etc/caddy/Caddyfile' >/dev/null 2>&1 \
        || { sudo cp -p /etc/caddy/Caddyfile.before-qnx-relay /etc/caddy/Caddyfile; echo 'relay: Caddyfile did not validate, put back'; exit 1; }
      sudo systemctl reload caddy
    fi
    sleep 2
    sudo docker ps --filter name=qnx-relay --format 'relay: container {{.Status}}'"
  echo "relay: wss://$RELAY_NAME"
  ;;
install)
  need_bundle
  # /boot is the Pi's FAT partition; its image runs /boot/onboot at startup, which starts the
  # tunnel and keeps it up. The tunnel key moves off FAT to /data on the first start.
  # shellcheck disable=SC2086
  (cd "$BUNDLE/boot" && COPYFILE_DISABLE=1 tar --format ustar -cf - ./*) | ssh ${GM_SSH_OPTS:-} "$PI" 'tar -xmof - -C /boot 2>&1 | grep -v "change mode" || true'
  # shellcheck disable=SC2086
  ssh ${GM_SSH_OPTS:-} "$PI" 'sudo -n /proc/boot/on -d /proc/boot/ksh /boot/qnx-connect-supervisor.sh </dev/null >/dev/null 2>&1; sleep 20; tail -3 /boot/qnx-tunnel.log 2>/dev/null; tail -3 /boot/qnx-supervisor.log'
  echo "relay: installed on $PI; it starts at every boot. Try: qnx/relay.sh ssh"
  ;;
ssh)
  need_bundle
  shift
  through "$@"
  ;;
status)
  vm "sudo docker ps -a --filter name=qnx-relay --format 'relay: container {{.Status}}'"
  if [ -d "$BUNDLE" ] && through -o ConnectTimeout=25 'echo "relay: the Pi answers ($(hostname), Wi-Fi $(ifconfig bcm0 | sed -n "s/.*inet \([0-9.]*\) .*/\1/p"))"'; then :
  else echo "relay: the Pi does not answer through the relay"; fi
  ;;
*)
  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
  ;;
esac
