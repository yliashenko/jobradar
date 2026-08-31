"""Jinja filters and globals.

Registers the pure value-formatters (web.format), URL builders (web.urls), and
shared constants (web.constants) for use in templates, plus a few card helpers
(description highlighting, source logos, tags). Nothing here produces page
markup — that lives in templates.
"""

import json
import os
import urllib.parse

from markupsafe import Markup, escape

from jobradar import paths, skills
from jobradar.web.constants import (
    ACCOUNT_ICON,
    BAND_LABELS,
    COVER_JS,
    HIRING_JS,
    HIRING_LABELS,
    HIRING_ORDER,
    POPUP_JS,
    RADAR_ICON,
    SOURCE_LOGOS,
    STATUS_LABELS,
    STATUS_ORDER,
    TAG_HINTS,
)
from jobradar.web.format import (
    band_class,
    duration_text,
    feed_label,
    fmt_epoch,
    fmt_iso,
    humanize_feed_error,
    humanize_l0_reason,
    humanize_pattern,
    paragraphs_from_text,
    parse_points,
    render_markdown,
    row_get,
    row_text,
    score_text,
)
from jobradar.web.urls import (
    build_query,
    calendar_link,
    co_sets,
    company_link,
    feed_link,
    page_link,
    profile_link,
    tech_drop_href,
    tech_href,
    tech_sets,
    tech_state,
    tech_url,
)


def mark_skills(text) -> Markup:
    """Underline recognized stack terms in short scorer text (verdict, covers, gaps).

    Escape first, then run the same term-matcher the description uses (without a
    link) — so the popup and the description never disagree on what a skill is.
    """
    if not text:
        return Markup("")
    return Markup(skills.highlight_html(str(escape(text))))


_FILTERS = {
    "band_class": band_class,
    "score_text": score_text,
    "mark_skills": mark_skills,
    "fmt_iso": fmt_iso,
    "fmt_epoch": fmt_epoch,
    "humanize_l0_reason": humanize_l0_reason,
    "humanize_feed_error": humanize_feed_error,
    "humanize_pattern": humanize_pattern,
    "feed_label": feed_label,
    "duration_text": duration_text,
    "group_label": skills.group_label,
    "md": render_markdown,
}


def home_href(params) -> str:
    token = (params or {}).get("token", "")
    return "/" + (("?token=" + urllib.parse.quote(token)) if token else "")


def _logo_src(name) -> str:
    """Logo URL versioned by file mtime, so a replaced image busts the cache."""
    try:
        ver = int(os.path.getmtime(os.path.join(paths.resources_dir(), name)))
    except OSError:
        return f"/resources/{name}"
    return f"/resources/{name}?v={ver}"


def description(row, params) -> Markup:
    """Card description: sanitized HTML from the DB, else formatted plain text,
    with stack terms highlighted at render time (the skills dictionary still moves)."""

    def link(term):
        return tech_href(term, params)

    markup = str(row_get(row, "description_html")).strip()
    if markup:
        return Markup(skills.highlight_html(markup, link))
    plain = paragraphs_from_text(row_get(row, "description"))
    if plain:
        return Markup(skills.highlight_html(plain, link))
    return Markup(
        '<p class="none">No description in the source. '
        "Hit «open» — the full text is on the site.</p>"
    )


def card_tags(row) -> dict:
    shown, hidden = skills.card_terms(row_text(row))
    return {"shown": shown, "hidden": hidden}


def extra_chips(row) -> list:
    """Djinni structured fields as chips: English → experience → format → domain."""
    try:
        data = json.loads(row_get(row, "extra") or "{}")
    except (ValueError, TypeError):
        data = {}
    chips = []
    if data.get("english"):
        chips.append(f"English {data['english']}")
    if data.get("experience") is not None:
        chips.append(f"experience {data['experience']} yr")
    if data.get("work_format"):
        chips.append(str(data["work_format"]))
    if data.get("domain"):
        chips.append(str(data["domain"]))
    return chips


