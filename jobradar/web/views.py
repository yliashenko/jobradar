"""Data-shaping for the pages: SQL queries and post-filtering that turn database
rows into the context dicts templates render. No HTML here.
"""

import calendar as _calendar
import json
import math
import os
import re
from datetime import timedelta

from markupsafe import Markup, escape

from jobradar import candidate as profile_data
from jobradar import clock, paths, roles, runner, skills, stats
from jobradar.core import cover
from jobradar.core.db import KEEP_DUPS_FOR_RUNS
from jobradar.core.dedup import normalize_key
from jobradar.web.constants import STATUS_LABELS
from jobradar.web.format import fmt_epoch, fmt_iso, row_text
from jobradar.web.urls import build_query, co_sets, feed_link, tech_href, tech_sets

SORT_OPTS = (
    ("", "score: high → low"),
    ("score_asc", "score: low → high"),
    ("date", "newest first"),
    ("old", "oldest first"),
)
# The Applied tab is a to-do list of applications, not a ranked feed: it sorts by
# WHEN you applied (status_at). Score is meaningless here; only the time axes stay.
APPLIED_SORT_OPTS = (
    ("applied", "recently applied"),
    ("date", "newest first"),
    ("old", "oldest first"),
)
DAYS_OPTS = (
    ("", "all time"),
    ("1", "24 hours"),
    ("3", "3 days"),
    ("7", "week"),
    ("14", "two weeks"),
    ("30", "month"),
)
# Minimum-score filter: "any", then whole numbers 1..10 (score >= N).
SCORE_OPTS = (("", "any score"), *((str(n), str(n)) for n in range(1, 11)))

# Seniority words are stripped before matching titles: "Senior QA Engineer" and
# "QA Engineer" are the same role on different boards, and the level is just noise.
_SENIORITY_NOISE = {
    "junior",
    "middle",
    "senior",
    "lead",
    "strong",
    "trainee",
    "intern",
    "principal",
    "джуніор",
    "мідл",
    "старший",
    "сеньйор",
}

MONTHS = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# DOU returns at most this many records per feed; a feed that hit the cap is the
# only way the radar can silently drop rows, so /runs flags it.
DOU_FEED_CAP = 25

PIE_COLORS = (
    "var(--petrol)",
    "var(--accent)",
    "var(--stretch)",
    "var(--strong)",
    "var(--worth)",
    "var(--skip)",
)
PIE_MAX = 6


def tags_context(conn, params) -> dict:
    """Tag cloud: how often each dictionary skill appears across passed vacancies."""
    rows = conn.execute(
        "SELECT title, description FROM jobs WHERE l0_pass = 1"
    ).fetchall()
    texts = [f"{r['title']} {r['description']}" for r in rows]
    counts = skills.tally(texts)
    # Profile "not for me" terms drop out here as they drop out of the stats.
    muted = {
        skills.canonical(t).lower() for t in profile_data.load().get("exclude", [])
    }

    sections = []
    if counts:
        peak = max((n for t, n in counts.items() if t.lower() not in muted), default=1)
        for name, group in skills.GROUPS.items():
            present = sorted(
                (
                    (skills.canonical(t), counts.get(skills.canonical(t), 0))
                    for t in group
                    if skills.canonical(t).lower() not in muted
                ),
                key=lambda kv: (-kv[1], kv[0].lower()),
            )
            present = [(t, n) for t, n in present if n]
            if not present:
                continue
            # Chip size scales with frequency so the cloud reads without the numbers.
            sections.append(
                {
                    "name": name,
                    "tags": [
                        {"term": t, "count": n, "font_size": 0.78 + 0.55 * (n / peak)}
                        for t, n in present
                    ],
                }
            )

    included, excluded = tech_sets(params)
    return {
        "total": len(texts),
        "unique": len(counts),
        "sections": sections,
        "included": included,
        "excluded": excluded,
        "clear_params": {
            k: v for k, v in params.items() if k not in ("tech", "notech")
        },
    }


def _feeds(raw_feeds):
    try:
        feeds = json.loads(raw_feeds or "[]")
    except (ValueError, TypeError):
        feeds = []
    items, capped = [], []
    for it in feeds:
        count = int(it.get("count", 0) or 0)
        hours = it.get("window_hours")
        cap = bool(
            "dou.ua" in str(it.get("feed", ""))
            and count >= DOU_FEED_CAP
            and not it.get("error")
        )
        if cap and hours:
            capped.append(hours)
        items.append(
            {
                "feed": it.get("feed"),
                "count": count,
                "hours": hours,
                "error": it.get("error"),
                "cap": cap,
            }
        )
    return {
        "items": items,
        "any_cap": bool(capped),
        "narrowest": min([h for h in capped if h], default=None),
        "cap": DOU_FEED_CAP,
    }


