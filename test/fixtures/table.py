"""The synthetic table: what the host's camera sees at a given pan angle.

render(pan, faces) draws one 640x480 BGR frame, the size the body streams, of a
table seen from the host in the middle. Each Face sits at a known bearing (degrees,
in the same frame as POST /turn {deg}: 0 straight ahead, positive clockwise, i.e.
to the host's right) and is drawn either frontal (eyes, nose, mouth, looking at
the host) or down (the top of a head, no face showing). One face may be close: a
player leaning in to the host's screen, drawn several times wider and lower in
the frame.

A face is in the frame when its bearing is within half the field of view of the
pan; its x position is the pinhole projection of the bearing difference. The
drawing is deterministic (no randomness), so a frame is a pure function of its
arguments, and the vision code (P1) runs on it for real.

boxes(pan, faces) is the fixture's own ground truth (where it drew each face), for
the fixture's unit tests and for step bindings that need to say "the face at
seat three". The brain never sees it; it sees only the pixels.

CLI (writes PNG):

  table.py --pan=0 --face=-40:frontal --face=0:down --face=35:frontal:close [--out F]
  table.py --pans=-90,-60,-30,0,30,60,90 --face=... --out-dir DIR   # DIR/pan<deg>.png

Without --out (single pan) the PNG goes to stdout. Write negative values with "=",
as above, or argparse reads them as options.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

WIDTH, HEIGHT = 640, 480
HFOV_DEG = 60.0  # the body's camera, horizontally (a placeholder until P3 measures the CoreS3's)
FOCAL_PX = (WIDTH / 2) / math.tan(math.radians(HFOV_DEG / 2))

FACE_W = 64  # a seated player's face at about a metre
CLOSE_W = 240  # a player leaning in to the host's screen
POSES = ("frontal", "down")

_SKIN = [(140, 180, 225), (100, 140, 190), (80, 110, 160), (160, 195, 235), (70, 95, 135), (120, 160, 210)]
_HAIR = [(30, 30, 40), (40, 60, 90), (20, 20, 20), (60, 90, 140), (35, 35, 35), (50, 50, 70)]
_SHIRT = [(180, 80, 40), (60, 140, 60), (40, 60, 170), (150, 150, 40), (130, 50, 130), (90, 90, 90)]


@dataclass(frozen=True)
class Face:
    bearing: float
    pose: str = "frontal"
    close: bool = False

    def __post_init__(self) -> None:
        if self.pose not in POSES:
            raise ValueError(f"pose must be one of {POSES}, not {self.pose!r}")
        if not math.isfinite(self.bearing):
            raise ValueError("bearing must be finite")


@dataclass(frozen=True)
class Box:
    """Where a face was drawn: index into the faces list, and its box in pixels."""

    index: int
    face: Face
    x: int
    y: int
    w: int
    h: int


def _wrap(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


def _geometry(face: Face, pan: float) -> tuple[int, int, int, int] | None:
    """The face's centre and size in the frame at this pan, or None outside the field of view."""
    off = _wrap(face.bearing - pan)
    if abs(off) >= HFOV_DEG / 2:
        return None
    cx = int(round(WIDTH / 2 + FOCAL_PX * math.tan(math.radians(off))))
    w = CLOSE_W if face.close else FACE_W
    return cx, (300 if face.close else 190), w, int(w * 1.3)


def boxes(pan: float, faces: list[Face]) -> list[Box]:
    """The faces in view at this pan, with the box each is drawn in (clipped to the frame)."""
    out = []
    for i, face in enumerate(faces):
        g = _geometry(face, pan)
        if g is None:
            continue
        cx, cy, w, h = g
        x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
        x1, y1 = min(WIDTH, x0 + w), min(HEIGHT, y0 + h)
        x0, y0 = max(0, x0), max(0, y0)
        if x1 - x0 < w // 3:
            continue  # less than a third of the face is in the frame: not a face to find
        out.append(Box(i, face, x0, y0, x1 - x0, y1 - y0))
    return out


def _background() -> np.ndarray:
    img = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    for y in range(HEIGHT):
        if y < 260:
            v = 200 - y // 6
            img[y, :] = (v - 10, v, v + 5)  # a wall, lit from above
        else:
            img[y, :] = (40, 70, 110)  # the table top
    cv2.line(img, (0, 260), (WIDTH, 260), (30, 50, 80), 3)
    return img


