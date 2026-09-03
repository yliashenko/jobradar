"""Auto-scan scheduler: the due()/tick() decision, deterministically — no threads,
no real time, settings and last-run seed injected."""

from datetime import datetime, timedelta

from jobradar.scheduler import Scheduler


class _FakeRunner:
    def __init__(self, result="started"):
        self.result = result
        self.calls = 0

    def trigger(self):
        self.calls += 1
        return self.result


def _sched(runner=None, seed=None, **settings):
    base = {"enabled": True, "interval_hours": 3, "start_hour": 8, "end_hour": 23}
    base.update(settings)
    return Scheduler(
        runner or _FakeRunner(), settings=lambda: base, seed=(lambda: seed)
    )


def test_disabled_never_due():
    s = _sched(enabled=False)
    assert s.due(datetime(2026, 9, 3, 12, 0)) is False


def test_outside_window_not_due():
    s = _sched(start_hour=8, end_hour=23)
    assert s.due(datetime(2026, 9, 3, 6, 0)) is False  # before start
    assert s.due(datetime(2026, 9, 3, 23, 0)) is False  # end hour is exclusive


def test_within_window_no_prior_run_is_due():
    s = _sched(seed=None)
    assert s.due(datetime(2026, 9, 3, 9, 0)) is True


def test_recent_run_blocks_until_interval_elapses():
    now = datetime(2026, 9, 3, 12, 0)
    s = _sched(seed=now - timedelta(hours=2), interval_hours=3)
    assert s.due(now) is False
    assert s.due(now + timedelta(hours=1, minutes=1)) is True  # 3h+ since last


def test_tick_triggers_and_advances_the_interval():
    runner = _FakeRunner("started")
    s = _sched(runner=runner, seed=None, interval_hours=3)
    now = datetime(2026, 9, 3, 9, 0)
    assert s.tick(now) == "started" and runner.calls == 1
    # not due again until the interval elapses
    assert s.tick(now + timedelta(minutes=30)) is None and runner.calls == 1


def test_tick_busy_does_not_advance_the_interval():
    # A busy runner (a manual scan holds the lock) must not move the interval clock.
    runner = _FakeRunner("busy")
    s = _sched(runner=runner, seed=None)
    now = datetime(2026, 9, 3, 9, 0)
    assert s.tick(now) == "busy"
    assert s.due(now + timedelta(minutes=1)) is True  # still due, nothing ran