def _funnel(run):
    total = run["dup_skipped"] + run["l0_dropped"] + run["added"]
    return {
        "fetched": run["fetched"],
        "dup_skipped": run["dup_skipped"],
        "l0_dropped": run["l0_dropped"],
        "added": run["added"],
        "revived": run["revived"],
        "triple": f"{run['dup_skipped']} + {run['l0_dropped']} + {run['added']}",
        "converges": total == run["fetched"],
    }


def _l0_drops(conn, run_id):
    rows = conn.execute(
        "SELECT l0_reason, title, company FROM jobs "
        "WHERE run_id = ? AND l0_pass = 0 ORDER BY l0_reason, title",
        (run_id,),
    ).fetchall()
    grouped = {}
    for r in rows:
        grouped.setdefault(r["l0_reason"], []).append(r)
    out = []
    for reason, items in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        out.append(
            {
                "reason": reason,
                "count": len(items),
                "items": [
                    {"title": r["title"], "company": r["company"]} for r in items[:5]
                ],
                "more": max(0, len(items) - 5),
            }
        )
    return out


def _dups(conn, run_id):
    return conn.execute(
        """SELECT d.url AS new_url, d.title AS new_title, d.company AS new_company,
                  d.source AS new_source,
                  j.url AS old_url, j.title AS old_title, j.company AS old_company,
                  j.source AS old_source, j.first_seen AS old_seen
           FROM run_dups d LEFT JOIN jobs j ON j.hash = d.hash
           WHERE d.run_id = ? ORDER BY d.company, d.title""",
        (run_id,),
    ).fetchall()


def runs_context(conn, params) -> dict:
    """Processing log: the funnel and dedup detail for one run, plus recent runs."""
    runs = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 30").fetchall()
    current = None
    if runs:
        try:
            wanted = int(params.get("run", runs[0]["id"]))
        except (TypeError, ValueError):
            wanted = runs[0]["id"]
        current = next((r for r in runs if r["id"] == wanted), runs[0])

    ctx = {
        "runs": runs,
        "current": current,
        "token": params.get("token", ""),
        "keep_dups": KEEP_DUPS_FOR_RUNS,
    }
    if current is not None:
        ctx["feeds"] = _feeds(current["feeds"])
        ctx["funnel"] = _funnel(current)
        ctx["l0_drops"] = _l0_drops(conn, current["id"])
        ctx["dups"] = _dups(conn, current["id"])
    return ctx


def pie(items, params, empty_msg):
    """Slice geometry for the demand pie. Fraction = share of market demand among
    this set; over PIE_MAX skills fold into 'other'. The template renders the SVG."""
    items = sorted([(t, c) for t, c in items if c > 0], key=lambda x: -x[1])
    if not items:
        return {"slices": [], "empty": empty_msg}
    shown = (
        [*items[:PIE_MAX], ("other", sum(c for _, c in items[PIE_MAX:]))]
        if len(items) > PIE_MAX
        else items
    )
    weight = sum(c for _, c in shown)
    cx = cy = 60.0
    r = 54.0
    a0 = -math.pi / 2  # start at the top
    slices = []
    for i, (label, c) in enumerate(shown):
        frac = c / weight
        color = "var(--line)" if label == "other" else PIE_COLORS[i % len(PIE_COLORS)]
        href = None if label == "other" else tech_href(label, params, "/")
        if frac >= 0.999:
            slices.append(
                {
                    "kind": "circle",
                    "color": color,
                    "label": label,
                    "count": c,
                    "href": href,
                }
            )
            continue
        a1 = a0 + frac * 2 * math.pi
        x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
        large = 1 if frac > 0.5 else 0
        d = f"M60,60 L{x0:.2f},{y0:.2f} A54,54 0 {large},1 {x1:.2f},{y1:.2f} Z"
        slices.append(
            {
                "kind": "path",
                "d": d,
                "color": color,
                "label": label,
                "count": c,
                "href": href,
            }
        )
        a0 = a1
    return {"slices": slices, "empty": None}


def _srcbars(counts, total):
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
    return [
        {"k": k, "n": n, "pct": round(100 * n / total) if total else 0} for k, n in top
    ]


