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

The look. The face is drawn in one of FACE_THEMES (one per personality, Persona.face):
a solid colored background with a few small stars, white eyes with a colored iris and
a glint, pink cheeks, and a mouth that opens to show a tongue. A card is drawn in one
of STYLES, picked by Card.style (else by its kind, then its text: the role cards by team, a number):
a deep tinted background, a rounded border in the accent, the big line white over a
shadow, the sub line a light tint of the accent. Everything is solid fills, because a
gradient bands in RGB565. The gateway's "matrix" mode (90 frames, every eyes x mouth
pair) would let the face blink while talking; layered mode is enough for now.

Beside every set on disk sits its manifest (<set>.bin.json): which card each slot
holds. The host reads it to pick the face that shows a card; the fake gateway reads
it to say what the screen showed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
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

RGB = tuple[int, int, int]
WHITE: RGB = (250, 250, 250)


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    """a moved t of the way to b."""
    return (round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t), round(a[2] + (b[2] - a[2]) * t))


@dataclass(frozen=True)
class CardStyle:
    """A card's colors, from two: the accent (border, sub line) and the background."""

    accent: RGB
    bg: RGB

    @property
    def text(self) -> RGB:
        return WHITE

    @property
    def shadow(self) -> RGB:
        return _mix(self.bg, self.accent, 0.45)

    @property
    def sub(self) -> RGB:
        return _mix(self.accent, WHITE, 0.45)


# Card.style picks one of these; a new kind of card names one (or adds one here) and
# gets the whole look. Accents are bright and saturated so they read across a table.
STYLES: dict[str, CardStyle] = {
    "default": CardStyle(accent=(90, 150, 255), bg=(12, 20, 48)),  # blue: a word, anything else
    "villain": CardStyle(accent=(255, 64, 72), bg=(44, 8, 16)),  # red: Mafia, the Imposter
    "helper": CardStyle(accent=(40, 224, 176), bg=(4, 36, 32)),  # teal: the Doctor
    "town": CardStyle(accent=(255, 192, 56), bg=(40, 28, 8)),  # gold: a villager
    "number": CardStyle(accent=(184, 112, 255), bg=(28, 12, 52)),  # violet: Wavelength's target
    "win": CardStyle(accent=(120, 232, 88), bg=(12, 40, 12)),  # green: a winner
    "out": CardStyle(accent=(160, 160, 184), bg=(24, 24, 32)),  # grey: out of the game
}
# The style a card gets from its text when it names none: the role cards by team.
TEXT_STYLES = {"MAFIA": "villain", "IMPOSTER": "villain", "DOCTOR": "helper", "VILLAGER": "town"}
# The style a reveal gets from its kind (brain.table.REVEALS), before its text's.
KIND_STYLES = {"win": "win", "out": "out", "safe": "helper", "word": "default", "target": "number", "score": "number"}

# The blank slot stays plain and unlit: nothing to read, nothing to guess from.
CARD_BG: RGB = (10, 12, 20)
MARGIN = 8  # the text keeps this clear of every edge; the frame shows at 2x on the 320x240 screen
BORDER_INSET, BORDER_W, BORDER_R = 2, 3, 10
SHADOW = 2  # the big line's shadow, down and right, in pixels
MAX_TEXT_PX = 64  # the largest font for the big line
MIN_TEXT_PX = 10

# Shapes are drawn at SUPERSAMPLE times the frame size, then shrunk, so edges are smooth.
SUPERSAMPLE = 4


@dataclass(frozen=True)
class FaceTheme:
    """The host's face colors. Every frame of a set uses one theme."""

    bg: RGB  # the screen behind the face
    ink: RGB  # brows, the whites of the eyes, outlines
    iris: RGB
    pupil: RGB
    cheek: RGB
    mouth: RGB  # inside the open mouth
    tongue: RGB
    spark: RGB  # the little stars


