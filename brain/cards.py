"""The host's screen: role cards and the host's own face, packed into the avatar set
the StackChan loads at runtime (stackchan-mcp's load_avatar_set, layered mode).

A layered set is 14 full frames of 160x120 RGB565, little-endian, back to back:
the six faces (idle, happy, thinking, sad, surprised, embarrassed), then the three
eyes (open, half, closed), then the five mouths (closed, half, open, e, u), 537,600
bytes. The device has no compositor: it always shows exactly one whole frame, and a
blink or a mouth change swaps in the whole eyes or mouth frame. So every frame here
is a complete picture: idle is the host's face, the eyes and mouth frames are that
same face with only the eyes or the mouth changed (one geometry for every variant,
so nothing jumps), and the five card slots (happy..embarrassed) each hold one card
or a plain blank frame. set_avatar("happy") then shows the first card.

Beside every set on disk sits its manifest (<set>.bin.json): which card each slot
holds. The host reads it to pick the face that shows a card; the fake gateway reads
it to say what the screen showed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from brain.table import Card

FRAME_W, FRAME_H = 160, 120
FRAME_BYTES = FRAME_W * FRAME_H * 2  # 38,400
FACES = ("idle", "happy", "thinking", "sad", "surprised", "embarrassed")
SLOTS = FACES[1:]  # the card slots, filled in this order
EYES = ("open", "half", "closed")
MOUTHS = ("closed", "half", "open", "e", "u")
SET_BYTES = (len(FACES) + len(EYES) + len(MOUTHS)) * FRAME_BYTES  # 537,600
assert FRAME_BYTES == 38_400 and SET_BYTES == 537_600

# The card: white on near-black, the sub line in amber. The text keeps MARGIN pixels
# clear of every edge; the frame shows at 2x on the 320x240 screen.
CARD_BG = (14, 16, 26)
CARD_TEXT = (250, 250, 250)
CARD_SUB = (255, 196, 70)
MARGIN = 8
MAX_TEXT_PX = 64  # the largest font for the big line
MIN_TEXT_PX = 10

# The host's face: drawn at SUPERSAMPLE times the frame size, then shrunk, so edges are smooth.
FACE_BG = (12, 12, 20)
FACE_INK = (245, 245, 245)
FACE_CHEEK = (200, 90, 120)
FACE_MOUTH = (150, 40, 60)
SUPERSAMPLE = 4


def _font(px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # Pillow's built-in scalable font (Aileron, embedded in Pillow >= 10.1): the same
    # glyphs on the Mac and the Pi, no font file to ship.
    return ImageFont.load_default(size=px)


def _ink(text: str, px: int, color: tuple[int, int, int]) -> Image.Image:
    """The text in this colour on a transparent layer, cropped to its ink."""
    font = _font(px)
    stroke = 1 if px >= 24 else 0  # a faux bold for the big sizes
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font, stroke_width=stroke)
    layer = Image.new("RGBA", (r - l + 2, b - t + 2), (*color, 0))
    ImageDraw.Draw(layer).text((1 - l, 1 - t), text, font=font, fill=(*color, 255), stroke_width=stroke, stroke_fill=(*color, 255))
    return layer


def _fit(text: str, max_w: int, max_h: int, start: int, floor: int, color: tuple[int, int, int]) -> Image.Image:
    """The text as large as fits max_w x max_h, from `start` px down to `floor` px; below
    the floor it stays at the floor and is squeezed sideways instead, so a long word
    stays tall enough to read."""
    for px in range(start, floor - 1, -1):
        layer = _ink(text, px, color)
        if layer.width <= max_w and layer.height <= max_h:
            return layer
    px = floor
    while True:
        layer = _ink(text, px, color)
        if layer.height <= max_h or px <= MIN_TEXT_PX:
            break
        px -= 1
    if layer.width > max_w:
        layer = layer.resize((max_w, layer.height), Image.Resampling.LANCZOS)
    return layer


def render_card(card: Card) -> np.ndarray:
    """One card as a (120, 160, 3) uint8 RGB frame: the big line centred, the sub line under it."""
    if not card.text.strip():
        raise ValueError("a card needs text")
    img = Image.new("RGBA", (FRAME_W, FRAME_H), (*CARD_BG, 255))
    inner_w, inner_h = FRAME_W - 2 * MARGIN, FRAME_H - 2 * MARGIN
    gap = 4
    sub = _fit(card.sub, inner_w, 24, 22, 14, CARD_SUB) if card.sub else None
    main_h = inner_h - (sub.height + gap if sub else 0)
    main = _fit(card.text, inner_w, main_h, MAX_TEXT_PX, 30, CARD_TEXT)
    block_h = main.height + (gap + sub.height if sub else 0)
    top = MARGIN + (inner_h - block_h) // 2
    img.alpha_composite(main, ((FRAME_W - main.width) // 2, top))
    if sub:
        img.alpha_composite(sub, ((FRAME_W - sub.width) // 2, top + main.height + gap))
    return np.asarray(img.convert("RGB"), dtype=np.uint8).copy()


def blank_frame() -> np.ndarray:
    """An unused card slot: plain dark, nothing to read."""
    return np.full((FRAME_H, FRAME_W, 3), CARD_BG, np.uint8)


def host_face(eyes: str = "open", mouth: str = "closed") -> np.ndarray:
    """The host's own face as a (120, 160, 3) uint8 RGB frame. Every variant shares one
    geometry (the same eye centres, mouth centre, brows and cheeks); only the eyes or
    the mouth change."""
    if eyes not in EYES:
        raise ValueError(f"eyes must be one of {EYES}")
    if mouth not in MOUTHS:
        raise ValueError(f"mouth must be one of {MOUTHS}")
    s = SUPERSAMPLE
    img = Image.new("RGB", (FRAME_W * s, FRAME_H * s), FACE_BG)
    d = ImageDraw.Draw(img)

    def box(cx: float, cy: float, rx: float, ry: float) -> tuple[int, int, int, int]:
        return (int((cx - rx) * s), int((cy - ry) * s), int((cx + rx) * s), int((cy + ry) * s))

    eye_y, eye_r = 50, 12
    for cx, tilt in ((50, 1), (110, -1)):
        # Brows: a raised, slightly mischievous arch, the game master's look.
        d.line([(int((cx - 14) * s), int((eye_y - 18 + 3 * tilt) * s)), (int((cx + 14) * s), int((eye_y - 18 - 3 * tilt) * s))], fill=FACE_INK, width=3 * s)
        if eyes == "open":
            d.ellipse(box(cx, eye_y, eye_r, eye_r), fill=FACE_INK)
            d.ellipse(box(cx + 2, eye_y + 1, 5, 5), fill=FACE_BG)
        elif eyes == "half":
            d.ellipse(box(cx, eye_y, eye_r, eye_r), fill=FACE_INK)
            d.ellipse(box(cx + 2, eye_y + 1, 5, 5), fill=FACE_BG)
            d.rectangle(box(cx, eye_y - eye_r / 2 - 1, eye_r + 1, eye_r / 2 + 1), fill=FACE_BG)  # the lid over the top half
            d.line([(int((cx - eye_r) * s), int(eye_y * s)), (int((cx + eye_r) * s), int(eye_y * s))], fill=FACE_INK, width=2 * s)
        else:  # closed: a downward arc
            d.arc(box(cx, eye_y - 4, eye_r, 8), start=20, end=160, fill=FACE_INK, width=3 * s)
        d.ellipse(box(cx - 4 * tilt, eye_y + 22, 9, 5), fill=FACE_CHEEK)

    mx, my = 80, 88
    if mouth == "closed":
        d.arc(box(mx, my - 8, 16, 10), start=20, end=160, fill=FACE_INK, width=3 * s)
    elif mouth == "half":
        d.ellipse(box(mx, my, 10, 5), fill=FACE_MOUTH, outline=FACE_INK, width=2 * s)
    elif mouth == "open":
        d.ellipse(box(mx, my + 1, 12, 10), fill=FACE_MOUTH, outline=FACE_INK, width=2 * s)
    elif mouth == "e":
        d.ellipse(box(mx, my, 16, 5), fill=FACE_MOUTH, outline=FACE_INK, width=2 * s)
    else:  # u
        d.ellipse(box(mx, my, 6, 7), fill=FACE_MOUTH, outline=FACE_INK, width=2 * s)

    img = img.resize((FRAME_W, FRAME_H), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.uint8).copy()


def to_rgb565le(img: np.ndarray) -> bytes:
    """A (120, 160, 3) uint8 RGB frame as 38,400 bytes of RGB565, little-endian."""
    if img.shape != (FRAME_H, FRAME_W, 3) or img.dtype != np.uint8:
        raise ValueError(f"a frame is ({FRAME_H}, {FRAME_W}, 3) uint8, not {img.shape} {img.dtype}")
    r = img[..., 0].astype(np.uint16) >> 3
    g = img[..., 1].astype(np.uint16) >> 2
    b = img[..., 2].astype(np.uint16) >> 3
    return ((r << 11) | (g << 5) | b).astype("<u2").tobytes()


def from_rgb565le(data: bytes) -> np.ndarray:
    """38,400 bytes of RGB565 little-endian back to a (120, 160, 3) uint8 RGB frame."""
    if len(data) != FRAME_BYTES:
        raise ValueError(f"a frame is {FRAME_BYTES} bytes, not {len(data)}")
    v = np.frombuffer(data, dtype="<u2").reshape(FRAME_H, FRAME_W)
    r = (v >> 11) & 0x1F
    g = (v >> 5) & 0x3F
    b = v & 0x1F
    out = np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], axis=-1)
    return out.astype(np.uint8)


def _check(cards: list[Card]) -> None:
    if len(cards) > len(SLOTS):
        raise ValueError(f"a set holds at most {len(SLOTS)} cards, not {len(cards)}")
    if len(set(cards)) != len(cards):
        raise ValueError("the cards in a set must be distinct")


def frames(cards: list[Card]) -> list[np.ndarray]:
    """The 14 frames of the set, in the device's order."""
    _check(cards)
    out = [host_face()]
    out += [render_card(c) for c in cards]
    out += [blank_frame()] * (len(SLOTS) - len(cards))
    out += [host_face(eyes=e) for e in EYES]
    out += [host_face(mouth=m) for m in MOUTHS]
    return out


