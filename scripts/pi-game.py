"""Play one whole Mafia game on a test-mode brain, reacting to what the robot says, and
record what the robot was told. Run once with the referee in the brain (local) and once
with the referee elsewhere (remote); the records must match.

  python scripts/pi-game.py local OUT.json
  python scripts/pi-game.py remote OUT.json [--pi user@host --mac-ip IP]  (referee over ssh on the Pi)
  python scripts/pi-game.py loopback OUT.json                              (referee as a local process)
"""
import json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path
ROOT = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, ROOT)
from brain import keys, lines
from brain.__main__ import TEST_TABLE_TOKEN

PY = ROOT + "/.venv/bin/python"
FIVE = [{"bearing": b} for b in (-60, -30, 0, 30, 60)]

def http(url, method="GET", body=None, ctype="application/json"):
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read() or b"null")

def spawn(args, patterns, name, timeout=30):
    """Start a process, drain its output on a thread (a full pipe would stall it), and
    return once every pattern matched: (process, first groups)."""
    import threading
    p = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    buf = []
    def drain():
        for line in iter(p.stdout.readline, b""):
            buf.append(line.decode("utf-8", "replace"))
            if len(buf) > 4000:
                del buf[:2000]
    threading.Thread(target=drain, daemon=True).start()
    end = time.time() + timeout
    while time.time() < end:
        out = "".join(buf)
        found = [re.search(pat, out) for pat in patterns]
        if all(found):
            p.log = buf
            return p, [m.group(1) for m in found]
        if p.poll() is not None:
            break
        time.sleep(0.05)
    p.kill()
    raise RuntimeError(f"{name} did not start:\n" + "".join(buf)[-4000:])

def frame(pan, faces):
    args = [PY, "test/fixtures/table.py", f"--pan={pan}"] + [f"--face={f['bearing']}:{f.get('pose', 'frontal')}{':close' if f.get('close') else ''}" for f in faces]
    return subprocess.run(args, cwd=ROOT, capture_output=True, check=True).stdout

def play(url, fake):
    said = lambda: [c.get("line") for c in http(fake + "/mock/calls") if c["tool"] == "pcm" and c.get("error") is None]
    http(url + "/test/reset", "POST", {})
    http(url + "/test/table", "POST", {"faces": FIVE})
    http(url + "/test/rig", "POST", {"mafia": {"mafia": [2], "doctor": 4}})
    http(url + "/test/hear", "POST", {"text": "let's play mafia"})
    phase, answered, t0 = None, 0, time.monotonic()
    for step in range(2000):
        http(url + "/test/advance", "POST", {"seconds": 1})
        state = http(url + "/test/state")
        if state.get("phase") != phase:
            phase = state.get("phase")
            print(f"  t={step + 1:>4}s phase {phase}", flush=True)
            if phase == "deal":  # each seat leans in alone when the head turns to it
                for b in (-60, -30, 0, 30, 60):
                    http(f"{url}/test/frame?pan={b}", "POST", frame(b, [{"bearing": b, "close": True}]), "image/png")
            elif phase == "night":  # every head down
                http(url + "/test/table", "POST", {"faces": [{**f, "pose": "down"} for f in FIVE]})
            elif phase in ("day", "vote"):
                http(url + "/test/table", "POST", {"faces": FIVE})
        if state.get("over"):
            break
        s = said()
        if len(s) > answered:
            answered = len(s)
            last = s[-1]
            if last == lines.MAFIA_WHISPER:
                http(url + "/test/hear", "POST", {"text": "player five"})
            elif last == lines.DOCTOR_WHISPER:
                http(url + "/test/hear", "POST", {"text": "player one"})
            elif re.fullmatch(r"Player \w+, who\?", last or ""):
                http(url + "/test/hear", "POST", {"text": "player two"})
    for _ in range(30):  # the ceremony after the game ends
        http(url + "/test/advance", "POST", {"seconds": 1})
    record = [[c["tool"], {**c["args"], **({"archive_path": os.path.basename(c["args"]["archive_path"])} if "archive_path" in c["args"] else {})}, c.get("error"), c.get("line")] for c in http(fake + "/mock/calls")]
    return {"state": http(url + "/test/state"), "said": said(), "record": record, "seconds": round(time.monotonic() - t0, 1)}

def main():
    mode, out = sys.argv[1], sys.argv[2]
    pi = sys.argv[sys.argv.index("--pi") + 1] if "--pi" in sys.argv else "qnxuser@172.20.10.14"
    mac = sys.argv[sys.argv.index("--mac-ip") + 1] if "--mac-ip" in sys.argv else "172.20.10.13"
    procs = []
    try:
        fake_p, (fake,) = spawn([PY, "test/fake_gateway.py", "--port", "0"], [r"listening on (http://\S+)"], "fake gateway")
        procs.append(fake_p)
        args = [PY, "-m", "brain", "--test", "--gateway", fake + "/mcp", "--port", "0"]
        if mode == "local":
            brain_p, (url,) = spawn(args, [r"listening on (http://\S+)"], "brain")
            procs.append(brain_p)
        else:
            host = "0.0.0.0" if mode == "remote" else "127.0.0.1"
            port = "8090" if mode == "remote" else "0"
            # The Table's token (D85): over the network, the one qnx/deploy.sh carried to the Pi (~/.gm-table-token), so
            # the brain is told to use it too; on loopback, the test brain's fixed one.
            token = keys.read_env().get("GM_TABLE_TOKEN") if mode == "remote" else TEST_TABLE_TOKEN
            if not token:
                sys.exit("pi-game.py: no GM_TABLE_TOKEN in .env.local: start the real brain once with --referee remote, then qnx/deploy.sh")
            brain_p, (table, url) = spawn(args + ["--referee", "remote", "--table-host", host, "--table-port", port, "--table-token", token],
                                          [r"table for the referee at (http://\S+)", r"listening on (http://\S+)"], "brain")
            procs.append(brain_p)
            if mode == "remote":
                table = f"http://{mac}:{port}"
                ssh = ["ssh", "-tt", *os.environ.get("GM_SSH_OPTS", "").split(), pi, f'cd gm && exec python3 -m brain.referee --table {table} --token-file "$HOME/.gm-table-token"']
                ref_p, _ = spawn(ssh, [r"(attached) to the table"], "referee on the Pi", timeout=60)
            else:
                ref_p, _ = spawn([PY, "-S", "-m", "brain.referee", "--table", table, "--token", token], [r"(attached) to the table"], "referee")
            procs.append(ref_p)
            print(f"referee attached ({mode}) to {table}", flush=True)
        result = play(url, fake)
        result["mode"] = mode
        json.dump(result, open(out, "w"), indent=1)
        print(f"{mode}: {len(result['record'])} calls, {len(result['said'])} lines said, {result['seconds']} s real; state {result['state']}")
    finally:
        for p in reversed(procs):
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()

if __name__ == "__main__":
    main()
