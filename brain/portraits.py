"""A face and an avatar for each seat, from the photos of a counting sweep.

Pure functions of frames and faces; brain/dash.py runs them on its own worker thread
after host.count(), so the sweep is never slowed. Nothing here touches the network:
the crops and the colours stay in the brain's memory and are only served to the
dashboard's page.

- best_sightings(photos, seats, hfov): per seat, the sighting nearest the frame's
  centre among the well-scored ones (a face belongs to the nearest seat within
  vision.SEAT_TOLERANCE_DEG of its bearing).
- crop(frame, face): a square around the face, SIDE_SCALE times its width, clamped
  to the frame, as a SIZE x SIZE JPEG.
- traits(frame, face): the skin tone (the cheeks) and the hair colour (a band above
  the forehead), each snapped to the avatar style's palette.
- avatar(seat, count_id, traits): the dict the page passes to DiceBear.

The avatar style is DiceBear's Lorelei (artwork CC0 1.0 by Lisa Wischofsky; code MIT),
bundled offline at brain/dash/vendor/dicebear.js by `npm run build:avatars`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from brain import vision

SIZE = 160  # the crop's side, pixels
SIDE_SCALE = 1.8  # the crop's side over the face's width
LIFT = 0.1  # the crop's centre sits this many face heights above the face's, to keep the hair
GOOD_SCORE = 0.8  # a sighting within this fraction of the seat's best score is a candidate
STYLE = "lorelei"

# Skin tones and hair colours the avatar is drawn in (hex, no '#'), nearest wins in Lab.
SKIN_TONES = ("ffdbb4", "f1c27d", "e0ac69", "c68642", "8d5524", "5c3a21")
HAIR_COLORS = ("1b1b1b", "3b2a1a", "6a4e35", "a7856a", "d6b370", "b55239", "9e9e9e", "e8e1e1")

DARK_L = 40  # a median Lab lightness (0..255) below this is too dark to read a colour
BLUR_MIN = 4.0  # a face whose Laplacian variance is below this is too blurry to read
SAME_DE = 14.0  # Lab distance under which a pixel above the forehead reads as the skin or the wall, not hair
HAIR_SHARE = 0.15  # hair needs at least this share of the band above the forehead; less is "none"


@dataclass(frozen=True)
class Sighting:
    seat: int  # 1-based
    frame: np.ndarray  # BGR
    face: vision.Face


def best_sightings(
    photos: list[tuple[np.ndarray, list[vision.Face], float]], seats: list[float], hfov: float
) -> dict[int, Sighting]:
    """The best sighting per seat from the sweep's (frame, faces, yaw): of the seated
    faces nearest that seat (within SEAT_TOLERANCE_DEG), the well-scored one nearest
    the frame's centre."""
    found: dict[int, list[Sighting]] = {}
    if not seats:
        return {}
    for frame, faces, yaw in photos:
        for f in faces:
            if f.w >= vision.CLOSE_WIDTH:
                continue
            b = vision.bearing(f, yaw, hfov)
            seat, gap = min(((i + 1, abs(b - s)) for i, s in enumerate(seats)), key=lambda t: t[1])
            if gap <= vision.SEAT_TOLERANCE_DEG:
                found.setdefault(seat, []).append(Sighting(seat, frame, f))
    best: dict[int, Sighting] = {}
    for seat, sightings in found.items():
        top = max(s.face.score for s in sightings)
        good = [s for s in sightings if s.face.score >= GOOD_SCORE * top]
        best[seat] = min(good, key=lambda s: (abs(s.face.cx - 0.5), -s.face.score))
    return best


def _box(frame: np.ndarray, face: vision.Face) -> tuple[float, float, float, float]:
    """The face's box in the frame's pixels: x0, y0, w, h."""
    fh, fw = frame.shape[:2]
    return (face.cx - face.w / 2) * fw, (face.cy - face.h / 2) * fh, face.w * fw, face.h * fh


def crop(frame: np.ndarray, face: vision.Face) -> bytes | None:
    """A SIZE x SIZE JPEG of the face with a margin, the square clamped inside the frame."""
    fh, fw = frame.shape[:2]
    _, _, w, h = _box(frame, face)
    side = int(round(min(max(SIDE_SCALE * w, 16), fw, fh)))
    cx, cy = face.cx * fw, face.cy * fh - LIFT * h
    x0 = int(round(min(max(cx - side / 2, 0), fw - side)))
    y0 = int(round(min(max(cy - side / 2, 0), fh - side)))
    square = frame[y0 : y0 + side, x0 : x0 + side]
    if square.size == 0:
        return None
    interp = cv2.INTER_AREA if side > SIZE else cv2.INTER_CUBIC
    small = cv2.resize(square, (SIZE, SIZE), interpolation=interp)
    ok, data = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return data.tobytes() if ok else None