# One per personality (brain/personas.py, Persona.face).
FACE_THEMES: dict[str, FaceTheme] = {
    "friendly": FaceTheme(bg=(16, 24, 64), ink=(244, 246, 255), iris=(56, 200, 255), pupil=(12, 16, 40), cheek=(255, 112, 150), mouth=(72, 8, 32), tongue=(255, 104, 128), spark=(255, 208, 72)),
    "sarcastic": FaceTheme(bg=(40, 16, 48), ink=(240, 236, 244), iris=(232, 72, 200), pupil=(24, 8, 28), cheek=(216, 88, 152), mouth=(64, 8, 40), tongue=(240, 104, 152), spark=(184, 120, 224)),
    "energetic": FaceTheme(bg=(72, 24, 8), ink=(255, 248, 232), iris=(255, 200, 32), pupil=(48, 16, 4), cheek=(255, 88, 64), mouth=(80, 12, 8), tongue=(255, 112, 96), spark=(255, 232, 96)),
    "dramatic": FaceTheme(bg=(20, 8, 40), ink=(224, 232, 240), iris=(96, 255, 128), pupil=(8, 20, 12), cheek=(144, 72, 192), mouth=(16, 40, 24), tongue=(96, 200, 120), spark=(120, 255, 160)),
    "calm": FaceTheme(bg=(8, 48, 52), ink=(236, 252, 248), iris=(112, 232, 200), pupil=(4, 28, 28), cheek=(255, 152, 136), mouth=(48, 16, 24), tongue=(255, 128, 128), spark=(176, 248, 224)),
    "grumpy": FaceTheme(bg=(40, 36, 36), ink=(236, 232, 228), iris=(255, 128, 48), pupil=(28, 12, 4), cheek=(200, 104, 88), mouth=(56, 16, 12), tongue=(232, 112, 96), spark=(255, 176, 96)),
}
DEFAULT_FACE = "friendly"


def style_of(card: Card) -> CardStyle:
    """The card's colors: its own style, else its kind's, else its text's (a role, a number), else the
    default. An unknown style name falls back the same way, so a typo never stops a game."""
    if card.style in STYLES:
        return STYLES[card.style]
    key = KIND_STYLES.get(card.kind or "") or TEXT_STYLES.get(card.text.strip().upper())
    if key is None and card.text.strip().isdigit():
        key = "number"
    return STYLES[key or "default"]


def face_theme(face: str | None) -> FaceTheme:
    """The theme by name; None or an unknown name is the default host's."""
    return FACE_THEMES.get(face or DEFAULT_FACE, FACE_THEMES[DEFAULT_FACE])


def _font(px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # Pillow's built-in scalable font (Aileron, embedded in Pillow >= 10.1): the same
    # glyphs on the Mac and the Pi, no font file to ship.
    return ImageFont.load_default(size=px)


def _ink(text: str, px: int, color: RGB, shadow: RGB | None = None) -> Image.Image:
    """The text in this colour on a transparent layer, cropped to its ink; with a
    shadow, the same text in the shadow colour SHADOW pixels down and right under it."""
    font = _font(px)
    stroke = 1 if px >= 24 else 0  # a faux bold for the big sizes
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font, stroke_width=stroke)
    off = SHADOW if shadow else 0
    layer = Image.new("RGBA", (r - l + 2 + off, b - t + 2 + off), (*color, 0))
    d = ImageDraw.Draw(layer)
    if shadow:
        d.text((1 - l + off, 1 - t + off), text, font=font, fill=(*shadow, 255), stroke_width=stroke, stroke_fill=(*shadow, 255))
    d.text((1 - l, 1 - t), text, font=font, fill=(*color, 255), stroke_width=stroke, stroke_fill=(*color, 255))
    return layer


def _fit(text: str, max_w: int, max_h: int, start: int, floor: int, color: RGB, shadow: RGB | None = None) -> Image.Image:
    """The text as large as fits max_w x max_h, from `start` px down to `floor` px; below
    the floor it stays at the floor and is squeezed sideways instead, so a long word
    stays tall enough to read."""
    for px in range(start, floor - 1, -1):
        layer = _ink(text, px, color, shadow)
        if layer.width <= max_w and layer.height <= max_h:
            return layer
    px = floor
    while True:
        layer = _ink(text, px, color, shadow)
        if layer.height <= max_h or px <= MIN_TEXT_PX:
            break
        px -= 1
    if layer.width > max_w:
        layer = layer.resize((max_w, layer.height), Image.Resampling.LANCZOS)
    return layer