def _draw(img: np.ndarray, i: int, face: Face, pan: float) -> None:
    g = _geometry(face, pan)
    assert g is not None
    cx, cy, w, h = g
    skin, hair, shirt = _SKIN[i % len(_SKIN)], _HAIR[i % len(_HAIR)], _SHIRT[i % len(_SHIRT)]

    # Shoulders under the head.
    sw = int(w * 2.2)
    top = cy + h // 2 - w // 10
    cv2.ellipse(img, (cx, top + w), (sw // 2, w), 0, 180, 360, shirt, -1, cv2.LINE_AA)
    cv2.rectangle(img, (cx - sw // 2, top + w), (cx + sw // 2, HEIGHT), shirt, -1)

    if face.pose == "down":
        # Head bowed toward the table: the crown of the head and a sliver of neck.
        cv2.ellipse(img, (cx, cy + h // 6), (w // 2, int(h * 0.42)), 0, 0, 360, hair, -1, cv2.LINE_AA)
        cv2.ellipse(img, (cx, cy + h // 2), (w // 4, h // 10), 0, 0, 180, skin, -1, cv2.LINE_AA)
        return

    # Frontal: a face looking at the host.
    cv2.ellipse(img, (cx, cy), (w // 2, h // 2), 0, 0, 360, skin, -1, cv2.LINE_AA)
    cv2.ellipse(img, (cx, cy - h // 4), (w // 2 + 2, h // 4), 0, 180, 360, hair, -1, cv2.LINE_AA)
    ey = cy - h // 10
    for side in (-1, 1):
        ex = cx + side * w // 5
        cv2.ellipse(img, (ex, ey), (max(2, w // 10), max(1, w // 16)), 0, 0, 360, (245, 245, 245), -1, cv2.LINE_AA)
        cv2.circle(img, (ex, ey), max(1, w // 22), (40, 30, 20), -1, cv2.LINE_AA)
        cv2.line(img, (ex - w // 9, ey - w // 7), (ex + w // 9, ey - w // 7), hair, max(1, w // 30), cv2.LINE_AA)
    nose = (int(skin[0] * 0.8), int(skin[1] * 0.8), int(skin[2] * 0.8))
    cv2.line(img, (cx, ey + w // 12), (cx - w // 20, cy + h // 8), nose, max(1, w // 30), cv2.LINE_AA)
    cv2.ellipse(img, (cx, cy + h // 4 - h // 20), (w // 6, max(1, h // 22)), 0, 0, 180, (60, 60, 150), max(1, w // 25), cv2.LINE_AA)


def render(pan: float, faces: list[Face]) -> np.ndarray:
    """One BGR frame, 640x480, of the table seen at this pan."""
    if not math.isfinite(pan):
        raise ValueError("pan must be finite")
    img = _background()
    shown = {b.index for b in boxes(pan, faces)}
    for i in sorted(shown, key=lambda i: faces[i].close):  # close faces in front
        _draw(img, i, faces[i], pan)
    return img


def png(pan: float, faces: list[Face]) -> bytes:
    ok, data = cv2.imencode(".png", render(pan, faces))
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return data.tobytes()


def parse_face(spec: str) -> Face:
    """BEARING[:POSE[:close]], e.g. "-40", "0:down", "35:frontal:close"."""
    parts = spec.split(":")
    if not 1 <= len(parts) <= 3 or (len(parts) == 3 and parts[2] != "close"):
        raise ValueError(f"face spec is BEARING[:frontal|down[:close]], not {spec!r}")
    return Face(float(parts[0]), parts[1] if len(parts) > 1 else "frontal", len(parts) == 3)


def _fmt(deg: float) -> str:
    return str(int(deg)) if float(deg).is_integer() else str(deg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="table.py", description=__doc__.split("\n\n")[0])
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--pan", type=float, help="one pan angle; PNG to --out or stdout")
    where.add_argument("--pans", help="comma-separated pan angles; one PNG each into --out-dir")
    parser.add_argument("--face", action="append", default=[], help="BEARING[:frontal|down[:close]] (repeatable)")
    parser.add_argument("--out", type=Path, help="with --pan: the PNG file (default stdout)")
    parser.add_argument("--out-dir", type=Path, help="with --pans: the directory for pan<deg>.png")
    args = parser.parse_args(argv)
    try:
        faces = [parse_face(s) for s in args.face]
    except ValueError as e:
        parser.error(str(e))
    if args.pan is not None:
        data = png(args.pan, faces)
        if args.out:
            args.out.write_bytes(data)
        else:
            sys.stdout.buffer.write(data)
        return 0
    if not args.out_dir:
        parser.error("--pans needs --out-dir")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for pan in (float(p) for p in args.pans.split(",") if p.strip()):
        (args.out_dir / f"pan{_fmt(pan)}.png").write_bytes(png(pan, faces))
    return 0


if __name__ == "__main__":
    sys.exit(main())
