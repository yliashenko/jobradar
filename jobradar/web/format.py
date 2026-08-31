"""Value formatters: time, scores, human-readable filter reasons, paragraphs.

The 'value → string' layer, almost no HTML. The exception is
paragraphs_from_text (flat description → <p>/<ul> for records without
description_html and for email), which builds escaped markup.
"""

import json
import re
from datetime import datetime, timezone

import mistune
from markupsafe import Markup, escape

from jobradar import runner
from jobradar.core.text import DESCRIPTION_HTML_LIMIT
from jobradar.web.constants import BAND_LABELS

BULLET_RE = re.compile(r"^\s*[-—–•*·]\s+")

# escape=True neutralises any raw HTML the model emits (it only ever means to send
# markdown); the table plugin renders the cover letter's requirement matrix.
_MD = mistune.create_markdown(escape=True, plugins=["table", "strikethrough"])


def render_markdown(text) -> Markup:
    """Markdown → HTML for the cover-letter fit evaluation / traceability preview.

    Empty in → empty out, so the fold's :empty rule can hide a blank block.
    """
    text = (text or "").strip()
    return Markup(_MD(text)) if text else Markup("")


def band_class(row):
    band = row["band"] if row["band"] in BAND_LABELS else ""
    return band or ("none" if row["score"] is None else "skip")


def score_text(row):
    if row["score"] is None:
        return "—"
    return f"{row['score']:g}"


def parse_points(raw):
    try:
        items = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return []
    return [str(x) for x in items if str(x).strip()]


def fmt_iso(raw, fmt="%d.%m %H:%M"):
    """ISO timestamp from the DB (UTC) → local time. Empty if it doesn't parse."""
    try:
        moment = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone().strftime(fmt)


def fmt_epoch(value, fmt="%H:%M:%S"):
    if not value:
        return ""
    return datetime.fromtimestamp(float(value)).strftime(fmt)


def row_get(row, key, default=""):
    """A field that may be missing from an older record."""
    try:
        value = row[key]
    except (IndexError, KeyError):
        return default
    return default if value is None else value


def row_text(row):
    """Vacancy text for tag matching. Flat description isn't always there (email),
    markup isn't either (old records) — take what exists. One function for both
    the card tags and the filter, so a tag on a card and in the filter mean the same."""
    plain = row_get(row, "description") or re.sub(
        r"<[^>]+>", " ", str(row_get(row, "description_html"))
    )
    return f"{row_get(row, 'title')} {plain}"


def paragraphs_from_text(text, limit=DESCRIPTION_HTML_LIMIT):
    """Flat description → paragraphs and lists. Fallback for records collected
    before description_html existed, and for email (no markup at all)."""
    content = (text or "")[:limit]
    out, bullets = [], []

    def flush():
        if bullets:
            lis = "".join(f"<li>{escape(b)}</li>" for b in bullets)
            out.append(f"<ul>{lis}</ul>")
            bullets.clear()

    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        if BULLET_RE.match(line):
            bullets.append(BULLET_RE.sub("", line))
        else:
            flush()
            out.append(f"<p>{escape(line)}</p>")
    flush()
    return "".join(out)


def humanize_pattern(pattern):
    """Regex from config.json → the words it catches. The DB keeps the machine
    reason (what actually fired and what to edit in config); people see words."""
    text = str(pattern or "")
    text = re.sub(r"\(\?i\)|\\b", "", text)
    text = re.sub(r"\\s[+*]?", " ", text)  # \s+ is a space, not emptiness
    text = text.replace("\\", "").replace("|", " / ")
    text = re.sub(r"\s+", " ", text).strip()
    # Keep brackets: in "(a|b|c)-based only" they're the only thing showing what
    # the suffix belongs to. Drop them only when they wrap the whole thing.
    if text.startswith("(") and text.endswith(")") and "(" not in text[1:-1]:
        text = text[1:-1].strip()
    return text or str(pattern)


def humanize_l0_reason(reason):
    """The drop reason in the words a person thinks about it."""
    raw = str(reason or "")
    if raw.startswith("title matched exclude:"):
        return f"banned word in the title: {humanize_pattern(raw.split(':', 1)[1])}"
    if raw.startswith("text matched exclude:"):
        return f"banned condition in the text: {humanize_pattern(raw.split(':', 1)[1])}"
    if "require_any_text" in raw:
        return (
            "no QA word in the text — this vacancy doesn't look like it's about testing"
        )
    if raw.startswith("salary cap"):
        return raw
    return raw or "no reason"


def humanize_feed_error(raw):
    """A feed error in human terms; text from the network is often long and machine."""
    return runner.describe_error(Exception(str(raw or "")))


def feed_label(url):
    """Long feed URL → what distinguishes it from its neighbours."""
    text = str(url or "")
    if "?" in text and "dou.ua" in text:
        return "DOU " + text.split("?", 1)[1].replace("&", " ")
    return text


def duration_text(started, finished):
    try:
        delta = datetime.fromisoformat(finished) - datetime.fromisoformat(started)
    except (TypeError, ValueError):
        return ""
    return f"{max(0, int(delta.total_seconds()))} s"
