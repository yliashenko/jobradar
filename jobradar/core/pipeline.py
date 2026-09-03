"""Run orchestration: collect → dedup/L0/store → scoring/notification → journal.

run() is the whole run, split into steps (_store, _score_and_notify), each tested
separately. Sources and scorer are swappable (requirements #3, #4):
run(cfg, args, http=None, scorer=None). Time via clock, DB via core.db.
"""

import json
import logging
from datetime import datetime, timedelta

from jobradar import clock
from jobradar.core import sources
from jobradar.core.db import (
    db_connect,
    merge_source,
    meta_get,
    meta_set,
    now_iso,
    run_finish,
    run_start,
)
from jobradar.core.dedup import job_hash
from jobradar.core.filters import l0_filter
from jobradar.core.notify import (
    effective_telegram,
    effective_threshold,
    format_notification,
    heartbeat_hours,
    telegram_enabled,
    telegram_send,
)
from jobradar.core.scoring import (
    RUBRIC_VERSION,
    build_scorer,
    effective_api_key,
    load_profile,
)
from jobradar.core.text import escape

log = logging.getLogger("jobradar")


def run(cfg, args, http=None, scorer=None, notify=None):
    """A full run. http/scorer/notify are injected in tests (requirements #3, #4)."""
    notify = notify or telegram_send
    conn = db_connect()
    # triggered_by: CLI/run.sh don't set it (→ 'cron'), the webui button sets 'button'.
    run_id = run_start(conn, getattr(args, "triggered_by", "cron"))
    # core.sources knows the active sources (boards, or a fixture for e2e); feeds
    # accumulates a row per feed for the /runs page.
    feeds = []
    collected = sources.collect(cfg, report=feeds, http=http)
    log.info("Collected in total: %d records (before dedup)", len(collected))

    new_jobs, counters = _store(conn, run_id, collected, cfg)
    if collected:
        meta_set(conn, "last_collect_ok", now_iso())
    if new_jobs:
        meta_set(conn, "last_new_job_at", now_iso())

    counters["notified"] = _score_and_notify(conn, cfg, new_jobs, args, scorer, notify)
    run_finish(conn, run_id, feeds, counters)
    heartbeat(conn, args.dry_run, notify)
    conn.close()
    return 0


def _store(conn, run_id, collected, cfg):
    """Dedup within TTL + L0 + store. Returns (new vacancies, funnel counters)."""
    new_jobs = []
    ttl_days = int(cfg.get("dedup_ttl_days", 180))
    cutoff = (clock.now() - timedelta(days=ttl_days)).isoformat(timespec="seconds")
    revived = dup_skipped = l0_dropped = 0
    for job in collected:
        digest = job_hash(job["company"] or job["url"], job["title"])
        # Already seen — only if within TTL; older than that is the same role afresh.
        exists = conn.execute(
            "SELECT hash FROM jobs WHERE hash = ? AND first_seen > ?", (digest, cutoff)
        ).fetchone()
        if exists:
            # The dropped record goes to the journal, else the dedup decision is left nowhere.
            dup_skipped += 1
            conn.execute(
                "INSERT INTO run_dups(run_id, hash, source, url, title, company)"
                " VALUES(?,?,?,?,?,?)",
                (
                    run_id,
                    digest,
                    job["source"],
                    job["url"],
                    job["title"],
                    job["company"],
                ),
            )
            # The same vacancy found on another board — append the source.
            merge_source(conn, digest, job["source"], job["url"])
            continue
        stale = conn.execute(
            "SELECT first_seen FROM jobs WHERE hash = ?", (digest,)
        ).fetchone()
        if stale:
            revived += 1
            log.info(
                "Reopened vacancy (last seen %s): %s",
                stale["first_seen"][:10],
                job["title"][:60],
            )
        passed, reason = l0_filter(job, cfg.get("l0", {}))
        conn.execute(
            """INSERT OR REPLACE INTO jobs(hash, source, url, title, company, location, salary,
                                           description, description_html, published_at,
                                           extra, sources, first_seen, l0_pass, l0_reason,
                                           status, run_id)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'new',?)""",
            (
                digest,
                job["source"],
                job["url"],
                job["title"],
                job["company"],
                job["location"],
                job["salary"],
                job["description"],
                # A source may give no HTML markup or publish date — left empty then.
                job.get("description_html", ""),
                job.get("published_at") or None,
                job.get("extra", ""),
                json.dumps({job["source"]: job["url"]}, ensure_ascii=False),
                now_iso(),
                1 if passed else 0,
                reason,
                run_id,
            ),
        )
        conn.commit()
        if passed:
            job["hash"] = digest
            new_jobs.append(job)
        else:
            l0_dropped += 1
            log.debug("L0 filtered out %r: %s", job["title"][:60], reason)

    log.info(
        "New after dedup and L0: %d (of them reopened: %d)",
        len(new_jobs),
        revived,
    )
    counters = {
        "fetched": len(collected),
        "dup_skipped": dup_skipped,
        "l0_dropped": l0_dropped,
        "added": len(new_jobs),
        "revived": revived,
    }
    return new_jobs, counters