def _region(frame: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
    """The pixels (n x 3, BGR) of a box, clipped to the frame."""
    fh, fw = frame.shape[:2]
    a, b = int(max(0, round(x0))), int(min(fw, round(x1)))
    c, d = int(max(0, round(y0))), int(min(fh, round(y1)))
    if b <= a or d <= c:
        return np.zeros((0, 3), np.uint8)
    return frame[c:d, a:b].reshape(-1, 3)


def _lab(bgr: np.ndarray) -> np.ndarray:
    """Lab (OpenCV's 8-bit scale) of BGR pixels, n x 3 float."""
    return cv2.cvtColor(bgr.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)


def _median_lab(pixels: np.ndarray) -> np.ndarray | None:
    if len(pixels) < 4:
        return None
    return np.median(_lab(pixels), axis=0)


def _hex_lab(palette: tuple[str, ...]) -> np.ndarray:
    rgb = np.array([[int(h[i : i + 2], 16) for i in (0, 2, 4)] for h in palette], np.uint8)
    return _lab(rgb[:, ::-1])


_SKIN_LAB = _hex_lab(SKIN_TONES)
_HAIR_LAB = _hex_lab(HAIR_COLORS)


def _nearest(lab: np.ndarray, palette: tuple[str, ...], table: np.ndarray) -> str:
    return palette[int(np.argmin(np.linalg.norm(table - lab, axis=1)))]


def traits(frame: np.ndarray, face: vision.Face) -> dict[str, str | None]:
    """{"skin": hex or None, "hair": hex or "none" or None}: None when the face is too
    dark or too blurry to read; hair "none" when the band above the forehead looks like
    the background or the skin (bald, a hat the wall's colour, a face at the top edge)."""
    x0, y0, w, h = _box(frame, face)
    x1 = x0 + w
    gray = cv2.cvtColor(frame[max(0, int(y0)) : int(y0 + h), max(0, int(x0)) : int(x1)], cv2.COLOR_BGR2GRAY)
    if gray.size == 0 or float(cv2.Laplacian(gray, cv2.CV_64F).var()) < BLUR_MIN:
        return {"skin": None, "hair": None}
    cheeks = np.concatenate([
        _region(frame, x0 + 0.15 * w, y0 + 0.5 * h, x0 + 0.35 * w, y0 + 0.7 * h),
        _region(frame, x0 + 0.65 * w, y0 + 0.5 * h, x0 + 0.85 * w, y0 + 0.7 * h),
    ])
    skin = _median_lab(cheeks)
    if skin is None or skin[0] < DARK_L:
        return {"skin": None, "hair": None}
    # The band from above the box's top to the forehead: the detector's box may end at
    # the hairline or inside the hair. Pixels that look like the skin or the wall beside
    # the head are dropped; hair is what is left, when enough is.
    top, bottom = y0 - 0.3 * h, y0 + 0.15 * h
    band = _region(frame, x0 + 0.2 * w, top, x1 - 0.2 * w, bottom)
    background = _median_lab(np.concatenate([
        _region(frame, x0 - 0.7 * w, top, x0 - 0.3 * w, bottom),
        _region(frame, x1 + 0.3 * w, top, x1 + 0.7 * w, bottom),
    ]))
    hair_hex = "none"
    if len(band) >= 4:
        lab = _lab(band)
        keep = np.linalg.norm(lab - skin, axis=1) >= SAME_DE
        if background is not None:
            keep &= np.linalg.norm(lab - background, axis=1) >= SAME_DE
        if keep.sum() >= max(4, HAIR_SHARE * len(lab)):
            hair_hex = _nearest(np.median(lab[keep], axis=0), HAIR_COLORS, _HAIR_LAB)
    return {"skin": _nearest(skin, SKIN_TONES, _SKIN_LAB), "hair": hair_hex}


def seed(seat: int, count_id: int) -> str:
    return f"seat-{seat}-{count_id}"


def avatar(seat: int, count_id: int, found: dict[str, str | None]) -> dict[str, Any]:
    """The avatar for a seat: the style, the seed, the colours read (hex without '#', or
    None / "none"), and `options`, exactly what the page passes to DiceBear:
    createAvatar(style, avatar.options).toString() is the SVG. A colour that could not be
    read is left out of options, and the style's default (Lorelei: white skin, black
    hair) draws it."""
    s = seed(seat, count_id)
    options: dict[str, Any] = {"seed": s}
    if found.get("skin"):
        options["skinColor"] = [found["skin"]]
    if found.get("hair") not in (None, "none"):
        options["hairColor"] = [found["hair"]]
    return {"style": STYLE, "seed": s, "skin": found.get("skin"), "hair": found.get("hair"), "options": options}
