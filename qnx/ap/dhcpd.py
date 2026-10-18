"""The DHCP server for the Pi's own Wi-Fi network: it hands out addresses and the
netmask, and nothing else. No router and no DNS: the network gives its clients no
internet, and a Mac on it keeps its internet on another interface (qnx/README.md). The
Pi's own internet, with the uplink, goes out the hotspot link, never through here.

QNX 8 has no DHCP server, and the robot's Wi-Fi needs one. Standard library only
(Python 3.11 to 3.14). Port 67 needs root.

  sudo python3 dhcpd.py --iface bcm0 --server 10.77.0.1 --netmask 255.255.255.0 \\
      --pool 10.77.0.100-10.77.0.199 --leases leases.json [--ignore MAC]...

Only requests that arrive on --iface, the access point's interface (bcm0, or bcm1
beside the hotspot link), are answered (IP_RECVIF, which QNX's io-sock and macOS both
have), so the hotspot or an Ethernet cable into some other network never gets an
answer from here. A client keeps its address across restarts of either side: the
leases are kept in a file, by MAC address. Replies go to the subnet's broadcast
address, which leaves on the access point's interface, or straight to a client that
already has its address; never to 255.255.255.255, which would follow the default
route (none without the uplink, the hotspot link with it).
"""

from __future__ import annotations

import argparse
import dataclasses
import ipaddress
import json
import os
import socket
import struct
import sys
import time
from collections.abc import Callable
from typing import Any

MAGIC = b"\x63\x82\x53\x63"
DISCOVER, OFFER, REQUEST, DECLINE, ACK, NAK, RELEASE, INFORM = 1, 2, 3, 4, 5, 6, 7, 8
NAMES = {1: "DISCOVER", 2: "OFFER", 3: "REQUEST", 4: "DECLINE", 5: "ACK", 6: "NAK", 7: "RELEASE", 8: "INFORM"}
# Option codes. Router (3) and DNS (6) are left out on purpose and never sent.
SUBNET_MASK, HOSTNAME, BROADCAST, REQUESTED_IP, LEASE_TIME, MSG_TYPE, SERVER_ID, MESSAGE, RENEWAL, REBINDING = 1, 12, 28, 50, 51, 53, 54, 56, 58, 59
IP_RECVIF = getattr(socket, "IP_RECVIF", 20)  # BSD: the receiving interface as ancillary data
HEADER = struct.Struct("!BBBBIHH4s4s4s4s16s64s128s")  # 236 bytes, then the magic cookie
DECLINED_FOR = 600.0  # seconds an address a client found in use is not handed out


@dataclasses.dataclass
class Packet:
    op: int
    htype: int
    hlen: int
    xid: int
    flags: int
    ciaddr: str
    yiaddr: str
    giaddr: str
    chaddr: bytes  # all 16 bytes, as sent
    options: dict[int, bytes]

    @property
    def mac(self) -> str:
        return ":".join(f"{b:02x}" for b in self.chaddr[: self.hlen])

    @property
    def type(self) -> int | None:
        v = self.options.get(MSG_TYPE)
        return v[0] if v else None

    def ip_option(self, code: int) -> str | None:
        v = self.options.get(code)
        return socket.inet_ntoa(v) if v and len(v) == 4 else None

    @property
    def hostname(self) -> str:
        return self.options.get(HOSTNAME, b"").decode("utf-8", "replace")


def parse(data: bytes) -> Packet | None:
    """A BOOTP/DHCP packet, or None for anything else."""
    if len(data) < HEADER.size + 4 or data[HEADER.size : HEADER.size + 4] != MAGIC:
        return None
    op, htype, hlen, _hops, xid, _secs, flags, ciaddr, yiaddr, _siaddr, giaddr, chaddr, _sname, _file = HEADER.unpack_from(data)
    options: dict[int, bytes] = {}
    i = HEADER.size + 4
    while i < len(data):
        code = data[i]
        if code == 255:
            break
        if code == 0:
            i += 1
            continue
        if i + 1 >= len(data):
            break
        n = data[i + 1]
        options[code] = data[i + 2 : i + 2 + n]
        i += 2 + n
    return Packet(op, htype, hlen, xid, flags, socket.inet_ntoa(ciaddr), socket.inet_ntoa(yiaddr), socket.inet_ntoa(giaddr), chaddr, options)


