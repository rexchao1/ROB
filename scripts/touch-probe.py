"""Watch the robot's head-touch sensor live: prints each change in the three pads and
every new tap or stroke the robot reports. Ctrl-C stops.

    .venv/bin/python scripts/touch-probe.py [--gateway URL] [--every SECONDS] [--enable]

--enable turns the sensor on first (the setting is kept on the robot across restarts).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from brain.body import BodyError, Gateway  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gateway", default="http://127.0.0.1:8767/mcp")
    ap.add_argument("--token", default=os.environ.get("STACKCHAN_TOKEN"))
    ap.add_argument("--every", type=float, default=0.05)
    ap.add_argument("--enable", action="store_true")
    args = ap.parse_args()
    gw = Gateway(args.gateway, args.token)
    for tool, call_args in (("get_touch_sensor_enabled", {}),) + ((("set_touch_sensor_enabled", {"enabled": True}),) if args.enable else ()):
        try:
            print(f"{tool}: {gw.call(tool, call_args).data}")
        except BodyError as e:
            print(f"{tool}: {e}")
    print("touch the head; Ctrl-C stops")
    start = time.monotonic()
    last_pads = None
    last_event_at = None
    while True:
        try:
            d = gw.call("get_touch_state").data
        except BodyError as e:
            print(f"get_touch_state: {e}")
            time.sleep(1)
            continue
        t = time.monotonic() - start
        pads = "".join("X" if d.get(f"zone{i}") else "." for i in range(3))
        if pads != last_pads:
            print(f"{t:7.2f}s  pads {pads}  raw {d.get('raw')}")
            last_pads = pads
        age = d.get("last_event_age_ms")
        if d.get("last_event") not in (None, "idle") and isinstance(age, (int, float)) and age >= 0:
            at = t - age / 1000
            if last_event_at is None or abs(at - last_event_at) > 0.2:
                print(f"{t:7.2f}s  event {d.get('last_event')} ({age} ms ago)  {d}")
                last_event_at = at
        time.sleep(args.every)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
