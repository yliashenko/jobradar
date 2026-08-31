#!/usr/bin/env python3
"""
jobradar runner — one pipeline, two triggers.

The same `cmd_run` from engine.py runs both on a schedule (run.sh) and by hand
from the web UI (the "Refresh now" button). The collection logic isn't
duplicated here — this module only decides whether a start is allowed right now,
and holds the state for the header indicator.

The lock is the same `.lock` directory as run.sh, with the same staleness rule
(one hour). This is deliberate: if the webui had its own lock, the button and
the scheduler could coincide within a second and launch two parallel runs over
one database. `mkdir` is atomic on POSIX, so the inter-process guard needs no
dependency.
"""

import logging
import os
import sqlite3
import threading
import time
import types

from jobradar import paths
from jobradar.config import load_config
from jobradar.core import pipeline

# The lock lives under HOME (= project root in prod) to match run.sh (which creates
# .lock in its own directory). If it lived in the package, the button and cron would hold different locks.
LOCK_DIR = paths.lock_dir()

# Nobody reads the machine exception text in the header. We translate the most
# common cases into human terms; the rest stays as is — better unclear than lying.
ERROR_HINTS = (
    ("nodename nor servname", "no internet, or DNS isn't responding"),
    ("Name or service not known", "no internet, or DNS isn't responding"),
    ("timed out", "the source didn't respond in time"),
    ("Connection refused", "the source refused the connection"),
    ("Connection reset", "the source dropped the connection"),
    ("certificate verify failed", "the site's certificate didn't check out"),
    ("HTTP Error 404", "no page at that address (404)"),
    ("HTTP Error 403", "the source denied access (403)"),
    ("HTTP Error 429", "the source is asking to slow down (429)"),
    ("HTTP Error 5", "the source had an internal error"),
    ("no such table", "the DB is missing a required table — a migration didn't run"),
    ("database is locked", "the DB is busy with another process"),
    ("authentication failed", "the mailbox rejected the login or password"),
    ("AUTHENTICATIONFAILED", "the mailbox rejected the login or password"),
)


def describe_error(exc):
    """Exception → a line for a human."""
    raw = str(exc) or type(exc).__name__
    for needle, human in ERROR_HINTS:
        if needle.lower() in raw.lower():
            return human
    if isinstance(exc, KeyError):
        return f"config.json is missing the field {raw}"
    return raw


# The same value as in run.sh. If you change it — change it in both places,
# otherwise one trigger will consider the lock alive while the other sees it stale.
STALE_LOCK_SECONDS = 3600

log = logging.getLogger("engine.runner")


class RunLock:
    """Inter-process lock on a directory. Compatible with run.sh's lock."""

    def __init__(
        self, path=LOCK_DIR, stale_seconds=STALE_LOCK_SECONDS, clock=time.time
    ):
        self.path = path
        self.stale_seconds = stale_seconds
        self.clock = clock
        self.owned = False

    def exists(self):
        return os.path.isdir(self.path)

    def age_seconds(self):
        """How long the lock has been held. None if there's no lock."""
        try:
            return self.clock() - os.path.getmtime(self.path)
        except OSError:
            return None

    def acquire(self, _retry=True):
        """True — the lock is ours and we can work. False — someone else is already running."""
        try:
            os.mkdir(self.path)
            self.owned = True
            return True
        except FileExistsError:
            pass

        age = self.age_seconds()
        if age is None:
            # The directory vanished between mkdir and getmtime — retry, but exactly
            # once: a loop here would mean we're spinning inside someone else's race.
            return self.acquire(_retry=False) if _retry else False
        if age <= self.stale_seconds:
            return False

        # Stale lock: the previous run died without cleaning up (kill -9, power
        # loss). We remove it — same as run.sh does.
        log.warning("Found a stale lock (%d s), removing it.", int(age))
        try:
            os.rmdir(self.path)
        except OSError:
            return False
        try:
            os.mkdir(self.path)
        except OSError:
            return False
        self.owned = True
        return True

    def release(self):
        if not self.owned:
            return
        try:
            os.rmdir(self.path)
        except OSError as exc:
            log.error("Couldn't remove the lock %s: %s", self.path, exc)
        self.owned = False

    def held_elsewhere(self):
        """The lock exists but isn't ours — a scheduled run is in progress.

        A lock older than the stale threshold is a dead run, not a live one: the
        next acquire() reclaims it. The UI must not report it as "scanning" —
        that disables the Scan button, and the only thing that clears the lock is
        the acquire() a scan triggers, so a crashed run would wedge the UI until
        a scheduled run happens to clear it."""
        if self.owned or not self.exists():
            return False
        age = self.age_seconds()
        return age is not None and age <= self.stale_seconds


def last_run_stats(db_path):
    """Summary of the last run — the same line /runs shows.

    The button used to count the row-count difference in jobs and show "+9 new"
    even when only 4 reached the feed: L0-filtered rows land in the DB too. Two
    different sources for one number — a guaranteed mismatch, so the source is
    now single — the run journal.
    """
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """SELECT added, l0_dropped, dup_skipped, fetched FROM runs
                   WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def default_run(cfg):
    """The same entry point as `python3 -m jobradar run`.

    We re-read the config here rather than using the startup one: between server
    runs the user may have changed the role in the profile, and "Save & Scan"
    must scan with the new role, not the one that was set when webui started.
    """
    fresh = load_config()
    return pipeline.run(
        fresh, types.SimpleNamespace(dry_run=False, triggered_by="button")
    )


class Runner:
    """State of a manual run: whether it's running, when it finished, how it ended."""

    def __init__(
        self,
        cfg,
        run_func=default_run,
        lock=None,
        db_path=None,
        clock=time.time,
    ):
        self.cfg = cfg
        self.run_func = run_func
        self.lock = lock if lock is not None else RunLock(clock=clock)
        self.db_path = db_path if db_path is not None else paths.db_path()
        self.clock = clock
        self._guard = threading.Lock()
        self._running = False
        self._started_at = None
        self._finished_at = None
        self._error = ""
        self._added = None
        self._thread = None

    # -- trigger -----------------------------------------------------------

    def trigger(self):
        """'started' — a new run began, 'busy' — something is already running.

        The check and the lock acquisition are under one mutex: two simultaneous
        POSTs would otherwise both see `_running is False` and start twice.
        """
        with self._guard:
            if self._running:
                return "busy"
            if not self.lock.acquire():
                return "busy"
            self._running = True
            self._started_at = self.clock()
            self._error = ""
            self._added = None
            self._thread = threading.Thread(
                target=self._work, name="jobradar-run", daemon=True
            )
            self._thread.start()
            return "started"

    def _work(self):
        try:
            self.run_func(self.cfg)
            error = ""
        except BaseException as exc:
            log.exception("Manual run failed")
            error = describe_error(exc)
        with self._guard:
            self._running = False
            self._finished_at = self.clock()
            self._error = error
            self.lock.release()

    # -- state for the indicator ------------------------------------------

    def status(self):
        with self._guard:
            running = self._running
            snapshot = {
                "running": running,
                "started_at": self._started_at,
                "finished_at": self._finished_at,
                "error": self._error,
            }
        # The lock is someone else's — a run is in another process (run.sh on schedule).
        snapshot["external"] = (not running) and self.lock.held_elsewhere()
        return snapshot

    def wait(self, timeout=None):
        """For tests only: wait until the run thread finishes."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