def _sources_section(conn):
    rows = conn.execute(
        "SELECT source, salary, extra FROM jobs WHERE l0_pass = 1"
    ).fetchall()
    if not rows:
        return None
    per_source, eng, fmt = {}, {}, {}
    dj_total = dj_salary = 0
    for r in rows:
        per_source[r["source"]] = per_source.get(r["source"], 0) + 1
        if r["source"] == "djinni":
            dj_total += 1
            if r["salary"]:
                dj_salary += 1
            try:
                d = json.loads(r["extra"] or "{}")
            except (ValueError, TypeError):
                d = {}
            if d.get("english"):
                eng[d["english"]] = eng.get(d["english"], 0) + 1
            if d.get("work_format"):
                fmt[d["work_format"]] = fmt.get(d["work_format"], 0) + 1
    return {
        "src_bars": _srcbars(per_source, len(rows)),
        "dj_total": dj_total,
        "dj_salary": dj_salary,
        "dj_pct": round(100 * dj_salary / dj_total) if dj_total else 0,
        "eng_bars": _srcbars(eng, dj_total) if eng else [],
        "fmt_bars": _srcbars(fmt, dj_total) if fmt else [],
    }


def stats_context(conn, params) -> dict:
    """Positioning against the market: coverage, table stakes, differentiator and
    gap pies, source comparison. Nothing the sample can't support."""
    rows = conn.execute(
        "SELECT title, description FROM jobs WHERE l0_pass = 1"
    ).fetchall()
    texts = [f"{r['title']} {r['description']}" for r in rows]
    prof = profile_data.load()
    owned = prof.get("skills", []) + prof.get("extra_skills", [])
    data = stats.analyse(texts, owned, prof.get("exclude", []))
    if data is None:
        return {"data": None}

    total = data["total"]

    def pct(c):
        return round(100 * c / total)

    sources = (
        ", ".join(
            r["source"]
            for r in conn.execute(
                "SELECT DISTINCT source FROM jobs WHERE l0_pass = 1 ORDER BY source"
            )
        )
        or "—"
    )
    return {
        "data": data,
        "total": total,
        "role_label": roles.label(prof.get("role")),
        "sources": sources,
        "coverage_ratio": (100 * data["covered"] / data["top_n"])
        if data["top_n"]
        else 0,
        "stakes_have": [{"term": t, "pct": pct(c)} for t, c, h in data["stakes"] if h],
        "stakes_lack": [
            {"term": t, "pct": pct(c)} for t, c, h in data["stakes"] if not h
        ],
        "diff_pie": pie(
            data["differentiators"],
            params,
            "None yet: the skills are either ubiquitous or the market here isn't asking for them.",
        ),
        "gaps_pie": pie(
            data["gaps"],
            params,
            "No gaps — you cover everything the market here asks for.",
        ),
        "sources_section": _sources_section(conn),
    }


def _shift_month(year, month, delta):
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def calendar_context(conn, params) -> dict:
    """Monthly activity grid: new vacancies found (first_seen, L0-passed) and
    applications sent (status='applied'/'archived' by status_at) per day, with
    per-day modals. Archived counts too — it was still an application sent."""
    today = clock.now()
    try:
        year = int(params.get("year") or today.year)
        month = int(params.get("month") or today.month)
    except (ValueError, TypeError):
        year, month = today.year, today.month
    month = month if 1 <= month <= 12 else today.month
    year = max(2000, min(2100, year))

    prefix = f"{year:04d}-{month:02d}"
    cols = "hash, title, company, score, band, url, source"
    new_by_day: dict[str, list] = {}
    applied_by_day: dict[str, list] = {}
    for r in conn.execute(
        "SELECT " + cols + ", substr(first_seen,1,10) d FROM jobs "
        "WHERE l0_pass = 1 AND substr(first_seen,1,7) = ? "
        "ORDER BY (score IS NULL), score DESC, title",
        (prefix,),
    ):
        new_by_day.setdefault(r["d"], []).append(r)
    for r in conn.execute(
        "SELECT " + cols + ", substr(status_at,1,10) d FROM jobs "
        "WHERE status IN ('applied', 'archived') AND status_at IS NOT NULL "
        "AND substr(status_at,1,7) = ? ORDER BY title",
        (prefix,),
    ):
        applied_by_day.setdefault(r["d"], []).append(r)

    weeks: list[list] = []
    modals: list[dict] = []
    for week in _calendar.monthcalendar(year, month):
        cells: list = []
        for day in week:
            if day == 0:
                cells.append(None)
                continue
            dstr = f"{prefix}-{day:02d}"
            new_rows = new_by_day.get(dstr, [])
            app_rows = applied_by_day.get(dstr, [])
            cells.append(
                {
                    "day": day,
                    "dstr": dstr,
                    "is_today": year == today.year
                    and month == today.month
                    and day == today.day,
                    "new": len(new_rows),
                    "applied": len(app_rows),
                }
            )
            if new_rows:
                modals.append(
                    {
                        "anchor": "calN-" + dstr,
                        "day": day,
                        "label": "new",
                        "rows": new_rows,
                    }
                )
            if app_rows:
                modals.append(
                    {
                        "anchor": "calA-" + dstr,
                        "day": day,
                        "label": "applied",
                        "rows": app_rows,
                    }
                )
        weeks.append(cells)

    py, pm = _shift_month(year, month, -1)
    ny, nm = _shift_month(year, month, 1)
    return {
        "year": year,
        "month": month,
        "month_name": MONTHS[month],
        "gen_month": MONTHS[month],
        "weekdays": WEEKDAYS,
        "weeks": weeks,
        "modals": modals,
        "prev": (py, pm),
        "next": (ny, nm),
        "today": today,
        "month_opts": [(str(i), MONTHS[i]) for i in range(1, 13)],
        "total_new": sum(len(v) for v in new_by_day.values()),
        "total_applied": sum(len(v) for v in applied_by_day.values()),
    }


