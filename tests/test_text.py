"""Очищення тексту з чужих бордів: санітайзер HTML, дата фіда, плоский текст."""

from jobradar.core.text import parse_feed_date, sanitize_html, strip_html


class TestSanitizeHtml:
    def test_keeps_safe_tags(self):
        out = sanitize_html("<p>Робота з <strong>Playwright</strong></p>")
        assert "<p>" in out and "<strong>Playwright</strong>" in out

    def test_strips_script(self):
        out = sanitize_html("<p>ок</p><script>alert(1)</script>")
        assert "script" not in out and "alert" not in out

    def test_drops_attributes(self):
        out = sanitize_html('<p class="x" onclick="bad()">текст</p>')
        assert "onclick" not in out and "class" not in out

    def test_escapes_bare_text(self):
        assert "&lt;" in sanitize_html("<p>1 &lt; 2 та a < b</p>")

    def test_empty_input(self):
        assert sanitize_html("") == ""


class TestStripHtml:
    def test_tags_removed_text_kept(self):
        assert "Playwright" in strip_html("<p>Playwright</p>")
        assert "<p>" not in strip_html("<p>Playwright</p>")


class TestParseFeedDate:
    def test_rfc2822_to_iso(self):
        iso = parse_feed_date("Mon, 17 Aug 2026 20:49:31 +0300")
        assert iso.startswith("2026-08-17")  # зведено до UTC-ISO

    def test_empty_on_garbage(self):
        assert parse_feed_date("не дата") == ""
        assert parse_feed_date("") == ""
