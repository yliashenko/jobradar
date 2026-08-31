#!/usr/bin/env python3
"""Deterministic test-data seeding for the e2e suite.

JOBRADAR_HOME must be set (the worker fixture does this); db_connect then creates
the schema and writes jobs.db into the worker's temp home.

We seed at the DB level because jobradar has no write API for vacancies — only a
real scan creates them. To limit the schema coupling that brings: the schema
comes from the product (db_connect), we touch only a small, stable set of
columns via the vac() builder, and any drift fails loudly at fixture setup.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from jobradar.core.db import db_connect  # noqa: E402

# The server clock can't be frozen from e2e, so "now" rows land in the current
# calendar month and inside the recency window; dated rows use days_ago().
NOW_DT = datetime.now(timezone.utc)
NOW = NOW_DT.isoformat()

def days_ago(n):
    """A past ISO timestamp for period/recency tests (no clock freeze in e2e)."""
    return (NOW_DT - timedelta(days=n)).isoformat()

def vac(hash, title, company, *, source="dou", desc="", status="new",
        score=None, band="", verdict="", matched=None, gaps=None, seen=None, at=None):
    """One vacancy row with sensible defaults; a test overrides only what it needs.
    Card tags come from skills.card_terms(description), so tech goes in `desc`.
    matched/gaps are stored as JSON (the product does json.dumps on them)."""
    return {
        "hash": hash,
        "source": source,
        "url": f"https://example.test/{hash}",
        "title": title,
        "company": company,
        "description": desc,
        "description_html": f"<p>{desc}</p>",
        "first_seen": seen or NOW,
        "published_at": seen or NOW,
        "l0_pass": 1,
        "status": status,
        "status_at": at if at is not None else (None if status == "new" else NOW),
        "score": score,
        "band": band,
        "verdict": verdict,
        "matched": json.dumps(matched or [], ensure_ascii=False),
        "gaps": json.dumps(gaps or [], ensure_ascii=False),
    }

# The `catalog` set: one rich, documented read-fixture. Row names are stable so
# tests assert by identity, not by global counts.
CATALOG = [
    # v1 also carries a full scorer breakdown → the score-details popup.
    vac("v1", "Senior QA Automation Engineer", "Acme",
        desc="Playwright, pytest, Python, API testing", score=8.7, band="strong",
        verdict="Strong automation fit; Playwright and pytest are core here.",
        matched=["Playwright", "pytest", "API testing"],
        gaps=["Python is curated LLM code, not a work language"]),
    # Second Acme row → company grouping and a company page with two vacancies.
    vac("v2", "SDET (Java)", "Acme", desc="Java, Selenium, REST Assured",
        score=7.2, band="good"),
    # JavaScript (not Java) → the word-boundary filter test.
    vac("v3", "QA Automation (JavaScript)", "Globex", source="djinni",
        desc="JavaScript, Cypress, Node.js", score=6.5, band="maybe"),
    # 12 terms > card_terms limit of 10 → the card collapses extras into "+N".
    vac("v4", "Test Automation Lead", "Initech",
        desc="Playwright, pytest, Python, Selenium, Cypress, Postman, SQL, Docker, "
             "Kubernetes, TypeScript, Java, API", score=8.0, band="strong"),
    vac("v5", "Automation QA Engineer", "Umbrella", source="djinni",
        desc="pytest, API, SQL", score=7.0, band="good"),
    # interested / applied → status tabs and the calendar.
    vac("v6", "QA Engineer", "Hooli", desc="Playwright, Python",
        status="interested", score=7.5, band="good"),
    vac("v7", "Senior AQA", "Stark", desc="Selenium, Java",
        status="applied", score=8.2, band="strong"),
    # Archived (finished hiring): hidden from every feed tab, but still counted on
    # the calendar. Unique company / dou / reused tech so it perturbs no existing
    # count; status_at is "today", coinciding with v7's applied activity.
    vac("v_arch", "Automation QA Engineer", "Zenith", desc="Playwright, pytest",
        status="archived", score=7.8, band="good", at=days_ago(5)),
    # Unscored → sinks to the bottom under either score sort (tech "API" groups it
    # with v1/v4/v5, all distinct companies so no company-grouping reorders).
    vac("v8", "QA Automation Engineer", "Nimbus", desc="API testing"),
    # Dated rows for the period filter. Tech reused from v4 (Docker/SQL/Kubernetes/
    # Postman/TypeScript) so no new tag and no clash with the pytest/Java/Python
    # count tests; scores < 8 so the min=8 filter is unaffected.
    vac("v9", "QA Automation", "Orbit", desc="Docker, SQL",
        score=6.0, band="maybe", seen=days_ago(3)),
    vac("v10", "Automation QA", "Vertex", desc="Kubernetes, Postman",
        score=6.8, band="maybe", seen=days_ago(10)),
    vac("v11", "QA Engineer", "Photon", desc="TypeScript",
        score=7.1, band="good", seen=days_ago(40)),
]

COLUMNS = [
    "hash", "source", "url", "title", "company", "description", "description_html",
    "first_seen", "published_at", "l0_pass", "status", "status_at", "score", "band",
    "verdict", "matched", "gaps",
]

def insert(conn, rows):
    placeholders = ",".join("?" * len(COLUMNS))
    conn.executemany(
        f"INSERT INTO jobs ({','.join(COLUMNS)}) VALUES ({placeholders})",
        [tuple(r[c] for c in COLUMNS) for r in rows],
    )

SETS = {"catalog": CATALOG}

def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "catalog"
    if which == "empty":
        return 0  # no rows: the pre-first-scan state
    conn = db_connect()
    try:
        insert(conn, SETS[which])
        conn.commit()
    finally:
        conn.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