def _title_core(title):
    """Title core for matching: no brackets, no tail after a dash, no level words."""
    text = re.sub(r"\(.*?\)", " ", (title or "").lower())
    text = re.split(r"[—\-–|/]", text)[0]
    toks = [w.strip("+#.") for w in re.findall(r"[a-zа-яїієґ0-9+#.]+", text)]
    return " ".join(w for w in toks if w and w not in _SENIORITY_NOISE)


def build_also_on(conn, rows):
    """Cross-reference 'same vacancy on another board' WITHOUT merging rows: same
    company + exact title-core match. Returns {hash: [(source, url), …]}."""
    by_co = {}
    for r in conn.execute(
        "SELECT hash, source, url, title, company FROM jobs WHERE company != ''"
    ):
        by_co.setdefault(normalize_key(r["company"]), []).append(r)

    out = {}
    for row in rows:
        if not row["company"]:
            continue
        core = _title_core(row["title"])
        if not core:
            continue
        try:
            have = set(json.loads(row["sources"])) if row["sources"] else set()
        except (ValueError, TypeError):
            have = set()
        have.add(row["source"])
        best = {}
        for cand in by_co.get(normalize_key(row["company"]), []):
            if cand["hash"] == row["hash"] or cand["source"] in have:
                continue
            if _title_core(cand["title"]) == core and cand["source"] not in best:
                best[cand["source"]] = cand["url"]
        if best:
            out[row["hash"]] = list(best.items())
    return out


def run_activity_text(status):
    """What is happening right now (css class, text). Empty when idle — calm is
    the default state and a line about it only took up header space."""
    if status.get("running"):
        return (
            "runstat live",
            f"scan running… started at {fmt_epoch(status.get('started_at'))}",
        )
    if status.get("external"):
        return "runstat live", "scheduled scan running…"
    if status.get("error"):
        return "runstat err", (
            f"scan at {fmt_epoch(status.get('finished_at'))} failed: "
            f"{str(status['error'])[:120]}"
        )
    return "", ""


def _last_collect_at(conn):
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'last_collect_ok'"
        ).fetchone()
    except Exception:
        return ""
    return row["value"] if row else ""


def last_collect_text(last_collect, last_run=None):
    when = fmt_iso(last_collect)
    if not when:
        return "no scan yet", ""
    hint = ""
    if last_run:
        added = int(last_run.get("added") or 0)
        dropped = int(last_run.get("l0_dropped") or 0)
        hint = f"+{added} new" if added else "no new ones"
        if dropped:
            hint += f", {dropped} filtered out"
    return f"last scan {when}", hint


def _build_where(params):
    where, args = [], []
    status = params.get("status", "new")
    if status == "applied" and params.get("archived") == "1":
        # The Applied tab is the hiring pipeline; its "Show archived" toggle folds
        # finalized vacancies back into the same list.
        where.append("status IN ('applied', 'archived')")
    elif status and status != "all":
        where.append("status = ?")
        args.append(status)
    else:
        # The 'all' tab still hides archived — finished vacancies live on the
        # Applied tab, behind its archived toggle.
        where.append("status != 'archived'")
    if params.get("source"):
        where.append("source = ?")
        args.append(params["source"])
    if params.get("q"):
        where.append(
            "(LOWER(title) LIKE ? OR LOWER(company) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(description) LIKE ?)"
        )
        needle = "%" + params["q"].lower() + "%"
        args.extend([needle, needle, needle, needle])
    if params.get("min"):
        try:
            args.append(float(params["min"]))
            where.append("score >= ?")
        except ValueError:
            pass
    if params.get("l0") != "1":
        where.append("l0_pass = 1")
    chosen_co = co_sets(params)
    if chosen_co:
        where.append(f"company IN ({','.join('?' * len(chosen_co))})")
        args.extend(chosen_co)
    if params.get("days"):
        try:
            cutoff = (clock.now() - timedelta(days=int(params["days"]))).isoformat(
                timespec="seconds"
            )
            where.append("COALESCE(published_at, first_seen) >= ?")
            args.append(cutoff)
        except ValueError:
            pass
    included, _ = tech_sets(params)
    for term in included:
        # LIKE only narrows; skills.mentions decides so "Java" doesn't catch "JavaScript".
        needle = "%" + term.lower() + "%"
        where.append("(LOWER(title) LIKE ? OR LOWER(description) LIKE ?)")
        args.extend([needle, needle])
    return where, args


