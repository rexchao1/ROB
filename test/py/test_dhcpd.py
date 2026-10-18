"""The Pi's DHCP server (qnx/ap/dhcpd.py): it hands out addresses from the pool and
the netmask, never a router or DNS; a client keeps its address across a restart; it
answers only its own network's interface, and refuses what is not its to give."""

import importlib.util
import socket
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("dhcpd", ROOT / "qnx" / "ap" / "dhcpd.py")
dhcpd = importlib.util.module_from_spec(_spec)
sys.modules["dhcpd"] = dhcpd
_spec.loader.exec_module(dhcpd)

ROBOT = "a4:cf:12:34:56:78"
PHONE = "3c:22:fb:00:00:01"
PI = "b8:27:eb:74:f2:6c"


def request(kind, mac=ROBOT, xid=0x1234, ciaddr="0.0.0.0", giaddr="0.0.0.0", options=()):
    """A client's packet, built here without the server's own code."""
    chaddr = bytes.fromhex(mac.replace(":", "")) + b"\x00" * 10
    head = struct.pack("!BBBBIHH4s4s4s4s16s64s128s", 1, 1, 6, 0, xid, 0, 0, socket.inet_aton(ciaddr), socket.inet_aton("0.0.0.0"),
                       socket.inet_aton("0.0.0.0"), socket.inet_aton(giaddr), chaddr, b"", b"")
    opts = bytes([53, 1, kind]) + b"".join(bytes([c, len(v)]) + v for c, v in options) + b"\xff"
    return head + b"\x63\x82\x53\x63" + opts


def ip_opt(code, ip):
    return (code, socket.inet_aton(ip))


def server(tmp_path, pool="10.77.0.100-10.77.0.102", **kw):
    leases = dhcpd.Leases(dhcpd.pool_range(pool), str(tmp_path / "leases.json"), 3600)
    return dhcpd.Server("10.77.0.1", "255.255.255.0", leases, log=lambda m: None, **kw)


def answer(srv, data):
    out = srv.handle(dhcpd.parse(data))
    if out is None:
        return None, None
    return dhcpd.parse(out[0]), out[1]


def test_an_offer_carries_an_address_and_the_netmask_and_no_router_or_dns(tmp_path):
    srv = server(tmp_path)
    reply, to = answer(srv, request(dhcpd.DISCOVER))
    assert reply.op == 2 and reply.type == dhcpd.OFFER and reply.xid == 0x1234 and reply.mac == ROBOT
    assert reply.yiaddr == "10.77.0.100"
    assert reply.ip_option(dhcpd.SUBNET_MASK) == "255.255.255.0"
    assert reply.ip_option(dhcpd.SERVER_ID) == "10.77.0.1"
    assert struct.unpack("!I", reply.options[dhcpd.LEASE_TIME])[0] == 3600
    assert 3 not in reply.options and 6 not in reply.options and 15 not in reply.options  # router, DNS, domain
    assert to == ("10.77.0.255", 68)  # the subnet's broadcast: the client has no address yet


def test_a_request_for_the_offer_is_acked_and_the_address_survives_a_restart(tmp_path):
    srv = server(tmp_path)
    offer, _ = answer(srv, request(dhcpd.DISCOVER))
    ack, _ = answer(srv, request(dhcpd.REQUEST, options=[ip_opt(54, "10.77.0.1"), ip_opt(50, offer.yiaddr)]))
    assert ack.type == dhcpd.ACK and ack.yiaddr == offer.yiaddr
    assert 3 not in ack.options and 6 not in ack.options
    again, _ = answer(server(tmp_path), request(dhcpd.DISCOVER, xid=9))  # a new process, the same lease file
    assert again.yiaddr == offer.yiaddr
    other, _ = answer(srv, request(dhcpd.DISCOVER, mac=PHONE))
    assert other.yiaddr == "10.77.0.101"


