"""The synthetic table: 640x480, faces where their bearings put them, frontal and
down drawn differently, a close face bigger, nothing outside the field of view."""

import math

import cv2
import numpy as np
import pytest
import table
from table import Face


def test_a_frame_is_640x480_bgr_and_deterministic():
    faces = [Face(-20), Face(10, "down"), Face(0, close=True)]
    a, b = table.render(0, faces), table.render(0, faces)
    assert a.shape == (480, 640, 3) and a.dtype == np.uint8
    assert np.array_equal(a, b)


def test_the_png_decodes_to_the_rendered_frame():
    faces = [Face(5)]
    decoded = cv2.imdecode(np.frombuffer(table.png(0, faces), np.uint8), cv2.IMREAD_COLOR)
    assert np.array_equal(decoded, table.render(0, faces))


def test_a_face_straight_ahead_is_centred_and_bearings_project_left_to_right():
    (box,) = table.boxes(0, [Face(0)])
    assert abs(box.x + box.w / 2 - 320) <= 1
    xs = [b.x for b in table.boxes(0, [Face(-20), Face(-5), Face(10), Face(25)])]
    assert xs == sorted(xs)


def test_turning_the_head_moves_the_face_the_other_way():
    (at0,) = table.boxes(0, [Face(10)])
    (at10,) = table.boxes(10, [Face(10)])
    assert at0.x > at10.x
    assert abs(at10.x + at10.w / 2 - 320) <= 1


def test_faces_outside_the_field_of_view_are_not_drawn():
    half = table.HFOV_DEG / 2
    assert table.boxes(0, [Face(half + 1)]) == []
    assert table.boxes(0, [Face(-half - 1)]) == []
    assert np.array_equal(table.render(0, [Face(120)]), table.render(0, []))
    assert table.boxes(90, [Face(-170)]) == []  # wraps: -170 is 100 deg from 90
    assert [b.index for b in table.boxes(170, [Face(-175)])] == [0]  # 15 deg past 180


def test_the_face_is_drawn_inside_its_box_and_nowhere_else():
    empty = table.render(0, [])
    img = table.render(0, [Face(0)])
    (box,) = table.boxes(0, [Face(0)])
    face_region = (slice(box.y, box.y + box.h), slice(box.x, box.x + box.w))
    assert np.abs(img[face_region].astype(int) - empty[face_region]).sum() > 0
    above = (slice(0, box.y), slice(0, 640))
    assert np.array_equal(img[above], empty[above])


def test_frontal_and_down_differ_and_down_shows_no_eyes():
    up = table.render(0, [Face(0, "frontal")])
    down = table.render(0, [Face(0, "down")])
    assert not np.array_equal(up, down)
    (box,) = table.boxes(0, [Face(0)])
    eyes = (slice(box.y + box.h // 4, box.y + box.h // 2), slice(box.x, box.x + box.w))
    white = lambda img: int((img[eyes].min(axis=2) > 235).sum())  # noqa: E731
    assert white(up) > 0
    assert white(down) == 0


def test_a_close_face_is_several_times_wider():
    (far,) = table.boxes(0, [Face(0)])
    (near,) = table.boxes(0, [Face(0, close=True)])
    assert near.w >= 3 * far.w


def test_two_close_faces_side_by_side_are_both_boxed():
    found = table.boxes(0, [Face(-8, close=True), Face(8, close=True)])
    assert [b.index for b in found] == [0, 1]


@pytest.mark.parametrize("spec,face", [("-40", Face(-40)), ("0:down", Face(0, "down")), ("35:frontal:close", Face(35, close=True))])
def test_face_specs_parse(spec, face):
    assert table.parse_face(spec) == face


@pytest.mark.parametrize("spec", ["", "x", "0:sideways", "0:frontal:near", "0:down:close:extra"])
def test_bad_face_specs_are_refused(spec):
    with pytest.raises(ValueError):
        table.parse_face(spec)


def test_bad_values_are_refused():
    with pytest.raises(ValueError):
        Face(math.nan)
    with pytest.raises(ValueError):
        table.render(math.inf, [])


def test_the_cli_writes_one_png_per_pan(tmp_path):
    assert table.main(["--pans=-30,0,30", "--face=-30", "--face=0:down", "--out-dir", str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pan-30.png", "pan0.png", "pan30.png"]
    decoded = cv2.imread(str(tmp_path / "pan-30.png"))
    assert np.array_equal(decoded, table.render(-30, [Face(-30), Face(0, "down")]))