def _effective_sort(params):
    """The Applied tab defaults to application time (newest first); other tabs
    default to score. An explicit choice from that tab's dropdown wins; anything
    outside its options (e.g. a score sort carried over from another tab) is
    clamped back to the application-time default."""
    sort = params.get("sort", "")
    if params.get("status", "new") == "applied":
        return sort if sort in ("date", "old") else "applied"
    return sort


def _order_by(sort):
    if sort == "applied":
        # Recently applied on top, long-ago applications sink to the bottom.
        return "status_at DESC, first_seen DESC"
    if sort == "date":
        return "COALESCE(published_at, first_seen) DESC"
    if sort == "old":
        return "COALESCE(published_at, first_seen) ASC"
    if sort == "score_asc":
        # Unscored (NULL) still sink to the bottom, then weakest scores first.
        return "(score IS NULL), score ASC, COALESCE(published_at, first_seen) DESC"
    return "(score IS NULL), score DESC, COALESCE(published_at, first_seen) DESC"


def _group(rows):
    counts = {}
    for r in rows:
        if r["company"]:
            counts[r["company"]] = counts.get(r["company"], 0) + 1
    items, emitted = [], set()
    for r in rows:
        co = r["company"]
        if co and counts.get(co, 0) >= 2:
            if co in emitted:
                continue
            emitted.add(co)
            items.append(
                {
                    "kind": "group",
                    "company": co,
                    "members": [x for x in rows if x["company"] == co],
                }
            )
        else:
            items.append({"kind": "job", "row": r})
    return items


def _tabs(params, counts, total, shown):
    status = params.get("status", "new")
    tabs = []
    for key in ("new", "interested", "applied", "skipped", "all"):
        tabs.append(
            {
                "key": key,
                "label": "all" if key == "all" else STATUS_LABELS[key],
                "count": total if key == "all" else counts.get(key, 0),
                "on": status == key,
                "href": feed_link(params, status=key),
            }
        )
    return {
        "tabs": tabs,
        "total": total,
        "shown": shown,
    }


def _filters(conn, params):
    sources = [
        r["source"]
        for r in conn.execute("SELECT DISTINCT source FROM jobs ORDER BY source")
    ]
    applied = params.get("status", "new") == "applied"
    # Anything that narrows the feed — the tab (status) and sort order are view
    # state, not filters, so clearing keeps them.
    filter_keys = ("source", "q", "min", "l0", "days", "tech", "notech", "co")
    return {
        "sources": sources,
        "sort": _effective_sort(params),
        "sort_opts": APPLIED_SORT_OPTS if applied else SORT_OPTS,
        "days_opts": DAYS_OPTS,
        "score_opts": SCORE_OPTS,
        "filters_active": any(params.get(k) for k in filter_keys),
    }


def _pick_tags(conn, params):
    # Count within the current view (status, source, search, company, days…) so
    # a tag's number matches what selecting it actually shows in the feed. The
    # tech selection itself is dropped from the WHERE — otherwise every count
    # would collapse onto the already-picked tags. Profile "not for me" rows
    # (title match) are cut here too, exactly as the feed cuts them.
    base = {k: v for k, v in params.items() if k not in ("tech", "notech")}
    where, args = _build_where(base)
    sql = "SELECT title, description FROM jobs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = conn.execute(sql, args).fetchall()
    muted = profile_data.load().get("exclude", [])
    if muted:
        rows = [
            r
            for r in rows
            if not any(profile_data.present_in_cv(t, r["title"] or "") for t in muted)
        ]
    tally = skills.tally([f"{r['title']} {r['description']}" for r in rows])
    included, _ = tech_sets(params)
    # A profile-excluded tag is not offered as a filter at all (it drops out of
    # the stats too) — you manage it on the Profile page, not here.
    muted_terms = {skills.canonical(t).lower() for t in muted}
    sections = []
    for name, group in skills.GROUPS.items():
        present = sorted(
            (
                (skills.canonical(t), tally.get(skills.canonical(t), 0))
                for t in group
                if skills.canonical(t).lower() not in muted_terms
            ),
            key=lambda kv: (-kv[1], kv[0].lower()),
        )
        present = [(t, n) for t, n in present if n]
        if present:
            sections.append(
                {
                    "name": name,
                    "rows": [
                        {"value": t, "count": n, "checked": t in included}
                        for t, n in present
                    ],
                }
            )
    return {"sections": sections, "included": len(included)}