def card_text(card: Card) -> Image.Image:
    """The card's words alone, as a frame-sized RGBA layer (transparent where there is
    no ink): the big line centred, the sub line under it, all inside MARGIN."""
    if not card.text.strip():
        raise ValueError("a card needs text")
    style = style_of(card)
    layer = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))
    inner_w, inner_h = FRAME_W - 2 * MARGIN, FRAME_H - 2 * MARGIN
    gap = 4
    sub = _fit(card.sub, inner_w, 24, 22, 14, style.sub) if card.sub else None
    main_h = inner_h - (sub.height + gap if sub else 0)
    main = _fit(card.text, inner_w, main_h, MAX_TEXT_PX, 30, style.text, style.shadow)
    block_h = main.height + (gap + sub.height if sub else 0)
    top = MARGIN + (inner_h - block_h) // 2
    layer.alpha_composite(main, ((FRAME_W - main.width) // 2, top))
    if sub:
        layer.alpha_composite(sub, ((FRAME_W - sub.width) // 2, top + main.height + gap))
    return layer


def render_card(card: Card) -> np.ndarray:
    """One card as a (120, 160, 3) uint8 RGB frame: its style's background and rounded
    border, then its words."""
    words = card_text(card)  # first: it refuses an empty card
    style = style_of(card)
    s = SUPERSAMPLE
    img = Image.new("RGB", (FRAME_W * s, FRAME_H * s), style.bg)
    i = BORDER_INSET * s
    ImageDraw.Draw(img).rounded_rectangle((i, i, FRAME_W * s - 1 - i, FRAME_H * s - 1 - i), radius=BORDER_R * s, outline=style.accent, width=BORDER_W * s)
    out = img.resize((FRAME_W, FRAME_H), Image.Resampling.LANCZOS).convert("RGBA")
    out.alpha_composite(words)
    return np.asarray(out.convert("RGB"), dtype=np.uint8).copy()


def blank_frame() -> np.ndarray:
    """An unused card slot: plain dark, nothing to read."""
    return np.full((FRAME_H, FRAME_W, 3), CARD_BG, np.uint8)


# The background's little stars, (x, y, radius): clear of the eyes and the mouth, and
# the same in every frame.
SPARKS = ((16, 18, 5), (144, 16, 4), (12, 96, 3), (148, 102, 5), (134, 64, 2), (26, 70, 2))


def host_face(eyes: str = "open", mouth: str = "closed", face: str | None = None) -> np.ndarray:
    """The host's own face as a (120, 160, 3) uint8 RGB frame, in the colors of
    FACE_THEMES[face]. Every variant shares one geometry (the same stars, brows, eye
    centres, cheeks and mouth centre); only the eyes or the mouth change."""
    if eyes not in EYES:
        raise ValueError(f"eyes must be one of {EYES}")
    if mouth not in MOUTHS:
        raise ValueError(f"mouth must be one of {MOUTHS}")
    th = face_theme(face)
    s = SUPERSAMPLE
    img = Image.new("RGB", (FRAME_W * s, FRAME_H * s), th.bg)
    d = ImageDraw.Draw(img)

    def box(cx: float, cy: float, rx: float, ry: float) -> tuple[int, int, int, int]:
        return (int((cx - rx) * s), int((cy - ry) * s), int((cx + rx) * s), int((cy + ry) * s))

    def pt(x: float, y: float) -> tuple[int, int]:
        return (int(x * s), int(y * s))

    for x, y, r in SPARKS:  # four-pointed stars
        w = max(r / 3, 0.8)
        d.polygon([pt(x, y - r), pt(x + w, y - w), pt(x + r, y), pt(x + w, y + w), pt(x, y + r), pt(x - w, y + w), pt(x - r, y), pt(x - w, y - w)], fill=th.spark)

    eye_y, eye_r = 50, 13
    for cx, tilt in ((50, 1), (110, -1)):
        # Brows: a raised, slightly mischievous arch, the game master's look, with round ends.
        a, b = (cx - 14, eye_y - 20 + 3 * tilt), (cx + 14, eye_y - 20 - 3 * tilt)
        d.line([pt(*a), pt(*b)], fill=th.ink, width=4 * s)
        for x, y in (a, b):
            d.ellipse(box(x, y, 2, 2), fill=th.ink)
        if eyes in ("open", "half"):
            d.ellipse(box(cx, eye_y, eye_r, eye_r), fill=th.ink)
            d.ellipse(box(cx + 2, eye_y + 1, 8, 8), fill=th.iris)
            d.ellipse(box(cx + 2, eye_y + 1, 4, 4), fill=th.pupil)
            d.ellipse(box(cx - 1, eye_y - 3, 2.5, 2.5), fill=th.ink)  # the glint
            if eyes == "half":  # the lid over the top half, its edge in ink
                d.rectangle(box(cx, eye_y - eye_r / 2 - 1, eye_r + 1, eye_r / 2 + 1), fill=th.bg)
                d.line([pt(cx - eye_r, eye_y), pt(cx + eye_r, eye_y)], fill=th.ink, width=3 * s)
        else:  # closed: a downward arc
            d.arc(box(cx, eye_y - 4, eye_r, 8), start=20, end=160, fill=th.ink, width=3 * s)
        d.ellipse(box(cx - 4 * tilt, eye_y + 23, 9, 5), fill=th.cheek)

    mx, my = 80, 88
    if mouth == "closed":
        d.arc(box(mx, my - 8, 16, 10), start=20, end=160, fill=th.ink, width=3 * s)
    else:
        # An open mouth: a "D" (flat on top, round below), or a round "u"; the inside,
        # a tongue at the bottom, the outline over both.
        cx, cy, rx, ry = {"half": (mx, my - 2, 11, 7), "open": (mx, my - 4, 14, 14), "e": (mx, my - 2, 17, 7), "u": (mx, my, 7, 8)}[mouth]
        outline = box(cx, cy, rx, ry)
        mask = Image.new("L", img.size, 0)
        if mouth == "u":
            ImageDraw.Draw(mask).ellipse(outline, fill=255)
        else:
            ImageDraw.Draw(mask).chord(outline, start=0, end=180, fill=255)
        inside = Image.new("RGB", img.size, th.mouth)
        ImageDraw.Draw(inside).ellipse(box(cx, cy + ry * (0.75 if mouth == "u" else 0.85), rx * 0.7, ry * 0.5), fill=th.tongue)
        img.paste(inside, (0, 0), mask)
        d = ImageDraw.Draw(img)
        if mouth == "u":
            d.ellipse(outline, outline=th.ink, width=2 * s)
        else:
            d.chord(outline, start=0, end=180, outline=th.ink, width=2 * s)

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


def frames(cards: list[Card], face: str | None = None) -> list[np.ndarray]:
    """The 14 frames of the set, in the device's order, the host's face in FACE_THEMES[face]."""
    _check(cards)
    out = [host_face(face=face)]
    out += [render_card(c) for c in cards]
    out += [blank_frame()] * (len(SLOTS) - len(cards))
    out += [host_face(eyes=e, face=face) for e in EYES]
    out += [host_face(mouth=m, face=face) for m in MOUTHS]
    return out


def pack(cards: list[Card], face: str | None = None) -> tuple[bytes, dict[str, Any]]:
    """The layered archive (537,600 bytes) and its manifest for these cards (at most five)."""
    data = b"".join(to_rgb565le(f) for f in frames(cards, face))
    assert len(data) == SET_BYTES
    slots: dict[str, Any] = {slot: None for slot in SLOTS}
    for slot, card in zip(SLOTS, cards):
        slots[slot] = {"text": card.text, "sub": card.sub, **({"kind": card.kind} if card.kind else {})}
        if card.style is not None:
            slots[slot]["style"] = card.style
    manifest = {"mode": "layered", "bytes": SET_BYTES, "sha256": hashlib.sha256(data).hexdigest(), "face": face or DEFAULT_FACE, "slots": slots}
    return data, manifest


def manifest_path(path: Path) -> Path:
    return Path(str(path) + ".json")


def write_set(cards: list[Card], directory: Path, face: str | None = None) -> Path:
    """Write the set as <directory>/<first 12 hex of its sha256>.bin with its manifest
    beside it (.bin.json); returns the .bin path. Writes nothing when it already exists."""
    data, manifest = pack(cards, face)
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
    return None if held is None else Card(held["text"], held.get("sub"), held.get("kind"), held.get("style"))
