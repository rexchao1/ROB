"""`python -m brain`: the game master's brain in one process.

  python -m brain [--gateway URL] [--pcm URL] [--token T] [--flip-yaw] [--pitch DEG] [--speaker robot|mac]
                  [--hfov DEG] [--day-seconds S] [--voice-dir DIR] [--piper-model ONNX]
                  [--voice piper|eleven] [--eleven-voice ID] [--eleven-model M]
                  [--sets-dir DIR] [--banter URL|none] [--welcome on|off] [--host ADDR] [--port N]
                  [--talk anthropic|gemini|ollama|off] [--talk-model MODEL]
                  [--referee local|remote] [--table-host ADDR] [--table-port N] [--table-token T]
  python -m brain --test --gateway <fake>/mcp --pcm <fake>/pcm [--port 0]

The real loop runs on the wall clock against the stackchan-mcp gateway daemon (MCP at
:8767/mcp, PCM at :8766/pcm by default), speaks with the recorded lines and Piper
behind them, and serves GET /state on --port for watching a game.

--test runs the same host on a virtual clock against test/fake_gateway.py, with the
test voice (each line's text rides in its clip), no banter, a seeded rng, and the
/test/* endpoints (brain/server.py).

--referee remote moves the rules out: the host runs no loop of its own and serves its
Table on --table-port (brain/remote.py) to a referee, `python3 -m brain.referee
--table http://<this machine>:8090` on the QNX Pi, which plays every game through it.
The setup, /state and (under --test) every /test/* endpoint stay here.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import random
import socket
import sys
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path

from brain import games, settings, vision
from brain.banter import Banter, NoBanter
from brain.body import Body, Gateway
from brain.clock import RealClock, VirtualClock
from brain.dash import SETTINGS_FILE, Dash
from brain.host import RECOVERY, Host
from brain.keys import env_file, load_env
from brain.remote import PORT as TABLE_PORT
from brain.remote import TableServer
from brain.server import FakeControl, serve
from brain.talk import DEFAULT_MODELS, Talk
from brain.voice import ELEVEN_MODEL, ELEVEN_VOICE, TestVoice, VoiceError, env, make_voice



ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    load_env()  # the keys set from the dashboard, before the flags read them as defaults
    p = argparse.ArgumentParser(prog="python -m brain")
    p.add_argument("--test", action="store_true", help="test mode: virtual clock, the fake gateway, /test/* endpoints")
    p.add_argument("--gateway", default="http://127.0.0.1:8767/mcp", help="the gateway's MCP endpoint")
    p.add_argument("--pcm", default=None, help="the gateway's PCM endpoint (default: port 8766 on the gateway's host, or the fake's /pcm)")
    p.add_argument("--token", default=os.environ.get("STACKCHAN_TOKEN") or None, help="bearer token (default $STACKCHAN_TOKEN)")
    p.add_argument("--flip-yaw", action="store_true", help="the head turns the other way: negate every yaw")
    p.add_argument("--pitch", type=int, default=25, help="the head's pitch while it works, 5..85, lower looks down (at 45 the camera sees the ceiling; 25 framed a seated player)")
    p.add_argument("--speaker", choices=("robot", "mac"), default=None, help="where the host's voice plays: the robot's speaker, or this Mac's audio output (any speaker connected to it) while the robot moves its mouth (default: the last one picked, else robot)")
    p.add_argument("--hfov", type=float, default=vision.HFOV_DEG, help="the camera's horizontal field of view, degrees")
    p.add_argument("--keep-photos", type=Path, default=None, metavar="DIR", help="save every photo the host takes in DIR, with the faces it found drawn on (named by time, count|deal|night, head angle)")
    p.add_argument("--day-seconds", type=float, default=None, help="Mafia's discussion time (default 120; D18)")
    p.add_argument("--voice-dir", type=Path, default=ROOT / "voice", help="the recorded lines (<sha256>.wav)")
    p.add_argument("--piper-model", type=Path, default=None, help="a Piper voice (.onnx) for the lines not recorded")
    p.add_argument("--voice", choices=("piper", "eleven"), default=None, help="the voice for lines not recorded: eleven (ElevenLabs live, needs ELEVENLABS_API_KEY in the environment or .env.local; the default when the key is there) or piper")
    p.add_argument("--eleven-voice", default=None, metavar="ID", help=f"the ElevenLabs voice id when the personality names none (default $ELEVENLABS_VOICE_ID, else {ELEVEN_VOICE}, \"Chris\")")
    p.add_argument("--eleven-model", default=ELEVEN_MODEL, help=f"the ElevenLabs model (default {ELEVEN_MODEL})")
    p.add_argument("--sets-dir", type=Path, default=None, help="where card sets are written (default .cache/sets)")
    p.add_argument("--banter", default="http://127.0.0.1:11434", help="Ollama's URL for quips, or none")
    p.add_argument("--talk", choices=("anthropic", "gemini", "ollama", "off"), default=None, help="who writes the host's small talk and quips (brain/talk.py): anthropic needs ANTHROPIC_API_KEY, gemini needs GEMINI_API_KEY (environment or .env.local); without a key, scripted lines (default: the last one picked, else anthropic)")
    p.add_argument("--talk-model", default=None, metavar="MODEL", help=f"the talk model (defaults: {', '.join(f'{k} {v}' for k, v in DEFAULT_MODELS.items())}; claude-sonnet-5-5 also works)")
    p.add_argument("--welcome", choices=("on", "off"), default="on", help="greet and count the table when the host starts (D38; test mode: only when a reset asks)")
    p.add_argument("--seed", type=int, default=None, help="the rng's seed (test mode: 0)")
    p.add_argument("--host", default="127.0.0.1", help="address to bind (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=8080, help="port to bind; 0 picks a free one (default 8080)")
    p.add_argument("--referee", choices=("local", "remote"), default="local", help="where the rules run: here (local), or a referee over the Table (remote)")
    p.add_argument("--table-host", default=None, help="address the Table binds for the referee (default 127.0.0.1 under --test, else 0.0.0.0)")
    p.add_argument("--table-port", type=int, default=TABLE_PORT, help=f"the Table's port; 0 picks a free one (default {TABLE_PORT})")
    p.add_argument("--table-token", default=os.environ.get("GM_TABLE_TOKEN") or None, help="token the referee must send (default $GM_TABLE_TOKEN)")
    args = p.parse_args(argv)

    options = games.Options() if args.day_seconds is None else games.Options(day_seconds=args.day_seconds)
    if args.test:
        return _test(args, options)

    rob_file = ROOT / "gamemaster.rob.json"
    settings.load(rob_file)  # ROB's picks as last made (personality, voice, talk, speaker); a flag given overrides one
    saved = _saved(rob_file)
    if args.speaker:
        settings.update(speaker=args.speaker)
    pcm = args.pcm or _pcm_beside(args.gateway)
    gateway = Gateway(args.gateway, token=args.token)
    body = Body(gateway, pcm, token=args.token, flip_yaw=args.flip_yaw, pitch=args.pitch, speaker=settings.current.speaker or "robot")

    try:
        eleven_key = env("ELEVENLABS_API_KEY")
        if args.voice or "voice" not in saved:
            settings.update(voice=args.voice or ("eleven" if eleven_key else "piper"))
        voice = make_voice(
            args.voice_dir if args.voice_dir.is_dir() else None,
            args.piper_model,
            eleven_key=eleven_key,
            eleven_voice=args.eleven_voice or env("ELEVENLABS_VOICE_ID") or ELEVEN_VOICE,
            eleven_model=args.eleven_model,
        )
        if settings.current.voice == "eleven" and not eleven_key:
            print("python -m brain: --voice eleven needs ELEVENLABS_API_KEY; Piper speaks instead", file=sys.stderr)
    except VoiceError as e:
        print(f"python -m brain: {e}", file=sys.stderr)
        return 2
    banter = NoBanter() if args.banter == "none" else Banter(args.banter)
    if isinstance(banter, Banter):
        threading.Thread(target=banter.warm, name="banter-warm", daemon=True).start()
    if args.talk or args.talk_model:  # a model given alone keeps the provider; a provider alone takes its default model
        settings.update(talk=args.talk or settings.current.talk, talk_model=args.talk_model)
    talk = Talk(args.banter if args.banter != "none" else "http://127.0.0.1:11434")  # reads brain.settings at each call
    seed = args.seed if args.seed is not None else random.randrange(1 << 30)
    host = Host(
        body,
        RealClock(),
        voice,
        banter,
        sets_dir=args.sets_dir or ROOT / ".cache" / "sets",
        rng=random.Random(seed),
        options=options,
        hfov=args.hfov,
        keep_photos=args.keep_photos,
        welcome=args.welcome == "on",
        talk=talk,
    )
    Dash(host, mode="real", referee=args.referee, settings_path=SETTINGS_FILE, keys_path=env_file()).load()
    if args.referee == "remote":
        table = TableServer(
            host, host.clock, args.table_host or "0.0.0.0", args.table_port, args.table_token,
            setup=host._setup, rigs=_rigs(host), hello=_hello(host, args.seed),  # noqa: SLF001
        ).start()
        print(f"gamemaster: table for the referee at {_reachable(table)}", flush=True)
    server = serve(host, args.host, args.port)
    print(f"gamemaster: listening on http://{args.host}:{server.server_address[1]} (gateway {args.gateway}, pcm {pcm})", flush=True)
    dashboard_url = _dashboard_url(args.host, server.server_address[1])
    print(f"gamemaster: dashboard at {dashboard_url}"
          + ("" if args.host == "0.0.0.0" else " (this Mac only; --host 0.0.0.0 opens it to phones on the network)"), flush=True)
    if args.referee == "local":
        host.start()
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


@dataclass
class TestBrain:
    """A brain in test mode: its server (not yet serving), host, clock and reset."""

    __test__ = False  # not a pytest class

    server: ThreadingHTTPServer
    host: Host
    clock: VirtualClock
    reset: Callable[..., None]  # reset(welcome=False)
    table: TableServer | None = None  # --referee remote: the Table the referee plays through

    @property
    def url(self) -> str:
        return f"http://{self.server.server_address[0]}:{self.server.server_address[1]}"


def make_test_brain(
    gateway: str,
    pcm: str | None = None,
    *,
    address: str = "127.0.0.1",
    port: int = 0,
    sets_dir: Path | None = None,
    seed: int = 0,
    hfov: float = vision.HFOV_DEG,
    options: games.Options | None = None,
    referee: str = "local",
    table_address: str = "127.0.0.1",
    table_port: int = 0,
    table_token: str | None = None,
) -> TestBrain:
    """Build the test-mode brain against the fake gateway at `gateway` (its /mcp URL) and
    start the host's loop; the caller runs server.serve_forever(). With referee="remote"
    the host runs no loop: its Table is served (and started) for a referee instead, and
    a reset starts that over."""
    base = gateway.rsplit("/", 1)[0]
    body = Body(Gateway(gateway), pcm or base + "/pcm")
    clock = VirtualClock()
    host = Host(
        body,
        clock,
        TestVoice(),
        NoBanter(),
        sets_dir=sets_dir or Path(tempfile.mkdtemp(prefix="gamemaster-sets-")),
        rng=random.Random(seed),
        options=options or games.Options(),
        hfov=hfov,
    )
    Dash(host, mode="test", referee=referee)  # no settings file: a test never reads or writes the operator's
    fake = FakeControl(base)
    resetting = threading.Lock()

    def wipe() -> None:
        status, answer = fake.post("/mock/reset", b"", "application/json")
        if status != 200:
            raise RuntimeError(f"the fake gateway did not reset: {answer}")
        clock.reset()
        host.clear()
        host.rng.seed(seed)

    if referee == "remote":
        table = TableServer(
            host, clock, table_address, table_port, table_token,
            setup=host._setup, rigs=_rigs(host), hello=_hello(host, seed, test=True),  # noqa: SLF001
        )

        def reset_remote(welcome: bool = False) -> None:
            with resetting:
                host.welcome_at_start = welcome  # the referee's next hello carries it
                table.reset(wipe)
                clock.settle()

        server = serve(host, address, port, fake=fake, reset=reset_remote)
        table.start()
        return TestBrain(server, host, clock, reset_remote, table)

    def reset(welcome: bool = False) -> None:
        with resetting:
            host.stop()
            wipe()
            host.welcome_at_start = welcome
            host.start()
            clock.settle()

    server = serve(host, address, port, fake=fake, reset=reset)
    host.start()
    return TestBrain(server, host, clock, reset)


def _rigs(host: Host) -> Callable[[str], dict | None]:
    def take(game: str) -> dict | None:
        with host._lock:  # noqa: SLF001 - as the host's own loop takes it
            return host.rigs.pop(game, None)

    return take


def _hello(host: Host, seed: int | None, test: bool = False) -> Callable[[], dict]:
    """What the referee needs from here, at each hello: the games' options, the idle
    loop's listening window, the recovery line, the seed (if one was given), and whether
    a fresh table starts with the welcome."""
    return lambda: {
        "options": dataclasses.asdict(host.options),
        "listen_window": host.listen_window,
        "recovery": RECOVERY,
        "seed": seed,
        "test": test,
        "welcome": host.welcome_at_start,
    }


def _dashboard_url(address: str, port: int) -> str:
    """The dashboard as a phone on the same network would open it."""
    if address == "0.0.0.0":
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("192.0.2.1", 9))  # no packet is sent: this only picks the route
                address = s.getsockname()[0]
        except OSError:
            pass
    return f"http://{address}:{port}/dash"


def _reachable(table: TableServer) -> str:
    """The Table's URL as a referee elsewhere would call it: bound to every address, the
    address of the interface that routes off this machine."""
    host, port = table.address
    if host == "0.0.0.0":
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("192.0.2.1", 9))  # no packet is sent: this only picks the route
                host = s.getsockname()[0]
        except OSError:
            pass
    return f"http://{host}:{port}"


def _test(args: argparse.Namespace, options: games.Options) -> int:
    brain = make_test_brain(
        args.gateway, args.pcm, address=args.host, port=args.port, sets_dir=args.sets_dir,
        seed=args.seed if args.seed is not None else 0, hfov=args.hfov, options=options,
        referee=args.referee, table_address=args.table_host or "127.0.0.1", table_port=args.table_port,
        table_token=args.table_token,
    )
    if brain.table is not None:
        print(f"gamemaster: table for the referee at {_reachable(brain.table)}", flush=True)
    print(f"gamemaster: listening on {brain.url} (test mode, gateway {args.gateway})", flush=True)
    try:
        brain.server.serve_forever(poll_interval=0.05)
    except KeyboardInterrupt:
        pass
    finally:
        brain.server.server_close()
    return 0


def _saved(path: Path) -> set[str]:
    """The settings ROB's file holds, so a default does not replace a pick."""
    try:
        saved = json.loads(path.read_text())
    except (OSError, ValueError):
        return set()
    return set(saved) if isinstance(saved, dict) else set()


def _pcm_beside(mcp_url: str) -> str:
    """The real gateway serves PCM on its capture port, 8766, on the same host."""
    from urllib.parse import urlsplit

    u = urlsplit(mcp_url)
    return f"{u.scheme}://{u.hostname}:8766/pcm"


if __name__ == "__main__":
    sys.exit(main())
