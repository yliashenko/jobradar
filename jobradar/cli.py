"""CLI: `python -m jobradar run|check|top|stats`.

A thin layer over pipeline and core: argument parsing, console printing, dispatch.
run() goes to core.pipeline; check/top/stats read the DB and network directly.
"""

import argparse
import imaplib
from datetime import timedelta

from jobradar import clock
from jobradar.config import load_config, setup_logging
from jobradar.core import pipeline
from jobradar.core.db import db_connect, meta_get
from jobradar.core.http import http_get
from jobradar.core.notify import effective_telegram, telegram_send
from jobradar.core.scoring import DEFAULT_MODEL, llm_settings, load_profile, score_job


def cmd_check(cfg, args):
    """Check that everything connected responds. Writes nothing to the DB."""
    ok = True

    dou_cfg = cfg.get("sources", {}).get("dou", {})
    if dou_cfg.get("enabled"):
        for url in dou_cfg.get("feeds", []):
            try:
                raw = http_get(url)
                count = raw.count("<item>")
                print(f"DOU OK   {url[:70]:<70} {count} records")
                if count == 0:
                    ok = False
            except Exception as exc:
                print(f"DOU FAIL {url[:70]:<70} {exc}")
                ok = False
    else:
        print("DOU      disabled in config")

    imap_cfg = cfg.get("sources", {}).get("imap", {})
    if imap_cfg.get("enabled"):
        try:
            conn = imaplib.IMAP4_SSL(imap_cfg["host"], int(imap_cfg.get("port", 993)))
            conn.login(imap_cfg["user"], imap_cfg["password"])
            folder = imap_cfg.get("folder", "INBOX")
            status, _ = conn.select(folder)
            if status == "OK":
                days = int(imap_cfg.get("lookback_days", 3))
                since = (clock.now() - timedelta(days=days)).strftime("%d-%b-%Y")
                _, data = conn.search(None, f'(UNSEEN SINCE "{since}")')
                print(
                    f"IMAP OK  folder {folder!r}, unread in period: {len(data[0].split())}"
                )
            else:
                print(f"IMAP FAIL couldn't open folder {folder!r}")
                ok = False
            conn.logout()
        except Exception as exc:
            print(f"IMAP FAIL {exc}")
            ok = False
    else:
        print("IMAP     disabled in config")

    scorer_cfg = cfg.get("scorer", {})
    # Resolve the key the same way the pipeline does (Profile → config → env), so
    # `check` reflects reality when the key lives in the profile, not config.json.
    provider, base_url, api_key = llm_settings(cfg)
    if scorer_cfg.get("enabled") and api_key:
        sample = {
            "title": "Senior QA Automation Engineer",
            "company": "Test Company",
            "location": "remote",
            "salary": "$4000",
            "description": "TypeScript, Playwright, API automation, GitLab CI, AWS.",
        }
        try:
            result = score_job(
                sample,
                api_key,
                scorer_cfg.get("model", DEFAULT_MODEL),
                load_profile(),
                int(scorer_cfg.get("timeout_seconds", 60)),
                provider=provider,
                base_url=base_url,
            )
            print(
                f"SCORER OK test vacancy scored {result['score']:g}/10 ({result['band']})"
            )
        except Exception as exc:
            print(f"SCORER FAIL {exc}")
            ok = False
    else:
        print("SCORER   disabled or no key — notifications will go out without a score")

    bot_token, chat_id = effective_telegram()
    if telegram_send(
        bot_token,
        chat_id,
        "✅ jobradar: connectivity check",
        args.dry_run,
    ):
        print("TELEGRAM OK")
    else:
        print("TELEGRAM FAIL")
        ok = False

    print(
        "\nSummary: "
        + ("all set" if ok else "there are problems, see the FAIL lines above")
    )
    return 0 if ok else 1


def cmd_top(cfg, args):
    conn = db_connect()
    rows = conn.execute(
        """SELECT title, company, salary, score, band, verdict, url, source, first_seen
           FROM jobs WHERE l0_pass = 1
           ORDER BY (score IS NULL), score DESC, first_seen DESC LIMIT ?""",
        (args.limit,),
    ).fetchall()
    if not rows:
        print("The DB is empty — run `python3 -m jobradar run` first.")
        return 0
    for row in rows:
        score = f"{row['score']:g}" if row["score"] is not None else "—"
        print(
            f"{score:<5} {row['source']:<9} {row['title'][:46]:<46} "
            f"{(row['company'] or '')[:22]:<22} {row['url']}"
        )
        if row["verdict"]:
            print(f"      {row['verdict']}")
    conn.close()
    return 0


def cmd_stats(cfg, args):
    conn = db_connect()
    total = conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"]
    passed = conn.execute(
        "SELECT COUNT(*) AS c FROM jobs WHERE l0_pass = 1"
    ).fetchone()["c"]
    notified = conn.execute(
        "SELECT COUNT(*) AS c FROM jobs WHERE notified_at IS NOT NULL"
    ).fetchone()["c"]
    print(f"Collected in total:  {total}")
    print(f"Passed L0:           {passed}")
    print(f"Sent to TG:          {notified}")
    print(f"Last collect:        {meta_get(conn, 'last_collect_ok') or 'not yet'}")
    print(f"Last new vacancy:    {meta_get(conn, 'last_new_job_at') or 'not yet'}")
    print("\nBy source:")
    for row in conn.execute(
        "SELECT source, COUNT(*) AS c FROM jobs GROUP BY source ORDER BY c DESC"
    ):
        print(f"  {row['source']:<10} {row['c']}")
    print("\nTop L0 filter reasons:")
    for row in conn.execute(
        """SELECT l0_reason, COUNT(*) AS c FROM jobs
           WHERE l0_pass = 0 AND l0_reason <> '' GROUP BY l0_reason ORDER BY c DESC LIMIT 8"""
    ):
        print(f"  {row['c']:<4} {row['l0_reason'][:80]}")
    conn.close()
    return 0


def main():
    parser = argparse.ArgumentParser(description="jobradar — vacancy monitoring")
    parser.add_argument("--verbose", action="store_true", help="verbose log")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="collect, filter, score, send")
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="send nothing to Telegram, print to the console",
    )

    check_parser = sub.add_parser("check", help="check all connections")
    check_parser.add_argument(
        "--dry-run", action="store_true", help="don't send a test message"
    )

    top_parser = sub.add_parser("top", help="show the best vacancies from the DB")
    top_parser.add_argument("--limit", type=int, default=15)

    sub.add_parser("stats", help="DB statistics")

    args = parser.parse_args()
    setup_logging(args.verbose)
    cfg = load_config()

    handlers = {
        "run": pipeline.run,
        "check": cmd_check,
        "top": cmd_top,
        "stats": cmd_stats,
    }
    return handlers[args.command](cfg, args)