def _pick_companies(conn, params):
    rows_db = conn.execute(
        "SELECT company, COUNT(*) AS c FROM jobs WHERE company != '' AND l0_pass = 1 "
        "GROUP BY company ORDER BY c DESC, company"
    ).fetchall()
    chosen = co_sets(params)
    return {
        "companies": [
            {"value": r["company"], "count": r["c"], "checked": r["company"] in chosen}
            for r in rows_db
        ],
        "chosen": len(chosen),
    }


def _runbox(conn, run_status, query):
    cls, activity = run_activity_text(run_status)
    busy = bool(run_status.get("running") or run_status.get("external"))
    line, hint = last_collect_text(
        _last_collect_at(conn), runner.last_run_stats(paths.db_path())
    )
    return {
        "cls": cls,
        "activity": activity,
        "busy": busy,
        "label": "Scanning…" if busy else "Scan!",
        "line": line,
        "hint": hint,
        "back": query,
    }


def _empty_feed(params):
    if params.get("tech"):
        return {
            "title": f"No vacancies tagged «{skills.canonical(params['tech'])}»",
            "body": "This stack isn't mentioned in what's been collected yet.",
        }
    if params.get("status", "new") == "new":
        return {
            "title": "No new vacancies",
            "body": "The collector runs on a schedule. The next ones will show up here after a run.",
        }
    return {
        "title": "Nothing found",
        "body": "Try removing filters or switching to the «all» tab.",
    }


def feed_context(conn, params, threshold, run_status, query="") -> dict:
    """The feed: filtered/grouped vacancy cards, status tabs, filters, runbox."""
    where, args = _build_where(params)
    sql = "SELECT * FROM jobs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY " + _order_by(_effective_sort(params)) + " LIMIT 300"
    rows = conn.execute(sql, args).fetchall()

    included, excluded = tech_sets(params)
    if included or excluded:
        # Included tags AND-narrow; excluded are cut post-query (NOT LIKE would lie
        # on word boundaries exactly like LIKE).
        rows = [
            r
            for r in rows
            if all(skills.mentions(row_text(r), t) for t in included)
            and not any(skills.mentions(row_text(r), t) for t in excluded)
        ]

    # A profile "not for me" skill hides a vacancy when the excluded tag is in the
    # TITLE (as the scan filters). A body-only match is left alone.
    muted = profile_data.load().get("exclude", [])

    def title_muted(title):
        return any(profile_data.present_in_cv(t, title or "") for t in muted)

    if muted:
        rows = [r for r in rows if not title_muted(r["title"])]

    counts: dict = {}
    for r in conn.execute(
        "SELECT status, title FROM jobs WHERE l0_pass = 1 AND status != 'archived'"
    ):
        if muted and title_muted(r["title"]):
            continue
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    ctx = {
        "has_jobs": bool(rows),
        "empty": _empty_feed(params),
        "tabs": _tabs(params, counts, sum(counts.values()), len(rows)),
        "filters": _filters(conn, params),
        "pick_tags": _pick_tags(conn, params),
        "pick_companies": _pick_companies(conn, params),
        "runbox": _runbox(conn, run_status, query),
        "threshold": threshold,
        "busy": bool(run_status.get("running") or run_status.get("external")),
    }
    # The Applied tab renders the hiring pipeline in place of the ranked feed: flat
    # (ungrouped) applied cards with stage/notes/cover, plus the archived toggle.
    if params.get("status", "new") == "applied":
        ctx.update(_applied_extra(conn, params, rows, query))
    else:
        ctx["applied"] = False
        ctx["groups"] = _group(rows)
        ctx["also"] = build_also_on(conn, rows)
    return ctx


def _applied_extra(conn, params, rows, query) -> dict:
    """Hiring-pipeline fields for the Applied tab: the flat filtered row list, the
    archived toggle, and the redirect target the stage/cover forms post back to."""
    show_archived = params.get("archived") == "1"
    archived_count = conn.execute(
        "SELECT COUNT(*) AS c FROM jobs WHERE status = 'archived'"
    ).fetchone()["c"]
    toggle_qs = build_query(params, archived="" if show_archived else "1")
    return {
        "applied": True,
        "rows": rows,
        "archived_count": archived_count,
        "show_archived": show_archived,
        "hiring_toggle_href": "/" + (("?" + toggle_qs) if toggle_qs else ""),
        "hiring_back": query,
    }