def build(request: Packet, msg_type: int, yiaddr: str, options: list[tuple[int, bytes]], broadcast_flag: bool = False) -> bytes:
    """A reply to `request`: op 2, the same transaction and hardware address."""
    flags = request.flags | (0x8000 if broadcast_flag else 0)
    ciaddr = request.ciaddr if msg_type == ACK else "0.0.0.0"
    head = HEADER.pack(2, 1, 6, 0, request.xid, 0, flags, socket.inet_aton(ciaddr), socket.inet_aton(yiaddr),
                       socket.inet_aton("0.0.0.0"), socket.inet_aton("0.0.0.0"), request.chaddr, b"", b"")
    body = bytes([MSG_TYPE, 1, msg_type]) + b"".join(bytes([code, len(v)]) + v for code, v in options) + b"\xff"
    packet = head + MAGIC + body
    return packet + b"\x00" * max(0, 300 - len(packet))  # some clients drop replies shorter than BOOTP's 300 bytes


class Leases:
    """Which MAC has which address from the pool, kept in a JSON file. A MAC keeps
    its address for as long as nobody else needs it, expired or not."""

    def __init__(self, pool: list[str], path: str | None, lease_seconds: int, clock: Callable[[], float] = time.time) -> None:
        self.pool = pool
        self.path = path
        self.lease_seconds = lease_seconds
        self.clock = clock
        self.by_mac: dict[str, dict[str, Any]] = {}  # mac -> {"ip", "expires", "hostname"}
        self.declined: dict[str, float] = {}  # ip -> until
        if path and os.path.exists(path):
            try:
                with open(path) as f:
                    saved = json.load(f)
                self.by_mac = {m: v for m, v in saved.items() if isinstance(v, dict) and v.get("ip") in pool}
            except (OSError, ValueError):
                self.by_mac = {}

    def holder(self, ip: str) -> str | None:
        for mac, lease in self.by_mac.items():
            if lease["ip"] == ip:
                return mac
        return None

    def _usable(self, ip: str, mac: str) -> bool:
        if ip not in self.pool or self.declined.get(ip, 0) > self.clock():
            return False
        other = self.holder(ip)
        return other is None or other == mac

    def offer(self, mac: str, requested: str | None = None) -> str | None:
        """The address to offer `mac`: its own, else the one it asks for if free, else
        the first never used, else the one whose lease ran out longest ago."""
        mine = self.by_mac.get(mac)
        if mine and self._usable(mine["ip"], mac):
            return mine["ip"]
        if requested and self._usable(requested, mac):
            return requested
        for ip in self.pool:
            if self._usable(ip, mac):
                return ip
        now = self.clock()
        expired = sorted((lease["expires"], m) for m, lease in self.by_mac.items() if lease["expires"] < now and self.declined.get(lease["ip"], 0) <= now)
        return self.by_mac[expired[0][1]]["ip"] if expired else None

    def bind(self, mac: str, ip: str, hostname: str = "") -> bool:
        """Lease `ip` to `mac`; False if it is not ours to give. An expired lease of
        someone else's is taken over."""
        if ip not in self.pool or self.declined.get(ip, 0) > self.clock():
            return False
        other = self.holder(ip)
        if other is not None and other != mac:
            if self.by_mac[other]["expires"] >= self.clock():
                return False
            del self.by_mac[other]
        self.by_mac[mac] = {"ip": ip, "expires": self.clock() + self.lease_seconds, "hostname": hostname}
        self.save()
        return True

    def release(self, mac: str, ip: str) -> None:
        lease = self.by_mac.get(mac)
        if lease and lease["ip"] == ip:
            lease["expires"] = 0  # kept as a hint: the same MAC gets it back next time
            self.save()

    def decline(self, mac: str, ip: str | None) -> None:
        if ip:
            self.declined[ip] = self.clock() + DECLINED_FOR
            if self.by_mac.get(mac, {}).get("ip") == ip:
                del self.by_mac[mac]
                self.save()

    def save(self) -> None:
        if not self.path:
            return
        tmp = f"{self.path}.tmp"
        with open(tmp, "w") as f:
            json.dump(self.by_mac, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)


