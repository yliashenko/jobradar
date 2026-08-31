"""Database: schema, migrations, connection, meta keys, and the run log.

Only this module knows the schema and migrations (webui once kept its own copy
of the table truth — and a page would break on a DB created before the log).
The DB path comes from paths (JOBRADAR_HOME for tests/e2e), time from clock
(ADR-0007).
"""

import json
import logging
import sqlite3

from jobradar import clock, paths

log = logging.getLogger("jobradar")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    hash          TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    url           TEXT NOT NULL,
    title         TEXT NOT NULL,
    company       TEXT NOT NULL DEFAULT '',
    location      TEXT NOT NULL DEFAULT '',
    salary        TEXT NOT NULL DEFAULT '',
    description   TEXT NOT NULL DEFAULT '',
    -- The description is stored twice on purpose: flat text feeds L0 and the
    -- scorer (regex over markup would work by accident), sanitized HTML is only
    -- for display.
    description_html TEXT NOT NULL DEFAULT '',
    -- Djinni-specific structured fields (experience/English/format/domain)
    -- as JSON; empty for DOU. Different source — hence an optional column.
    extra         TEXT NOT NULL DEFAULT '',
    -- All sources where this vacancy was seen, as JSON {source: url}. The source
    -- column stays the primary one (where it was seen first), while sources
    -- gathers all: the same role on DOU and Djinni is merged by dedup, but on the
    -- card we show both links. Empty → we show source/url itself.
    sources       TEXT NOT NULL DEFAULT '',
    -- When the vacancy was published at the source. This is NOT first_seen: that
    -- says when the radar first saw it, and after a pause in work the difference
    -- will be days.
    published_at  TEXT,
    first_seen    TEXT NOT NULL,
    l0_pass       INTEGER NOT NULL DEFAULT 0,
    l0_reason     TEXT NOT NULL DEFAULT '',
    score         REAL,
    band          TEXT NOT NULL DEFAULT '',
    verdict       TEXT NOT NULL DEFAULT '',
    matched       TEXT NOT NULL DEFAULT '',
    gaps          TEXT NOT NULL DEFAULT '',
    rubric        TEXT NOT NULL DEFAULT '',
    scored_at     TEXT,
    notified_at   TEXT,
    status        TEXT NOT NULL DEFAULT 'new',
    -- When the status was last changed (for the activity calendar: how many
    -- applications per day). Old records stay NULL — when exactly they applied
    -- back then can't be recovered retroactively.
    status_at     TEXT,
    run_id        INTEGER,
    -- Hiring pipeline for applied vacancies. hiring_status = current stage
    -- (see HIRING_ORDER in web.constants); hiring_notes = JSON {stage: text},
    -- one note per stage. Both empty until you start tracking an applied role.
    hiring_status TEXT NOT NULL DEFAULT '',
    hiring_notes  TEXT NOT NULL DEFAULT '',
    -- Generated cover letter for an applied vacancy, as JSON {letter, evaluation,
    -- traceability, fit_score, band, model, generated_at}. Empty until you press
    -- "Generate cover letter" on the hiring card. Kept, never recomputed on view.
    cover_data    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Run log. Needed for exactly one thing: to see what did NOT arrive.
-- An empty feed looks the same whether the market is quiet or a feed died;
-- telling one from the other is only possible from the numbers per feed over time.
CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    triggered_by TEXT NOT NULL DEFAULT 'cron',
    fetched      INTEGER NOT NULL DEFAULT 0,
    dup_skipped  INTEGER NOT NULL DEFAULT 0,
    l0_dropped   INTEGER NOT NULL DEFAULT 0,
    added        INTEGER NOT NULL DEFAULT 0,
    revived      INTEGER NOT NULL DEFAULT 0,
    notified     INTEGER NOT NULL DEFAULT 0,
    feeds        TEXT NOT NULL DEFAULT ''
);

