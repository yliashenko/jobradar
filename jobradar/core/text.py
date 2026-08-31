"""Cleaning and transforming text that arrives from third-party sites.

A vacancy description is untrusted HTML from another board, so the only safe way
to show it is an allowlist of tags WITHOUT any attribute (no href, no style, no
on*). Also here: flat text for L0/scorer, feed-date parsing, and html-escape.
"""

import email.utils
import html
import logging
import re
from datetime import timezone
from html.parser import HTMLParser

log = logging.getLogger("jobradar")

# Tags kept in the description for display. Everything else is dropped along
# with attributes: the description comes from a third-party site, and the only
# safe way to show it is an allowlist without any attribute (no href, no style, no on*).
SAFE_TAGS = ("p", "br", "ul", "ol", "li", "strong", "b", "em", "i", "h3", "blockquote")

# How many characters of the description we keep. Nobody needs more on a card —
# for the full text there's a button to the source site.
DESCRIPTION_HTML_LIMIT = 8000


class TagStripper(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3"):
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip > 0:
            self.skip -= 1

    def handle_data(self, data):
        if self.skip == 0:
            self.chunks.append(data)

    def text(self):
        raw = "".join(self.chunks)
        raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n", raw)
        return raw.strip()


class HtmlSanitizer(HTMLParser):
    """Keeps structure (paragraphs, lists, emphasis) and drops the rest."""

    def __init__(self, limit=DESCRIPTION_HTML_LIMIT):
        super().__init__(convert_charrefs=True)
        self.limit = limit
        self.out = []
        self.size = 0
        self.skip = 0
        self.stack = []
        self.truncated = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
            return
        if self.truncated or tag not in SAFE_TAGS:
            return
        if tag == "br":
            self.out.append("<br>")
        else:
            self.out.append(f"<{tag}>")
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and not self.truncated:
            self.out.append("<br>")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
            return
        if tag not in SAFE_TAGS or tag == "br" or tag not in self.stack:
            return
        # Unwind the stack down to the wanted tag: foreign markup often leaves
        # elements unclosed, and without this they'd bleed across the whole page.
        while self.stack:
            top = self.stack.pop()
            self.out.append(f"</{top}>")
            if top == tag:
                break

    def handle_data(self, data):
        if self.skip or self.truncated or not data:
            return
        room = self.limit - self.size
        if room <= 0:
            self.truncated = True
            self.out.append(" …")
            return
        chunk = data[:room]
        self.size += len(chunk)
        self.out.append(html.escape(chunk, quote=False))
        if len(data) > room:
            self.truncated = True
            self.out.append(" …")

    def result(self):
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return re.sub(r"(<p></p>|<li></li>)", "", "".join(self.out)).strip()


def sanitize_html(raw):
    """HTML from a feed → safe HTML for display. Empty if nothing remains."""
    if not raw:
        return ""
    parser = HtmlSanitizer()
    try:
        parser.feed(raw)
        parser.close()
    except Exception as exc:
        log.warning("Description didn't sanitize, leaving without markup: %s", exc)
        return ""
    return parser.result()


def parse_feed_date(raw):
    """RFC-2822 from pubDate → ISO. Empty if there's no date or it's broken."""
    if not raw:
        return ""
    try:
        moment = email.utils.parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError):
        return ""
    if moment is None:
        return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def strip_html(raw):
    if not raw:
        return ""
    parser = TagStripper()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        return re.sub(r"<[^>]+>", " ", raw)
    return parser.text()


def escape(value):
    return html.escape(value or "", quote=False)
