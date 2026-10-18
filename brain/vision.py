"""The host's eyes: faces in a camera frame, and what they mean at the table.

Everything here is a pure function of pixels and pan angles, so the host (brain/host.py)
decides when to look and this module only says what it sees:

- find_faces(image): the faces in one frame, with OpenCV's YuNet detector
  (cv2.FaceDetectorYN, the model in brain/models/). A bowed head shows no face, so it
  is simply not found; that is what the heads-down rule relies on (D9, D10).
- bearing(face, pan): where a face sits, in the same degrees as the head's pan: 0 is
  straight ahead, positive is the host's right, so Player one (on the host's left) has
  the most negative bearing.
- sweep_pans() and seats(views): the counting sweep (D5): the head's stops, then one
  bearing per distinct seated face, left to right. Seat N is seats(...)[N - 1].
- close(faces): the faces leaning in to the private screen (D7, D8).
- heads_down_pans() and seats_up(views, seats): the night sweep (D9 to D11).

YuNet scores a face well only within a band of sizes relative to its input, so
find_faces runs it on the frame at a few widths (the seated faces, about a tenth of
the frame, read best at 320 pixels; a face leaning in, a third of the frame or more,
at 200 or 128), drops what a pass found too small to trust, and merges the rest, one
Face per face.

The numbers below fit the synthetic table (test/fixtures/table.py). The real camera's
field of view, resolution and lens are measured at P3, where HFOV_DEG and CLOSE_WIDTH
are tuned.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

HFOV_DEG: float = 60.0  # the camera's horizontal field of view; matches table.py until P3 measures it
CLOSE_WIDTH: float = 0.25  # a face at least this fraction of the frame's width is close (seated about 0.1, leaning in about 0.37)
SEAT_TOLERANCE_DEG: float = 10.0  # sightings closer than this are one seat; a face up this near a seat is that seat
SCORE_MIN: float = 0.5  # YuNet's confidence floor (the drawn faces score 0.5 to 0.9; real faces score higher)
EDGE_MARGIN_DEG: float = 6.0  # a face this near the frame's edge may be cut off and missed; plan views without relying on it
SWEEP_DEFAULT_DEG: float = 12.0  # the counting sweep's stops are at most this far apart (and a third of the field of view): small steps the head can glide through, and every face in four or five photos
SWEEP_STEP_DEG: float | None = None  # the dashboard's "Scan step" when the operator sets it: the stops' spacing instead of the default

# The widths (pixels) the frame is run at: wider for seated faces, narrower for close ones.
_WIDTHS = (640, 320, 200, 128)
# A detection narrower than this, in the pixels of the pass that found it, is dropped:
# YuNet invents faces in hair and shoulders at that size (a bowed head, seen at 128
# pixels wide, came back as a face).
_MIN_PX = 16
_MERGE_IOU = 0.3
_MODEL = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"


@dataclass(frozen=True)
class Face:
    """One face in a frame. Position and size are fractions of the frame (0..1)."""

    cx: float
    cy: float
    w: float
    h: float
    score: float
    frontal: bool  # facing the host: eyes level and the nose between them


_detector: cv2.FaceDetectorYN | None = None
_lock = threading.Lock()


def _detect(image: np.ndarray, width: int) -> np.ndarray:
    """YuNet on the frame resized to `width`: rows of 15 values (box, five landmarks,
    score) in the original frame's pixels."""
    global _detector
    scale = width / image.shape[1]
    small = image if scale == 1 else cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    h, w = small.shape[:2]
    with _lock:
        if _detector is None:
            if not _MODEL.exists():
                raise FileNotFoundError(f"the face model is missing: {_MODEL}")
            _detector = cv2.FaceDetectorYN.create(str(_MODEL), "", (w, h), SCORE_MIN, 0.3, 5000)
        _detector.setInputSize((w, h))
        _, out = _detector.detect(small)
    if out is None:
        return np.zeros((0, 15), np.float32)
    rows = out[out[:, 2] >= _MIN_PX].copy()
    rows[:, :14] /= scale
    return rows


def _frontal(row: np.ndarray) -> bool:
    """Facing the host, from YuNet's landmarks: the eyes (the person's right eye first,
    on the image's left) roughly level and far enough apart for the face's width, and the
    nose tip between them. A face turned to the side squeezes its eyes together and slides
    its nose toward one of them."""
    bw = float(row[2])
    rx, ry, lx, ly, nx = (float(v) for v in (row[4], row[5], row[6], row[7], row[8]))
    eyes = lx - rx
    if bw <= 0 or eyes < 0.2 * bw:
        return False
    if abs(ly - ry) > 0.35 * eyes:
        return False
    return 0.2 <= (nx - rx) / eyes <= 0.8


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    ax0, ay0, aw, ah = (float(v) for v in a[:4])
    bx0, by0, bw, bh = (float(v) for v in b[:4])
    ix = max(0.0, min(ax0 + aw, bx0 + bw) - max(ax0, bx0))
    iy = max(0.0, min(ay0 + ah, by0 + bh) - max(ay0, by0))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def find_faces(image: np.ndarray) -> list[Face]:
    """The faces in one BGR frame of any size, most confident first. Each face is found
    once, however many of the passes found it."""
    if image is None or image.ndim != 3 or image.shape[2] != 3 or image.shape[0] < 16 or image.shape[1] < 16:
        raise ValueError("find_faces needs a BGR image (height x width x 3)")
    fh, fw = image.shape[:2]
    widths = sorted({min(w, fw) for w in _WIDTHS}, reverse=True)
    rows = [r for width in widths for r in _detect(image, width)]
    rows.sort(key=lambda r: -float(r[14]))
    kept: list[np.ndarray] = []
    for r in rows:
        if all(_iou(r, k) <= _MERGE_IOU for k in kept):
            kept.append(r)
    faces = []
    for r in kept:
        x, y, w, h = (float(v) for v in r[:4])
        faces.append(Face(cx=(x + w / 2) / fw, cy=(y + h / 2) / fh, w=w / fw, h=h / fh, score=float(r[14]), frontal=_frontal(r)))
    return faces