def source_links(row) -> list:
    """The vacancy's source(s): each links to the posting; cross-posts show several."""
    smap = {}
    raw_sources = row_get(row, "sources")
    if raw_sources:
        try:
            smap = json.loads(raw_sources)
        except (ValueError, TypeError):
            smap = {}
    if not smap:
        smap = {row_get(row, "source"): row_get(row, "url")}
    out = []
    for src, url in smap.items():
        logo = SOURCE_LOGOS.get(src)
        out.append({"src": src, "url": url, "logo": _logo_src(logo) if logo else None})
    return out


def hiring_notes(row) -> dict:
    """Per-stage notes for an applied vacancy: {stage: text}. Stored as JSON in
    jobs.hiring_notes; empty or malformed → {}."""
    raw = row_get(row, "hiring_notes")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def hiring_sel(row) -> str:
    """The stage the notes textarea edits: the current hiring_status, or the
    first stage before any is picked."""
    return row_get(row, "hiring_status") or HIRING_ORDER[0]


def hiring_cover(row) -> dict:
    """The saved cover-letter generation for an applied vacancy: the parsed
    jobs.cover_data JSON (letter, evaluation, traceability, fit_score, band), or
    {} when none has been generated yet or the JSON is malformed."""
    raw = row_get(row, "cover_data")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


# Fit bands from the cover-letter evaluation (fit-score.md). A separate scale from
# the scorer's bands, so it gets its own class rather than reusing band_class.
_COVER_BANDS = {
    "GREEN": "green",
    "GREEN EDGE": "edge",
    "AMBER": "amber",
    "RED": "red",
    "SKIP": "skip",
}


def cover_band_class(band) -> str:
    return _COVER_BANDS.get((band or "").strip().upper(), "")


_GLOBALS = {
    "feed_link": feed_link,
    "tech_url": tech_url,
    "tech_href": tech_href,
    "tech_drop_href": tech_drop_href,
    "tech_state": tech_state,
    "company_link": company_link,
    "page_link": page_link,
    "calendar_link": calendar_link,
    "profile_link": profile_link,
    "build_query": build_query,
    "tech_sets": tech_sets,
    "co_sets": co_sets,
    "row_get": row_get,
    "row_text": row_text,
    "parse_points": parse_points,
    "home_href": home_href,
    "description": description,
    "card_tags": card_tags,
    "extra_chips": extra_chips,
    "source_links": source_links,
    "paragraphs": lambda text: Markup(paragraphs_from_text(text)),
    "hiring_notes": hiring_notes,
    "hiring_sel": hiring_sel,
    "hiring_cover": hiring_cover,
    "cover_band_class": cover_band_class,
    "STATUS_LABELS": STATUS_LABELS,
    "STATUS_ORDER": STATUS_ORDER,
    "BAND_LABELS": BAND_LABELS,
    "HIRING_LABELS": HIRING_LABELS,
    "HIRING_ORDER": HIRING_ORDER,
    "TAG_HINTS": TAG_HINTS,
    "SOURCE_LOGOS": SOURCE_LOGOS,
    "RADAR_ICON": Markup(RADAR_ICON),
    "ACCOUNT_ICON": Markup(ACCOUNT_ICON),
    "POPUP_JS": Markup(POPUP_JS),
    "COVER_JS": Markup(COVER_JS),
    "HIRING_JS": Markup(HIRING_JS),
}


def _css_version() -> int:
    try:
        return int(os.path.getmtime(os.path.join(paths.static_dir(), "app.css")))
    except OSError:
        return 0


def register_jinja(app) -> None:
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True
    app.jinja_env.filters.update(_FILTERS)
    app.jinja_env.globals.update(_GLOBALS)

    @app.context_processor
    def _inject_css_version():
        return {"css_version": _css_version()}

    @app.context_processor
    def _inject_llm_ready():
        """Whether an LLM key is configured (Profile → config → env). Templates use
        it to gate scoring/cover-letter affordances into an explanation instead."""
        from flask import current_app

        from jobradar.core.scoring import effective_api_key

        try:
            return {
                "llm_ready": bool(
                    effective_api_key(current_app.config.get("JOBRADAR", {}))
                )
            }
        except Exception:
            return {"llm_ready": False}
