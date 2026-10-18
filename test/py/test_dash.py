"""The operator dashboard's API (brain/dash.py behind brain/server.py's /dash/api/*): what
the host said and heard comes back as events, typed hearing reaches the rules as a
voice would, and settings and content apply live. A test-mode brain never reads or
writes the operator's settings file."""

import json
import time
import urllib.error
import urllib.request

import pytest
from calls import call
from conftest import dash

from brain import games, lines, settings, vision
from brain.__main__ import TEST_DASH_KEY
from brain.dash import SETTINGS_FILE

FIVE = [{"bearing": b} for b in (-60, -30, 0, 30, 60)]


def _said(fake):
    return [c.get("line") for c in fake.device.calls if c["tool"] == "pcm" and c.get("error") is None]


def _until(check, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return False


def _raw(url, method="GET", headers=None):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, res.headers, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


@pytest.fixture
def restore():
    """Put back the module-level values a settings or content change sets."""
    saved = (vision.SCORE_MIN, vision.CLOSE_WIDTH, vision.SWEEP_STEP_DEG, lines.IMPOSTER_WORDS, lines.SPECTRA)
    existed = SETTINGS_FILE.exists()
    yield
    vision.SCORE_MIN, vision.CLOSE_WIDTH, vision.SWEEP_STEP_DEG, lines.IMPOSTER_WORDS, lines.SPECTRA = saved
    if vision._detector is not None:
        vision._detector.setScoreThreshold(vision.SCORE_MIN)
    assert SETTINGS_FILE.exists() == existed  # a test brain never writes the operator's file


def test_state_reports_the_mode_the_referee_and_no_photo_yet(brain):
    status, state = call(brain.url, "GET", "/dash/api/state")
    assert status == 200
    assert state["game"] == {"game": None} and state["mode"] == "test" and state["referee"] == "local"
    assert state["photo"] is None and state["typed_pending"] == 0 and state["yaw"] == 0.0


def test_what_the_host_says_and_hears_comes_back_as_events_after_an_id(brain, fake):
    call(brain.url, "POST", "/test/hear", {"text": "Hello there"})
    call(brain.url, "POST", "/test/advance", {"seconds": 5})
    status, answer = dash(brain.url, "POST", "/dash/api/say", {"text": "Welcome to the table."})
    assert (status, answer) == (200, {"ok": True})
    assert _until(lambda: "Welcome to the table." in _said(fake))
    _, got = dash(brain.url, "GET", "/dash/api/events?since=0")
    kinds = [(e["kind"], e["text"]) for e in got["events"]]
    assert ("heard", "hello there") in kinds and ("say", "Welcome to the table.") in kinds
    ids = [e["id"] for e in got["events"]]
    assert ids == sorted(ids) and got["next"] == ids[-1]
    assert dash(brain.url, "GET", f"/dash/api/events?since={ids[-1]}")[1]["events"] == []
    assert dash(brain.url, "POST", "/dash/api/say", {"text": "  "})[0] == 400
    assert dash(brain.url, "GET", "/dash/api/events?since=x")[0] == 400


def test_typed_hearing_starts_a_game_as_a_voice_would(brain, fake):
    call(brain.url, "POST", "/test/table", {"faces": FIVE})
    assert dash(brain.url, "POST", "/dash/api/game", {"name": "mafia"}) == (200, {"ok": True, "pending": 1})
    assert call(brain.url, "GET", "/dash/api/state")[1]["typed_pending"] == 1
    call(brain.url, "POST", "/test/advance", {"seconds": 20})
    state = call(brain.url, "GET", "/dash/api/state")[1]
    assert state["typed_pending"] == 0 and state["game"]["game"] == "mafia" and len(state["seats"]) == 5
    assert _said(fake)[0].startswith("Five of you.")
    kinds = [(e["kind"], e["text"]) for e in dash(brain.url, "GET", "/dash/api/events")[1]["events"]]
    assert ("typed", "let's play mafia") in kinds and ("game", "game: mafia") in kinds
    assert "listen" not in [c["tool"] for c in fake.device.calls][:6]  # the typed text, not the microphone
    assert dash(brain.url, "POST", "/dash/api/game", {"name": "chess"})[0] == 400
    assert dash(brain.url, "POST", "/dash/api/hear", {"text": "stop the game"}) == (200, {"ok": True, "pending": 1})


def test_the_photo_is_missing_until_the_host_takes_one_then_a_jpeg_with_its_faces(brain):
    status, headers, _ = _raw(brain.url + "/dash/api/photo?key=" + TEST_DASH_KEY)
    assert status == 404
    call(brain.url, "POST", "/test/table", {"faces": FIVE})
    dash(brain.url, "POST", "/dash/api/game", {"name": "imposter"})
    call(brain.url, "POST", "/test/advance", {"seconds": 20})
    status, headers, data = _raw(brain.url + "/dash/api/photo?key=" + TEST_DASH_KEY)
    assert status == 200 and headers["Content-Type"] == "image/jpeg" and data[:2] == b"\xff\xd8"
    assert "Access-Control-Allow-Origin" not in headers  # no origin asked: none answered
    assert _raw(brain.url + "/dash/api/photo")[0] == 403  # the camera leaves the machine for the page only (D86)
    photo = call(brain.url, "GET", "/dash/api/state")[1]["photo"]
    assert photo["id"] > 1 and photo["faces"] and set(photo["faces"][0]) == {"cx", "cy", "w", "h", "score", "close"}


def test_settings_apply_live_round_trip_and_refuse_bad_values(brain, restore):
    status, got = call(brain.url, "GET", "/dash/api/settings")
    assert status == 200
    keys = [s["key"] for s in got["schema"]]
    assert keys == ["pitch", "hfov", "sweep_step", "score_min", "close_width", "listen_window", "day_seconds", "vote_seconds", "whisper_seconds", "clue_seconds", "banter"]
    assert {s["group"] for s in got["schema"]} == {"Camera", "Head", "Timing", "Voice"}
    change = {"pitch": 30, "hfov": 70, "score_min": 0.6, "close_width": 0.3, "listen_window": 6, "day_seconds": 60, "vote_seconds": 5, "banter": False}
    status, got = dash(brain.url, "POST", "/dash/api/settings", change)
    assert status == 200 and all(got["values"][k] == v for k, v in change.items())
    host = brain.host
    assert host.body.pitch == 30 and host.hfov == 70 and host.listen_window == 6
    assert vision.SCORE_MIN == 0.6 and vision.CLOSE_WIDTH == 0.3
    assert host.options.day_seconds == 60 and host.options.vote_seconds == 5 and host.options.clue_seconds == 6
    assert call(brain.url, "GET", "/dash/api/settings")[1]["values"] == got["values"]
    for bad in ({"pitch": 90}, {"hfov": "70"}, {"banter": 1}, {"day_seconds": True}, {"volume": 3}, {"pitch": 20, "hfov": 5}):
        assert dash(brain.url, "POST", "/dash/api/settings", bad)[0] == 400
    assert host.body.pitch == 30  # a bad batch applies nothing


def test_the_scan_step_sets_how_many_photos_a_count_takes(brain, fake, restore):
    got = call(brain.url, "GET", "/dash/api/settings")[1]
    assert got["values"]["sweep_step"] == 12 and got["photos"] == 16  # unset: the default glide, 12 degrees
    got = dash(brain.url, "POST", "/dash/api/settings", {"sweep_step": 30})[1]
    assert got["values"]["sweep_step"] == 30 and got["photos"] == 7
    assert vision.sweep_pans() == [-90, -60, -30, 0, 30, 60, 90]
    for bad in ({"sweep_step": 5}, {"sweep_step": 50}):
        assert dash(brain.url, "POST", "/dash/api/settings", bad)[0] == 400
    call(brain.url, "POST", "/test/table", {"faces": FIVE})
    dash(brain.url, "POST", "/dash/api/game", {"name": "imposter"})
    call(brain.url, "POST", "/test/advance", {"seconds": 20})
    assert len([c for c in fake.device.calls if c["tool"] == "take_photo"]) >= 7
    assert len(call(brain.url, "GET", "/dash/api/state")[1]["seats"]) == 5


def test_content_round_trips_and_the_next_game_uses_it(brain, restore):
    status, got = call(brain.url, "GET", "/dash/api/content")
    assert status == 200 and got == {"imposter_words": list(lines.IMPOSTER_WORDS), "spectra": list(lines.SPECTRA)}
    status, got = dash(brain.url, "POST", "/dash/api/content", {"imposter_words": ["lighthouse", " zoo "]})
    assert status == 200 and got["imposter_words"] == ["lighthouse", "zoo"]
    assert lines.IMPOSTER_WORDS == ("lighthouse", "zoo")
    assert dash(brain.url, "POST", "/dash/api/content", {"spectra": ["dry - wet"]})[1]["spectra"] == ["dry - wet"]
    for bad in ({"imposter_words": []}, {"imposter_words": ["ok", 3]}, {"spectra": ["hot"]}, {"words": ["x"]}):
        assert dash(brain.url, "POST", "/dash/api/content", bad)[0] == 400
    assert lines.SPECTRA == ("dry - wet",)


def test_a_rig_waits_for_the_next_game(brain):
    rig = {"imposter": {"word": "beach", "imposter": 3}}
    assert call(brain.url, "GET", "/dash/api/rig") == (200, {})
    assert dash(brain.url, "POST", "/dash/api/rig", rig) == (200, rig)
    assert brain.host.rigs == rig
    assert dash(brain.url, "POST", "/dash/api/rig", {"imposter": 3})[0] == 400
    assert dash(brain.url, "POST", "/dash/api/rig", {"chess": {}})[0] == 400


def test_the_head_moves_where_the_operator_says(brain, fake):
    assert dash(brain.url, "POST", "/dash/api/head", {"yaw": 40, "pitch": 35}) == (200, {"yaw": 40.0, "pitch": 35})
    move = [c for c in fake.device.calls if c["tool"] == "move_head"][-1]
    assert move["args"]["yaw"] == 40 and move["args"]["pitch"] == 35
    assert brain.host.yaw == 40.0
    assert dash(brain.url, "POST", "/dash/api/head", {"yaw": 120})[0] == 400
    assert dash(brain.url, "POST", "/dash/api/head", {"pitch": 2})[0] == 400


def test_the_page_and_its_cors_preflight_answer_the_pages_own_origin_only(brain):
    """D86: no Access-Control-Allow-Origin: * anywhere; the page's own origin or nothing."""
    status, headers, _ = _raw(brain.url + "/dash")
    assert status in (200, 404)
    if status == 200:
        assert headers["Content-Type"].startswith("text/html")
    status, headers, _ = _raw(brain.url + "/dash/api/settings", "OPTIONS")
    assert status == 204 and "Access-Control-Allow-Origin" not in headers
    assert "X-Dash-Key" in headers["Access-Control-Allow-Headers"]
    status, headers, _ = _raw(brain.url + "/dash/api/settings", "OPTIONS", {"Origin": brain.url})
    assert status == 204 and headers["Access-Control-Allow-Origin"] == brain.url and headers["Vary"] == "Origin"
    for origin in ("https://evil.example", "http://127.0.0.1:1", "null"):
        for method in ("OPTIONS", "GET"):
            status, headers, _ = _raw(brain.url + "/dash/api/settings", method, {"Origin": origin})
            assert status in (200, 204) and "Access-Control-Allow-Origin" not in headers, (origin, method)
    status, headers, _ = _raw(brain.url + "/dash/api/state", headers={"Origin": brain.url})
    assert status == 200 and headers["Access-Control-Allow-Origin"] == brain.url


def test_a_setting_changed_on_the_page_reaches_the_next_idle_listen_and_the_next_game(brain, fake, restore, monkeypatch):
    """D1: the lobby reads the host's options and window at each listen and each game."""
    call(brain.url, "POST", "/test/advance", {"seconds": 5})
    assert [c["args"]["duration_ms"] for c in fake.device.calls if c["tool"] == "listen"] == [4000]
    assert dash(brain.url, "POST", "/dash/api/settings", {"listen_window": 6, "day_seconds": 60})[0] == 200
    call(brain.url, "POST", "/test/advance", {"seconds": 10})  # the window running (4 s) ends, then one of the new length
    assert [c["args"]["duration_ms"] for c in fake.device.calls if c["tool"] == "listen"] == [4000, 4000, 6000]
    seen = []
    monkeypatch.setattr(games, "play", lambda name, table, rng, **kw: seen.append(kw["options"]))
    dash(brain.url, "POST", "/dash/api/game", {"name": "mafia"})
    call(brain.url, "POST", "/test/advance", {"seconds": 15})  # the window running ends; the next hears the typed name
    assert len(seen) == 1 and seen[0].day_seconds == 60 and seen[0] is brain.host.options


def test_the_head_is_refused_while_the_host_counts_or_deals(brain, fake):
    """D2: a head move from the page while the sweep attributes faces to the host's yaw
    would land the seats at the wrong bearings; it is refused with 409."""
    call(brain.url, "POST", "/test/table", {"faces": FIVE})
    dash(brain.url, "POST", "/dash/api/game", {"name": "mafia"})
    call(brain.url, "POST", "/test/advance", {"seconds": 5})  # the typed name heard at 4.15; the sweep is on its first photos
    assert brain.host.busy
    assert dash(brain.url, "POST", "/dash/api/head", {"yaw": 40}) == (409, {"error": "the host is counting"})
    assert 40 not in [c["args"]["yaw"] for c in fake.device.calls if c["tool"] == "move_head"]
    for _ in range(30):  # the count ends, the count line, then the deal: the first lean-in awaited
        call(brain.url, "POST", "/test/advance", {"seconds": 1})
        if "Player one, lean in." in _said(fake):
            break
    assert brain.host.busy and brain.host.state["seats"] == 5
    assert dash(brain.url, "POST", "/dash/api/head", {"yaw": 40})[0] == 409
    call(brain.url, "POST", "/test/reset")
    assert not brain.host.busy
    assert dash(brain.url, "POST", "/dash/api/head", {"yaw": 40})[0] == 200


def test_the_dashboards_settings_refuse_odd_values_with_400_and_key_shaped_models(brain):
    for bad in ({"persona": ["host"]}, {"persona": {"key": "host"}}, {"talk": 3}, {"voice": None}, {"eleven_voice": ["x"]},
                {"talk_model": ["claude"]}, {"talk_model": {"m": 1}}, {"talk_model": "sk_abcDEF123456"}, {"talk_model": "sk-ant-api03-x"},
                {"talk_model": "AIzaSyD-example"}, {"talk_model": "0123456789abcdef0123456789abcdef"}, {"talk_model": "claude haiku"}):
        status, answer = dash(brain.url, "POST", "/dashboard/settings", bad)
        assert status == 400 and "error" in answer, (bad, status, answer)
    before = settings.snapshot()
    try:
        assert dash(brain.url, "POST", "/dashboard/settings", {"talk_model": "claude-haiku-5-5"})[1]["talk_model"] == "claude-haiku-5-5"
        assert dash(brain.url, "POST", "/dashboard/settings", {"talk_model": ""})[1]["talk_model"] is None
    finally:
        settings.update(**before)


def test_the_saved_personality_file_is_checked_before_it_is_believed(tmp_path):
    before, file_before = settings.snapshot(), settings.file
    try:
        path = tmp_path / "rob.json"
        path.write_text(json.dumps({"persona": ["evil"], "eleven_voice": 42, "talk_model": "sk-not-saved", "voice": "gramophone"}))
        settings.load(path)
        assert settings.snapshot() == before  # nothing of it believed
        path.write_text(json.dumps({"persona": "roaster", "eleven_voice": None}))
        settings.load(path)
        assert settings.snapshot()["persona"] == "roaster" and settings.snapshot()["eleven_voice"] is None
        path.write_text(json.dumps({"persona": "nobody", "eleven_voice": "nobody"}))
        settings.load(path)
        assert settings.snapshot()["persona"] == "roaster"
    finally:
        settings.file = None
        settings.update(**before)
        settings.file = file_before


def test_backdrops_come_from_the_art_folder_and_nowhere_else(brain, tmp_path, monkeypatch):
    from brain import server

    (tmp_path / "mafia-night.jpg").write_bytes(b"\xff\xd8 not really a jpeg")
    monkeypatch.setattr(server, "ART", tmp_path)
    status, headers, body = _raw(brain.url + "/dash/art/mafia-night.jpg")
    assert status == 200 and headers["Content-Type"] == "image/jpeg" and body.startswith(b"\xff\xd8")
    for name in ("missing.jpg", "..%2Findex.html", "CREDITS.md", "alt/mafia-night-2.jpg"):
        assert _raw(brain.url + "/dash/art/" + name)[0] == 404
