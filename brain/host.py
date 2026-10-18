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
the first photo with two. A player can answer it without the camera too: a head tap,
or "show me" (typed, or said in a short listen while nobody leans in) puts the card up
on trust, "got it" moves on, and "pause" or "stop the game" work there as anywhere.

Every listen also takes the host's own commands, then listens again: "pause" (or
"shut up", a bare "stop"), "change your speaker to the Mac" and "say that again".

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
from brain import ears, games, lines, settings, vision
from brain.body import Body, BodyError
from brain.clock import Clock, ClockCancelled, VirtualClock
from brain.games.common import GameStopped
from brain.lobby import Lobby
from brain.table import MOODS, Card

POLL = 0.25  # seconds between photos while a card is owed: well inside D8's one second
SEEN = 1.5  # a card shown this long has been read
LEFT = 1.0  # no close face this long after it has been read: the player leaned back
REPROMPT = 10.0  # ask for the lean-in again (and teach "show me") after this long with nobody close
GIVE_UP = 30.0  # stop waiting for a lean-in after this long
HEAR_AFTER = 4.0  # nobody close this long after the lean-in line: a short listen for "show me"
HEAR_EVERY = 6.0  # and again this often; photos stop while the host listens (one gateway command at a time)
HEAR_SECONDS = 3.0  # each of those listens
TOUCH_EVERY = 1.0  # the head's touch is read this often while no card is up: a tap is "show me"
TRUST = 4.0  # seconds the card stays up on a tap or "show me", the camera or not
SPEAKERS = ("robot", "mac")
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
RECOVERY = "Sorry, I lost my place. Tap my head to start again."
PAUSED_WINDOW = 10.0  # seconds per listen while paused: the robot chimes each time its microphone opens
PAUSED_LEDS = (6, 6, 10)  # the ring while paused
ASLEEP_LEDS = (2, 2, 4)  # the ring while the host naps between games, its microphone off
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
        self.asleep = False  # napping between games: no listening until a tap on the head
        self._paused_for = 0.0  # seconds spent paused, left out of now() so a game's timers stop
        self.last_line: str | None = None  # the game's last line, for "say that again"
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
        self.asleep = False
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
        self.last_line = line
        self._speak(line)

    def _speak(self, line: str) -> None:
        """Say a line; the host's own lines (the pause, the speaker) come here directly,
        so "say that again" still repeats the game's."""
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
        """What the table says in the next `seconds`. The host's own commands are taken
        here and this listen starts over: "pause" holds everything until "resume" or a
        tap on the head, a speaker change moves the voice, "say that again" repeats the
        game's last line."""
        while True:
            text = self._hear(seconds)
            if ears.wants_pause(text) and self._in_game():
                text = self._pause()
                if text:  # "stop the game" or "reset" said while paused: the game hears it
                    return text
            elif not self._command(text):
                return text

    def _in_game(self) -> bool:
        """A game is on (from its count to its end): "pause" holds it. Between games a
        "stop" or "shut up" goes to the lobby, which naps."""
        state = self.state
        return not (state is None or state.get("phase") == "welcome" or state.get("over"))

    def _command(self, text: str) -> bool:
        """A speaker change or "say that again", done; False for anything else."""
        if self._speaker_change(text):
            return True
        if ears.wants_repeat(text) and self.last_line:
            self._speak(self.last_line)
            return True
        return False

    def set_speaker(self, speaker: str) -> None:
        """Where the voice plays from the next line on: "robot", or "mac" (this Mac's
        audio output, the robot moving its mouth); kept with ROB's saved settings."""
        if speaker not in SPEAKERS:
            raise ValueError(f"speaker must be one of {SPEAKERS}")
        self.body.speaker = speaker
        settings.update(speaker=speaker)
        self._log(f"speaker: {speaker}")

    def _speaker_change(self, text: str) -> bool:
        """"Change your speaker to the Mac": the speaker changed and a line through it."""
        speaker = ears.speaker_said(text)
        if speaker is None:
            return False
        self.set_speaker(speaker)
        self._speak(lines.SPEAKER_MAC if speaker == "mac" else lines.SPEAKER_ROBOT)
        return True

    def _pause(self) -> str:
        """Hold until "resume", a head tap or the page's Resume; what was said instead
        when it was a stop or a reset."""
        self._log("paused")
        start = self.clock.now()
        self.paused = True
        if self.dash is not None:
            self.dash.record("game", "paused")
        try:
            self._speak(PAUSED)
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
        self._speak(RESUMED)
        return ""

    def sleep(self, seconds: float) -> str | None:
        """Nap between games, for at most `seconds` a call (the lobby calls again, so a
        referee's call never holds the table for long): the microphone off (no chime
        every few seconds), the ring dim, the head's touch read every TOUCH_EVERY
        seconds. "" for a tap, the line typed on either page, or None when the time ran
        out with neither."""
        self._check_stop()
        if not self.asleep:
            self._log("asleep: a tap on the head wakes me")
            if self.dash is not None:
                self.dash.record("game", "asleep")
            self.body.leds([ASLEEP_LEDS])
            self._listening = False
            self.asleep = True
        start = checked = self.clock.now()
        woke: str | None = None
        while woke is None and self.clock.now() - start < seconds:
            typed = self._take_injected()
            if not typed and self.dash is not None:
                typed = (self.dash.take_typed() or "").lower()  # the game screen's Wake ROB and its buttons
            if typed:
                woke = typed
                break
            self.wait(TOUCH_EVERY)
            now = self.clock.now()
            if self.body.touched(now - checked + 0.5):
                woke = ""
            checked = now
        if woke is None:
            return None
        self.asleep = False
        self._log("awake" + (f" (typed): {woke}" if woke else ": the head was tapped"))
        if self.dash is not None:
            self.dash.record("game", "awake")
        self.body.leds([self.ring])
        return woke

    def _hear(self, seconds: float, typed_too: bool = True) -> str:
        """The robot's microphone for `seconds`, or a line typed on the dashboard. With
        typed_too False (the deal's short listens, which read typed lines on their own)
        only the microphone."""
        self._check_stop()
        self.asleep = False
        self._cue(True)
        typed = self._take_injected() if typed_too else ""
        if typed_too and not typed and self.dash is not None:
            typed = (self.dash.take_typed() or "").lower()  # the operator typed what the table said
            if typed and self.virtual:
                self.clock.sleep(max(0.1, seconds))
        if typed:
            self._heard_typed(typed)
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
        if typed_too:
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
        """The card for `seat` on the private screen; True once it has been read (D7,
        D8). The camera decides as the rules have it, and the player can answer without
        it: a head tap or "show me" puts the card up on trust for TRUST seconds (still
        blanked while two close faces show), "got it" moves on. Each pass reads what was
        typed; with nobody close it reads the head's touch, and now and then listens for
        HEAR_SECONDS. A stop ends the game here (GameStopped), a pause holds it and
        asks for the lean-in again. A typed line not meant for the deal is heard at the
        next listen."""
        manifest = self._wait_for_cards()
        slot = cardset.slot_of(manifest, card)
        self.look(seat)
        self.say(lines.lean_in(seat))
        start = prompted = last_close = touch_checked = self.clock.now()
        next_hear = start + HEAR_AFTER
        showing = False
        shown_for = 0.0
        shown_at = 0.0
        trusted: float | None = None  # the card is up on trust until then
        crowded = False
        blinking_off = False
        held: list[str] = []  # typed lines that were not for the deal

        def show(now: float) -> None:
            nonlocal showing, shown_at, blinking_off
            if not showing:
                if not blinking_off:
                    self.body.blink(False)
                    blinking_off = True
                self._avatar(slot, "card")
                showing, shown_at = True, now

        def hide(now: float) -> None:
            nonlocal showing, shown_for
            if showing:
                self._avatar("off", "off")
                showing, shown_for = False, shown_for + (now - shown_at)

        try:
            while True:
                self._check_stop()
                now = self.clock.now()
                n = len(vision.close(self._look("deal")))
                if trusted is not None and now >= trusted:
                    hide(now)
                    return True
                if n >= 2:
                    last_close = now
                    hide(now)
                    if not crowded:
                        crowded = True
                        self.say(lines.ONE_AT_A_TIME)
                elif n == 1 or trusted is not None:
                    if n == 1:
                        last_close = now
                    crowded = False
                    show(now)
                else:
                    crowded = False
                    hide(now)
                    if shown_for >= SEEN and now - last_close >= LEFT:
                        return True
                    if now - start >= GIVE_UP:
                        return shown_for >= SEEN
                    if shown_for == 0 and now - prompted >= REPROMPT:
                        prompted = now
                        self.say(lines.lean_in_again(seat))
                if trusted is None and now - start >= GIVE_UP + SEEN:  # still reading, or still crowded: enough
                    hide(now)
                    return shown_for >= SEEN
                if n:
                    next_hear = max(next_hear, now + HEAR_AFTER)

                answers = [(text, True) for text in self._typed()]
                if not showing and trusted is None:
                    if now - touch_checked >= TOUCH_EVERY:
                        if self.body.touched(now - touch_checked + 0.5):
                            self._log("head tapped: the card goes up")
                            answers.append(("show me", False))
                        touch_checked = now
                    if n == 0 and now >= next_hear and now + HEAR_SECONDS <= start + GIVE_UP:
                        next_hear = now + HEAR_EVERY
                        try:
                            answers.append((self._hear(HEAR_SECONDS, typed_too=False), False))
                        except BodyError as e:  # the robot dropped off Wi-Fi: the camera carries on
                            self._log(f"listen failed during the deal ({e})")
                        self._cue(False)
                for text, typed in answers:
                    what = self._deal_answer(text)
                    if what is None:
                        if typed:
                            held.append(text)
                        continue
                    if typed:
                        self._heard_typed(text)
                    now = self.clock.now()
                    if what == "stop":
                        raise GameStopped(reset=ears.wants_to_reset(text))
                    if what == "seen":
                        hide(now)
                        return True
                    if what == "show" and trusted is None:
                        trusted = now + TRUST
                        if not crowded:
                            show(now)
                    elif what == "speaker":
                        self._speaker_change(text)
                    elif what == "repeat":
                        self.say(lines.lean_in(seat))
                    elif what == "pause":
                        hide(now)
                        trusted = None
                        stopped = self._pause()
                        if stopped:  # "stop the game" or "reset" said while paused
                            raise GameStopped(reset=ears.wants_to_reset(stopped))
                        self.say(lines.lean_in(seat))
                        start = prompted = last_close = touch_checked = self.clock.now()
                        next_hear = start + HEAR_AFTER
                self.clock.sleep(POLL)
        finally:
            if showing:
                self._avatar("off", "off")
            self._avatar("idle", "idle")
            if blinking_off:
                self.body.blink(True)
            for text in held:  # heard at the next listen, so the game still hears it
                self.inject(text)

    def _deal_answer(self, text: str) -> str | None:
        """What a line heard or typed at the private screen asks of the deal: "stop",
        "pause", "speaker", "repeat", "seen" or "show"; None when it is not for the deal."""
        if not text:
            return None
        if ears.wants_to_stop(text):
            return "stop"
        if ears.wants_pause(text):
            return "pause"
        if ears.speaker_said(text) is not None:
            return "speaker"
        if ears.wants_repeat(text):
            return "repeat"
        if ears.saw_card(text):
            return "seen"
        if ears.wants_card(text):
            return "show"
        return None

    def _typed(self) -> list[str]:
        """Every line typed on the dashboard and not heard yet, each on its own."""
        with self._lock:
            out = list(self._injected)
            self._injected.clear()
        if self.dash is not None:
            while (typed := self.dash.take_typed()) is not None:
                out.append(typed.strip().lower())
        return [t for t in out if t]

    def _heard_typed(self, text: str) -> None:
        self._log(f"heard (dashboard): {text}")
        self._note("heard", text)
        if self.dash is not None:
            self.dash.record("typed", text)

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
        self.asleep = False  # the ring is the mood's again; a nap after this dims it anew
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
