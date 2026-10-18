"""The host: brain.table.Table made real on the body, the camera, the voice and the clock,
and the loop that waits for someone to name a game and runs it.

The rules (brain/games/) decide everything; this module only does what they ask, as
the body can: it turns the head, takes photos and reads them with brain.vision, puts
cards on the screen (brain.cards) and blanks it, speaks lines (brain.voice, played
through the gateway's /pcm so the head can move while it talks), and listens. Every
wait is on the Clock, so a test runs the whole host on a virtual clock and nothing in
it waits real time.

The private screen (D7, D8) is the one tight loop: a photo every POLL seconds while a
card is owed, the card up only while exactly one close face is in view, blanked at
the first photo with two.

Only "idle" and "off" are ever set as the avatar outside show_private: once a game's
set is loaded, every other face name is one of its cards.

While the host listens the ring shows the "listening" colour, steady across
back-to-back listens, and goes back to the mood's colour when it next speaks or the
mood changes (D43).
"""

from __future__ import annotations

import math
import random
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from brain import cards as cardset
from brain import ears, games, lines, vision
from brain.body import Body, BodyError
from brain.clock import Clock, ClockCancelled, VirtualClock
from brain.lobby import Lobby
from brain.table import MOODS, Card

POLL = 0.25  # seconds between photos while a card is owed: well inside D8's one second
SEEN = 1.5  # a card shown this long has been read
LEFT = 1.0  # no close face this long after it has been read: the player leaned back
REPROMPT = 10.0  # say "Player N, lean in." again after this long with nobody close
GIVE_UP = 30.0  # stop waiting for a lean-in after this long
LISTEN_WINDOW = 4.0  # the idle loop's listening window, waiting for a game's name
MAX_LISTEN = 30.0  # the gateway's longest listen
TURN_RATE = 240.0  # degrees per second at speed "high"
TURN_SETTLE = 0.15  # seconds after the head arrives before a photo is trusted
SWEEP_SPEED = 24  # degrees per second asked of each step of the counting sweep: the firmware eases a 12-degree step over about a third of a second, so the head glides from photo to photo
RETURN_SPEED = 60  # degrees per second back to the middle after the count: about a second, not a snap
PHOTO_TRIES = 3  # a photo that fails (the robot dropped off Wi-Fi for a moment) is tried this often
PHOTO_RETRY_WAIT = 3.0  # seconds between those tries; the robot reconnects on its own
SCAN_ON = (0, 22, 40)  # the ring's colour for the part of the counting sweep done so far
SCAN_SEEN = (0, 90, 30)  # the ring's colour where the sweep saw a face
RING = 12  # LEDs on the ring
RECOVERY = "Sorry, I lost my place. Say a game's name to start again."
PAUSED_WINDOW = 10.0  # seconds per listen while paused: the robot chimes each time its microphone opens
PAUSED_LEDS = (6, 6, 10)  # the ring while paused
PAUSED = "Paused. Say resume or tap my head when you're ready."
RESUMED = "Okay, back to it."


def glide_seconds(travel: float, speed: float) -> float:
    """How long a move_head of `travel` degrees at `speed` degrees per second takes to
    settle on the robot. The firmware (stackchan-mcp 2.2.6, MapDurationToSpringOptions)
    runs every move as a critically damped spring whose stiffness falls as the asked
    duration grows; this is the time to within about 4% of the target, where photos
    measured as sharp as a still head's (2026-10-18)."""
    if travel <= 0:
        return TURN_SETTLE
    duration_ms = max(20.0, travel * 1000.0 / speed)
    s = min(1000.0, max(1.0, 300_000.0 / duration_ms))
    stiffness = 10.0 + (s / 1000.0) ** 2 * 640.0
    return 5.0 / math.sqrt(stiffness)


def _led(yaw: float) -> int:
    """The ring's LED for a head angle: -90 is the first, 90 the last."""
    return round((max(-90.0, min(90.0, yaw)) + 90.0) / 180.0 * (RING - 1))

