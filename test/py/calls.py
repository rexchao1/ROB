"""Plain HTTP calls for the Python tests (urllib, loopback only)."""

import json
import urllib.error
import urllib.request


def call(base, method, path, body=None, content_type="application/json"):
    """(status, parsed JSON) for one request; an HTTP error status is returned, not raised."""
    data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": content_type})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

