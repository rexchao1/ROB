#!/proc/boot/ksh

export PATH=/proc/boot:/system/bin:/usr/bin:/bin:/sbin
LOG=/boot/qnx-supervisor.log
LOCK_DIR=/tmp/qnx-connect-supervisor.lock

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

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    OLD_PID="$(cat "$LOCK_DIR/pid" 2>/dev/null)"
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        log_msg "supervisor already running as pid $OLD_PID"
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

if [ -r /usr/lib/qnx-headless-connect/qnx-tunnel-launcher.sh ]; then
    LAUNCHER=/usr/lib/qnx-headless-connect/qnx-tunnel-launcher.sh
else
    LAUNCHER=/boot/qnx-tunnel-launcher.sh
fi

log_msg "supervisor starting launcher=$LAUNCHER"
while true; do
    /proc/boot/ksh "$LAUNCHER"
    LAUNCHER_RC=$?
    log_msg "launcher exited (rc=$LAUNCHER_RC), retry in 5s"
    sleep 5
done
