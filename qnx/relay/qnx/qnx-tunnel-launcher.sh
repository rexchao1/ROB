#!/proc/boot/ksh

BOOT_LOG=/boot/qnx-onboot.log
if [ -f "$BOOT_LOG" ]; then
    BOOT_LOG_SIZE="$(wc -c < "$BOOT_LOG" 2>/dev/null)"
    case "$BOOT_LOG_SIZE" in ''|*[!0-9]*) BOOT_LOG_SIZE=0 ;; esac
    if [ "$BOOT_LOG_SIZE" -gt 1048576 ]; then
        mv -f "$BOOT_LOG" "$BOOT_LOG.previous"
    fi
fi
exec >>"$BOOT_LOG" 2>&1
export PATH=/proc/boot:/system/bin:/usr/bin:/bin:/sbin
export HOME=/data/home/root

# Per-device, non-secret settings are generated into this file by
# scripts/configure.py. Keeping them outside the launcher makes the same boot
# payload usable with Railway or any other WebSocket-capable relay host.
CONFIG=/boot/qnx-connect.conf
if [ ! -r "$CONFIG" ]; then
    echo "missing $CONFIG"
    exit 1
fi

# Treat the boot-volume config as data, not shell code. The FAT volume is the
# headless recovery interface, so sourcing it as root would turn a typo (or an
# unexpected file) into arbitrary commands during boot.
DEVICE_NAME=qnxpi
RELAY_URL=
REMOTE_PORT=2222
while IFS= read -r CONFIG_LINE || [ -n "$CONFIG_LINE" ]; do
    case "$CONFIG_LINE" in
        ''|'#'*) ;;
        DEVICE_NAME=*) DEVICE_NAME="${CONFIG_LINE#DEVICE_NAME=}" ;;
        RELAY_URL=*) RELAY_URL="${CONFIG_LINE#RELAY_URL=}" ;;
        REMOTE_PORT=*) REMOTE_PORT="${CONFIG_LINE#REMOTE_PORT=}" ;;
        *)
            echo "unsupported setting in $CONFIG: $CONFIG_LINE"
            exit 1
            ;;
    esac
done < "$CONFIG"

case "$DEVICE_NAME" in
    ''|*[!A-Za-z0-9._-]*)
        echo "DEVICE_NAME contains unsupported characters"
        exit 1
        ;;
esac
if [ -r /usr/lib/qnx-headless-connect/qnx-tunnel.sh ]; then
    CONNECT_HOME=/usr/lib/qnx-headless-connect
else
    CONNECT_HOME=/boot
fi
case "$RELAY_URL" in
    wss://*) ;;
    *)
        echo "RELAY_URL must start with wss://"
        exit 1
        ;;
esac
case "$REMOTE_PORT" in
    ''|*[!0-9]*)
        echo "REMOTE_PORT must be numeric"
        exit 1
        ;;
esac
if [ "$REMOTE_PORT" -lt 1024 ] || [ "$REMOTE_PORT" -gt 65535 ]; then
    echo "REMOTE_PORT must be between 1024 and 65535"
    exit 1
fi

# Serialize the whole boot install/start sequence. This prevents two startup
# invocations racing while they rewrite authorized_keys or move the FAT key.
LAUNCHER_LOCK=/tmp/qnx-tunnel-launcher.lock
if ! mkdir "$LAUNCHER_LOCK" 2>/dev/null; then
    OLD_LAUNCHER_PID="$(cat "$LAUNCHER_LOCK/pid" 2>/dev/null)"
    if [ -n "$OLD_LAUNCHER_PID" ] && kill -0 "$OLD_LAUNCHER_PID" 2>/dev/null; then
        echo "launcher already running as pid $OLD_LAUNCHER_PID"
        exit 0
    fi
    rm -f "$LAUNCHER_LOCK/pid"
    rmdir "$LAUNCHER_LOCK" 2>/dev/null || true
    mkdir "$LAUNCHER_LOCK" 2>/dev/null || exit 1