def test_a_renewal_is_answered_straight_to_the_client(tmp_path):
    srv = server(tmp_path)
    answer(srv, request(dhcpd.REQUEST, options=[ip_opt(54, "10.77.0.1"), ip_opt(50, "10.77.0.100")]))
    ack, to = answer(srv, request(dhcpd.REQUEST, ciaddr="10.77.0.100"))
    assert ack.type == dhcpd.ACK and ack.yiaddr == "10.77.0.100" and to == ("10.77.0.100", 68)


def test_what_is_not_ours_to_give_is_refused(tmp_path):
    srv = server(tmp_path)
    assert answer(srv, request(dhcpd.REQUEST, options=[ip_opt(54, "172.20.10.1"), ip_opt(50, "172.20.10.3")])) == (None, None)  # another server's offer
    nak, to = answer(srv, request(dhcpd.REQUEST, options=[ip_opt(50, "172.20.10.3")]))  # an address from the old network
    assert nak.type == dhcpd.NAK and to == ("10.77.0.255", 68)
    answer(srv, request(dhcpd.REQUEST, options=[ip_opt(54, "10.77.0.1"), ip_opt(50, "10.77.0.100")]))
    taken, _ = answer(srv, request(dhcpd.REQUEST, mac=PHONE, options=[ip_opt(54, "10.77.0.1"), ip_opt(50, "10.77.0.100")]))
    assert taken.type == dhcpd.NAK
    outside, _ = answer(srv, request(dhcpd.REQUEST, mac=PHONE, options=[ip_opt(50, "10.77.0.2")]))  # the Mac's fixed address
    assert outside.type == dhcpd.NAK


def test_its_own_interface_and_relays_get_no_answer(tmp_path):
    srv = server(tmp_path, ignore=(PI.upper(),))
    assert answer(srv, request(dhcpd.DISCOVER, mac=PI)) == (None, None)
    assert answer(srv, request(dhcpd.DISCOVER, giaddr="10.0.0.1")) == (None, None)


def test_a_full_pool_offers_the_lease_that_ran_out(tmp_path):
    now = [1000.0]
    leases = dhcpd.Leases(dhcpd.pool_range("10.77.0.100-10.77.0.100"), None, 60, clock=lambda: now[0])
    srv = dhcpd.Server("10.77.0.1", "255.255.255.0", leases, log=lambda m: None)
    answer(srv, request(dhcpd.REQUEST, options=[ip_opt(50, "10.77.0.100")]))
    assert answer(srv, request(dhcpd.DISCOVER, mac=PHONE)) == (None, None)
    now[0] += 61
    offer, _ = answer(srv, request(dhcpd.DISCOVER, mac=PHONE))
    assert offer.yiaddr == "10.77.0.100"
    ack, _ = answer(srv, request(dhcpd.REQUEST, mac=PHONE, options=[ip_opt(54, "10.77.0.1"), ip_opt(50, "10.77.0.100")]))
    assert ack.type == dhcpd.ACK and leases.holder("10.77.0.100") == PHONE


def test_a_declined_address_is_skipped_only_when_this_server_offered_it_to_that_client(tmp_path):
    """A5: a DECLINE names an address the client found in use; one it was never offered
    or leased, or from outside the pool, is ignored, so a stranger cannot empty the pool."""
    srv = server(tmp_path)
    answer(srv, request(dhcpd.DECLINE, options=[ip_opt(50, "10.77.0.100")]))  # never offered to this client
    answer(srv, request(dhcpd.DECLINE, mac=PHONE, options=[ip_opt(50, "10.77.0.2")]))  # the Mac's, outside the pool
    assert srv.leases.declined == {}
    offer, _ = answer(srv, request(dhcpd.DISCOVER))
    assert offer.yiaddr == "10.77.0.100"
    answer(srv, request(dhcpd.DECLINE, mac=PHONE, options=[ip_opt(50, "10.77.0.100")]))  # someone else declines our offer
    assert srv.leases.declined == {}
    answer(srv, request(dhcpd.DECLINE, options=[ip_opt(50, "10.77.0.100")]))  # the client it was offered to
    assert list(srv.leases.declined) == ["10.77.0.100"]
    offer, _ = answer(srv, request(dhcpd.DISCOVER))
    assert offer.yiaddr == "10.77.0.101"
    answer(srv, request(dhcpd.REQUEST, mac=PHONE, options=[ip_opt(54, "10.77.0.1"), ip_opt(50, "10.77.0.102")]))
    answer(srv, request(dhcpd.DECLINE, mac=PHONE, options=[ip_opt(50, "10.77.0.102")]))  # a leased address, declined by its holder
    assert sorted(srv.leases.declined) == ["10.77.0.100", "10.77.0.102"] and srv.leases.holder("10.77.0.102") is None


