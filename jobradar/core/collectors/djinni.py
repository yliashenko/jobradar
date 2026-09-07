"""Djinni — official RSS + enrichment of details by id via /api/jobs/.

Djinni's RSS gives only the title (no company/salary range/location — verified
live 18.08.2026), so details are fetched by id from its SPA's undocumented API
(a backend, not a contract). The API is fail-safe: any error → empty map,
collection falls back to RSS. The same vacancy can arrive from DOU and Djinni
twice — a deliberate boundary (§4): better extra than a miss.
"""

import json
import logging
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

from jobradar.core.http import http_get
from jobradar.core.text import parse_feed_date, sanitize_html, strip_html

log = logging.getLogger("jobradar")

DJINNI_API = "https://djinni.co/api/jobs/"

# An RSS primary_keyword Djinni doesn't recognize is not an error: the feed
# answers 200 with the WHOLE board (verified 07.09.2026 — a nonsense keyword and
# "Automation QA" return byte-identical listings of media buyers and PMs). The
# only signal is that those ids are absent from the same keyword's API category:
# a real keyword overlaps ~100%, an ignored one ~4%. Below this share we treat
# the filter as ignored and drop the feed rather than pour a whole job board
# into the pipeline.
KEYWORD_MIN_OVERLAP = 0.5


def _djinni_salary(j):
    lo, hi = j.get("public_salary_min"), j.get("public_salary_max")
    if lo and hi:
        return f"${lo}–{hi}"
    if lo:
        return f"${lo}+"
    if hi:
        return f"up to ${hi}"
    return ""


def djinni_api_details(keyword, request_delay=1.0, cap=200, http=None):
    """id → structured fields from /api/jobs/ (company, experience, English,
    format, domain, salary range). Enrichment model from docs/PRODUCT.md §6:
    «discovery via RSS + details by id via API». `http` is injected in tests.
    """
    fetch = http or http_get
    out = {}
    try:
        offset = 0
        while offset < cap:
            url = f"{DJINNI_API}?category={urllib.parse.quote(keyword)}&offset={offset}"
            data = json.loads(fetch(url))
            results = data.get("results") or []
            if not results:
                break
            for j in results:
                jid = j.get("id")
                if jid is None:
                    continue
                eng = j.get("english") or {}
                out[str(jid)] = {
                    "company": j.get("company_name") or "",
                    "salary": _djinni_salary(j),
                    "location": j.get("location") or "",
                    "experience": j.get("experience"),
                    "english": (eng.get("name") if isinstance(eng, dict) else eng)
                    or "",
                    "work_format": j.get("work_format") or "",
                    "domain": j.get("domain") or "",
                }
            offset += data.get("limit", 10)
            if offset >= (data.get("count") or 0):
                break
            time.sleep(request_delay)
    except Exception as exc:
        log.warning("Djinni API enrichment failed (%s), keeping RSS: %s", keyword, exc)
    return out


def _item_id(item):
    found = re.search(r"/jobs/(\d+)", (item.findtext("link") or "").strip())
    return found.group(1) if found else ""


def _keyword_ignored(items, details):
    """True when the RSS items are mostly NOT in the API category of the same
    keyword — i.e. Djinni served the unfiltered board instead of the filter."""
    ids = [i for i in (_item_id(it) for it in items) if i]
    if not ids:
        return False
    hits = sum(1 for i in ids if i in details)
    return (hits / len(ids)) < KEYWORD_MIN_OVERLAP


def collect_djinni(feed_urls, report=None, request_delay=1.0, enrich=True, http=None):
    """Djinni via the OFFICIAL RSS (/jobs/rss/?primary_keyword=…), not scraping.

    In the Djinni feed the title is only the position, without company, so
    company stays empty and dedup merges by URL. Salary and location aren't in
    the feed either — we pull them (and structured fields) by id from the API, if enrich is on.
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
            log.warning("Djinni feed failed to load (%s): %s", url, exc)
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            entry["error"] = f"failed to parse: {exc}"
            log.warning("Djinni feed failed to parse (%s): %s", url, exc)
            continue
        items = root.findall("./channel/item")
        entry["count"] = len(items)
        log.info("Djinni %s -> %d records", url, len(items))
        # Details by id from the API (company/salary range/experience/English/format/domain).
        km = re.search(r"primary_keyword=([^&]+)", url)
        details = (
            djinni_api_details(
                urllib.parse.unquote(km.group(1)), request_delay, http=http
            )
            if (enrich and km)
            else {}
        )
        if details and _keyword_ignored(items, details):
            # No extra request: the overlap falls out of the enrichment map we
            # already have. An empty map means the API itself is down — then we
            # decide nothing and keep the RSS rows, as before.
            entry["error"] = "Djinni ignored primary_keyword — returned the whole board"
            entry["count"] = 0
            log.warning(
                "Djinni ignored the keyword in %s — the feed returns the whole board, skipping",
                url,
            )
            continue
        for item in items:
            link = (item.findtext("link") or "").strip()
            title = (item.findtext("title") or "").strip()
            if not link or not title:
                continue
            raw_description = item.findtext("description") or ""
            jid = re.search(r"/jobs/(\d+)", link)
            d = details.get(jid.group(1), {}) if jid else {}
            # Djinni-specific fields go into one JSON column, extra; on a DOU card
            # it's empty and not shown.
            extra = {
                k: d[k]
                for k in ("experience", "english", "work_format", "domain")
                if d.get(k)
            }
            jobs.append(
                {
                    "source": "djinni",
                    "url": link.split("?")[0],
                    "title": title,
                    "company": d.get("company", ""),
                    "salary": d.get("salary", ""),
                    "location": d.get("location", ""),
                    "description": strip_html(raw_description),
                    "description_html": sanitize_html(raw_description),
                    "published_at": parse_feed_date(item.findtext("pubDate")),
                    "extra": json.dumps(extra, ensure_ascii=False) if extra else "",
                }
            )
    return jobs