# The base ring's colour per mood (r, g, b); the face stays the host's own.
MOOD_LEDS: dict[str, tuple[int, int, int]] = {
    "idle": (24, 20, 30),
    "listening": (0, 40, 60),
    "night": (0, 0, 36),
    "day": (70, 45, 10),
    "tense": (90, 0, 0),
    "win": (0, 90, 30),
}


class HostError(Exception):
    """The host could not do what a game asked (the screen would not load, a card unknown)."""


class _Stopped(BaseException):
    """The host is being stopped (a test's reset); unwinds a game without a recovery line."""


class Host:
    def __init__(
        self,
        body: Body,
        clock: Clock,
        voice: Any,
        banter: Any,
        *,
        sets_dir: Path,
        rng: random.Random | None = None,
        options: Any = None,
        hfov: float = vision.HFOV_DEG,
        listen_window: float = LISTEN_WINDOW,
        keep_photos: Path | None = None,
        log: Callable[[str], None] | None = None,
        talk: Any = None,
        welcome: bool = False,
    ) -> None:
        self.body = body
        self.clock = clock
        self.voice = voice
        self.banter = banter
        self.sets_dir = Path(sets_dir)
        self.rng = rng or random.Random()
        self.options = options if options is not None else games.Options()
        self.hfov = hfov
        self.listen_window = listen_window
        self.keep_photos = Path(keep_photos) if keep_photos is not None else None
        if self.keep_photos is not None:
            self.keep_photos.mkdir(parents=True, exist_ok=True)
        self.talk = talk  # brain/talk.py: the lines of chat(); None says nothing extra
        self.welcome_at_start = welcome  # the loop starts with the welcome (D38)
        self.ring = MOOD_LEDS["idle"]
        self._listening = False  # the ring shows "listening" (D43)
        self.virtual = isinstance(clock, VirtualClock)
        self._emit = log or (lambda msg: print(msg, file=sys.stderr, flush=True))
        self.dash: Any = None  # brain.dash.Dash, when the operator's dashboard is attached
        self._lock = threading.Lock()
        self.feed: deque[dict[str, Any]] = deque(maxlen=15)  # the dashboard's last lines heard and said
        self._injected: deque[str] = deque()  # the dashboard's typed lines, heard at the next listen
        self.robot_ok: bool | None = None  # the last listen reached the robot (None: not tried yet)
        self.paused = False  # someone said "pause"; the game waits for "resume" or a head tap
        self._paused_for = 0.0  # seconds spent paused, left out of now() so a game's timers stop
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._started = threading.Event()
        self.clear()

    def clear(self) -> None:
        """Forget the table: seats, the published state, rigs, the loaded cards."""
        with self._lock:
            self.seat_bearings: list[float] = []
            self.state: dict[str, Any] | None = None
            self.rigs: dict[str, dict[str, Any]] = {}
        if self.dash is not None:
            self.dash.clear_seats()
        self.yaw = 0.0
        self._listening = False
        self._manifest: dict[str, Any] | None = None
        self._loaded_path: str | None = None
        self._loading: threading.Thread | None = None
        self._load_error: Exception | None = None

    def _log(self, msg: str) -> None:
        self._emit(msg)
        if self.dash is not None:
            self.dash.log(msg)

    # --- Table: time, voice, ears ------------------------------------------------

    def now(self) -> float:
        """The game's clock: it stops while the game is paused."""
        return self.clock.now() - self._paused_for

    def wait(self, seconds: float) -> None:
        self._check_stop()
        self.clock.sleep(seconds)

    def say(self, line: str) -> None:
        self._check_stop()
        self._log(f"say: {line}")
        self._note("said", line)
        pcm = self.voice.pcm(line)
        self._cue(False)
        if self.dash is None:
            self.body.play(pcm)
            return
        self.dash.record("say", line)
        token = self.dash.speaking(line)
        try:
            self.body.play(pcm)
        finally:
            self.dash.spoken(token)

    def _cue(self, listening: bool) -> None:
        """The ring: "listening" while the host listens, else the mood's colour (D43);
        dim and steady while paused."""
        if self.paused:
            return
        if listening != self._listening:
            self.body.leds([MOOD_LEDS["listening"] if listening else self.ring])
            self._listening = listening

    def inject(self, text: str) -> None:
        """The dashboard: `text` is heard at the next listen, as if someone said it."""
        with self._lock:
            self._injected.append(text.strip().lower())

    def _take_injected(self) -> str:
        with self._lock:
            text = " ".join(self._injected)
            self._injected.clear()
        return text

    def _note(self, kind: str, text: str) -> None:
        with self._lock:
            self.feed.append({"t": time.time(), "kind": kind, "text": text})

    def listen(self, seconds: float) -> str:
        """What the table says in the next `seconds`. "pause" holds everything until
        "resume" or a tap on the head, then this listen starts over."""
        while True:
            text = self._hear(seconds)
            if not ears.wants_pause(text):
                return text
            text = self._pause()
            if text:  # "stop the game" or "reset" said while paused: the game hears it
                return text

    def _pause(self) -> str:
        """Hold until "resume", a head tap or the page's Resume; what was said instead
        when it was a stop or a reset."""
        self._log("paused")
        start = self.clock.now()
        self.paused = True
        if self.dash is not None:
            self.dash.record("game", "paused")
        try:
            self.say(PAUSED)
            self.body.leds([PAUSED_LEDS])
            self._listening = False
            while True:
                checked = self.clock.now()
                text = self._hear(PAUSED_WINDOW)
                if ears.wants_to_stop(text):
                    return text
                if ears.wants_resume(text) or (self.body.touched(self.clock.now() - checked + 1.0)):
                    break
        finally:
            self.paused = False
            self._paused_for += self.clock.now() - start
            self._log("resumed")
            if self.dash is not None:
                self.dash.record("game", "resumed")
        self.body.leds([self.ring])
        self._listening = False
        self.say(RESUMED)
        return ""

    def _hear(self, seconds: float) -> str:
        self._check_stop()
        self._cue(True)
        typed = self._take_injected()
        if not typed and self.dash is not None:
            typed = (self.dash.take_typed() or "").lower()  # the operator typed what the table said
            if typed and self.virtual:
                self.clock.sleep(max(0.1, seconds))
        if typed:
            self._log(f"heard (dashboard): {typed}")
            self._note("heard", typed)
            if self.dash is not None:
                self.dash.record("typed", typed)
            return typed
        heard: list[str] = []
        left = max(0.1, seconds)
        while left > 0:
            chunk = min(MAX_LISTEN, left)
            if self.virtual:
                self.clock.sleep(chunk)  # the window passes on the clock; the fake answers at once
            try:
                heard.append(self.body.listen(chunk))
            except BodyError:
                self.robot_ok = False
                raise
            self.robot_ok = True
            left -= chunk
        heard.append(self._take_injected())  # typed on the dashboard during the window
        text = " ".join(h.strip() for h in heard if h and h.strip()).lower()
        if text:
            self._log(f"heard: {text}")
            self._note("heard", text)
            if self.dash is not None:
                self.dash.record("heard", text)
        return text

    # --- Table: the head and the camera ------------------------------------------

    def _turn(self, yaw: float, speed: int | None = None) -> None:
        """Turn the head and wait until a photo would be sharp: at the body's own (fast)
        speed, or gently at `speed` degrees per second."""
        yaw = max(-90.0, min(90.0, yaw))
        travel = abs(yaw - self.yaw)
        self.body.turn(yaw, speed)
        self.yaw = yaw
        self.clock.sleep(TURN_SETTLE + travel / TURN_RATE if speed is None else glide_seconds(travel, speed))

    def _look(self, kind: str) -> list[vision.Face]:
        """One photo's faces. A failed photo is tried again (PHOTO_TRIES in all) after a
        pause, since the robot drops off Wi-Fi for a few seconds now and then. With
        keep_photos, the photo is saved there with its faces drawn."""
        for attempt in range(PHOTO_TRIES):
            self._check_stop()
            try:
                image = self.body.photo()
                break
            except BodyError as e:
                if attempt + 1 == PHOTO_TRIES:
                    raise
                self._log(f"photo failed ({e}); trying again")
                self.clock.sleep(PHOTO_RETRY_WAIT)
        faces = vision.find_faces(image)
        if self.keep_photos is not None:
            self._keep(image, faces, kind)
        if self.dash is not None:
            self.dash.photo(image, faces, self.yaw)
        return faces

    def _keep(self, image: np.ndarray, faces: list[vision.Face], kind: str) -> None:
        h, w = image.shape[:2]
        out = image.copy()
        for f in faces:
            x0, y0 = int((f.cx - f.w / 2) * w), int((f.cy - f.h / 2) * h)
            x1, y1 = int((f.cx + f.w / 2) * w), int((f.cy + f.h / 2) * h)
            colour = (0, 0, 255) if f.w >= vision.CLOSE_WIDTH else (0, 200, 0)
            cv2.rectangle(out, (x0, y0), (x1, y1), colour, 1)
            cv2.putText(out, f"{f.score:.2f}{'' if f.frontal else ' side'}", (x0, max(10, y0 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, colour, 1)
        now = time.time()
        stamp = time.strftime("%H%M%S", time.localtime(now)) + f"{int(now * 1000) % 1000:03d}"
        assert self.keep_photos is not None
        cv2.imwrite(str(self.keep_photos / f"{stamp}-{kind}-yaw{round(self.yaw):+04d}-{len(faces)}faces.jpg"), out)

    def look(self, seat: int | None) -> None:
        self._check_stop()
        if seat is None:
            self._turn(0.0)
            return
        if not 1 <= seat <= len(self.seat_bearings):
            raise HostError(f"no seat {seat}: the host counted {len(self.seat_bearings)}")
        self._turn(self.seat_bearings[seat - 1])

    def _views(self, pans: list[float]) -> list[tuple[float, list[vision.Face]]]:
        views = []
        for pan in pans:
            self._check_stop()
            self._turn(pan)
            views.append((self.yaw, self._look("night")))
        return views

    def count(self) -> int:
        """The counting sweep (D5): a quick turn to the far left, then small gentle steps
        to the far right with a photo at each, the ring filling in as it goes and
        lighting green where it saw someone, then back to the middle. The dashboard gets
        the sweep's photos and crops each seat's face on its own thread."""
        if self.dash is not None:
            self.dash.count_started()
        try:
            found = self._sweep()
        except BaseException:
            if self.dash is not None:
                self.dash.count_failed()
            raise
        with self._lock:
            self.seat_bearings = found
        if self.dash is not None:
            self.dash.counted(found, self.hfov)
        self._log(f"count: {len(found)} seats at {[round(b, 1) for b in found]}")
        self._turn(0.0, RETURN_SPEED)
        self.body.leds([self.ring])
        return len(found)

    def _sweep(self) -> list[float]:
        pans = vision.sweep_pans(self.hfov)
        half_step = max(b - a for a, b in zip(pans, pans[1:])) / 2
        views: list[tuple[float, list[vision.Face]]] = []
        seen: set[int] = set()
        self._listening = False  # the sweep's ring replaces the cue
        for i, pan in enumerate(pans):
            self._check_stop()
            self._turn(pan, None if i == 0 else SWEEP_SPEED)
            faces = self._look("count")
            views.append((self.yaw, faces))
            for f in faces:
                b = vision.bearing(f, self.yaw, self.hfov)
                if f.w < vision.CLOSE_WIDTH and abs(b - self.yaw) <= half_step + 1:  # near the middle of this view: light it once
                    seen.add(_led(b))
            self.body.leds([SCAN_SEEN if j in seen else SCAN_ON if j <= _led(self.yaw) else (0, 0, 0) for j in range(RING)])
        return vision.seats(views, self.hfov)

    def faces_up(self) -> list[int]:
        if not self.seat_bearings:
            return []
        views = self._views(vision.heads_down_pans(self.seat_bearings, self.hfov))
        up = vision.seats_up(views, self.seat_bearings, self.hfov)
        self._log(f"faces up: {up}")
        return up

    # --- Table: the private screen ------------------------------------------------

    def prepare(self, cards: list[Card]) -> None:
        self._check_stop()
        path = cardset.write_set(list(cards), self.sets_dir)
        manifest = cardset.read_manifest(path)
        if str(path) == self._loaded_path and self._load_error is None:
            self._manifest = manifest
            return
        self._manifest = manifest
        self._load_error = None
        if self.virtual:
            self._load(str(path))  # in order, so a test's record of calls is the same every run
        else:
            self._loading = threading.Thread(target=self._load, args=(str(path),), name="avatar-load", daemon=True)
            self._loading.start()

    def _load(self, path: str) -> None:
        try:
            self.body.load_set(path)
            self._loaded_path = path
            self._log(f"cards loaded: {path}")
        except Exception as e:  # kept for show_private, which retries once
            self._load_error = e
            self._loaded_path = None
            self._log(f"cards failed to load: {e}")

    def show_private(self, seat: int, card: Card) -> bool:
        manifest = self._wait_for_cards()
        slot = cardset.slot_of(manifest, card)
        self.look(seat)
        self.say(lines.lean_in(seat))
        start = self.clock.now()
        prompted = start
        showing = False
        shown_for = 0.0
        shown_at = 0.0
        last_close = start
        crowded = False
        blinking_off = False
        try:
            while True:
                self._check_stop()
                now = self.clock.now()
                n = len(vision.close(self._look("deal")))
                if n == 1:
                    last_close = now
                    crowded = False
                    if not showing:
                        if not blinking_off:
                            self.body.blink(False)
                            blinking_off = True
                        self._avatar(slot, "card")
                        showing, shown_at = True, now
                elif n >= 2:
                    last_close = now
                    if showing:
                        self._avatar("off", "off")
                        showing, shown_for = False, shown_for + (now - shown_at)
                    if not crowded:
                        crowded = True
                        self.say(lines.ONE_AT_A_TIME)
                else:
                    crowded = False
                    if showing:
                        self._avatar("off", "off")
                        showing, shown_for = False, shown_for + (now - shown_at)
                    if shown_for >= SEEN and now - last_close >= LEFT:
                        return True
                    if now - start >= GIVE_UP:
                        return shown_for >= SEEN
                    if shown_for == 0 and now - prompted >= REPROMPT:
                        prompted = now
                        self.say(lines.lean_in(seat))
                if now - start >= GIVE_UP + SEEN:  # still reading, or still crowded: enough
                    if showing:
                        self._avatar("off", "off")
                        showing, shown_for = False, shown_for + (now - shown_at)
                    return shown_for >= SEEN
                self.clock.sleep(POLL)
        finally:
            if showing:
                self._avatar("off", "off")
            self._avatar("idle", "idle")
            if blinking_off:
                self.body.blink(True)

    def _avatar(self, face: str, shown: str) -> None:
        """Put a face on the screen; the dashboard mirrors what it shows (idle, card, off)."""
        self.body.avatar(face)
        if self.dash is not None:
            self.dash.robot_face(shown)

    def _wait_for_cards(self) -> dict[str, Any]:
        if self._manifest is None:
            raise HostError("show_private before prepare")
        if self._loading is not None:
            self._loading.join()
            self._loading = None
        if self._load_error is not None:  # one retry, in line
            path = self._manifest_path()
            self._load_error = None
            self._load(path)
            if self._load_error is not None:
                raise HostError(f"the cards would not load onto the screen: {self._load_error}")
        return self._manifest

    def _manifest_path(self) -> str:
        assert self._manifest is not None
        return str(self.sets_dir.resolve() / f"{self._manifest['sha256'][:12]}.bin")

    # --- Table: looks, state, banter ----------------------------------------------

    def mood(self, name: str) -> None:
        if name not in MOODS:
            raise ValueError(f"mood must be one of {MOODS}")
        self._check_stop()
        self._avatar("idle", "idle")
        self.ring = MOOD_LEDS[name]
        self.body.leds([self.ring])
        self._listening = False
        if self.dash is not None:
            self.dash.robot_mood(name, self.ring)

    def report(self, state: dict[str, Any]) -> None:
        with self._lock:
            self.state = dict(state)

    def quip(self, slot: str, **context: Any) -> None:
        if self.talk is not None and self.talk.active():  # the cloud talk, when it has a key
            try:
                line = self.talk.quip(slot, context)
            except Exception as e:  # decoration only: a failure says nothing
                self._log(f"talk failed: {type(e).__name__}: {e}")
                line = None
        else:
            line = self.banter.line(slot, context)
        if line:
            self.say(line)

    def chat(self, situation: str, heard: str = "", **facts: Any) -> str | None:
        self._check_stop()
        if self.talk is None:
            return None
        try:
            line = self.talk.reply(situation, heard, facts)
        except Exception as e:  # the talk is decoration: a failure is a scripted line
            self._log(f"talk failed: {type(e).__name__}: {e}")
            return None
        if line:
            self._log(f"talk: {line}")
        return line or None

    # --- the loop -------------------------------------------------------------------

    def start(self) -> None:
        """Run the loop on its own worker thread."""
        self._stop.clear()
        self._started.clear()
        self._thread = threading.Thread(target=self._worker, name="host", daemon=True)
        self._thread.start()
        self._started.wait(5)  # registered on the clock, so a settle() right after waits for it

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the loop wherever it is (a test's reset). Virtual clock only."""
        self._stop.set()
        if isinstance(self.clock, VirtualClock) and self._thread is not None:
            self.clock.cancel(self._thread.ident)
        if self._thread is not None:
            self._thread.join(timeout)
            if self._thread.is_alive():
                raise HostError("the host's loop did not stop")
        self._thread = None

    def _worker(self) -> None:
        if isinstance(self.clock, VirtualClock):
            self.clock.register()
        self._started.set()
        try:
            self.run()
        except (_Stopped, ClockCancelled):
            pass
        finally:
            if isinstance(self.clock, VirtualClock):
                self.clock.unregister()

    def run(self) -> None:
        """The welcome (if welcome_at_start), then idle-listen for a game's name, play it,
        go back to idle; forever (brain/lobby.py)."""
        self._setup()
        Lobby(
            self, self.rng, options=self.options, listen_window=self.listen_window, recovery=RECOVERY,
            rigs=self._take_rig, stopped=self._stop.is_set, log=self._log,
        ).run(welcome=self.welcome_at_start)

    def _take_rig(self, game: str) -> dict[str, Any] | None:
        with self._lock:
            return self.rigs.pop(game, None)

    def _setup(self) -> None:
        """Screen on for good, blinking, the idle look; retried until the robot answers."""
        while not self._stop.is_set():
            try:
                self.body.setup()
                self.mood("idle")
                self._turn(0.0)
                return
            except BodyError as e:
                self._log(f"waiting for the robot: {e}")
                self.clock.sleep(3.0)

    def _check_stop(self) -> None:
        if self._stop.is_set():
            raise _Stopped()
