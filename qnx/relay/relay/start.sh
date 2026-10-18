#!/bin/bash
set -euo pipefail
mkdir -p /run/sshd

# Stable host key from env so redeploys don't invalidate client known_hosts.
if [ -n "${TUNNEL_HOST_KEY_B64:-}" ]; then
    echo "$TUNNEL_HOST_KEY_B64" | base64 -d > /etc/ssh/ssh_host_ed25519_key
else
    echo "WARN: TUNNEL_HOST_KEY_B64 unset; generating ephemeral host key" >&2
    rm -f /etc/ssh/ssh_host_ed25519_key /etc/ssh/ssh_host_ed25519_key.pub
    ssh-keygen -t ed25519 -N '' -f /etc/ssh/ssh_host_ed25519_key -q
fi
chmod 600 /etc/ssh/ssh_host_ed25519_key
ssh-keygen -y -f /etc/ssh/ssh_host_ed25519_key > /etc/ssh/ssh_host_ed25519_key.pub

if [ -n "${TUNNEL_AUTHORIZED_KEYS_B64:-}" ]; then
    printf '%s' "$TUNNEL_AUTHORIZED_KEYS_B64" | base64 -d > /home/tunnel/.ssh/authorized_keys
elif [ -n "${TUNNEL_AUTHORIZED_KEYS:-}" ]; then
    printf '%s\n' "$TUNNEL_AUTHORIZED_KEYS" > /home/tunnel/.ssh/authorized_keys
else
    echo "TUNNEL_AUTHORIZED_KEYS_B64 or TUNNEL_AUTHORIZED_KEYS must be set" >&2
    exit 1
fi
chmod 600 /home/tunnel/.ssh/authorized_keys
chown -R tunnel:tunnel /home/tunnel/.ssh

if [ ! -s /home/tunnel/.ssh/authorized_keys ] || ! awk '
    /^[[:space:]]*(#|$)/ { next }
    $0 !~ /(^|[[:space:]])ssh-ed25519[[:space:]][A-Za-z0-9+\/=]+([[:space:]]|$)/ { exit 1 }
    { found = 1 }
    END { if (!found) exit 1 }
' /home/tunnel/.ssh/authorized_keys; then
    echo "authorized_keys is empty or contains an invalid key line" >&2
    exit 1
fi

/usr/sbin/sshd -t

SSHD_PID=
BRIDGE_PID=
cleanup() {
    trap - EXIT INT TERM
    [ -z "$SSHD_PID" ] || kill "$SSHD_PID" 2>/dev/null || true
    [ -z "$BRIDGE_PID" ] || kill "$BRIDGE_PID" 2>/dev/null || true
    [ -z "$SSHD_PID" ] || wait "$SSHD_PID" 2>/dev/null || true
    [ -z "$BRIDGE_PID" ] || wait "$BRIDGE_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

/usr/sbin/sshd -D -e &
SSHD_PID=$!
python3 /opt/wsbridge.py &
BRIDGE_PID=$!

# A relay with only one healthy child is unusable. Exit and let the hosting
# platform restart the whole container whenever either service stops.
set +e
wait -n "$SSHD_PID" "$BRIDGE_PID"
CHILD_RC=$?
set -e
echo "relay child exited (rc=$CHILD_RC); stopping container" >&2
cleanup
exit 1
