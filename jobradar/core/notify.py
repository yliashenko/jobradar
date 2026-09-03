"""Notification: format a vacancy card and send it to Telegram.

Telegram is the single output channel (CLAUDE.md: the tool sends matches to
Telegram, then web triage). http_post is injected for tests; format_notification
is pure.
"""

import logging

from jobradar.core.http import http_post_json
from jobradar.core.text import escape

log = logging.getLogger("jobradar")


# These read the profile as the SINGLE source of truth — config.json no longer
# carries telegram credentials, the notify threshold or the heartbeat window (one
# settings home, edited on the Profile page).


def effective_telegram():
    """(bot_token, chat_id) for the output channel, from profile.json. bot_token
    from @BotFather, chat_id from getUpdates; personal data, never committed."""
    from jobradar import candidate

    prof = candidate.load()
    return prof.get("telegram_bot_token", ""), prof.get("telegram_chat_id", "")


def telegram_enabled():
    """The bot master switch (default on). Off → pipeline scores and stores as
    usual but pushes nothing to Telegram. `check` still probes."""
    from jobradar import candidate

    return bool(candidate.load().get("telegram_enabled", True))


def effective_threshold():
    """Notify cutoff (default 7). A vacancy is pushed when its score is ≥ this;
    the web feed bands against the same number."""
    from jobradar import candidate

    raw = str(candidate.load().get("notify_min_score", "")).strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return 7.0


def heartbeat_hours():
    """Silence window before the "nothing new" alert (default 24h; CLAUDE.md §4)."""
    from jobradar import candidate

    try:
        return int(candidate.load().get("heartbeat_alert_hours", 24))
    except (TypeError, ValueError):
        return 24


def telegram_send(bot_token, chat_id, text, dry_run, http_post=None):
    if dry_run:
        print(
            "\n----- TELEGRAM (dry-run) -----\n"
            + text
            + "\n------------------------------"
        )
        return True
    post = http_post or http_post_json
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        result = post(url, payload, {}, timeout=25)
        if not result.get("ok"):
            log.error("Telegram refused: %s", result)
            return False
        return True
    except Exception as exc:
        log.error("Telegram didn't respond: %s", exc)
        return False


def format_notification(job, row):
    lines = []
    score = row.get("score")
    if score is not None:
        head = f"🎯 <b>{escape(job['title'])}</b> — {score:g}/10"
    else:
        head = f"🎯 <b>{escape(job['title'])}</b>"
    lines.append(head)
    meta = []
    if job["company"]:
        meta.append(escape(job["company"]))
    if job["salary"]:
        meta.append(escape(job["salary"]))
    if job["location"]:
        meta.append(escape(job["location"]))
    meta.append(job["source"])
    lines.append(" · ".join(meta))
    if row.get("verdict"):
        lines.append("")
        lines.append(f"<i>{escape(row['verdict'])}</i>")
    if row.get("matched"):
        lines.append("")
        lines.append("✅ " + escape("; ".join(row["matched"])))
    if row.get("gaps"):
        lines.append("⚠️ " + escape("; ".join(row["gaps"])))
    lines.append("")
    lines.append(job["url"])
    return "\n".join(lines)
