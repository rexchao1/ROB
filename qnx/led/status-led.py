"""The Pi's status light: one red-yellow-green LED on the GPIO header, showing how far
the box has come up. The colours add up: each stage keeps the ones before it lit. Runs on the QNX Pi as qnxuser (in the gpio group), standard
library only; qnx/led.sh installs and starts it.

    red                 the Pi is on (this program is running)
    red, yellow         the Wi-Fi is up: bcm0 has an address, on the hotspot or the gamemaster network
    red, yellow, green  the robot is on the same Wi-Fi: its MAC answers a ping

Wiring (qnx/README.md, "The status light"): red leg to pin 11 (GPIO17), yellow to
pin 13 (GPIO27), green to pin 15 (GPIO22), the common (longest) leg to pin 9 (ground),
a 220-330 ohm resistor on each colour leg. QNX's rpi_gpio exposes each pin as
/dev/gpio/N: write "out" once, then "on" or "off".

  python3 status-led.py --robot-mac 7c:4f:ad:af:ca:6c [--iface bcm0] [--leases FILE]
  python3 status-led.py --test        each colour for 2 s, then off
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PINS = {"red": 17, "yellow": 27, "green": 22}
POLL = 3.0  # seconds between checks
PING_WAIT = 2  # seconds a ping waits: the robot's Wi-Fi power save answers in up to ~1 s
MISSES = 3  # pings in a row the robot may miss before the light goes back to yellow
SWEEP_EVERY = 20.0  # seconds between looks for the robot's address when it is not known
SWEEP_MAX = 256  # addresses at most in one look (the gamemaster network is a /24)


def gpio(pin: int, value: str) -> None:
    with open(f"/dev/gpio/{pin}", "w") as f:
        f.write(value)


def show(stage: str | None, alone: bool = False) -> None:
    """`stage` and every colour before it lit (only `stage` when `alone`); None is all off."""
    lit = list(PINS)[: list(PINS).index(stage) + 1] if stage else []
    for name, pin in PINS.items():
        gpio(pin, "on" if name in lit and (not alone or name == stage) else "off")


def run(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def network(iface: str) -> ipaddress.IPv4Interface | None:
    """bcm0's IPv4 address and netmask, None while it has none."""
    m = re.search(r"\binet (\d+\.\d+\.\d+\.\d+) netmask (0x[0-9a-f]+)", run("ifconfig", iface))
    if not m:
        return None
    return ipaddress.IPv4Interface(f"{m.group(1)}/{bin(int(m.group(2), 16)).count('1')}")


def ping(ip: str) -> bool:
    return subprocess.run(["ping", "-c1", f"-t{PING_WAIT}", ip], capture_output=True).returncode == 0


def arp_ip(mac: str) -> str | None:
    """The address the ARP table holds for `mac`, if any."""
    for line in run("arp", "-an").splitlines():
        m = re.match(r"\? \((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-f:]+) ", line)
        if m and canon(m.group(2)) == mac:
            return m.group(1)
    return None


def lease_ip(leases: Path | None, mac: str) -> str | None:
    """The address dhcpd.py gave `mac` on the gamemaster network, if it did."""
    if leases is None or not leases.is_file():
        return None
    try:
        data = json.loads(leases.read_text())
    except (OSError, ValueError):
        return None
    for key, value in (data.items() if isinstance(data, dict) else []):
        if canon(key) == mac and isinstance(value, dict) and value.get("ip"):
            return str(value["ip"])
    return None


def sweep(net: ipaddress.IPv4Interface) -> None:
    """Ping every address on the network once, so the ARP table learns who is there."""
    hosts = [str(h) for h in net.network.hosts() if h != net.ip][:SWEEP_MAX]
    with ThreadPoolExecutor(max_workers=32) as pool:
        list(pool.map(ping, hosts))


def canon(mac: str) -> str:
    """aa:b:cc... and AA:0B:CC... to aa:0b:cc..."""
    return ":".join(f"{int(p, 16):02x}" for p in mac.split(":"))


class Robot:
    """Whether the robot is on the Wi-Fi, from its MAC: find its address, then ping it."""

    def __init__(self, mac: str, leases: Path | None) -> None:
        self.mac, self.leases = canon(mac), leases
        self.ip: str | None = None
        self.misses = MISSES
        self.swept = 0.0

    def present(self, net: ipaddress.IPv4Interface) -> bool:
        if self.ip is None or ipaddress.IPv4Address(self.ip) not in net.network:
            self.ip = lease_ip(self.leases, self.mac) or arp_ip(self.mac)
            if self.ip is None and time.monotonic() - self.swept >= SWEEP_EVERY:
                self.swept = time.monotonic()
                sweep(net)
                self.ip = arp_ip(self.mac)
        if self.ip is not None and ping(self.ip):
            self.misses = 0
        else:
            self.misses += 1
            if self.misses >= MISSES:
                self.ip = None  # look for it again: it may come back at another address
        return self.misses < MISSES


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="The Pi's red-yellow-green status light.")
    ap.add_argument("--robot-mac", help="the robot's Wi-Fi MAC (qnx/ap/net.conf ROBOT_MAC)")
    ap.add_argument("--iface", default="bcm0")
    ap.add_argument("--leases", type=Path, help="dhcpd.py's leases file on the gamemaster network")
    ap.add_argument("--test", action="store_true", help="each colour for 2 s, then off")
    args = ap.parse_args(argv)

    for pin in PINS.values():
        gpio(pin, "out")
    if args.test:
        for colour in PINS:
            print(colour, flush=True)
            show(colour, alone=True)
            time.sleep(2)
        show(None)
        return 0

    def stop(*_: object) -> None:
        show(None)
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    robot = Robot(args.robot_mac, args.leases) if args.robot_mac else None
    shown = None
    while True:
        net = network(args.iface)
        stage = "red" if net is None else "green" if robot and robot.present(net) else "yellow"
        if stage != shown:
            show(stage)
            print(time.strftime("%m-%d %H:%M:%S"), stage, robot.ip if robot and stage == "green" else "", flush=True)
            shown = stage
        time.sleep(POLL)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
