"""The operator dashboard's state and logic, served by brain/server.py under /dash.

The host records into a Dash when one is attached (Host.dash): every line it says,
every listen that heard something, its log, and every photo it takes. The operator
reads that back (events, the latest photo with its faces, the reported state) and
feeds the host the way a voice would: typed hearing is a queue that the host's next
listen drains before it asks the microphone, so the rules see the same text either
way.

Settings are the tuning numbers that were module constants and flags (the head's
pitch, the field of view, the face score floor, the close-face width, the listening
window, the games' timings, quips on or off). Applying one sets the live value; in
real mode the values and any edited content (Imposter words, Wavelength spectrums) are
saved to gamemaster.settings.json beside package.json and read at the next start. A
test-mode Dash has no file: tests never read or write the operator's settings.

The robot's face, mirrored: the host tells the Dash when it speaks (and the line),
its mood and the base ring's colour, and whether the screen shows a card, is blanked
or shows the host's face; the speaker's volume is read from the gateway once at start
(best effort, on its own thread) and set live (never saved: it is the device's own).

The seats' faces: the photos of a counting sweep are kept, and after host.count() a
worker thread of the Dash crops each seat's best sighting and reads its colours for an
avatar (brain/portraits.py), so the sweep is not slowed. The crops live in memory only,
replaced at the next count and dropped by host.clear(); they never leave this machine
except to the dashboard's page.
"""

from __future__ import annotations

import dataclasses
import json
import queue
import threading
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from brain import cards as cardset
from brain import lines, portraits, vision
from brain.dashboard import LABELS, SPOKEN
from brain.games import GAMES
from brain.banter import NoBanter
from brain.body import BodyError
from brain.host import MOOD_LEDS
from brain.keys import Keys

if TYPE_CHECKING:
    from brain.host import Host

RING = 500  # events kept
SETTINGS_FILE = Path(__file__).resolve().parent.parent / "gamemaster.settings.json"
VOLUME_RETRY = 30.0  # seconds between tries at reading the volume while it is unknown
ROBOT_FACES = ("idle", "card", "off")
SWEEP_MAX = 64  # photos kept from one counting sweep (it takes 7 to 19)


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


# The host's own face as cards.py draws it on the robot's screen, for the page to draw the same.
FACE_STYLE = {"bg": _hex(cardset.FACE_BG), "ink": _hex(cardset.FACE_INK), "cheek": _hex(cardset.FACE_CHEEK), "mouth": _hex(cardset.FACE_MOUTH)}


class DashError(ValueError):
    """A request the dashboard cannot apply (a bad value, a bad shape); answered 400."""


@dataclasses.dataclass(frozen=True)
class Setting:
    key: str
    label: str
    group: str
    kind: str  # "number" or "bool"
    min: float | None = None
    max: float | None = None
    step: float | None = None
    unit: str = ""
    help: str = ""


SCHEMA: tuple[Setting, ...] = (
    Setting("pitch", "Head pitch", "Head", "number", 5, 85, 1, "deg", "Lower looks down; 25 framed a seated player."),
    Setting("hfov", "Field of view", "Camera", "number", 20, 120, 1, "deg", "The camera's horizontal field of view."),
    Setting(
        "sweep_step", "Scan step", "Camera", "number", 10, 45, 1, "\u00b0",
        "Degrees the head turns between photos while counting; the scan takes 180 / step + 1 photos. "
        "Above half the field of view a seat may be seen in only one photo and missed.",
    ),
    Setting(
        "sweep_speed", "Scan speed", "Camera", "number", 10, 90, 1, "deg/s",
        "How fast the head turns between photos while counting. Faster finishes sooner; "
        "if counts start missing people, slow it down.",
    ),
    Setting("score_min", "Face score floor", "Camera", "number", 0.3, 0.99, 0.01, "", "A face scoring below this is not a face."),
    Setting("close_width", "Close-face width", "Camera", "number", 0.05, 0.6, 0.01, "of frame", "A face this wide is leaning in to the screen."),
    Setting("listen_window", "Idle listen window", "Voice", "number", 1, 15, 0.5, "s", "How long each idle listen waits for a game's name."),
    Setting("day_seconds", "Mafia discussion", "Timing", "number", 10, 300, 5, "s", "The day's discussion time."),
    Setting("vote_seconds", "Vote listen", "Timing", "number", 1, 20, 0.5, "s", "One player's vote."),
    Setting("whisper_seconds", "Night whisper", "Timing", "number", 1, 20, 0.5, "s", "A night whisper."),
    Setting("clue_seconds", "Clue listen", "Timing", "number", 1, 20, 0.5, "s", "One clue in Imposter and Wavelength."),
    Setting("banter", "Quips", "Voice", "bool", help="The host's short in-character quips."),
)
_BY_KEY = {s.key: s for s in SCHEMA}
_OPTIONS = ("day_seconds", "vote_seconds", "whisper_seconds", "clue_seconds")