def test_declines_are_capped_and_age_out(tmp_path):
    now = [1000.0]
    leases = dhcpd.Leases(dhcpd.pool_range("10.77.0.100-10.77.0.199"), None, 3600, clock=lambda: now[0])
    srv = dhcpd.Server("10.77.0.1", "255.255.255.0", leases, log=lambda m: None)
    for i in range(100):
        mac = f"3c:22:fb:00:01:{i:02x}"
        offer, _ = answer(srv, request(dhcpd.DISCOVER, mac=mac))
        answer(srv, request(dhcpd.DECLINE, mac=mac, options=[ip_opt(50, offer.yiaddr)]))
    assert len(leases.declined) == dhcpd.MAX_DECLINED == 64
    offer, _ = answer(srv, request(dhcpd.DISCOVER))  # the pool is not empty: the oldest declines were let go
    assert offer is not None and offer.yiaddr in leases.pool
    now[0] += dhcpd.DECLINED_FOR + 1
    answer(srv, request(dhcpd.DISCOVER, mac=PHONE))  # any packet prunes the old entries
    assert leases.declined == {}


def test_a_hostname_reaches_the_log_and_the_lease_file_as_printable_ascii_only(tmp_path):
    logged = []
    leases = dhcpd.Leases(dhcpd.pool_range("10.77.0.100-10.77.0.102"), str(tmp_path / "leases.json"), 3600)
    srv = dhcpd.Server("10.77.0.1", "255.255.255.0", leases, log=logged.append)
    name = "rob\x1b[2Jot\n\u00e9" + "x" * 100
    answer(srv, request(dhcpd.REQUEST, options=[ip_opt(54, "10.77.0.1"), ip_opt(50, "10.77.0.100"), (12, name.encode("utf-8"))]))
    text = "\n".join(logged) + (tmp_path / "leases.json").read_text()
    assert "\x1b" not in text and "\u00e9" not in text and "rob?" in text
    assert all(32 <= ord(c) < 127 or c == "\n" for c in text)
    assert len(leases.by_mac[ROBOT]["hostname"]) <= 64


def test_the_pool_must_sit_inside_the_network(capsys):
    assert dhcpd.main(["--server", "10.77.0.1", "--netmask", "255.255.255.0", "--pool", "10.78.0.1-10.78.0.9"]) == 2
    assert dhcpd.main(["--server", "10.77.0.1", "--netmask", "255.255.255.0", "--pool", "10.77.0.1-10.77.0.9"]) == 2


@pytest.mark.skipif(sys.platform != "darwin", reason="IP_RECVIF on loopback (lo0): macOS here, QNX on the Pi")
def test_over_a_socket_only_the_named_interface_is_answered(tmp_path):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind(("127.0.0.1", 0))
    client.settimeout(2)
    srv = server(tmp_path, iface="lo0", port=0, client_port=client.getsockname()[1], broadcast="127.0.0.1", bind="127.0.0.1")
    sock = srv.open()
    try:
        client.sendto(request(dhcpd.DISCOVER), sock.getsockname())
        srv.serve_once()
        offer = dhcpd.parse(client.recv(1024))
        assert offer.type == dhcpd.OFFER and offer.yiaddr == "10.77.0.100"
        srv.iface = "bcm0"  # the same packet, arriving on an interface it does not serve
        client.sendto(request(dhcpd.DISCOVER, xid=2), sock.getsockname())
        srv.serve_once()
        with pytest.raises(socket.timeout):
            client.settimeout(0.3)
            client.recv(1024)
    finally:
        sock.close()
        client.close()
