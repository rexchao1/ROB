"""The host's eyes on the synthetic table: counting sweeps find every frontal face once
and number the seats left to right; bowed heads are not faces; a face leaning in is
close and a second one beside it is a second; the night sweep names exactly the seats
with a face up. Every check runs on the 640x480 fixture and again after the 320x240
JPEG round trip the camera (and the fake gateway) serves.

The two probes the plan names (a second close face, every head down) are written as
checks that take the function under test, and each is also run against a broken
version of it, which it must reject: a probe that cannot fail proves nothing."""

import math

import cv2
import numpy as np
import pytest
import table
from table import Face as Drawn

from brain import vision
from brain.vision import Face

CAMERA = {
    "640": lambda img: img,
    "320 jpeg": lambda img: cv2.imdecode(
        cv2.imencode(".jpg", cv2.resize(img, (320, 240), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 80])[1],
        cv2.IMREAD_COLOR,
    ),
}


@pytest.fixture(params=list(CAMERA))
def camera(request):
    return CAMERA[request.param]


def look(camera, pan: float, drawn: list[Drawn]) -> list[Face]:
    return vision.find_faces(camera(table.render(pan, drawn)))


def sweep(camera, drawn: list[Drawn], pans: list[float] | None = None) -> list[tuple[float, list[Face]]]:
    return [(p, look(camera, p, drawn)) for p in (vision.sweep_pans() if pans is None else pans)]


def spread(n: int) -> list[float]:
    """n bearings across the head's range plus half the field of view, ends included."""
    return [round(-100 + i * 200 / (n - 1), 2) for i in range(n)]


# --- the counting sweep (D5) ------------------------------------------------------


def test_the_sweep_runs_left_to_right_across_the_whole_head_range_with_overlapping_views():
    pans = vision.sweep_pans()
    assert pans[0] == -90 and pans[-1] == 90 and pans == sorted(pans)
    assert max(b - a for a, b in zip(pans, pans[1:])) <= vision.HFOV_DEG / 3 + 1e-9
    reach = vision.HFOV_DEG / 2 - vision.EDGE_MARGIN_DEG
    for b in range(-90, 91):
        assert sum(abs(b - p) <= reach for p in pans) >= 2, f"bearing {b} is well inside fewer than two views"


@pytest.mark.parametrize("n", range(3, 11))
def test_a_sweep_counts_every_frontal_face_once_and_numbers_the_seats_left_to_right(camera, n):
    bearings = spread(n)
    found = vision.seats(sweep(camera, [Drawn(b) for b in bearings]))
    assert len(found) == n
    assert found == sorted(found)
    for seat, (got, want) in enumerate(zip(found, bearings), start=1):
        assert abs(got - want) <= 1.5, f"seat {seat} at {got:.1f}, drawn at {want}"


def test_players_at_the_ends_of_the_sweep_are_counted(camera):
    bearings = [-104, -91, 0, 92, 103]
    assert len(vision.seats(sweep(camera, [Drawn(b) for b in bearings]))) == 5


def test_bowed_heads_are_not_counted(camera):
    drawn = [Drawn(-60), Drawn(-30, "down"), Drawn(0), Drawn(30, "down"), Drawn(60)]
    found = vision.seats(sweep(camera, drawn))
    assert len(found) == 3
    assert [round(b) for b in found] == pytest.approx([-60, 0, 60], abs=2)


def test_bowed_heads_between_players_add_no_seats(camera):
    players = [-80.0, -50.0, -20.0, 10.0, 40.0, 70.0]
    bowed = [Drawn(b + 15, "down") for b in players[:-1]] + [Drawn(-96, "down"), Drawn(96, "down")]
    found = vision.seats(sweep(camera, [Drawn(b) for b in players] + bowed))
    assert found == pytest.approx(players, abs=1.5)


