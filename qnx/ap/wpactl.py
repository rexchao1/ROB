"""Ask a running wpa_supplicant something over its control socket (the QNX image has
no wpa_cli). Needs root, as the socket does.

  python3 wpactl.py IFACE COMMAND...      each command's answer, e.g. STATUS, DRIVER_FLAGS
  python3 wpactl.py IFACE get KEY         one field of STATUS (wpa_state, freq, mode, ...)
  python3 wpactl.py IFACE stations        the clients of an access point, one MAC a line
"""

from __future__ import annotations

import os
import socket
import sys

SOCKETS = "/var/run/wpa_supplicant"


def query(iface: str, commands: list[str]) -> list[str]:
    local = f"/tmp/gm-wpactl-{os.getpid()}"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    s.bind(local)
    s.settimeout(5)
    answers = []
    try:
        for c in commands:
            s.sendto(c.encode(), f"{SOCKETS}/{iface}")
            answers.append(s.recv(16384).decode("utf-8", "replace"))
    finally:
        s.close()
        os.unlink(local)
    return answers


def stations(iface: str) -> list[str]:
    found = []
    answer = query(iface, ["STA-FIRST"])[0]
    while answer and not answer.startswith("FAIL") and len(found) < 64:
        mac = answer.split("\n", 1)[0].strip()
        found.append(mac)
        answer = query(iface, [f"STA-NEXT {mac}"])[0]
    return found


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    iface, rest = argv[0], argv[1:]
    try:
        if rest[0] == "get" and len(rest) == 2:
            for line in query(iface, ["STATUS"])[0].splitlines():
                key, _, value = line.partition("=")
                if key == rest[1]:
                    print(value)
                    return 0
            return 1
        if rest == ["stations"]:
            print("\n".join(stations(iface)))
            return 0
        for c, a in zip(rest, query(iface, rest)):
            print(f"== {c}\n{a.rstrip()}")
    except OSError as e:
        print(f"wpactl: {iface}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