def bearing(face: Face, pan: float, hfov: float = HFOV_DEG) -> float:
    """The face's bearing in degrees: the pan plus the pinhole angle of its centre."""
    off = math.degrees(math.atan((face.cx - 0.5) * 2 * math.tan(math.radians(hfov / 2))))
    return pan + off


def _reach(hfov: float) -> float:
    """How far from the pan a face can sit and still be found reliably."""
    return hfov / 2 - EDGE_MARGIN_DEG


def sweep_pans(hfov: float = HFOV_DEG) -> list[float]:
    """The counting sweep's stops, -90 to 90 inclusive, left to right, evenly spaced and
    at most sweep_step() apart, so a face anywhere in the head's range is well inside at
    least two views."""
    n = sweep_photos(hfov)
    step = 180 / (n - 1)
    return [round(-90 + i * step, 3) for i in range(n)]


def sweep_step(hfov: float = HFOV_DEG) -> float:
    """The most the counting sweep's stops may be apart: SWEEP_STEP_DEG when set, else
    SWEEP_DEFAULT_DEG or a third of the field of view, whichever is smaller."""
    return SWEEP_STEP_DEG if SWEEP_STEP_DEG is not None else min(SWEEP_DEFAULT_DEG, hfov / 3)


def sweep_photos(hfov: float = HFOV_DEG) -> int:
    """How many photos the counting sweep takes."""
    return math.ceil(180 / sweep_step(hfov)) + 1


def seats(views: list[tuple[float, list[Face]]], hfov: float = HFOV_DEG) -> list[float]:
    """One bearing per distinct seated face, left to right, from a sweep's views (pan,
    faces). Close faces are ignored. Sightings within SEAT_TOLERANCE_DEG of each other in
    different views are one seat. A seat needs sightings in two views, or in one when only
    one view had it well inside the frame (the ends of the sweep), so a stray detection in
    a single frame does not become a player."""
    sightings = sorted(
        (bearing(f, pan, hfov), i) for i, (pan, faces) in enumerate(views) for f in faces if f.w < CLOSE_WIDTH
    )
    clusters: list[list[tuple[float, int]]] = []
    for b, view in sightings:
        last = clusters[-1] if clusters else None
        if last is not None:
            mean = sum(s[0] for s in last) / len(last)
            if b - mean <= SEAT_TOLERANCE_DEG and all(v != view for _, v in last):
                last.append((b, view))
                continue
        clusters.append([(b, view)])
    reach = _reach(hfov)
    out = []
    for c in clusters:
        mean = sum(s[0] for s in c) / len(c)
        seen_in = len({v for _, v in c})
        could = sum(1 for pan, _ in views if abs(mean - pan) <= reach)
        if seen_in >= min(2, max(1, could)):
            out.append(mean)
    return out


def close(faces: list[Face]) -> list[Face]:
    """The faces leaning in to the screen: at least CLOSE_WIDTH of the frame wide and
    facing the host."""
    return [f for f in faces if f.w >= CLOSE_WIDTH and f.frontal]


def heads_down_pans(seat_bearings: list[float], hfov: float = HFOV_DEG) -> list[float]:
    """The fewest stops, left to right and within the head's -90..90, that put every seat
    well inside a view."""
    reach = _reach(hfov)
    pans: list[float] = []
    for b in sorted(seat_bearings):
        if pans and abs(b - pans[-1]) <= reach:
            continue
        pans.append(round(min(90.0, max(-90.0, b + reach)), 3))
    return pans


def seats_up(views: list[tuple[float, list[Face]]], seat_bearings: list[float], hfov: float = HFOV_DEG) -> list[int]:
    """The seats (1-based, ascending) with a face up and facing the host in any of the
    views. A face belongs to the nearest seat within SEAT_TOLERANCE_DEG; a face near no
    seat is nobody's."""
    if not seat_bearings:
        return []
    up: set[int] = set()
    for pan, faces in views:
        for f in faces:
            if not f.frontal:
                continue
            b = bearing(f, pan, hfov)
            seat, gap = min(((i + 1, abs(b - s)) for i, s in enumerate(seat_bearings)), key=lambda t: t[1])
            if gap <= SEAT_TOLERANCE_DEG:
                up.add(seat)
    return sorted(up)
