"""DOU RSS — official feeds (category/exp/remote/search params verified).

A DOU title packs company, salary range, and location into one line
(«Senior QA Engineer в Ciklum, $4000–5000, Київ, віддалено»), so there's a
dedicated title parser here. A feed returns at most 25 records — the only way to
silently lose something (§4), so we put the feed window in hours into report for /runs.
"""

import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from jobradar.core.filters import SALARY_RE
from jobradar.core.http import http_get
from jobradar.core.text import parse_feed_date, sanitize_html, strip_html

log = logging.getLogger("jobradar")

DOU_TITLE_RE = re.compile(
    r"^(?P<title>.+?)\s+в\s+(?P<tail>[^,]+)(?:,\s*(?P<rest>.*))?$"
)


def parse_dou_title(raw_title):
    """'Senior QA Engineer в Ciklum, $4000–5000, Київ, віддалено' -> parts."""
    raw_title = html.unescape(raw_title).strip()
    match = DOU_TITLE_RE.match(raw_title)
    if not match:
        return raw_title, "", "", ""
    title = match.group("title").strip()
    company = match.group("tail").strip()
    rest = (match.group("rest") or "").strip()
    salary = ""
    location_parts = []
    for piece in [p.strip() for p in rest.split(",") if p.strip()]:
        if SALARY_RE.search(piece):
            salary = piece
        else:
            location_parts.append(piece)
    return title, company, salary, ", ".join(location_parts)


def collect_dou(feed_urls, report=None, http=None):
    """report — a list that gets a row appended for EVERY feed, even a dead one.

    Feeds can't be counted by collected records: a feed that returned zero or
    failed would simply vanish from such a count — and that's exactly the case
    we want to see. `http` is injected in tests (RSS fixture, no network).
    """
    fetch = http or http_get
    jobs = []
    for url in feed_urls:
        entry = {"feed": url, "count": 0, "error": ""}
        if report is not None:
            report.append(entry)
        try:
            raw = fetch(url)
        except Exception as exc:
            entry["error"] = str(exc)
            log.warning("DOU feed failed to load (%s): %s", url, exc)
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            entry["error"] = f"failed to parse: {exc}"
            log.warning("DOU feed failed to parse (%s): %s", url, exc)
            continue
        items = root.findall("./channel/item")
        entry["count"] = len(items)
        log.info("DOU %s -> %d records", url, len(items))
        # How many hours of the market the feed window spans. This answers the
        # question «are we losing rows to the cap of 25»: as long as the window
        # is wider than the interval between runs, we're not. Narrowed to the interval — we are.
        stamps = sorted(
            s for s in (parse_feed_date(i.findtext("pubDate")) for i in items) if s
        )
        if len(stamps) > 1:
            try:
                span = datetime.fromisoformat(stamps[-1]) - datetime.fromisoformat(
                    stamps[0]
                )
                entry["window_hours"] = round(span.total_seconds() / 3600.0, 1)
            except ValueError:
                pass
        for item in items:
            link = (item.findtext("link") or "").strip()
            raw_title = (item.findtext("title") or "").strip()
            if not link or not raw_title:
                continue
            title, company, salary, location = parse_dou_title(raw_title)
            raw_description = item.findtext("description") or ""
            jobs.append(
                {
                    "source": "dou",
                    "url": link.split("?")[0],
                    "title": title,
                    "company": company,
                    "salary": salary,
                    "location": location,
                    "description": strip_html(raw_description),
                    "description_html": sanitize_html(raw_description),
                    "published_at": parse_feed_date(item.findtext("pubDate")),
                }
            )
    return jobs
