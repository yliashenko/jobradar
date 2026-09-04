"""Auto-scan scheduler: the due()/tick() decision, deterministically — no threads,
no real time, settings and last-run seed injected.

The cadence is reminder-style: a `repeat` (hourly, daily, weekday, weekly, biweekly,
monthly) anchored on an `hour`, with a `weekday` for the weekly ones and a `monthday`
for monthly. `_matches` picks the slots; a fixed minimum gap keeps a slot firing once.
"""

from datetime import datetime, timedelta

from jobradar.scheduler import Scheduler

# Reference days used below (weekday() has Mon=0 … Sun=6; ISO-week parity matters
# only for biweekly): 2026-09-07 Mon (ISO week 37, odd), 2026-09-14 Mon (week 38,
# even), 2026-09-12 Sat, 2026-09-13 Sun.


class _FakeRunner:
    def __init__(self, result="started"):
        self.result = result
        self.calls = 0

    def trigger(self):
        self.calls += 1
        return self.result


def _sched(runner=None, seed=None, **settings):
    base = {"enabled": True, "repeat": "daily", "hour": 8, "weekday": 0, "monthday": 1}
    base.update(settings)
    return Scheduler(
        runner or _FakeRunner(), settings=lambda: base, seed=(lambda: seed)
    )


def test_disabled_never_due():
    s = _sched(enabled=False, repeat="daily")
    assert s.due(datetime(2026, 9, 7, 8, 0)) is False


def test_daily_only_fires_at_the_anchor_hour():
    s = _sched(repeat="daily", hour=8, seed=None)
    assert s.due(datetime(2026, 9, 7, 8, 0)) is True
    assert s.due(datetime(2026, 9, 7, 9, 0)) is False  # wrong hour
    assert s.due(datetime(2026, 9, 7, 7, 0)) is False


def test_every_6h_fires_off_the_anchor():
    s = _sched(repeat="every_6h", hour=8, seed=None)
    for hour in (8, 14, 20, 2):
        assert s.due(datetime(2026, 9, 7, hour, 0)) is True, hour
    assert s.due(datetime(2026, 9, 7, 9, 0)) is False
    assert s.due(datetime(2026, 9, 7, 11, 0)) is False


def test_every_12h_fires_twice_a_day():
    s = _sched(repeat="every_12h", hour=8, seed=None)
    assert s.due(datetime(2026, 9, 7, 8, 0)) is True
    assert s.due(datetime(2026, 9, 7, 20, 0)) is True
    assert s.due(datetime(2026, 9, 7, 14, 0)) is False


def test_weekday_skips_the_weekend():
    s = _sched(repeat="weekday", hour=8, seed=None)
    assert s.due(datetime(2026, 9, 7, 8, 0)) is True  # Monday
    assert s.due(datetime(2026, 9, 12, 8, 0)) is False  # Saturday
    assert s.due(datetime(2026, 9, 13, 8, 0)) is False  # Sunday


def test_weekly_only_on_the_chosen_weekday():
    s = _sched(repeat="weekly", hour=8, weekday=0, seed=None)  # Mondays
    assert s.due(datetime(2026, 9, 7, 8, 0)) is True  # Monday
    assert s.due(datetime(2026, 9, 8, 8, 0)) is False  # Tuesday
    assert s.due(datetime(2026, 9, 7, 9, 0)) is False  # right day, wrong hour


def test_biweekly_only_on_even_iso_weeks():
    s = _sched(repeat="biweekly", hour=8, weekday=0, seed=None)  # Mondays, fortnightly
    assert s.due(datetime(2026, 9, 7, 8, 0)) is False  # Monday, ISO week 37 (odd)
    assert s.due(datetime(2026, 9, 14, 8, 0)) is True  # Monday, ISO week 38 (even)


def test_monthly_only_on_the_chosen_day_of_month():
    s = _sched(repeat="monthly", hour=8, monthday=15, seed=None)
    assert s.due(datetime(2026, 9, 15, 8, 0)) is True
    assert s.due(datetime(2026, 9, 14, 8, 0)) is False
    assert s.due(datetime(2026, 9, 15, 9, 0)) is False  # right day, wrong hour


def test_a_slot_fires_once_then_the_gap_blocks_re_fire():
    # The 60s poll hits the slot's hour many times; the min-gap fires it just once.
    now = datetime(2026, 9, 7, 8, 0)
    s = _sched(repeat="daily", hour=8, seed=now - timedelta(minutes=30))
    assert s.due(now) is False  # a run 30 min ago (inside the gap) blocks it
    s2 = _sched(repeat="daily", hour=8, seed=now - timedelta(hours=25))
    assert s2.due(now) is True  # a day-old run is well past the gap


def test_tick_triggers_and_the_gap_holds_the_rest_of_the_slot():
    runner = _FakeRunner("started")
    s = _sched(runner=runner, repeat="daily", hour=8, seed=None)
    now = datetime(2026, 9, 7, 8, 0)
    assert s.tick(now) == "started" and runner.calls == 1
    # later polls in the same 08:00 slot don't fire again
    assert s.tick(now + timedelta(minutes=30)) is None and runner.calls == 1
    # the next day's slot fires
    assert s.tick(now + timedelta(days=1)) == "started" and runner.calls == 2


def test_tick_busy_does_not_advance_the_gap():
    # A busy runner (a manual scan holds the lock) must not move the gap clock.
    runner = _FakeRunner("busy")
    s = _sched(runner=runner, repeat="daily", hour=8, seed=None)
    now = datetime(2026, 9, 7, 8, 0)
    assert s.tick(now) == "busy"
    assert s.due(now + timedelta(minutes=1)) is True  # still due, nothing ran