def test_a_face_leaning_in_during_the_sweep_is_not_a_seat(camera):
    drawn = [Drawn(-40), Drawn(0, close=True), Drawn(40)]
    assert len(vision.seats(sweep(camera, drawn))) == 2


def at(off: float) -> Face:
    """A seated face `off` degrees from the frame's centre."""
    cx = 0.5 + math.tan(math.radians(off)) / (2 * math.tan(math.radians(vision.HFOV_DEG / 2)))
    return Face(cx, 0.4, 0.1, 0.13, 0.9, True)


def test_a_stray_detection_in_one_frame_is_not_a_player():
    # A face at bearing 0 is well inside the views at -10 and 10, and seen in both.
    views = [(-10.0, [at(10)]), (10.0, [at(-10)]), (30.0, [])]
    assert vision.seats(views) == [pytest.approx(0.0, abs=1e-6)]
    # The same face in only one of the two views that should both see it is a ghost.
    ghost = [(-10.0, []), (10.0, [at(-10)]), (30.0, [])]
    assert vision.seats(ghost) == []
    # At the end of the sweep only one view has it well inside: once is enough.
    end = [(70.0, []), (90.0, [at(10)])]
    assert vision.seats(end) == [pytest.approx(100.0, abs=1e-6)]


def test_bearings_follow_the_tables_geometry(camera):
    for pan, b in [(0, 0), (0, -20), (0, 25), (30, 10), (-60, -75)]:
        (face,) = look(camera, pan, [Drawn(b)])
        assert vision.bearing(face, pan) == pytest.approx(b, abs=1.0)


# --- the private screen (D7, D8) ----------------------------------------------------


def two_close_check(close_fn, camera) -> None:
    """The D8 probe: two faces leaning in side by side are two close faces."""
    for d in (18, 14, 10):
        faces = vision.find_faces(camera(table.render(0, [Drawn(-d, close=True), Drawn(d, close=True)])))
        assert len(close_fn(faces)) == 2, f"two faces leaning in {2 * d} degrees apart read as {len(close_fn(faces))}"


def test_one_face_leaning_in_is_close(camera):
    for pan in (-20, -10, 0, 10, 20):
        faces = look(camera, pan, [Drawn(0, close=True)])
        (face,) = vision.close(faces)
        assert face.w >= vision.CLOSE_WIDTH and face.frontal


def test_two_faces_leaning_in_side_by_side_are_two_close_faces(camera):
    two_close_check(vision.close, camera)


def test_the_two_close_probe_fails_a_lock_that_always_sees_one(camera):
    def always_one(faces):
        return faces[:1]

    with pytest.raises(AssertionError):
        two_close_check(always_one, camera)


def test_seated_faces_beside_a_close_one_are_not_close(camera):
    faces = look(camera, 0, [Drawn(0, close=True), Drawn(20), Drawn(-25)])
    assert len(faces) == 3
    assert len(vision.close(faces)) == 1
    # A seated face half hidden behind the one leaning in.
    assert len(vision.close(look(camera, 0, [Drawn(12), Drawn(0, close=True)]))) == 1


def test_no_face_leaning_in_means_nothing_is_close(camera):
    assert vision.close(look(camera, 0, [Drawn(-15), Drawn(15)])) == []
    assert vision.close(look(camera, 0, [])) == []


# --- the night sweep (D9 to D11) ----------------------------------------------------

SEATS = [-60.0, -30.0, 0.0, 30.0, 60.0]


def night(camera, up: set[int], extra: list[Drawn] = ()) -> list[tuple[float, list[Face]]]:
    drawn = [Drawn(b, "frontal" if i + 1 in up else "down") for i, b in enumerate(SEATS)] + list(extra)
    return sweep(camera, drawn, vision.heads_down_pans(SEATS))


def every_head_down_check(seats_up_fn, camera) -> None:
    """The D10 probe: with every head down, nobody is named."""
    assert seats_up_fn(night(camera, set()), SEATS) == []


