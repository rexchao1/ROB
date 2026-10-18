"""The opt-in deploy selects only Anthropic credentials and never prints values."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("deploy_key", ROOT / "qnx/deploy_key.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_only_anthropic_credentials_are_selected(tmp_path):
    path = tmp_path / ".env.local"
    path.write_text('export ANTHROPIC_API_KEY="fake-test-secret"\nANTHROPIC_WORKSPACE_ID=workspace\n'
                    'ELEVENLABS_API_KEY=other-secret\nGM_WIFI_PASSWORD=wifi-secret\n')
    assert module.selected(path) == "ANTHROPIC_API_KEY=fake-test-secret\nANTHROPIC_WORKSPACE_ID=workspace\n"
    path.write_text("GEMINI_API_KEY=other-secret\n")
    with pytest.raises(ValueError):
        module.selected(path)


def test_deploy_key_is_opt_in_and_never_in_output_or_arguments(tmp_path):
    # Fake SSH consumes stdin locally; no sockets or Pi access, even if deploy changes.
    (tmp_path / "qnx/ap").mkdir(parents=True)
    (tmp_path / "brain").mkdir()
    (tmp_path / "bin").mkdir()
    for name in ("deploy.sh", "deploy_key.py"):
        shutil.copyfile(ROOT / "qnx" / name, tmp_path / "qnx" / name)
    (tmp_path / "qnx/ap/net.conf").write_text("MAC_ADDR=10.77.0.2\nPI_ADDR=10.77.0.1\n")
    (tmp_path / "brain/__init__.py").touch()
    (tmp_path / "brain/referee.py").touch()
    (tmp_path / ".env.local").write_text("ANTHROPIC_API_KEY=fake-test-secret\nELEVENLABS_API_KEY=other-secret\n")
    ssh = tmp_path / "bin/ssh"
    ssh.write_text(f'#!{sys.executable}\nimport os, sys\nfrom pathlib import Path\n'
                   'root = Path(os.environ["DEPLOY_CAPTURE"])\n'
                   'n = len(list(root.glob("call-*")))\n'
                   '(root / f"call-{n}").write_bytes(sys.stdin.buffer.read())\n'
                   '(root / f"args-{n}").write_text(repr(sys.argv[1:]))\n')
    ssh.chmod(0o755)
    ifconfig = tmp_path / "bin/ifconfig"
    ifconfig.write_text("#!/bin/sh\nexit 0\n")
    ifconfig.chmod(0o755)
    env = {**os.environ, "PATH": str(tmp_path / "bin") + os.pathsep + os.environ["PATH"],
           "DEPLOY_CAPTURE": str(tmp_path)}
    for args, expected_calls in (([], 1), (["--with-key"], 3)):
        result = subprocess.run(["sh", "qnx/deploy.sh", *args, "loopback-test"], cwd=tmp_path,
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "fake-test-secret" not in result.stdout + result.stderr
        assert len(list(tmp_path.glob("call-*"))) == expected_calls
    assert (tmp_path / "call-2").read_text() == "ANTHROPIC_API_KEY=fake-test-secret\n"
    remote_command = (tmp_path / "args-2").read_text()
    assert "chmod 600" in remote_command and "gm-memory/talk.env" in remote_command
    assert "fake-test-secret" not in remote_command
    assert not list(tmp_path.glob("*.new"))
