"""Check log lifetimes with shell functions that never contact or stop ROB."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "scripts/rob.sh").read_text()
FUNCTIONS = SCRIPT[SCRIPT.index('say() {'):SCRIPT.index('\ncmd=')]
STUBS = '''
LOGS=.cache/game
PIDS=$LOGS/pids
PORTS="8080 8767 8768"
ROOT=$PWD
IP=127.0.0.1
PIPER_VOICE=test
MAC_ADDR=10.77.0.2
SSID=test
TABLE_PORT=8090
DEV=""
running() { :; }
listening() { echo 123; }
folder() { echo elsewhere; }
kill() { echo "unexpected kill" >&2; exit 90; }
ps() { echo VISION_HOST=127.0.0.1; }
wifi_addr() { :; }
pi_up() { return 1; }
robot_joined() { return 0; }
preflight() { mkdir -p "$LOGS"; }
clear_ports() { return 1; }
pick_network() { REFEREE=local; }
nohup() { :; }
curl() { return 0; }
open() { :; }
'''


def run(tmp_path, command, keep=False):
    env = dict(os.environ, GM_KEEP_LOGS="1" if keep else "0")
    return subprocess.run(["sh", "-c", "set -eu\n" + FUNCTIONS + STUBS + command], cwd=tmp_path, env=env,
                          capture_output=True, text=True, check=True)


@pytest.mark.parametrize("keep", [False, True])
def test_stop_removes_logs_unless_debugging_and_status_needs_no_log(tmp_path, keep):
    logs = tmp_path / ".cache/game"
    logs.mkdir(parents=True)
    for name in ("brain", "gateway", "ota-stub", "old"):
        (logs / f"{name}.log").write_text("private speech\n")
    run(tmp_path, "stop\nstatus", keep)
    assert bool(list(logs.glob("*.log"))) == keep


@pytest.mark.parametrize("keep", [False, True])
def test_start_empties_every_old_log_even_when_debugging(tmp_path, keep):
    logs = tmp_path / ".cache/game"
    logs.mkdir(parents=True)
    for name in ("brain", "gateway", "ota-stub", "old"):
        (logs / f"{name}.log").write_text("previous session\n")
    run(tmp_path, "start", keep)
    assert all("previous session" not in log.read_text() for log in logs.glob("*.log"))


def test_restart_stops_then_starts_a_fresh_log(tmp_path):
    logs = tmp_path / ".cache/game"
    logs.mkdir(parents=True)
    (logs / "brain.log").write_text("previous session\n")
    run(tmp_path, 'stop\ntest ! -e "$LOGS/brain.log"\nstart')
    assert (logs / "brain.log").read_text() == ""


@pytest.mark.parametrize("keep", [False, True])
def test_terminal_game_removes_logs_on_exit_unless_debugging(tmp_path, keep):
    script = (ROOT / "scripts/game.sh").read_text()
    setup = script[script.index('STARTED=""'):script.index('\nif ! ifconfig')]
    logs = tmp_path / ".cache/game"
    logs.mkdir(parents=True)
    (logs / "gateway.log").write_text("this session\n")
    subprocess.run(["sh", "-c", 'set -eu\nLOGS=.cache/game\n' + setup], cwd=tmp_path,
                   env=dict(os.environ, GM_KEEP_LOGS="1" if keep else "0"), check=True)
    assert (logs / "gateway.log").exists() == keep
