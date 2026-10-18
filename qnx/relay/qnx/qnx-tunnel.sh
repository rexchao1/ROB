#!/bin/sh
# Runs ON the QNX Pi. Keeps a reverse tunnel open to a WebSocket relay so the
# target is reachable from anywhere. Only outbound 443 is required.
#
# Prereqs on the QNX Pi:
#   python3 on PATH        (wsproxy.py is stdlib-only, nothing to install)
#   $WSPROXY               copy of wsproxy.py
#   $KEY                   private key whose pubkey is in the relay's authorized_keys
#
# RPORT must match the permitlisten in the relay's authorized_keys.
RELAY="${RELAY:-}"
WSPROXY="${WSPROXY:-/boot/wsproxy.py}"
KEY="${KEY:-/data/home/root/.ssh/qnx_tunnel_key}"
RPORT="${RPORT:-2222}"
BIND_ADDRESS="${BIND_ADDRESS:-}"
LOG="${LOG:-/tmp/qnx-tunnel.log}"
LOCK_DIR="${LOCK_DIR:-/tmp/qnx-tunnel.lock}"

case "$RELAY" in
    wss://*) ;;
    *)
        echo "RELAY must be a wss:// URL" >&2
        exit 2
        ;;
esac
case "$RPORT" in
    ''|*[!0-9]*)
        echo "RPORT must be numeric" >&2
        exit 2
        ;;
esac
if [ "$RPORT" -lt 1024 ] || [ "$RPORT" -gt 65535 ]; then
    echo "RPORT must be between 1024 and 65535" >&2
    exit 2
fi
if [ -z "$BIND_ADDRESS" ]; then
    echo "BIND_ADDRESS must be the bcm0 Wi-Fi address" >&2
    exit 2
fi

rotate_log() {
    [ -f "$LOG" ] || return 0
    LOG_SIZE="$(wc -c < "$LOG" 2>/dev/null)"
    case "$LOG_SIZE" in ''|*[!0-9]*) LOG_SIZE=0 ;; esac
    if [ "$LOG_SIZE" -gt 1048576 ]; then
        mv -f "$LOG" "$LOG.previous"
    fi
}
log_msg() {
    rotate_log
    echo "$(date): $*" >> "$LOG"
}

# QNX's shell treats an inline NAME=value inside ProxyCommand as an executable
# filename. Export the CA path so the Python TLS client inherits it normally.
SSL_CERT_FILE="${SSL_CERT_FILE:-/etc/ssl/certs/cacert.pem}"
export SSL_CERT_FILE

# QNX can invoke startup hooks more than once. Keep exactly one reconnect loop,
# while recovering automatically from a stale lock left by an unclean stop.
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    OLD_PID="$(cat "$LOCK_DIR/pid" 2>/dev/null)"
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        log_msg "tunnel already running as pid $OLD_PID"
        exit 0
    fi
    rm -f "$LOCK_DIR/pid"
    rmdir "$LOCK_DIR" 2>/dev/null || true
    mkdir "$LOCK_DIR" 2>/dev/null || exit 1
fi
echo "$$" > "$LOCK_DIR/pid"
cleanup_lock() {
    rm -f "$LOCK_DIR/pid"
    rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup_lock 0 1 2 15

log_msg "tunnel starting RPORT=$RPORT RELAY=$RELAY"
while true; do
    rotate_log
    ssh -n -N \
        -b "$BIND_ADDRESS" \
        -o BatchMode=yes \
        -o NumberOfPasswordPrompts=0 \
        -o ConnectTimeout=20 \
        -o ProxyCommand="python3 $WSPROXY $RELAY" \
        -o IdentityFile="$KEY" \
        -o IdentitiesOnly=yes \
        -o StrictHostKeyChecking=yes \
        -o UserKnownHostsFile=/data/home/root/.ssh/relay_known_hosts \
        -o ExitOnForwardFailure=yes \
        -o ServerAliveInterval=15 \
        -o ServerAliveCountMax=20 \
        -R "127.0.0.1:$RPORT:127.0.0.1:22" \
        tunnel@qnx-rdv 2>>"$LOG"
    SSH_RC=$?
    log_msg "tunnel dropped (rc=$SSH_RC), retry in 5s"
    sleep 5
done