def pack(cards: list[Card]) -> tuple[bytes, dict[str, Any]]:
    """The layered archive (537,600 bytes) and its manifest for these cards (at most five)."""
    data = b"".join(to_rgb565le(f) for f in frames(cards))
    assert len(data) == SET_BYTES
    slots: dict[str, Any] = {slot: None for slot in SLOTS}
    for slot, card in zip(SLOTS, cards):
        slots[slot] = {"text": card.text, "sub": card.sub, **({"kind": card.kind} if card.kind else {})}
    manifest = {"mode": "layered", "bytes": SET_BYTES, "sha256": hashlib.sha256(data).hexdigest(), "slots": slots}
    return data, manifest


def manifest_path(path: Path) -> Path:
    return Path(str(path) + ".json")


def write_set(cards: list[Card], directory: Path) -> Path:
    """Write the set as <directory>/<first 12 hex of its sha256>.bin with its manifest
    beside it (.bin.json); returns the .bin path. Writes nothing that is already there."""
    data, manifest = pack(cards)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{manifest['sha256'][:12]}.bin"
    side = manifest_path(path)
    if not (path.exists() and path.stat().st_size == SET_BYTES):
        tmp = path.with_suffix(".bin.tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    text = json.dumps(manifest, indent=2) + "\n"
    if not side.exists() or side.read_text() != text:  # the same pixels may carry other kinds
        side.write_text(text)
    return path.resolve()


def read_manifest(path: Path) -> dict[str, Any]:
    """The manifest beside a set's .bin."""
    return json.loads(manifest_path(Path(path)).read_text())


def slot_of(manifest: dict[str, Any], card: Card) -> str:
    """The set_avatar face name that shows this card; KeyError when the set does not hold it."""
    for slot in SLOTS:
        held = manifest["slots"].get(slot)
        if held is not None and held["text"] == card.text and held.get("sub") == card.sub and held.get("kind") == card.kind:
            return slot
    raise KeyError(f"the set does not hold {card!r}")


def card_in(manifest: dict[str, Any], face: str) -> Card | None:
    """What a face name shows in this set: its card, or None for the host's face, a blank slot or "off"."""
    held = manifest["slots"].get(face) if face in SLOTS else None
    return None if held is None else Card(held["text"], held.get("sub"), held.get("kind"))
