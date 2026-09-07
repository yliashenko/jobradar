"""HTTP transport: a thin wrapper over urllib.

Two functions — GET (text) and POST JSON. Split out so collectors and the scorer
don't duplicate headers and decoding, and tests can swap a single network point.
"""

import contextlib
import json
import urllib.error
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 jobradar/1.0"
)


def http_get(url, timeout=25):
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Language": "uk,en;q=0.8"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def http_post_json(url, payload, headers, timeout=60):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    merged = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    merged.update(headers)
    req = urllib.request.Request(url, data=body, headers=merged, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        # urllib's own message is just "HTTP Error 400: Bad Request" — the reason
        # (a wrong model, an expired key) is only in the body, and swallowing it
        # leaves the log with nothing actionable.
        detail = ""
        with contextlib.suppress(Exception):
            detail = exc.read().decode("utf-8", errors="replace")[:400].strip()
        raise RuntimeError(
            f"HTTP {exc.code} from {url}" + (f": {detail}" if detail else "")
        ) from exc