def empty_context(run_status, back_query) -> dict:
    """The pre-first-scan page: just the Scan button (no menu — nothing to browse yet)."""
    cls, activity = run_activity_text(run_status)
    busy = bool(run_status.get("running") or run_status.get("external"))
    return {
        "busy": busy,
        "runbox": {
            "cls": cls,
            "activity": activity,
            "busy": busy,
            "label": "Scanning…" if busy else "Scan!",
            "line": "no scan yet",
            "hint": "",
            "back": back_query,
        },
    }


def _top_by_count(counts, limit=8):
    return [
        k
        for k, _ in sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0]).lower()))[
            :limit
        ]
    ]


def _company_info(rows):
    """Non-empty aggregated company fields, each a 'label: chips' row."""
    sources, domains, formats, english, locations = set(), {}, {}, {}, {}
    salaries, seen_sal = [], set()
    for r in rows:
        sources.add(r["source"])
        if r["location"]:
            locations[r["location"]] = locations.get(r["location"], 0) + 1
        if r["salary"] and r["salary"] not in seen_sal:
            seen_sal.add(r["salary"])
            salaries.append(r["salary"])
        try:
            data = json.loads(r["extra"]) if r["extra"] else {}
        except (ValueError, TypeError):
            data = {}
        for key, bucket in (
            ("domain", domains),
            ("work_format", formats),
            ("english", english),
        ):
            val = data.get(key)
            if val:
                bucket[val] = bucket.get(val, 0) + 1

    info_rows = []
    for label, items in (
        ("Sources", sorted(sources)),
        ("Domain", _top_by_count(domains)),
        ("Format", _top_by_count(formats)),
        ("English", _top_by_count(english)),
        ("Locations", _top_by_count(locations)),
        ("Salaries", salaries[:6]),
    ):
        chips = [str(i) for i in items]
        if chips:
            info_rows.append({"label": label, "chips": chips})

    texts = [f"{r['title']} {r['description']}" for r in rows]
    tech = sorted(skills.tally(texts).items(), key=lambda kv: (-kv[1], kv[0].lower()))[
        :12
    ]
    return {"rows": info_rows, "tech": [{"term": t, "count": c} for t, c in tech]}


def company_context(conn, params, threshold) -> dict:
    """Company card: aggregated info from all its vacancies (L0-dropped included)."""
    name = (params.get("name") or "").strip()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE company = ? "
        "ORDER BY (l0_pass = 0), (score IS NULL), score DESC, first_seen DESC",
        (name,),
    ).fetchall()
    if not name or not rows:
        return {"name": name, "found": False}
    return {
        "name": name,
        "found": True,
        "rows": rows,
        "count": len(rows),
        "passed": sum(1 for r in rows if r["l0_pass"]),
        "info": _company_info(rows),
        "also": build_also_on(conn, rows),
        "threshold": threshold,
    }


def cv_tagged(cv_text, active=None, custom=None):
    """CV text with skills highlighted inline. Each unique skill is one checkbox
    (name="skills") and every mention a label on it; unchecking dims all its
    mentions at once via :has() — no JS. Returns {order, block}."""
    text = cv_text or ""
    active_lower = None if active is None else {s.lower() for s in active}

    # Dictionary + custom matches, then overlaps removed: the longer span wins
    # (so "REST Assured" isn't split into "REST").
    spans = [
        (m.start(), m.end(), skills.canonical(m.group(0)))
        for m in skills.PATTERN.finditer(text)
    ]
    for term in custom or []:
        if not term.strip():
            continue
        for m in re.finditer(rf"(?<![\w#+]){re.escape(term)}(?![\w#+])", text, re.I):
            spans.append((m.start(), m.end(), term))
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))

    index, order, parts, pos, last = {}, [], [], 0, -1
    for st, en, canon in spans:
        if st < last:
            continue
        key = canon.lower()
        if key not in index:
            index[key] = len(order)
            order.append(canon)
        i = index[key]
        parts.append(str(escape(text[pos:st])))
        parts.append(
            f'<label class="cvtag" for="sk{i}" data-t="{i}">{escape(text[st:en])}</label>'
        )
        pos = last = en
    parts.append(str(escape(text[pos:])))
    tagged = "".join(parts).replace("\n", "<br>")

    boxes, rules = [], []
    for i, term in enumerate(order):
        checked = (
            " checked" if (active_lower is None or term.lower() in active_lower) else ""
        )
        boxes.append(
            f'<input type="checkbox" class="skcb" id="sk{i}" name="skills" '
            f'value="{escape(term)}"{checked}>'
        )
        # An unchecked box strikes through every mention of that tag in the text.
        rules.append(
            f'.cvbox:has(#sk{i}:not(:checked)) [data-t="{i}"]'
            "{color:var(--dim);text-decoration:line-through;"
            "border-bottom-color:transparent;background:none}"
        )
    block = (
        f"<style>{''.join(rules)}</style>"
        f'<div class="cvbox">{"".join(boxes)}<div class="cvtext">{tagged}</div></div>'
    )
    return {"order": order, "block": Markup(block)}


