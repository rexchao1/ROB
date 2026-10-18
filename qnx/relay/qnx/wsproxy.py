#!/usr/bin/env python3
"""
Minimal dependency-free WebSocket ProxyCommand for SSH.

Usage (as an SSH ProxyCommand):
    ssh -o ProxyCommand="python3 wsproxy.py wss://host[/path]" user@anything ...

It connects to the given ws://|wss:// URL, performs the WebSocket handshake,
then pipes raw bytes between stdin/stdout (the SSH transport) and the WebSocket
data frames. Uses only the Python 3 standard library, so it runs on QNX, macOS,
and Linux without installing anything.
"""
import sys
import os
import socket
import ssl
import base64
import hashlib
import struct
import select
import time
from urllib.parse import urlparse


PING_INTERVAL = 15
MAX_HEADER_BYTES = 65536
MAX_FRAME_BYTES = 1 << 20
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def log(msg):
    sys.stderr.write("wsproxy: " + msg + "\n")
    sys.stderr.flush()


def write_all(fd, data):
    """Write every byte, handling short writes on a busy pipe."""
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        view = view[n:]


def main():
    if len(sys.argv) < 2:
        log("usage: wsproxy.py wss://host[:port][/path]")
        sys.exit(2)

    url = sys.argv[1]
    u = urlparse(url)
    if u.scheme not in ("ws", "wss") or not u.hostname:
        log("URL must be a complete ws:// or wss:// URL")
        sys.exit(2)
    if u.username or u.password or u.fragment:
        log("URL cannot contain credentials or a fragment")
        sys.exit(2)
    secure = (u.scheme == "wss")
    host = u.hostname
    try:
        port = u.port or (443 if secure else 80)
    except ValueError as exc:
        log("invalid URL port: %s" % exc)
        sys.exit(2)
    path = u.path or "/"
    if u.query:
        path += "?" + u.query

    def connect_tls():
        raw = socket.create_connection((host, port), timeout=20)
        raw.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        cafile = os.environ.get("SSL_CERT_FILE")
        if not cafile and sys.platform == "darwin" and os.path.exists("/etc/ssl/cert.pem"):
            cafile = "/etc/ssl/cert.pem"
        ctx = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
        return ctx.wrap_socket(raw, server_hostname=host)

    if secure:
        sock = connect_tls()
    else:
        sock = socket.create_connection((host, port), timeout=20)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    key = base64.b64encode(os.urandom(16)).decode()
    host_header = "[%s]" % host if ":" in host else host
    if port != (443 if secure else 80):
        host_header += ":%d" % port
    req = (
        "GET %s HTTP/1.1\r\n"
        "Host: %s\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: %s\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    ) % (path, host_header, key)
    sock.sendall(req.encode())

    # Read HTTP handshake response headers.
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            log("handshake failed: connection closed")
            sys.exit(1)
        buf += chunk
        if len(buf) > MAX_HEADER_BYTES:
            log("handshake failed: response headers are too large")
            sys.exit(1)
    header, _, rest = buf.partition(b"\r\n\r\n")
    lines = header.split(b"\r\n")
    status_line = lines[0]
    parts = status_line.split(None, 2)
    if len(parts) < 2 or parts[1] != b"101":
        log("bad handshake: %r" % status_line)
        sys.exit(1)
    headers = {}
    for line in lines[1:]:
        if b":" not in line:
            log("bad handshake header: %r" % line)
            sys.exit(1)
        name, value = line.split(b":", 1)
        name = name.strip().lower()
        value = value.strip()
        headers[name] = headers.get(name, b"") + (b", " if name in headers else b"") + value
    upgrade_tokens = [v.strip().lower() for v in headers.get(b"upgrade", b"").split(b",")]
    connection_tokens = [v.strip().lower() for v in headers.get(b"connection", b"").split(b",")]
    expected_accept = base64.b64encode(
        hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()
    )
    if b"websocket" not in upgrade_tokens or b"upgrade" not in connection_tokens:
        log("bad handshake: missing WebSocket upgrade headers")
        sys.exit(1)
    if headers.get(b"sec-websocket-accept") != expected_accept:
        log("bad handshake: Sec-WebSocket-Accept does not match")
        sys.exit(1)

    inbuf = bytearray(rest)
    outbuf = bytearray()

    def send_frame(data, opcode=0x2):
        # Queue a masked client frame; actual writes happen in the select loop
        # so a busy/!writable TLS socket never blocks the read path.
        n = len(data)
        out = bytearray([0x80 | opcode])
        if n < 126:
            out.append(0x80 | n)
        elif n < 65536:
            out.append(0x80 | 126)
            out += struct.pack("!H", n)
        else:
            out.append(0x80 | 127)
            out += struct.pack("!Q", n)
        mask = os.urandom(4)
        out += mask
        out += bytes(b ^ mask[i & 3] for i, b in enumerate(data))
        outbuf.extend(out)

    def parse_frames():
        """Extract complete frames from inbuf. Returns True if a close was seen."""
        while True:
            if len(inbuf) < 2:
                return False
            b0 = inbuf[0]
            b1 = inbuf[1]
            fin = b0 & 0x80
            rsv = b0 & 0x70
            opcode = b0 & 0x0F
            masked = b1 & 0x80
            ln = b1 & 0x7F
            idx = 2
            if ln == 126:
                if len(inbuf) < 4:
                    return False
                ln = struct.unpack("!H", bytes(inbuf[2:4]))[0]
                idx = 4
            elif ln == 127:
                if len(inbuf) < 10:
                    return False
                ln = struct.unpack("!Q", bytes(inbuf[2:10]))[0]
                idx = 10
            if masked:
                raise ValueError("server sent a masked frame")
            if rsv:
                raise ValueError("server sent unsupported RSV bits")
            if not fin:
                raise ValueError("fragmented frames are unsupported")
            if ln > MAX_FRAME_BYTES:
                raise ValueError("WebSocket frame exceeds 1 MiB")
            if opcode >= 0x8 and ln > 125:
                raise ValueError("oversized WebSocket control frame")
            if len(inbuf) < idx + ln:
                return False
            payload = bytes(inbuf[idx:idx + ln])
            del inbuf[:idx + ln]
            if opcode == 0x8:        # close
                send_frame(payload, opcode=0x8)
                return True
            elif opcode == 0x9:      # ping -> pong
                send_frame(payload, opcode=0xA)
            elif opcode == 0xA:      # pong
                pass
            elif opcode == 0x2:      # binary data
                if payload:
                    write_all(1, payload)
            else:
                raise ValueError("unsupported WebSocket opcode 0x%x" % opcode)

    if parse_frames():
        return

    # Non-blocking pump. A blocking recv() after select() can deadlock on a TLS
    # socket when select() fired for post-handshake/control records that carry
    # no application data; non-blocking recv() with SSLWantRead avoids that.
    sock.setblocking(False)
    stdin_fd = 0
    stdin_open = True
    last_ping = time.monotonic()

    def drain_recv():
        """Read all currently-available decrypted bytes. Returns True on EOF."""
        while True:
            try:
                chunk = sock.recv(65536)
            except (ssl.SSLWantReadError, ssl.SSLWantWriteError, BlockingIOError):
                return False
            except ssl.SSLError:
                raise
            if chunk == b"":
                return True
            inbuf.extend(chunk)

    def flush_send():
        """Write as much of outbuf as the socket will take right now."""
        while outbuf:
            try:
                n = sock.send(bytes(outbuf[:65536]))
            except (ssl.SSLWantReadError, ssl.SSLWantWriteError, BlockingIOError):
                return
            except ssl.SSLError:
                raise
            if n <= 0:
                raise ConnectionResetError("socket write returned zero")
            del outbuf[:n]

    while True:
        now = time.monotonic()
        if now - last_ping >= PING_INTERVAL:
            send_frame(b"qnx", opcode=0x9)
            last_ping = now

        rset = [sock]
        if stdin_open:
            rset.append(stdin_fd)
        wset = [sock] if outbuf else []
        try:
            # Never wait forever here.  A dead network path can otherwise leave
            # the parent SSH process stuck indefinitely, preventing its outer
            # reconnect loop from running.
            r, w, _ = select.select(rset, wset, [], 5)
        except (InterruptedError, OSError):
            continue

        if sock in r:
            if drain_recv():
                break
            if parse_frames():
                break

        if stdin_open and stdin_fd in r:
            try:
                data = os.read(stdin_fd, 65536)
            except (BlockingIOError, InterruptedError):
                data = None  # spurious wakeup; nothing to do
            if data:
                send_frame(data)
            elif data == b"":
                # stdin closed: stop reading it, flush remaining output, then exit
                stdin_open = False

        if outbuf and (sock in w or sock in r):
            flush_send()

        # Always attempt a flush so queued frames make progress.
        if outbuf:
            flush_send()

        if not stdin_open and not outbuf:
            break


if __name__ == "__main__":
    try:
        main()
    except (BrokenPipeError, ConnectionResetError, KeyboardInterrupt):
        pass
    except (TimeoutError, socket.timeout, ssl.SSLError, OSError, ValueError) as e:
        # Transient transport failure: exit non-zero so the caller's reconnect
        # loop retries, but without dumping a traceback.
        log("transient error: %s" % e)
        sys.exit(1)