def test_the_night_sweep_puts_every_seat_well_inside_a_view():
    reach = vision.HFOV_DEG / 2 - vision.EDGE_MARGIN_DEG
    for seats in (SEATS, [-100.0, -95.0, 0.0, 97.0], spread(10), [5.0]):
        pans = vision.heads_down_pans(seats)
        assert pans == sorted(pans) and all(-90 <= p <= 90 for p in pans)
        for b in seats:
            nearest = min(abs(b - p) for p in pans)
            assert nearest <= max(reach, abs(b) - 90 + 1e-9), f"seat at {b} is not well inside any of {pans}"
    assert len(vision.heads_down_pans(SEATS)) <= 3
    assert vision.heads_down_pans([]) == []


def test_one_face_up_among_bowed_heads_names_that_seat(camera):
    assert vision.seats_up(night(camera, {3}), SEATS) == [3]
    assert vision.seats_up(night(camera, {1, 5}), SEATS) == [1, 5]


def test_every_head_down_names_nobody(camera):
    every_head_down_check(vision.seats_up, camera)


def test_the_every_head_down_probe_fails_a_sweep_that_always_names_a_seat(camera):
    def always_three(views, seats, hfov=vision.HFOV_DEG):
        return [3]

    with pytest.raises(AssertionError):
        every_head_down_check(always_three, camera)


def test_a_face_up_between_seats_is_nobodys(camera):
    assert vision.seats_up(night(camera, set(), [Drawn(-45.0), Drawn(15.0)]), SEATS) == []


def test_a_face_up_near_its_seat_after_shifting_a_little_is_that_seat(camera):
    drawn = [Drawn(b, "down") for b in SEATS if b != 30.0] + [Drawn(36.0)]
    views = sweep(camera, drawn, vision.heads_down_pans(SEATS))
    assert vision.seats_up(views, SEATS) == [4]


def test_seats_up_needs_seats():
    assert vision.seats_up([(0.0, [Face(0.5, 0.4, 0.1, 0.13, 0.9, True)])], []) == []


# --- find_faces itself --------------------------------------------------------------


def test_frontal_fixture_faces_are_frontal_and_found_once(camera):
    faces = look(camera, 0, [Drawn(-20), Drawn(-10), Drawn(0), Drawn(10), Drawn(20)])
    assert len(faces) == 5 and all(f.frontal for f in faces)
    assert all(0 < f.cx < 1 and 0 < f.cy < 1 and 0 < f.w < 1 and 0 < f.h < 1 for f in faces)


def test_an_empty_table_has_no_faces(camera):
    assert look(camera, 0, []) == []
    assert look(camera, 0, [Drawn(-10, "down"), Drawn(10, "down")]) == []


def test_find_faces_takes_any_frame_size_and_refuses_what_is_not_an_image():
    img = table.render(0, [Drawn(0)])
    for size in ((320, 240), (480, 360), (800, 600)):
        assert len(vision.find_faces(cv2.resize(img, size, interpolation=cv2.INTER_AREA))) == 1
    with pytest.raises(ValueError):
        vision.find_faces(np.zeros((480, 640), np.uint8))


def test_the_bearing_of_the_frame_centre_is_the_pan():
    centre = Face(0.5, 0.5, 0.1, 0.1, 0.9, True)
    assert vision.bearing(centre, 37.0) == 37.0
    edge = Face(1.0, 0.5, 0.1, 0.1, 0.9, True)
    assert vision.bearing(edge, 0.0) == pytest.approx(vision.HFOV_DEG / 2)
    assert vision.bearing(edge, 0.0, hfov=70.0) == pytest.approx(35.0)
    assert math.isclose(vision.bearing(Face(0.25, 0.5, 0.1, 0.1, 0.9, True), 0.0), -vision.bearing(Face(0.75, 0.5, 0.1, 0.1, 0.9, True), 0.0))