class Server:
    def __init__(self, server_ip: str, netmask: str, leases: Leases, *, iface: str | None = None, ignore: tuple[str, ...] = (),
                 port: int = 67, client_port: int = 68, broadcast: str | None = None, bind: str = "0.0.0.0",
                 log: Callable[[str], None] | None = None) -> None:
        self.server_ip = server_ip
        self.netmask = netmask
        self.net = ipaddress.IPv4Network(f"{server_ip}/{netmask}", strict=False)
        self.leases = leases
        self.iface = iface
        self.ignore = {m.lower() for m in ignore}
        self.port = port
        self.client_port = client_port
        self.broadcast = broadcast or str(self.net.broadcast_address)
        self.bind_addr = bind
        self.sock: socket.socket | None = None
        self._log = log or (lambda msg: print(f"dhcpd: {time.strftime('%H:%M:%S')} {msg}", flush=True))

    def _options(self, lease: bool) -> list[tuple[int, bytes]]:
        opts = [(SERVER_ID, socket.inet_aton(self.server_ip))]
        if lease:
            t = self.leases.lease_seconds
            opts += [(LEASE_TIME, struct.pack("!I", t)), (RENEWAL, struct.pack("!I", t // 2)), (REBINDING, struct.pack("!I", t * 7 // 8))]
        return opts + [(SUBNET_MASK, socket.inet_aton(self.netmask)), (BROADCAST, socket.inet_aton(str(self.net.broadcast_address)))]

    def _to(self, request: Packet, msg_type: int) -> tuple[str, int]:
        if msg_type != NAK and request.ciaddr != "0.0.0.0":
            return (request.ciaddr, self.client_port)
        return (self.broadcast, self.client_port)

    def _reply(self, request: Packet, msg_type: int, yiaddr: str, lease: bool = True) -> tuple[bytes, tuple[str, int]]:
        if msg_type == NAK:
            data = build(request, NAK, "0.0.0.0", [(SERVER_ID, socket.inet_aton(self.server_ip))], broadcast_flag=True)
        else:
            data = build(request, msg_type, yiaddr, self._options(lease))
        name = f" ({request.hostname})" if request.hostname else ""
        self._log(f"{NAMES[msg_type]} {yiaddr if msg_type != NAK else '-'} to {request.mac}{name}")
        return data, self._to(request, msg_type)

    def handle(self, request: Packet) -> tuple[bytes, tuple[str, int]] | None:
        """The reply to one request and where it goes, or None for no reply."""
        if request.op != 1 or request.htype != 1 or request.hlen != 6:
            return None
        if request.mac in self.ignore or request.giaddr != "0.0.0.0":
            return None  # this machine's own interface, or a relay (there are none here)
        kind = request.type
        if kind == DISCOVER:
            ip = self.leases.offer(request.mac, request.ip_option(REQUESTED_IP))
            if ip is None:
                self._log(f"no address left for {request.mac}")
                return None
            return self._reply(request, OFFER, ip)
        if kind == REQUEST:
            server = request.ip_option(SERVER_ID)
            if server is not None and server != self.server_ip:
                return None  # it took another server's offer
            want = request.ip_option(REQUESTED_IP) or (request.ciaddr if request.ciaddr != "0.0.0.0" else None)
            if want is None:
                return None
            if ipaddress.IPv4Address(want) not in self.net:
                return self._reply(request, NAK, want)  # an address from some other network
            if self.leases.bind(request.mac, want, request.hostname):
                return self._reply(request, ACK, want)
            return self._reply(request, NAK, want)
        if kind == RELEASE:
            self.leases.release(request.mac, request.ciaddr)
            self._log(f"RELEASE {request.ciaddr} from {request.mac}")
            return None
        if kind == DECLINE:
            self.leases.decline(request.mac, request.ip_option(REQUESTED_IP))
            self._log(f"DECLINE {request.ip_option(REQUESTED_IP)} from {request.mac}")
            return None
        if kind == INFORM and request.ciaddr != "0.0.0.0":
            return self._reply(request, ACK, "0.0.0.0", lease=False)
        return None

    def open(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        if self.iface:
            s.setsockopt(socket.IPPROTO_IP, IP_RECVIF, 1)  # no fallback: without it every network would be answered
        s.bind((self.bind_addr, self.port))
        self.sock = s
        return s

    def arrived_on(self, ancillary: list[tuple[int, int, bytes]]) -> str | None:
        """The interface name from IP_RECVIF's sockaddr_dl (len, family, index, type,
        nlen, alen, slen, then the name)."""
        for level, kind, blob in ancillary:
            if level == socket.IPPROTO_IP and kind == IP_RECVIF and len(blob) >= 8:
                nlen = blob[5]
                if nlen:
                    return blob[8 : 8 + nlen].decode("ascii", "replace")
                try:
                    return socket.if_indextoname(struct.unpack_from("=H", blob, 2)[0])
                except OSError:
                    return None
        return None

    def serve_once(self) -> None:
        assert self.sock is not None
        data, ancillary, _flags, _addr = self.sock.recvmsg(4096, socket.CMSG_SPACE(128))
        if self.iface and self.arrived_on(ancillary) != self.iface:
            return
        request = parse(data)
        if request is None:
            return
        out = self.handle(request)
        if out is not None:
            try:
                self.sock.sendto(*out)
            except OSError as e:
                self._log(f"could not send to {out[1]}: {e}")

    def serve_forever(self) -> None:
        if self.sock is None:
            self.open()
        self._log(f"serving {self.leases.pool[0]}-{self.leases.pool[-1]} on {self.iface or 'every interface'} as {self.server_ip}, no router, no DNS")
        while True:
            self.serve_once()


def pool_range(spec: str) -> list[str]:
    first, _, last = spec.partition("-")
    a, b = int(ipaddress.IPv4Address(first)), int(ipaddress.IPv4Address(last))
    if b < a:
        raise ValueError(f"empty pool {spec}")
    return [str(ipaddress.IPv4Address(n)) for n in range(a, b + 1)]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dhcpd.py", description="DHCP for the Pi's own Wi-Fi network: addresses only, no router, no DNS.")
    p.add_argument("--iface", default=None, help="answer only requests that arrive on this interface (the access point's on the Pi: bcm0, or bcm1 beside the hotspot link)")
    p.add_argument("--server", required=True, help="this machine's address on that network")
    p.add_argument("--netmask", required=True)
    p.add_argument("--pool", required=True, help="FIRST-LAST, inside the network")
    p.add_argument("--leases", default=None, help="the lease file (JSON), kept across restarts")
    p.add_argument("--lease-seconds", type=int, default=12 * 3600)
    p.add_argument("--ignore", action="append", default=[], help="a MAC never answered (this machine's own); repeatable")
    p.add_argument("--port", type=int, default=67)
    p.add_argument("--client-port", type=int, default=68)
    p.add_argument("--broadcast", default=None, help="where broadcast replies go (default the network's broadcast address)")
    p.add_argument("--bind", default="0.0.0.0")
    args = p.parse_args(argv)
    pool = pool_range(args.pool)
    net = ipaddress.IPv4Network(f"{args.server}/{args.netmask}", strict=False)
    outside = [ip for ip in (pool[0], pool[-1]) if ipaddress.IPv4Address(ip) not in net]
    if outside or args.server in pool:
        print(f"dhcpd.py: the pool must sit inside {net} and leave out {args.server}", file=sys.stderr)
        return 2
    server = Server(args.server, args.netmask, Leases(pool, args.leases, args.lease_seconds), iface=args.iface, ignore=tuple(args.ignore),
                    port=args.port, client_port=args.client_port, broadcast=args.broadcast, bind=args.bind)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
