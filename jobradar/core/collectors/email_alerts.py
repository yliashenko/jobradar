"""Djinni and LinkedIn email alerts: the script reads one IMAP folder (CLAUDE.md §3).

The boards send alerts to email themselves — this doesn't violate ToS or risk
bans. From a message we extract vacancy links (by id) and the titles next to
them. LinkedIn arrives without a description (the page isn't fetched — rate
limits), the Djinni page is fetched publicly (enrich_djinni). Message parsers are
pure functions over a ready msg, so they're tested on .eml fixtures without network.
"""

import contextlib
import email
import email.header
import imaplib
import logging
import re
import time
from datetime import timedelta
from html.parser import HTMLParser

from jobradar import clock
from jobradar.core.filters import SALARY_RE
from jobradar.core.http import http_get
from jobradar.core.text import strip_html

log = logging.getLogger("jobradar")

DJINNI_JOB_RE = re.compile(r"https?://(?:www\.)?djinni\.co/jobs/(\d+)[^\s\"'<>]*", re.I)
LINKEDIN_JOB_RE = re.compile(
    r"https?://[\w.]*linkedin\.com/(?:comm/)?jobs/view/(\d+)[^\s\"'<>]*", re.I
)


class AnchorCollector(HTMLParser):
    """Collects (href, text) for all <a> in the message."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []
        self._href = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._href = href
                self._buf = []

    def handle_data(self, data):
        if self._href is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            self.anchors.append((self._href, text))
            self._href = None
            self._buf = []


def decode_header_value(value):
    if not value:
        return ""
    parts = email.header.decode_header(value)
    out = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(chunk)
    return "".join(out).strip()


def message_html(msg):
    html_body, text_body = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if part.get_content_disposition() == "attachment":
                continue
            try:
                payload = part.get_payload(decode=True)
            except Exception:
                continue
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if ctype == "text/html" and not html_body:
                html_body = decoded
            elif ctype == "text/plain" and not text_body:
                text_body = decoded
    else:
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True) or b""
        decoded = payload.decode(charset, errors="replace")
        if msg.get_content_type() == "text/html":
            html_body = decoded
        else:
            text_body = decoded
    return html_body, text_body


def extract_jobs_from_message(msg):
    html_body, text_body = message_html(msg)
    anchors = []
    if html_body:
        collector = AnchorCollector()
        try:
            collector.feed(html_body)
            collector.close()
            anchors = collector.anchors
        except Exception as exc:
            log.debug("Failed to parse message HTML: %s", exc)
    combined = html_body + "\n" + text_body

    found = {}

    def register(source, job_id, url, title):
        key = source + ":" + job_id
        title = re.sub(r"\s+", " ", title or "").strip()
        if key not in found or (len(title) > len(found[key]["title"])):
            found[key] = {
                "source": source,
                "url": url,
                "title": title,
                "company": "",
                "salary": "",
                "location": "",
                "description": "",
            }

    for href, text in anchors:
        m = DJINNI_JOB_RE.match(href) or DJINNI_JOB_RE.search(href)
        if m:
            register(
                "djinni", m.group(1), f"https://djinni.co/jobs/{m.group(1)}/", text
            )
            continue
        m = LINKEDIN_JOB_RE.match(href) or LINKEDIN_JOB_RE.search(href)
        if m:
            register(
                "linkedin",
                m.group(1),
                f"https://www.linkedin.com/jobs/view/{m.group(1)}/",
                text,
            )

    for m in DJINNI_JOB_RE.finditer(combined):
        register("djinni", m.group(1), f"https://djinni.co/jobs/{m.group(1)}/", "")
    for m in LINKEDIN_JOB_RE.finditer(combined):
        register(
            "linkedin",
            m.group(1),
            f"https://www.linkedin.com/jobs/view/{m.group(1)}/",
            "",
        )

    plain = strip_html(html_body) if html_body else text_body
    for job in found.values():
        if not job["title"]:
            job["title"] = (
                guess_title_near_link(plain, job["url"]) or "Untitled vacancy"
            )
        job["title"], job["company"] = split_title_company(job["title"])
    return list(found.values())


def guess_title_near_link(plain_text, url):
    job_id = url.rstrip("/").rsplit("/", 1)[-1]
    idx = plain_text.find(job_id)
    if idx == -1:
        return ""
    window = plain_text[max(0, idx - 200) : idx]
    lines = [ln.strip() for ln in window.split("\n") if ln.strip()]
    return lines[-1] if lines else ""


def split_title_company(raw):
    """'Senior QA Engineer at Ciklum' / '... в Ciklum' -> (title, company)."""
    raw = raw.strip(" ·|-— ")
    for sep in (" at ", " в ", " у ", " — ", " · "):
        if sep in raw:
            left, right = raw.split(sep, 1)
            left, right = left.strip(), right.strip()
            if left and right and len(right) < 60:
                return left, right
    return raw, ""


def collect_imap(imap_cfg, fetch_djinni_pages, request_delay, http=None):
    jobs = []
    host = imap_cfg["host"]
    port = int(imap_cfg.get("port", 993))
    folder = imap_cfg.get("folder", "INBOX")
    mark_seen = bool(imap_cfg.get("mark_seen", True))
    lookback_days = int(imap_cfg.get("lookback_days", 3))

    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(imap_cfg["user"], imap_cfg["password"])
    except Exception as exc:
        log.error("IMAP: failed to connect to %s: %s", host, exc)
        return jobs

    try:
        status, _ = conn.select(folder)
        if status != "OK":
            log.error("IMAP: failed to open folder %r", folder)
            return jobs

        since = (clock.now() - timedelta(days=lookback_days)).strftime("%d-%b-%Y")
        criteria = f'(UNSEEN SINCE "{since}")'
        status, data = conn.search(None, criteria)
        if status != "OK":
            log.error("IMAP: search failed (%s)", criteria)
            return jobs

        uids = data[0].split()
        log.info(
            "IMAP: %d unread messages in folder %r over %d days",
            len(uids),
            folder,
            lookback_days,
        )

        for uid in uids:
            fetch_flag = "(RFC822)" if mark_seen else "(BODY.PEEK[])"
            status, payload = conn.fetch(uid, fetch_flag)
            if status != "OK" or not payload or not isinstance(payload[0], tuple):
                continue
            msg = email.message_from_bytes(payload[0][1])
            subject = decode_header_value(msg.get("Subject"))
            found = extract_jobs_from_message(msg)
            log.info("IMAP: message %r -> %d vacancies", subject[:70], len(found))
            jobs.extend(found)
    finally:
        with contextlib.suppress(Exception):
            conn.close()
        with contextlib.suppress(Exception):
            conn.logout()

    if fetch_djinni_pages:
        for job in jobs:
            if job["source"] != "djinni":
                continue
            enrich_djinni(job, http=http)
            time.sleep(request_delay)
    return jobs


def enrich_djinni(job, http=None):
    fetch = http or http_get
    try:
        raw = fetch(job["url"])
    except Exception as exc:
        log.debug("Djinni page unavailable (%s): %s", job["url"], exc)
        return
    text = strip_html(raw)
    text = re.sub(r"\n{2,}", "\n", text)
    job["description"] = text[:6000]
    salary = SALARY_RE.search(text[:1500])
    if salary and not job["salary"]:
        job["salary"] = salary.group(0)
