"""brain/cards.py: the avatar set the device loads is the right size, in the device's
frame order, and its manifest names the card each face shows. A wrong frame order
shows the wrong card to the wrong player, silently, so the order is checked frame by
frame against what was rendered."""

import json

import numpy as np
import pytest

from brain import cards
from brain.cards import Card

MAFIA = [Card("MAFIA"), Card("DOCTOR"), Card("VILLAGER")]


def frame(data: bytes, i: int) -> bytes:
    return data[i * cards.FRAME_BYTES : (i + 1) * cards.FRAME_BYTES]


def test_the_sizes_are_the_firmware_s():
    assert (cards.FRAME_W, cards.FRAME_H, cards.FRAME_BYTES, cards.SET_BYTES) == (160, 120, 38_400, 537_600)
    data, manifest = cards.pack(MAFIA)
    assert len(data) == 537_600
    assert manifest["bytes"] == 537_600 and manifest["mode"] == "layered"


def test_frames_are_in_the_device_order():
    data, _ = cards.pack(MAFIA)
    order = (
        [cards.host_face()]
        + [cards.render_card(c) for c in MAFIA]
        + [cards.blank_frame()] * 2
        + [cards.host_face(eyes=e) for e in ("open", "half", "closed")]
        + [cards.host_face(mouth=m) for m in ("closed", "half", "open", "e", "u")]
    )
    assert len(order) == 14
    for i, expected in enumerate(order):
        assert frame(data, i) == cards.to_rgb565le(expected), f"frame {i}"
    # happy (frame 1) is the first card, and nothing else
    assert frame(data, 1) == cards.to_rgb565le(cards.render_card(Card("MAFIA")))
    assert frame(data, 1) != frame(data, 2) != frame(data, 3)


def test_the_host_face_is_not_a_card_and_the_variants_share_one_face():
    data, _ = cards.pack(MAFIA)
    idle = frame(data, 0)
    for i in range(1, 6):
        assert frame(data, i) != idle
    base = cards.host_face().astype(int)
    for eyes in ("half", "closed"):
        diff = np.abs(cards.host_face(eyes=eyes).astype(int) - base).sum(axis=2) > 30
        ys, _ = np.nonzero(diff)
        assert ys.size and ys.max() < 66, f"eyes={eyes} changed something below the eyes"
    for mouth in ("half", "open", "e", "u"):
        diff = np.abs(cards.host_face(mouth=mouth).astype(int) - base).sum(axis=2) > 30
        ys, _ = np.nonzero(diff)
        assert ys.size and ys.min() > 70, f"mouth={mouth} changed something above the mouth"


def test_manifest_and_slot_of():
    _, manifest = cards.pack(MAFIA)
    assert manifest["slots"] == {
        "happy": {"text": "MAFIA", "sub": None},
        "thinking": {"text": "DOCTOR", "sub": None},
        "sad": {"text": "VILLAGER", "sub": None},
        "surprised": None,
        "embarrassed": None,
    }
    assert cards.slot_of(manifest, Card("DOCTOR")) == "thinking"
    assert cards.card_in(manifest, "sad") == Card("VILLAGER")
    assert cards.card_in(manifest, "idle") is None and cards.card_in(manifest, "off") is None
    with pytest.raises(KeyError):
        cards.slot_of(manifest, Card("IMPOSTER"))
    wave = [Card("7", "cold - hot"), Card("7", "dull - exciting")]
    _, m2 = cards.pack(wave)
    assert cards.slot_of(m2, Card("7", "dull - exciting")) == "thinking"


def test_write_set_and_read_manifest(tmp_path):
    path = cards.write_set(MAFIA, tmp_path)
    assert path.suffix == ".bin" and path.stat().st_size == 537_600
    manifest = cards.read_manifest(path)
    assert path.name == manifest["sha256"][:12] + ".bin"
    assert json.loads((tmp_path / (path.name + ".json")).read_text()) == manifest
    mtime = path.stat().st_mtime_ns
    assert cards.write_set(MAFIA, tmp_path) == path and path.stat().st_mtime_ns == mtime  # not rewritten
    assert cards.write_set([Card("beach"), Card("IMPOSTER")], tmp_path) != path


def test_rgb565_round_trip():
    rng = np.random.default_rng(1)
    img = rng.integers(0, 256, (120, 160, 3), dtype=np.uint8)
    data = cards.to_rgb565le(img)
    assert len(data) == 38_400
    back = cards.from_rgb565le(data)
    assert np.abs(back.astype(int) - img.astype(int)).max() <= 7  # 5/6/5 bits keep the top of each channel
    assert cards.to_rgb565le(back) == data
    # little-endian, red in the top five bits
    red = np.zeros((120, 160, 3), np.uint8)
    red[..., 0] = 255
    assert cards.to_rgb565le(red)[:2] == bytes([0x00, 0xF8])


@pytest.mark.parametrize(
    "card",
    [
        Card("IMPOSTER"),
        Card("VILLAGER"),
        Card("strawberry"),
        Card("WWWWWWWWWW"),
        Card("10", "cold - hot"),
        Card("3", "underrated - overrated"),
        Card("MAFIA"),
    ],
)
def test_no_card_clips(card):
    ink = np.asarray(cards.card_text(card))[..., 3] > 60  # the words, not the border
    ys, xs = np.nonzero(ink)
    assert ys.size, "nothing drawn"
    edge = 3
    assert xs.min() >= edge and xs.max() < cards.FRAME_W - edge and ys.min() >= edge and ys.max() < cards.FRAME_H - edge
    assert ys.max() - ys.min() >= 14, "text too small to read"


def test_short_words_are_big():
    ys, _ = np.nonzero(np.asarray(cards.card_text(Card("MAFIA")))[..., 3] > 60)
    assert ys.max() - ys.min() >= 30


def test_more_than_five_or_repeated_cards_are_refused():
    with pytest.raises(ValueError):
        cards.pack([Card(str(i)) for i in range(6)])
    with pytest.raises(ValueError):
        cards.pack([Card("MAFIA"), Card("MAFIA")])
    with pytest.raises(ValueError):
        cards.render_card(Card("  "))
    assert len(cards.pack([])[0]) == 537_600
    assert len(cards.pack([Card(str(i)) for i in range(5)])[0]) == 537_600


def test_card_styles():
    assert cards.style_of(Card("MAFIA")) == cards.STYLES["villain"]
    assert cards.style_of(Card("DOCTOR")) == cards.STYLES["helper"]
    assert cards.style_of(Card("7", "cold - hot")) == cards.STYLES["number"]
    assert cards.style_of(Card("beach")) == cards.STYLES["default"]
    assert cards.style_of(Card("beach", style="win")) == cards.STYLES["win"]
    assert cards.style_of(Card("beach", style="no such style")) == cards.STYLES["default"]
    # the style is the look only: the same card whatever it is drawn in
    assert Card("MAFIA", style="out") == Card("MAFIA")
    assert cards.render_card(Card("MAFIA")).tobytes() != cards.render_card(Card("MAFIA", style="out")).tobytes()
    _, manifest = cards.pack([Card("YOU WIN", style="win")])
    assert cards.card_in(manifest, "happy").style == "win"


def test_every_personality_has_a_face():
    from brain import personas

    faces = {p.face for p in personas.PERSONAS.values()}
    assert faces <= set(cards.FACE_THEMES) and len(faces) == len(personas.PERSONAS)
    assert cards.pack([], face="dramatic")[0] != cards.pack([], face="friendly")[0]
