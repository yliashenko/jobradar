#!/usr/bin/env python3
"""In-process auto-scan for the web server.

Deliberately tied to the running `serve` process rather than cron/launchd: the
Settings toggle promises "auto-scan **while the app is open**", and that is exactly
what an in-process thread gives — close the server and the schedule stops. It reuses
the Runner (and therefore the run lock shared with the button and run.sh), so a
scheduled scan never overlaps a manual one.

Settings live in the profile and are read fresh on every tick, so changing the
cadence on the Settings page takes effect without a restart. The cadence is
reminder-style: `_matches()` decides whether `now` is a scheduled slot (the hour
anchors every repeat; weekly/biweekly add a weekday, monthly a day-of-month), and
a single minimum-gap guard keeps one slot from firing twice. `due()`/`tick()` are
pure decisions over an injected `now`, so the logic is unit-tested without threads
or real time; `clock.now()` is the same freezable seam the rest of the app uses.
"""

import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta

from jobradar import clock, paths

log = logging.getLogger("jobradar.scheduler")

# Scheduled slots are one-hour-wide and at least 6h apart (the every-6h case is the
# tightest), so a single "at least this long since the last trigger" guard both
# stops a slot from firing twice across the 60s polls and never blocks the next one.
_MIN_GAP = timedelta(hours=2)


def _num(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_settings():
    """The auto-scan settings from the profile, normalized to ints/str/bool."""
    from jobradar import candidate

    p = candidate.load()
    return {
        "enabled": bool(p.get("schedule_enabled")),
        "repeat": str(p.get("schedule_repeat") or "daily"),
        "hour": _num(p.get("schedule_hour"), 9),
        "weekday": _num(p.get("schedule_weekday"), 0),
        "monthday": _num(p.get("schedule_monthday"), 1),
    }


def _matches(now, s):
    """Whether `now` falls in a scheduled slot for the cadence. Cron-like: the hour
    anchors every repeat; every_6h/every_12h also fire every N hours off that anchor,
    weekly/biweekly gate on a weekday, monthly on a day-of-month. Biweekly aligns to
    even ISO weeks — there is no stored start date to anchor a rolling fortnight to."""
    hour, repeat = s["hour"], s["repeat"]
    if repeat == "every_6h":
        return (now.hour - hour) % 6 == 0
    if repeat == "every_12h":
        return (now.hour - hour) % 12 == 0
    if now.hour != hour:
        return False
    if repeat == "daily":
        return True
    if repeat == "weekday":
        return now.weekday() < 5
    if repeat == "weekly":
        return now.weekday() == s["weekday"]
    if repeat == "biweekly":
        return now.weekday() == s["weekday"] and now.isocalendar()[1] % 2 == 0
    if repeat == "monthly":
        return now.day == s["monthday"]
    return False


def last_run_at():
    """When the last run finished (local, aware) or None. Seeds the interval so a
    server restart doesn't kick off a redundant scan right away."""
    try:
        conn = sqlite3.connect(paths.db_path(), timeout=5)
        try:
            row = conn.execute(
                "SELECT finished_at FROM runs WHERE finished_at IS NOT NULL "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    if not row or not row[0]:
        return None
    try:
        return datetime.fromisoformat(row[0]).astimezone()
    except ValueError:
        return None


class Scheduler:
    """Triggers Runner on the profile's cadence while the server is up."""

    def __init__(
        self,
        runner,
        settings=load_settings,
        seed=last_run_at,
        poll_seconds=60,
    ):
        self.runner = runner
        self.settings = settings
        self.poll_seconds = poll_seconds
        self._last_trigger = seed() if seed else None
        self._thread = None

    def due(self, now, settings=None):
        """Whether a scan should start at `now` — enabled, `now` in a scheduled slot,
        and at least `_MIN_GAP` since the last trigger (so a slot fires once)."""
        s = settings if settings is not None else self.settings()
        if not s["enabled"]:
            return False
        if not _matches(now, s):
            return False
        if self._last_trigger is None:
            return True
        return (now - self._last_trigger) >= _MIN_GAP

    def tick(self, now):
        """One scheduler beat. Returns the Runner result ('started'/'busy') or None
        when nothing was due. Only a real 'started' advances the interval clock."""
        if not self.due(now):
            return None
        result = self.runner.trigger()
        if result == "started":
            self._last_trigger = now
            log.info("scheduler: auto-scan started")
        return result

    def _loop(self):
        while True:
            time.sleep(self.poll_seconds)
            try:
                self.tick(clock.now().astimezone())
            except Exception:
                log.exception("scheduler tick failed")

    def start(self):
        self._thread = threading.Thread(
            target=self._loop, name="jobradar-scheduler", daemon=True
        )
        self._thread.start()
        log.info("scheduler thread started (poll every %ds)", self.poll_seconds)
        return self