fi
echo "$$" > "$LAUNCHER_LOCK/pid"
cleanup_launcher_lock() {
    rm -f "$LAUNCHER_LOCK/pid"
    rmdir "$LAUNCHER_LOCK" 2>/dev/null || true
}
trap cleanup_launcher_lock 0 1 2 15

TUNNEL_KEY_BOOT=/boot/qnx_tunnel_key
TARGET_PUB_BOOT=/boot/qnx_laptop.pub
RELAY_PUB_BOOT=/boot/qnx_relay.pub

echo "QNX relay launcher waiting for full userspace"
while ! command -v ssh >/dev/null 2>&1 || ! command -v ssh-keygen >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; do
    sleep 5
done

while [ ! -e /dev/socket ]; do
    sleep 5
done

while [ ! -d /data/home/root ] || [ ! -d /data/home/qnxuser ]; do
    sleep 5
done

# Raspberry Pi 5 images may put bcm0 on either the default io-sock instance or
# a second stack selected with SOCK=/wifi. Start sshd in the same stack that
# owns bcm0, and carry that selection into the outbound relay tunnel.
NETWORK_SOCK=""
if ifconfig bcm0 >/dev/null 2>&1; then
    echo "bcm0 uses the default network stack"
elif SOCK=/wifi ifconfig bcm0 >/dev/null 2>&1; then
    NETWORK_SOCK=/wifi
    echo "bcm0 uses the separate /wifi network stack"
    SOCK=/wifi /proc/boot/.ssh-server.sh || true
else
    echo "waiting for bcm0"
    while true; do
        if ifconfig bcm0 >/dev/null 2>&1; then
            echo "bcm0 appeared on the default network stack"
            break
        fi
        if SOCK=/wifi ifconfig bcm0 >/dev/null 2>&1; then
            NETWORK_SOCK=/wifi
            echo "bcm0 appeared on the separate /wifi network stack"
            SOCK=/wifi /proc/boot/.ssh-server.sh || true
            break
        fi
        sleep 5
    done
fi

# Do not fall back to Ethernet. The project exists for cable-free access, so
# wait for an IPv4 address on bcm0 and bind the outbound SSH transport to it.
WIFI_ADDRESS=
echo "waiting for a bcm0 IPv4 address"
while [ -z "$WIFI_ADDRESS" ]; do
    if [ "$NETWORK_SOCK" = /wifi ]; then
        WIFI_ADDRESS="$(SOCK=/wifi ifconfig bcm0 2>/dev/null | awk '$1 == "inet" { print $2; exit }')"
    else
        WIFI_ADDRESS="$(ifconfig bcm0 2>/dev/null | awk '$1 == "inet" { print $2; exit }')"
    fi
    [ -n "$WIFI_ADDRESS" ] || sleep 5
done
echo "bcm0 is ready with IPv4 address $WIFI_ADDRESS"

# Move private material off the FAT volume before OpenSSH reads it. On later
# boots, use the installed data-partition copy. The FAT transfer copy is removed
# after the first successful installation.
mkdir -p /data/home/root/.ssh
if [ -s "$TUNNEL_KEY_BOOT" ]; then
    cp "$TUNNEL_KEY_BOOT" /data/home/root/.ssh/qnx_tunnel_key || exit 1
    chmod 600 /data/home/root/.ssh/qnx_tunnel_key
    rm -f "$TUNNEL_KEY_BOOT"
fi
if [ ! -s /data/home/root/.ssh/qnx_tunnel_key ]; then
    echo "missing tunnel key on both boot and data partitions"
    exit 1
fi
if ! ssh-keygen -y -f /data/home/root/.ssh/qnx_tunnel_key >/dev/null 2>&1; then
    echo "installed tunnel private key is invalid"
    exit 1
fi
if [ ! -s /boot/relay_known_hosts ]; then
    echo "missing /boot/relay_known_hosts"
    exit 1
fi
cp /boot/relay_known_hosts /data/home/root/.ssh/relay_known_hosts
chmod 700 /data/home/root/.ssh
chmod 600 /data/home/root/.ssh/qnx_tunnel_key /data/home/root/.ssh/relay_known_hosts