@dataclasses.dataclass
class Photo:
    id: int
    t: float
    yaw: float
    frame: np.ndarray
    faces: list[vision.Face]


class Dash:
    def __init__(
        self, host: Host, *, mode: str, referee: str, settings_path: Path | None = None, keys_path: Path | None = None
    ) -> None:
        self.host = host
        self.mode = mode
        self.referee = referee
        self.settings_path = settings_path
        self._lock = threading.Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=RING)
        self._next = 1
        self._typed: deque[str] = deque()
        self._photo: Photo | None = None
        self._photos = 0
        self._banter = host.banter  # the original, swapped back in when quips are turned on
        self._banter_on = not isinstance(host.banter, NoBanter)
        self._content_edited = False
        self.keys = Keys(keys_path, apply=self._apply_key)
        # The robot as the page mirrors it.
        self._robot: dict[str, Any] = {
            "face": "idle", "mood": "idle", "led": list(MOOD_LEDS["idle"]), "speaking": False, "line": None, "speaking_since": None,
        }
        self._speech = 0  # the token of the line being spoken
        self._volume: int | None = None
        self._volume_reading = False
        self._volume_tried = 0.0
        # The seats' faces: the counting sweep's photos, then the worker's crops and avatars.
        self._sweep: list[tuple[np.ndarray, list[vision.Face], float]] | None = None
        self._count_id = 0  # one per count, never reset: the avatars' seeds
        self._crops: dict[int, bytes] = {}
        self._avatars: dict[int, dict[str, Any]] = {}
        self._jobs: queue.Queue[tuple[int, list[tuple[np.ndarray, list[vision.Face], float]], list[float], float]] = queue.Queue()
        threading.Thread(target=self._portrait_worker, name="dash-portraits", daemon=True).start()
        host.dash = self
        self._read_volume_soon()

    # --- events ------------------------------------------------------------------------

    def record(self, kind: str, text: str) -> None:
        with self._lock:
            self._events.append({"id": self._next, "t": time.time(), "kind": kind, "text": text})
            self._next += 1

    def log(self, msg: str) -> None:
        """The host's log line. Says and hearings are recorded on their own, so their log
        lines are not repeated; a "game:" line is the start of a game."""
        if msg.startswith(("say: ", "heard: ", "heard (dashboard): ")):
            return
        self.record("game" if msg.startswith("game:") else "log", msg)

    def events(self, since: int = 0) -> dict[str, Any]:
        with self._lock:
            return {"next": self._next - 1, "events": [e for e in self._events if e["id"] > since]}  # next: pass back as since

    # --- typed hearing -------------------------------------------------------------

    def hear(self, text: str) -> int:
        """Queue text for the host's next listen; the number now waiting."""
        if not text.strip():
            raise DashError("nothing to hear")
        with self._lock:
            self._typed.append(text.strip())
            return len(self._typed)

    def take_typed(self) -> str | None:
        with self._lock:
            return self._typed.popleft() if self._typed else None

    def game(self, name: str) -> int:
        if name == "stop":
            return self.hear("stop the game")
        if name not in GAMES:
            raise DashError(f"name must be one of {', '.join(GAMES)} or stop")
        return self.hear(f"let's play {SPOKEN.get(name, name)}")

    # --- the camera ----------------------------------------------------------------

    def photo(self, frame: np.ndarray, faces: list[vision.Face], yaw: float) -> None:
        with self._lock:
            self._photos += 1
            self._photo = Photo(self._photos, time.time(), yaw, frame, list(faces))
            if self._sweep is not None and len(self._sweep) < SWEEP_MAX:
                self._sweep.append((frame, list(faces), yaw))

    def photo_info(self) -> dict[str, Any] | None:
        with self._lock:
            p = self._photo
        if p is None:
            return None
        close = set(map(id, vision.close(p.faces)))
        faces = [
            {"cx": f.cx, "cy": f.cy, "w": f.w, "h": f.h, "score": f.score, "close": id(f) in close}
            for f in p.faces
        ]
        return {"id": p.id, "t": p.t, "yaw": p.yaw, "faces": faces}

    def photo_jpeg(self) -> bytes | None:
        """The latest frame with its faces boxed: green when close, white otherwise."""
        with self._lock:
            p = self._photo
        if p is None:
            return None
        image = p.frame.copy()
        fh, fw = image.shape[:2]
        close = set(map(id, vision.close(p.faces)))
        thick = max(1, fw // 320)
        for f in p.faces:
            x0, y0 = int((f.cx - f.w / 2) * fw), int((f.cy - f.h / 2) * fh)
            x1, y1 = int((f.cx + f.w / 2) * fw), int((f.cy + f.h / 2) * fh)
            color = (0, 220, 0) if id(f) in close else (255, 255, 255)
            cv2.rectangle(image, (x0, y0), (x1, y1), color, thick)
            cv2.putText(image, f"{f.score:.2f}", (x0, max(12, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4 * thick, color, thick)
        ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return data.tobytes() if ok else None

    # --- state, voice, head ----------------------------------------------------------

    def state(self) -> dict[str, Any]:
        host = self.host
        with host._lock:  # noqa: SLF001 - the dashboard is the host's operator side
            game = dict(host.state) if host.state is not None else {"game": None}
            seats = list(host.seat_bearings)
        with self._lock:
            pending = len(self._typed)
        return {
            "game": game,
            "games": [{"key": g, "label": LABELS.get(g, g.title())} for g in GAMES],
            "yaw": host.yaw,
            "pitch": host.body.pitch,
            "seats": seats,
            "mode": self.mode,
            "referee": self.referee,
            "photo": self.photo_info(),
            "typed_pending": pending,
            "paused": bool(getattr(host, "paused", False)),
            "asleep": bool(getattr(host, "asleep", False)),
            "robot": self.robot(),
            "face_style": FACE_STYLE,
            "seats_info": self.seats_info(seats),
        }

    def say(self, text: str) -> None:
        """Speak a line now, on its own thread, through the host's voice and body."""
        if not text.strip():
            raise DashError("nothing to say")
        text = text.strip()
        self.record("say", text)

        def speak() -> None:
            token = self.speaking(text)
            try:
                self.host.body.play(self.host.voice.pcm(text))
            except Exception as e:
                self.record("log", f"dash: could not say it: {e}")
            finally:
                self.spoken(token)

        threading.Thread(target=speak, name="dash-say", daemon=True).start()

    def head(self, yaw: Any = None, pitch: Any = None) -> dict[str, float]:
        if yaw is not None:
            yaw = _number(yaw, -90, 90, "yaw")
        if pitch is not None:
            self.host.body.pitch = int(round(_number(pitch, 5, 85, "pitch")))
        target = self.host.yaw if yaw is None else yaw
        self.host.body.turn(target)
        self.host.yaw = target
        return {"yaw": self.host.yaw, "pitch": self.host.body.pitch}

    # --- the robot, mirrored ---------------------------------------------------------

    def speaking(self, line: str) -> int:
        """The robot starts speaking this line; the token to pass to spoken()."""
        with self._lock:
            self._speech += 1
            self._robot.update(speaking=True, line=line, speaking_since=time.time())
            return self._speech

    def spoken(self, token: int) -> None:
        """The line with this token has played; a later line still playing stays."""
        with self._lock:
            if token == self._speech:
                self._robot.update(speaking=False, line=None, speaking_since=None)

    def robot_mood(self, mood: str, led: tuple[int, int, int]) -> None:
        with self._lock:
            self._robot.update(mood=mood, led=[int(c) for c in led])

    def robot_face(self, face: str) -> None:
        """What the screen shows: "idle" (the host's face), "card" or "off" (blanked)."""
        if face not in ROBOT_FACES:
            raise ValueError(f"face must be one of {ROBOT_FACES}")
        with self._lock:
            self._robot["face"] = face

    def robot(self) -> dict[str, Any]:
        self._read_volume_soon()
        with self._lock:
            return {**self._robot, "led": list(self._robot["led"]), "volume": self._volume}

    def _read_volume_soon(self) -> None:
        """Read the speaker's volume from the gateway on a thread, while it is unknown
        (at start, then at most every VOLUME_RETRY seconds)."""
        with self._lock:
            recent = self._volume_tried > 0 and time.monotonic() - self._volume_tried < VOLUME_RETRY
            if self._volume is not None or self._volume_reading or recent:
                return
            self._volume_reading = True
            self._volume_tried = time.monotonic()

        def read() -> None:
            try:
                volume = self.host.body.volume()
            except Exception:
                volume = None
            with self._lock:
                self._volume_reading = False
                if self._volume is None:
                    self._volume = volume

        threading.Thread(target=read, name="dash-volume", daemon=True).start()

    def set_volume(self, volume: Any) -> dict[str, int]:
        """Set the speaker's volume (0..100) on the robot, now; not saved."""
        if isinstance(volume, bool) or not isinstance(volume, (int, float)) or volume != int(volume) or not 0 <= volume <= 100:
            raise DashError("volume must be a whole number from 0 to 100")
        try:
            self.host.body.set_volume(int(volume))
        except BodyError as e:
            raise DashError(f"the robot did not take the volume: {e}") from e
        with self._lock:
            self._volume = int(volume)
        return {"volume": int(volume)}

    # --- the seats' faces ------------------------------------------------------------

    def count_started(self) -> None:
        """A counting sweep begins: keep its photos."""
        with self._lock:
            self._sweep = []

    def count_failed(self) -> None:
        """The sweep stopped part way: its photos are dropped."""
        with self._lock:
            self._sweep = None

    def counted(self, seats: list[float], hfov: float) -> None:
        """The sweep found these seats: the old faces go, and the worker crops the new."""
        with self._lock:
            photos, self._sweep = self._sweep or [], None
            self._count_id += 1
            self._crops, self._avatars = {}, {}
            job = (self._count_id, photos, list(seats), hfov)
        self._jobs.put(job)

    def clear_seats(self) -> None:
        """Forget the seats' faces (host.clear()); a crop still being made is dropped."""
        with self._lock:
            self._sweep = None
            self._count_id += 1
            self._crops, self._avatars = {}, {}

    def _portrait_worker(self) -> None:
        while True:
            count_id, photos, seats, hfov = self._jobs.get()
            try:
                for seat, sighting in sorted(portraits.best_sightings(photos, seats, hfov).items()):
                    with self._lock:
                        if count_id != self._count_id:
                            break  # cleared or counted again meanwhile
                    jpeg = portraits.crop(sighting.frame, sighting.face)
                    if jpeg is None:
                        continue
                    found = portraits.traits(sighting.frame, sighting.face)
                    with self._lock:
                        if count_id != self._count_id:
                            break
                        self._crops[seat] = jpeg
                        self._avatars[seat] = portraits.avatar(seat, count_id, found)
            except Exception as e:  # a bad frame never stops the worker
                self.record("log", f"dash: seat faces failed: {e}")

    def seat_jpeg(self, seat: int) -> bytes | None:
        with self._lock:
            return self._crops.get(seat)

    def seats_info(self, seats: list[float] | None = None) -> list[dict[str, Any]]:
        if seats is None:
            with self.host._lock:  # noqa: SLF001
                seats = list(self.host.seat_bearings)
        with self._lock:
            return [
                {"seat": i, "bearing": b, "face": i in self._crops, "avatar": self._avatars.get(i)}
                for i, b in enumerate(seats, start=1)
            ]

    # --- settings ----------------------------------------------------------------------

    def values(self) -> dict[str, Any]:
        host = self.host
        return {
            "pitch": host.body.pitch,
            "hfov": host.hfov,
            "sweep_step": vision.sweep_step(host.hfov),
            "sweep_speed": host.sweep_speed,
            "score_min": vision.SCORE_MIN,
            "close_width": vision.CLOSE_WIDTH,
            "listen_window": host.listen_window,
            **{k: getattr(host.options, k) for k in _OPTIONS},
            "banter": self._banter_on,
        }

    def settings(self) -> dict[str, Any]:
        return {
            "values": self.values(),
            "schema": [dataclasses.asdict(s) for s in SCHEMA],
            "photos": vision.sweep_photos(self.host.hfov),  # the counting scan's photos, at the current step
        }

    def apply(self, changes: dict[str, Any], save: bool = True) -> dict[str, Any]:
        """Check every change, then apply them all live (and save). Nothing is applied if
        any is bad."""
        checked: dict[str, Any] = {}
        for key, value in changes.items():
            s = _BY_KEY.get(key)
            if s is None:
                raise DashError(f"no setting {key!r}")
            if s.kind == "bool":
                if not isinstance(value, bool):
                    raise DashError(f"{key} must be true or false")
                checked[key] = value
            else:
                assert s.min is not None and s.max is not None
                checked[key] = _number(value, s.min, s.max, key)
        host = self.host
        options: dict[str, float] = {}
        for key, value in checked.items():
            if key == "pitch":
                host.body.pitch = int(round(value))
            elif key == "hfov":
                host.hfov = float(value)
            elif key == "sweep_step":
                vision.SWEEP_STEP_DEG = float(value)
            elif key == "sweep_speed":
                host.sweep_speed = int(round(value))
            elif key == "score_min":
                vision.SCORE_MIN = float(value)
                with vision._lock:  # noqa: SLF001 - the detector was built with the old floor
                    if vision._detector is not None:  # noqa: SLF001
                        vision._detector.setScoreThreshold(float(value))  # noqa: SLF001
            elif key == "close_width":
                vision.CLOSE_WIDTH = float(value)
            elif key == "listen_window":
                host.listen_window = float(value)
            elif key in _OPTIONS:
                options[key] = float(value)
            elif key == "banter":
                self._banter_on = value
                host.banter = self._banter if value else NoBanter()
        if options:
            host.options = dataclasses.replace(host.options, **options)
        if save:
            self.save()
        return self.settings()

    # --- content -----------------------------------------------------------------------

    def content(self) -> dict[str, Any]:
        return {"imposter_words": list(lines.IMPOSTER_WORDS), "spectra": list(lines.SPECTRA)}

    def set_content(self, body: dict[str, Any], save: bool = True) -> dict[str, Any]:
        unknown = set(body) - {"imposter_words", "spectra"}
        if unknown:
            raise DashError(f"no content {sorted(unknown)[0]!r}")
        words = body.get("imposter_words")
        spectra = body.get("spectra")
        if words is not None:
            words = _strings(words, "imposter_words")
        if spectra is not None:
            spectra = _strings(spectra, "spectra")
            if not all(" - " in s for s in spectra):
                raise DashError('each spectrum is "low - high", like "cold - hot"')
        if words is not None:
            lines.IMPOSTER_WORDS = tuple(words)
        if spectra is not None:
            lines.SPECTRA = tuple(spectra)
        self._content_edited = True
        if save:
            self.save()
        return self.content()

    # --- rigs --------------------------------------------------------------------------

    def rigs(self) -> dict[str, Any]:
        with self.host._lock:  # noqa: SLF001
            return dict(self.host.rigs)

    def rig(self, body: dict[str, Any]) -> dict[str, Any]:
        if not all(isinstance(v, dict) for v in body.values()):
            raise DashError('expected {"<game>": {...}}')
        unknown = set(body) - set(GAMES)
        if unknown:
            raise DashError(f"no game {sorted(unknown)[0]!r}")
        with self.host._lock:  # noqa: SLF001
            self.host.rigs.update(body)
        return self.rigs()

    # --- keys ---------------------------------------------------------------------------

    def _apply_key(self, name: str, value: str | None) -> None:
        """A key that can take effect at once does: the gateway's token goes to the body."""
        if name == "STACKCHAN_TOKEN":
            body = self.host.body
            body.token = value
            body.gateway.token = value
        self.record("log", f"{name} {'set' if value else 'cleared'}")  # never the value

    # --- the file ------------------------------------------------------------------------

    def save(self) -> None:
        if self.settings_path is None:
            return
        data: dict[str, Any] = {"values": self.values()}
        if vision.SWEEP_STEP_DEG is None:  # unset follows the field of view; saving it would pin it
            del data["values"]["sweep_step"]
        if self._content_edited:
            data["content"] = self.content()
        tmp = self.settings_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n")
        tmp.replace(self.settings_path)

    def load(self) -> None:
        """Apply the saved settings and content, if there is a file. A bad file is
        logged and left alone; the brain starts on its defaults."""
        if self.settings_path is None or not self.settings_path.exists():
            return
        try:
            data = json.loads(self.settings_path.read_text())
            values = {k: v for k, v in (data.get("values") or {}).items() if k in _BY_KEY}
            self.apply(values, save=False)
            if data.get("content"):
                self.set_content(data["content"], save=False)
            self.record("log", f"settings loaded from {self.settings_path.name}")
        except (OSError, ValueError, AttributeError) as e:
            self.record("log", f"settings not loaded from {self.settings_path}: {e}")
            print(f"gamemaster: settings not loaded from {self.settings_path}: {e}", flush=True)


def _number(value: Any, lo: float, hi: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
        raise DashError(f"{name} must be a number from {lo:g} to {hi:g}")
    return float(value)


def _strings(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(s, str) and s.strip() for s in value):
        raise DashError(f"{name} must be a list of words, at least one")
    return [s.strip() for s in value]
