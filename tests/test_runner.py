"""Фоновий прогін: міжпроцесний лок і single-flight кнопки «Scan!».

runner — конкурентний код: кнопка webui і cron ділять одну БД, тому один
лок не має пускати два прогони, а падіння мусить звільняти лок (інакше кнопка
залипає на годину).
"""

import logging
import threading
import time

from jobradar import runner
from jobradar.web import views


class TestRunLock:
    def test_holds_against_second(self, tmp_path):
        path = str(tmp_path / ".lock")
        mine = runner.RunLock(path=path)
        assert mine.acquire() is True

        cron = runner.RunLock(path=path)  # роль run.sh за розкладом
        assert cron.acquire() is False
        assert cron.held_elsewhere() is True

        mine.release()
        assert not (tmp_path / ".lock").is_dir()
        assert cron.acquire() is True
        cron.release()

    def test_stale_lock_reclaimed(self, tmp_path):
        path = str(tmp_path / ".lock")
        (tmp_path / ".lock").mkdir()  # процес помер, не прибравши
        stale = runner.RunLock(path=path, clock=lambda: time.time() + 2 * 3600)
        assert stale.acquire() is True
        stale.release()

    def test_fresh_lock_not_reclaimed(self, tmp_path):
        path = str(tmp_path / ".lock")
        (tmp_path / ".lock").mkdir()
        fresh = runner.RunLock(path=path, clock=lambda: time.time() + 60)
        assert fresh.acquire() is False

    def test_stale_lock_not_held_elsewhere(self, tmp_path):
        # мертвий забіг не прибрав лок — UI не має показувати "scanning",
        # інакше кнопка Scan лишиться заблокованою
        path = str(tmp_path / ".lock")
        (tmp_path / ".lock").mkdir()
        stale = runner.RunLock(path=path, clock=lambda: time.time() + 2 * 3600)
        assert stale.held_elsewhere() is False
        fresh = runner.RunLock(path=path, clock=lambda: time.time() + 60)
        assert fresh.held_elsewhere() is True


class TestRunnerSingleFlight:
    def test_second_trigger_is_busy(self, tmp_path):
        gate = threading.Event()
        calls = []

        def slow_run(cfg):
            calls.append(cfg)
            gate.wait(5)

        rn = runner.Runner(
            {},
            run_func=slow_run,
            lock=runner.RunLock(path=str(tmp_path / ".lock")),
            db_path=str(tmp_path / "jobs.db"),
        )
        first = rn.trigger()
        for _ in range(200):  # чекаємо, поки потік реально зайде в run_func
            if calls:
                break
            time.sleep(0.01)
        second = rn.trigger()
        mid = rn.status()
        gate.set()
        rn.wait(5)
        done = rn.status()

        assert first == "started"
        assert second == "busy"
        assert len(calls) == 1  # другий тригер не породив другий прогін
        assert mid["running"] is True
        assert done["running"] is False and done["error"] == ""
        assert not (tmp_path / ".lock").is_dir()  # лок знято


class TestRunnerFailure:
    def test_failure_releases_lock(self, tmp_path):
        quiet = logging.NullHandler()
        runner.log.addHandler(quiet)
        runner.log.propagate = False
        try:

            def broken_run(cfg):
                raise RuntimeError("DOU не відповів")

            rn = runner.Runner(
                {},
                run_func=broken_run,
                lock=runner.RunLock(path=str(tmp_path / ".lock")),
                db_path=str(tmp_path / "jobs.db"),
            )
            rn.trigger()
            rn.wait(5)
            done = rn.status()
            assert done["running"] is False
            assert "DOU не відповів" in done["error"]
            assert not (tmp_path / ".lock").is_dir()
            # наступний тригер після падіння можливий
            again = runner.Runner(
                {},
                run_func=lambda cfg: None,
                lock=runner.RunLock(path=str(tmp_path / ".lock")),
                db_path=str(tmp_path / "jobs.db"),
            )
            assert again.trigger() == "started"
        finally:
            runner.log.removeHandler(quiet)
            runner.log.propagate = True

    def test_network_error_humanised(self):
        assert (
            runner.describe_error(OSError("[Errno 8] nodename nor servname provided"))
            == "no internet, or DNS isn't responding"
        )


class TestRunActivityText:
    def test_running_shows_live(self):
        cls, text = views.run_activity_text(
            {"running": True, "started_at": time.time()}
        )
        assert "scan running" in text and "live" in cls

    def test_external_run_labelled(self):
        _cls, text = views.run_activity_text({"running": False, "external": True})
        assert "scheduled scan" in text

    def test_failure_is_red(self):
        cls, text = views.run_activity_text(
            {
                "running": False,
                "finished_at": time.time(),
                "error": "source didn't respond",
            }
        )
        assert "failed" in text and "err" in cls

    def test_idle_is_silent(self):
        cls, text = views.run_activity_text({"running": False})
        assert text == "" and cls == ""