# Install the separate laptop-to-QNX login key. The relay access key is not
# valid for target login, and this step actively keeps it out of the target's
# authorized_keys.
mkdir -p /data/home/qnxuser/.ssh
touch /data/home/qnxuser/.ssh/authorized_keys
if [ ! -s "$TARGET_PUB_BOOT" ]; then
    echo "missing $TARGET_PUB_BOOT"
    exit 1
fi
if ! ssh-keygen -l -f "$TARGET_PUB_BOOT" >/dev/null 2>&1; then
    echo "invalid SSH public key in $TARGET_PUB_BOOT"
    exit 1
fi
TARGET_KEY_BLOB="$(awk 'NR == 1 && $1 == "ssh-ed25519" { print $2; exit }' "$TARGET_PUB_BOOT")"
if [ -z "$TARGET_KEY_BLOB" ]; then
    echo "$TARGET_PUB_BOOT must contain an ssh-ed25519 key"
    exit 1
fi
AUTH_KEYS=/data/home/qnxuser/.ssh/authorized_keys
AUTH_NEW=/data/home/qnxuser/.ssh/authorized_keys.qnx-connect.$$
cp "$AUTH_KEYS" "$AUTH_NEW" || exit 1
if ! grep -q "$TARGET_KEY_BLOB" "$AUTH_NEW"; then
    cat "$TARGET_PUB_BOOT" >> "$AUTH_NEW" || exit 1
fi
if [ -f "$RELAY_PUB_BOOT" ]; then
    if ! ssh-keygen -l -f "$RELAY_PUB_BOOT" >/dev/null 2>&1; then
        echo "invalid SSH public key in $RELAY_PUB_BOOT"
        rm -f "$AUTH_NEW"
        exit 1
    fi
    RELAY_KEY_BLOB="$(awk 'NR == 1 && $1 == "ssh-ed25519" { print $2; exit }' "$RELAY_PUB_BOOT")"
    if [ -z "$RELAY_KEY_BLOB" ]; then
        echo "$RELAY_PUB_BOOT must contain an ssh-ed25519 key"
        rm -f "$AUTH_NEW"
        exit 1
    fi
    AUTH_FILTERED="$AUTH_NEW.filtered"
    grep -v "$RELAY_KEY_BLOB" "$AUTH_NEW" > "$AUTH_FILTERED" || true
    mv -f "$AUTH_FILTERED" "$AUTH_NEW" || exit 1
fi
chown 1000:1000 "$AUTH_NEW"
chmod 600 "$AUTH_NEW"
mv -f "$AUTH_NEW" "$AUTH_KEYS" || exit 1
chown -R 1000:1000 /data/home/qnxuser/.ssh
chmod 700 /data/home/qnxuser/.ssh
chmod 600 "$AUTH_KEYS"

sleep 10
echo "$(date): starting $DEVICE_NAME reverse tunnel on port $REMOTE_PORT"
if [ "$NETWORK_SOCK" = /wifi ]; then
    SOCK=/wifi \
    RELAY="$RELAY_URL" \
    WSPROXY="$CONNECT_HOME/wsproxy.py" \
    KEY=/data/home/root/.ssh/qnx_tunnel_key \
    RPORT="$REMOTE_PORT" \
    BIND_ADDRESS="$WIFI_ADDRESS" \
    LOG=/boot/qnx-tunnel.log \
        /proc/boot/ksh "$CONNECT_HOME/qnx-tunnel.sh"
else
    RELAY="$RELAY_URL" \
    WSPROXY="$CONNECT_HOME/wsproxy.py" \
    KEY=/data/home/root/.ssh/qnx_tunnel_key \
    RPORT="$REMOTE_PORT" \
    BIND_ADDRESS="$WIFI_ADDRESS" \
    LOG=/boot/qnx-tunnel.log \
        /proc/boot/ksh "$CONNECT_HOME/qnx-tunnel.sh"
fi