-- What exactly dedup dropped and what it merged it with. Without this table
-- its decisions can't be checked: a dropped record was kept nowhere.
CREATE TABLE IF NOT EXISTS run_dups (
    run_id   INTEGER NOT NULL,
    hash     TEXT NOT NULL,
    source   TEXT NOT NULL,
    url      TEXT NOT NULL,
    title    TEXT NOT NULL,
    company  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_run_dups_run ON run_dups(run_id);
"""

# Triage statuses. 'new' is set by the collector, the rest by you in the web UI.
# 'archived' is terminal: an applied vacancy whose hiring pipeline is finished
# (set from /hiring), hidden from the feed tabs and shown only on /hiring.
STATUSES = ("new", "interested", "applied", "skipped", "archived")

# How many recent runs we keep with the full list of duplicates. The runs rows
# themselves stay forever (they're tiny and needed as a time series per feed),
# but run_dups grows by ~100 rows per run — tens of thousands a month — and
# nobody needs it after the first check.
KEEP_DUPS_FOR_RUNS = 30


def migrate(conn):
    """Catches the schema up on DBs created by earlier versions of the script.

    The status index is created here, not in SCHEMA: on an old DB the column
    doesn't exist yet, and CREATE INDEX would fail before ALTER TABLE runs.
    """
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    if "status" not in existing:
        conn.execute("ALTER TABLE jobs ADD COLUMN status TEXT NOT NULL DEFAULT 'new'")
        conn.commit()
        log.info("Migration: added column status")
    if "run_id" not in existing:
        # Records made before the log stay NULL — that's more honest than
        # attributing them to some run retroactively.
        conn.execute("ALTER TABLE jobs ADD COLUMN run_id INTEGER")
        conn.commit()
        log.info("Migration: added column run_id")
    if "description_html" not in existing:
        # Old records stay without markup — webui shows them as flat text.
        # Re-collecting retroactively is pointless: the score is already set.
        conn.execute(
            "ALTER TABLE jobs ADD COLUMN description_html TEXT NOT NULL DEFAULT ''"
        )
        conn.commit()
        log.info("Migration: added column description_html")
    if "published_at" not in existing:
        conn.execute("ALTER TABLE jobs ADD COLUMN published_at TEXT")
        conn.commit()
        log.info("Migration: added column published_at")
    if "extra" not in existing:
        conn.execute("ALTER TABLE jobs ADD COLUMN extra TEXT NOT NULL DEFAULT ''")
        conn.commit()
        log.info("Migration: added column extra")
    if "status_at" not in existing:
        conn.execute("ALTER TABLE jobs ADD COLUMN status_at TEXT")
        conn.commit()
        log.info("Migration: added column status_at")
    if "hiring_status" not in existing:
        conn.execute(
            "ALTER TABLE jobs ADD COLUMN hiring_status TEXT NOT NULL DEFAULT ''"
        )
        conn.commit()
        log.info("Migration: added column hiring_status")
    if "hiring_notes" not in existing:
        conn.execute(
            "ALTER TABLE jobs ADD COLUMN hiring_notes TEXT NOT NULL DEFAULT ''"
        )
        conn.commit()
        log.info("Migration: added column hiring_notes")
    if "cover_data" not in existing:
        conn.execute("ALTER TABLE jobs ADD COLUMN cover_data TEXT NOT NULL DEFAULT ''")
        conn.commit()
        log.info("Migration: added column cover_data")
    if "sources" not in existing:
        conn.execute("ALTER TABLE jobs ADD COLUMN sources TEXT NOT NULL DEFAULT ''")
        # One-time backfill: the primary source + everything dedup previously
        # dropped into run_dups for the same hash. That way already-merged
        # DOU+Djinni dups show both sources at once, not only after the next scan.
        for row in conn.execute("SELECT hash, source, url FROM jobs").fetchall():
            smap = {}
            if row["source"]:
                smap[row["source"]] = row["url"]
            for d in conn.execute(
                "SELECT source, url FROM run_dups WHERE hash = ?", (row["hash"],)
            ):
                smap.setdefault(d["source"], d["url"])
            conn.execute(
                "UPDATE jobs SET sources = ? WHERE hash = ?",
                (json.dumps(smap, ensure_ascii=False), row["hash"]),
            )
        conn.commit()
        log.info("Migration: added column sources and merged sources from run_dups")
    if conn.execute("SELECT 1 FROM jobs WHERE status = 'rejected' LIMIT 1").fetchone():
        # The 'rejected' triage status was renamed to 'skipped'. Carry old rows
        # over so they still match a feed tab; idempotent once none remain.
        conn.execute("UPDATE jobs SET status = 'skipped' WHERE status = 'rejected'")
        conn.commit()
        log.info("Migration: renamed status 'rejected' to 'skipped'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
    conn.commit()


def db_connect(path=None):
    conn = sqlite3.connect(path or paths.db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    migrate(conn)
    return conn


def meta_get(conn, key, default=""):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def meta_set(conn, key, value):
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()


def now_iso():
    return clock.now().isoformat(timespec="seconds")


def run_start(conn, triggered_by):
    cur = conn.execute(
        "INSERT INTO runs(started_at, triggered_by) VALUES(?, ?)",
        (now_iso(), triggered_by),
    )
    conn.commit()
    return cur.lastrowid


def run_finish(conn, run_id, feeds, counters):
    conn.execute(
        """UPDATE runs SET finished_at = ?, fetched = ?, dup_skipped = ?, l0_dropped = ?,
                           added = ?, revived = ?, notified = ?, feeds = ?
           WHERE id = ?""",
        (
            now_iso(),
            counters.get("fetched", 0),
            counters.get("dup_skipped", 0),
            counters.get("l0_dropped", 0),
            counters.get("added", 0),
            counters.get("revived", 0),
            counters.get("notified", 0),
            json.dumps(feeds, ensure_ascii=False),
            run_id,
        ),
    )
    conn.execute(
        "DELETE FROM run_dups WHERE run_id <= ?",
        (max(0, int(run_id) - KEEP_DUPS_FOR_RUNS),),
    )
    conn.commit()


def merge_source(conn, digest, source, url):
    """Attach a source to an existing vacancy (found on another board too).

    The first link for each source wins — the same source appearing again
    doesn't change the card. An empty/broken sources column is healed on the
    fly with the row's primary source, so old records don't lose their source.
    """
    row = conn.execute(
        "SELECT source, url, sources FROM jobs WHERE hash = ?", (digest,)
    ).fetchone()
    if row is None:
        return
    try:
        smap = json.loads(row["sources"]) if row["sources"] else {}
    except (ValueError, TypeError):
        smap = {}
    if not smap and row["source"]:
        smap[row["source"]] = row["url"]
    if source in smap:
        return
    smap[source] = url
    conn.execute(
        "UPDATE jobs SET sources = ? WHERE hash = ?",
        (json.dumps(smap, ensure_ascii=False), digest),
    )
    conn.commit()
