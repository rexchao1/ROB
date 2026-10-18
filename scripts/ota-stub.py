"""The robot's startup update check, answered locally: "you are current, no activation".

The xiaozhi firmware checks an OTA server after joining Wi-Fi and before it opens
the gateway WebSocket. Its default server (api.tenclass.net) answers an unbound
device with an activation code, and the firmware then loops on activation forever,
never reaching the gateway. Pointing the robot's "Custom OTA URL" at this stub
(http://<this machine>:8768/ota/) skips that. If the stub is down when the robot
boots, the check fails and the firmware retries with growing delays, so keep it
running alongside the gateway. Standard library only.

    python3 scripts/ota-stub.py [--port 8768] [--version 2.2.6]
"""

from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--version", default="2.2.6", help="the firmware version to report as current")
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def answer(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)  # the device's system info; not needed
            body = json.dumps({
                # url present and version equal to the device's: "Current is the latest version"
                "firmware": {"version": args.version, "url": ""},
                "server_time": {"timestamp": int(time.time() * 1000), "timezone_offset": -(time.altzone if time.localtime().tm_isdst else time.timezone) // 60},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = answer

        def log_message(self, fmt: str, *a: object) -> None:
            print(f"{time.strftime('%H:%M:%S')} {self.client_address[0]} {fmt % a}", flush=True)

    print(f"ota stub listening on http://0.0.0.0:{args.port}/ota/", flush=True)
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