def _score_and_notify(conn, cfg, new_jobs, args, scorer=None, notify=telegram_send):
    """Score (swappable scorer), store the score, send those above the threshold."""
    scorer_cfg = cfg.get("scorer", {})
    if scorer is None:
        # The key lives only in the profile (Settings page) — one helper decides,
        # so gating and build_scorer never disagree.
        api_key = effective_api_key()
        profile = load_profile() if (scorer_cfg.get("enabled") and api_key) else ""
        scorer = build_scorer(cfg, profile=profile)
    threshold = effective_threshold()
    bot_token, chat_id = effective_telegram()
    notify_on = telegram_enabled()
    # Silent failure is the top risk (CLAUDE.md §4): if the bot is on but has no
    # token, matches would vanish with no trace — say so in the log.
    if notify_on and new_jobs and not (bot_token and chat_id):
        log.warning("Telegram is on but not configured — matches won't be delivered")

    sent = 0
    for job in new_jobs:
        row = scorer.score(job)
        if row["score"] is not None:
            conn.execute(
                """UPDATE jobs SET score = ?, band = ?, verdict = ?, matched = ?, gaps = ?,
                                   rubric = ?, scored_at = ? WHERE hash = ?""",
                (
                    row["score"],
                    row["band"],
                    row["verdict"],
                    json.dumps(row["matched"], ensure_ascii=False),
                    json.dumps(row["gaps"], ensure_ascii=False),
                    RUBRIC_VERSION,
                    now_iso(),
                    job["hash"],
                ),
            )
            conn.commit()
        # The bot master switch is off: the score is stored (the web feed still
        # shows it), but nothing goes to Telegram.
        if not notify_on:
            continue
        if row["score"] is not None and row["score"] < threshold:
            log.info(
                "Below threshold (%.1f < %.1f): %s",
                row["score"],
                threshold,
                job["title"][:60],
            )
            continue
        text = format_notification(job, row)
        if notify(bot_token, chat_id, text, args.dry_run):
            sent += 1
            if not args.dry_run:
                conn.execute(
                    "UPDATE jobs SET notified_at = ? WHERE hash = ?",
                    (now_iso(), job["hash"]),
                )
                conn.commit()
    log.info("Messages sent: %d", sent)
    return sent


def heartbeat(conn, dry_run, notify=telegram_send):
    """If there's been NOTHING new for a long time — suspect a silent parser failure.

    24h without a new record → a signal to Telegram (CLAUDE.md §4). Don't remove
    it when refactoring: an empty feed and a broken parser look identical. The
    window is a profile setting (heartbeat_hours), not config.json.
    """
    hours = heartbeat_hours()
    last_new = meta_get(conn, "last_new_job_at", "")
    last_alert = meta_get(conn, "last_heartbeat_alert", "")
    now = clock.now()
    if not last_new:
        meta_set(conn, "last_new_job_at", now_iso())
        return
    try:
        last_new_dt = datetime.fromisoformat(last_new)
    except ValueError:
        return
    if (now - last_new_dt) < timedelta(hours=hours):
        return
    if last_alert:
        try:
            if (now - datetime.fromisoformat(last_alert)) < timedelta(hours=hours):
                return
        except ValueError:
            pass
    total = conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"]
    text = (
        f"🔕 <b>jobradar: silence for {hours}h</b>\n"
        f"No new vacancy since {escape(last_new[:16])}. Either the market really is "
        "empty, or a feed broke silently (a DOU/Djinni RSS layout change).\n"
        f"Total in the DB: {total}."
    )
    if not telegram_enabled():
        return
    bot_token, chat_id = effective_telegram()
    if notify(bot_token, chat_id, text, dry_run):
        meta_set(conn, "last_heartbeat_alert", now_iso())