def profile_view_context(params, data, saved) -> dict:
    notes = data.get("notes", "")
    return {
        "saved": saved,
        "token": params.get("token", ""),
        "role_label": roles.label(data.get("role")),
        "stack": ", ".join(data.get("stack", [])),
        "seniority": data.get("seniority", ""),
        "skills": data.get("skills", []),
        "extra_skills": ", ".join(data.get("extra_skills", [])),
        "exclude": ", ".join(data.get("exclude", [])),
        "notes_html": Markup(str(escape(notes)).replace("\n", "<br>"))
        if notes
        else None,
        "api_key_set": bool(data.get("api_key")),
        "llm_model": data.get("llm_model", ""),
        "llm_provider": data.get("llm_provider", "") or "anthropic",
        "llm_base_url": data.get("llm_base_url", ""),
        "telegram_bot_token_set": bool(data.get("telegram_bot_token")),
        "telegram_chat_id": data.get("telegram_chat_id", ""),
        "telegram_enabled": data.get("telegram_enabled", True),
        "notify_min_score": str(data.get("notify_min_score", "")).strip(),
        "heartbeat_alert_hours": data.get("heartbeat_alert_hours", 24),
        "schedule_enabled": data.get("schedule_enabled", False),
        "schedule_interval_hours": data.get("schedule_interval_hours", 3),
        "schedule_start_hour": data.get("schedule_start_hour", 8),
        "schedule_end_hour": data.get("schedule_end_hour", 23),
    }


def _provider_ui(data) -> str:
    """Which provider option to preselect: anthropic / openai / custom. 'custom' is
    the stored openai + a base URL — a distinct UI state so the base-URL field can
    hide for Anthropic and plain OpenAI (which use their own default endpoint)."""
    prov = data.get("llm_provider", "") or "anthropic"
    if prov == "openai" and str(data.get("llm_base_url", "")).strip():
        return "custom"
    return prov


def profile_edit_context(params, data, preview=None) -> dict:
    cv_text = data.get("cv_text", "")
    cv = None
    if cv_text.strip():
        active = None if preview is not None else data.get("skills")
        # Highlight hand-added terms (non-dictionary CV skills + extra_skills) that
        # occur in the CV; extra_skills not in the CV simply don't match anything.
        custom = [
            s for s in (data.get("skills") or []) if s.lower() not in skills.CANONICAL
        ] + list(data.get("extra_skills") or [])
        cv = cv_tagged(cv_text, active, custom)
    return {
        "token": params.get("token", ""),
        "role": data.get("role", roles.DEFAULT_ROLE),
        "roles": [(k, roles.label(k)) for k in roles.ROLE_ORDER],
        "cv_text": cv_text,
        "cv": cv,
        "extra": ", ".join(data.get("extra_skills", [])),
        "stack": ", ".join(data.get("stack", [])),
        "seniority": data.get("seniority", ""),
        "exclude": ", ".join(data.get("exclude", [])),
        "notes": data.get("notes", ""),
        "api_key": data.get("api_key", ""),
        "llm_model": data.get("llm_model", ""),
        # The provider dropdown is a 3-way UI (anthropic / openai / custom); "custom"
        # is stored as provider=openai + a base URL, and the base-URL field shows only
        # for it. Derive which option to preselect from the stored pair.
        "provider_ui": _provider_ui(data),
        "llm_base_url": data.get("llm_base_url", ""),
        "cover_models": cover.COVER_MODEL_CHOICES,
        "cover_model_known": (data.get("llm_model", "") or "") in cover.COVER_MODEL_IDS,
        "telegram_bot_token": data.get("telegram_bot_token", ""),
        "telegram_chat_id": data.get("telegram_chat_id", ""),
        "telegram_enabled": data.get("telegram_enabled", True),
        "notify_min_score": data.get("notify_min_score", ""),
        "heartbeat_alert_hours": data.get("heartbeat_alert_hours", 24),
        "schedule_enabled": data.get("schedule_enabled", False),
        "schedule_interval_hours": data.get("schedule_interval_hours", 3),
        "schedule_start_hour": data.get("schedule_start_hour", 8),
        "schedule_end_hour": data.get("schedule_end_hour", 23),
        "has_profile": os.path.exists(paths.profile_json_path()),
    }
