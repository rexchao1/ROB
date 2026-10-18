"""The head's touch pad, as the real robot has it (stackchan-mcp 0.18, measured): only a
whole hand on top registers, the pad stays on seconds after the hand leaves, and when
it clears the robot reports a "stroke" from when the hand left. Body.touched() counts
each touch once: a hand held on the head is one touch, however long the pad stays on."""

from brain.body import Body, BodyError, Gateway


def _calls(fake, tool):
    return [c for c in fake.device.calls if c["tool"] == tool]


class _Clock:
    """A hand-moved clock for the fake's touch pad and the body's reads."""

    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def _rig(fake):
    clock = _Clock()
    fake.device.now = clock
    return Body(Gateway(fake.mcp_url), fake.pcm_url), clock


def _reads(body, clock, until, every=0.5, within=1.5):
    """Read the head every `every` seconds up to `until`; the times a touch counted."""
    hits = []
    while clock.t < until - 1e-9:
        clock.t = round(clock.t + every, 6)
        if body.touched(within, clock.t):
            hits.append(clock.t)
    return hits


def test_one_hand_held_on_the_head_counts_once(fake):
    body, clock = _rig(fake)
    assert _reads(body, clock, 101) == []
    fake.device.touching = True
    assert _reads(body, clock, 104) == [101.5]
    fake.device.touching = False  # the pad stays on until about 106.8
    assert _reads(body, clock, 112) == []
    state = Gateway(fake.mcp_url).call("get_touch_state").data
    assert state["last_event"] == "stroke" and not state["zone0"]  # the hold's own event: not a second touch
    fake.device.touching = True  # a new hold after the pad cleared counts again
    assert _reads(body, clock, 113) == [112.5]
    fake.device.touching = False
    assert _reads(body, clock, 120) == []


def test_a_slow_reader_across_the_pad_clearing_still_counts_once(fake):
    body, clock = _rig(fake)
    fake.device.touching = True
    clock.t += 0.3
    assert body.touched(1.5, clock.t)
    clock.t += 3
    fake.device.touching = False
    assert _reads(body, clock, clock.t + 10, every=1.0) == []


def test_a_brief_retouch_after_the_pad_clears_counts_again(fake):
    # As measured: on 1.5 s, off 0.2 s, on 5 s. A read in the gap sees two touches.
    body, clock = _rig(fake)
    fake.device.PAD_STICKS = 0.0  # this time the pad clears when the hand leaves
    fake.device.touching = True
    assert _reads(body, clock, 101.5, every=0.1) == [100.1]
    fake.device.touching = False
    assert _reads(body, clock, 101.7, every=0.1) == []  # the gap, and the first hold's stroke
    fake.device.touching = True
    assert _reads(body, clock, 106.7, every=0.1) == [101.8]


def test_a_new_event_with_the_pad_clear_counts_once_and_an_old_one_never(fake):
    body, clock = _rig(fake)
    fake.device._touch_event = ("tap", clock.t - 30)  # from before: older than `within`
    assert not body.touched(1.5, clock.t)
    clock.t += 1
    fake.device._touch_event = ("tap", clock.t - 0.2)  # a tap the pads never showed
    assert body.touched(1.5, clock.t)
    clock.t += 1
    assert not body.touched(1.5, clock.t)  # the same event again


def test_setup_turns_the_touch_sensor_on_once(fake):
    fake.device.touch_enabled = False
    body = Body(Gateway(fake.mcp_url), fake.pcm_url)
    body.setup()
    body.setup()
    assert [c["args"] for c in _calls(fake, "set_touch_sensor_enabled")] == [{"enabled": True}]
    assert fake.device.touch_enabled


def test_setup_carries_on_when_the_robot_has_no_touch_sensor_tool(fake, monkeypatch):
    gateway = Gateway(fake.mcp_url)
    real = gateway.call

    def call(name, args=None, timeout=None):
        if name == "set_touch_sensor_enabled":
            raise BodyError("Unknown tool: set_touch_sensor_enabled")
        return real(name, args, timeout)

    monkeypatch.setattr(gateway, "call", call)
    Body(gateway, fake.pcm_url).setup()
    assert _calls(fake, "set_off_timeout") and _calls(fake, "set_blink")
