#!/usr/bin/env python3
"""Generate a one-device QNX headless-connectivity deployment bundle."""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")


def fail(message: str) -> "NoReturn":
    raise SystemExit(message)


def generate_key(path: Path, comment: str) -> None:
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", comment, "-f", str(path)],
        check=True,
    )
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    path.with_suffix(path.suffix + ".pub").chmod(
        stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
    )


def public_key(path: Path) -> str:
    fields = path.read_text(encoding="utf-8").strip().split()
    if len(fields) < 2 or fields[0] != "ssh-ed25519":
        fail(f"unexpected public key format in {path}")
    return " ".join(fields)


def shell_value(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_./:@?=+-]+", value):
        fail(f"value cannot be represented safely in qnx-connect.conf: {value!r}")
    return value


def write_private(path: Path, data: str) -> None:
    path.write_text(data, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate relay variables, an SD-card payload, and an SSH client config."
    )
    parser.add_argument("--relay-url", required=True, help="public wss:// URL of the relay")
    parser.add_argument("--device-name", default="qnxpi", help="SSH alias and bundle name")
    parser.add_argument("--remote-port", type=int, default=2222, help="relay loopback port")
    parser.add_argument(
        "--output",
        type=Path,
        help="new output directory (default: .qnx-connect/<device-name>)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not NAME_RE.fullmatch(args.device_name):
        fail("--device-name must use letters, digits, dots, underscores, or hyphens")
    parsed = urlparse(args.relay_url)
    if parsed.scheme != "wss" or not parsed.hostname:
        fail("--relay-url must be a complete wss:// URL")
    if parsed.username or parsed.password or parsed.fragment:
        fail("--relay-url cannot contain credentials or a fragment")
    if not 1024 <= args.remote_port <= 65535:
        fail("--remote-port must be between 1024 and 65535")

    output = (args.output or (ROOT / ".qnx-connect" / args.device_name)).expanduser().resolve()
    if output.exists():
        fail(f"output already exists; choose a new directory or move it aside: {output}")

    boot = output / "boot"
    client = output / "client"
    relay = output / "relay"
    for directory in (boot, client, relay):
        directory.mkdir(parents=True)

    tunnel_key = boot / "qnx_tunnel_key"
    laptop_key = client / "qnx_laptop"
    relay_access_key = client / "qnx_relay"
    relay_host_key = relay / "ssh_host_ed25519_key"
    generate_key(tunnel_key, f"{args.device_name}-tunnel")
    generate_key(laptop_key, f"{args.device_name}-login")
    generate_key(relay_access_key, f"{args.device_name}-relay-client")
    generate_key(relay_host_key, f"{args.device_name}-relay-host")

    tunnel_pub = public_key(tunnel_key.with_suffix(".pub"))
    login_pub = public_key(laptop_key.with_suffix(".pub"))
    relay_access_pub = public_key(relay_access_key.with_suffix(".pub"))
    relay_host_pub = public_key(relay_host_key.with_suffix(".pub"))

    authorized_keys = (
        f'restrict,port-forwarding,permitlisten="127.0.0.1:{args.remote_port}" {tunnel_pub}\n'
        f'restrict,port-forwarding,permitopen="127.0.0.1:{args.remote_port}" {relay_access_pub}\n'
    )
    (relay / "authorized_keys").write_text(authorized_keys, encoding="utf-8")
    host_key_b64 = base64.b64encode(relay_host_key.read_bytes()).decode("ascii")
    authorized_b64 = base64.b64encode(authorized_keys.encode("utf-8")).decode("ascii")
    write_private(
        relay / "relay.env",
        f"TUNNEL_HOST_KEY_B64={host_key_b64}\n"
        f"TUNNEL_AUTHORIZED_KEYS_B64={authorized_b64}\n",
    )

    relay_alias = f"qnx-rdv-{args.device_name}"
    host_key_fields = " ".join(relay_host_pub.split()[:2])
    (boot / "relay_known_hosts").write_text(
        f"qnx-rdv {host_key_fields}\n", encoding="utf-8"
    )
    (client / "relay_known_hosts").write_text(
        f"{relay_alias} {host_key_fields}\n", encoding="utf-8"
    )
    shutil.copy2(laptop_key.with_suffix(".pub"), boot / "qnx_laptop.pub")
    shutil.copy2(relay_access_key.with_suffix(".pub"), boot / "qnx_relay.pub")

    for name in (
        "onboot",
        "qnx-connect-supervisor.sh",
        "qnx-tunnel-launcher.sh",
        "qnx-tunnel.sh",
        "wsproxy.py",
    ):
        shutil.copy2(ROOT / "qnx" / name, boot / name)
    (boot / "qnx-connect.conf").write_text(
        f"DEVICE_NAME={shell_value(args.device_name)}\n"
        f"RELAY_URL={shell_value(args.relay_url)}\n"
        f"REMOTE_PORT={args.remote_port}\n",
        encoding="utf-8",
    )

    wsproxy = client / "wsproxy.py"
    shutil.copy2(ROOT / "client" / "wsproxy.py", wsproxy)
    wsproxy.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    target_known_hosts = client / "target_known_hosts"
    target_known_hosts.touch(mode=stat.S_IRUSR | stat.S_IWUSR)
    ssh_config = client / "ssh_config"
    ssh_config.write_text(
        f"Host {relay_alias}\n"
        f'    ProxyCommand python3 "{wsproxy}" "{args.relay_url}"\n'
        "    User tunnel\n"
        f'    IdentityFile "{relay_access_key}"\n'
        "    IdentitiesOnly yes\n"
        f'    UserKnownHostsFile "{client / "relay_known_hosts"}"\n'
        "    StrictHostKeyChecking yes\n"
        "    BatchMode yes\n"
        "    ConnectTimeout 20\n"
        "    ServerAliveInterval 15\n"
        "    ServerAliveCountMax 20\n"
        "    TCPKeepAlive yes\n"
        "    ControlMaster no\n\n"
        f"Host {args.device_name}\n"
        "    HostName 127.0.0.1\n"
        f"    Port {args.remote_port}\n"
        "    User qnxuser\n"
        f"    ProxyJump {relay_alias}\n"
        f'    IdentityFile "{laptop_key}"\n'
        "    IdentitiesOnly yes\n"
        "    BatchMode yes\n"
        "    ConnectTimeout 20\n"
        f'    UserKnownHostsFile "{target_known_hosts}"\n'
        "    StrictHostKeyChecking accept-new\n"
        "    ServerAliveInterval 15\n"
        "    ServerAliveCountMax 20\n"
        "    TCPKeepAlive yes\n"
        "    ControlMaster auto\n"
        "    ControlPath ~/.ssh/cm-%C\n"
        "    ControlPersist no\n",
        encoding="utf-8",
    )
    ssh_config.chmod(stat.S_IRUSR | stat.S_IWUSR)

    helper = client / "connection.sh"
    helper.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        f"CONFIG={shlex.quote(str(ssh_config))}\n"
        f"HOST={shlex.quote(args.device_name)}\n"
        "case ${1:-start} in\n"
        "  status)\n"
        "    if ssh -F \"$CONFIG\" -O check \"$HOST\"; then exit 0; fi\n"
        "    echo \"connection keeper is not running\" >&2; exit 1\n"
        "    ;;\n"
        "  stop)\n"
        "    if ssh -F \"$CONFIG\" -O check \"$HOST\" >/dev/null 2>&1; then\n"
        "      exec ssh -F \"$CONFIG\" -O exit \"$HOST\"\n"
        "    fi\n"
        "    echo \"connection keeper is already stopped\"\n"
        "    exit 0\n"
        "    ;;\n"
        "  start)\n"
        "    if ssh -F \"$CONFIG\" -O check \"$HOST\" >/dev/null 2>&1; then\n"
        "      exec ssh -F \"$CONFIG\" -O check \"$HOST\"\n"
        "    fi\n"
        "    CONTROL_PATH=$(ssh -F \"$CONFIG\" -G \"$HOST\" 2>/dev/null | "
        "awk '/^controlpath / { print $2; exit }')\n"
        "    case \"$CONTROL_PATH\" in \"$HOME\"/.ssh/cm-*) ;; "
        "*) echo \"unsafe control path: $CONTROL_PATH\" >&2; exit 1 ;; esac\n"
        "    if [ -e \"$CONTROL_PATH\" ] || [ -L \"$CONTROL_PATH\" ] || [ -S \"$CONTROL_PATH\" ]; then rm -f \"$CONTROL_PATH\"; fi\n"
        "    ssh -F \"$CONFIG\" -o ControlMaster=yes -o ControlPersist=no "
        "-f \"$HOST\" 'while :; do /proc/boot/sleep 3600; done'\n"
        "    ATTEMPTS=0\n"
        "    while [ \"$ATTEMPTS\" -lt 10 ]; do\n"
        "      if ssh -F \"$CONFIG\" -O check \"$HOST\" >/dev/null 2>&1; then\n"
        "        exec ssh -F \"$CONFIG\" -O check \"$HOST\"\n"
        "      fi\n"
        "      ATTEMPTS=$((ATTEMPTS + 1)); sleep 1\n"
        "    done\n"
        "    echo \"connection keeper did not become ready\" >&2; exit 1\n"
        "    ;;\n"
        "  *) echo \"usage: $0 [start|status|stop]\" >&2; exit 2 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    helper.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    print(f"Generated deployment bundle: {output}")
    print(f"Relay variables:           {relay / 'relay.env'}")
    print(f"SD-card payload:           {boot}")
    print(f"SSH config:                {ssh_config}")
    print("Private keys exist only inside this generated directory. Do not commit it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
