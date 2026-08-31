"""База: міграція старих БД, meta-ключі, журнал прогонів.

Обидва реальні баги проєкту знайшли тести, не огляд коду — один із них: індекс
по status створювався до міграції, і стара база не відкривалась узагалі. Тому
міграцію тримаємо під регресом окремо.
"""

import sqlite3

from jobradar import paths
from jobradar.core import db


def _legacy_db(path):
    """БД ранньої версії: оригінальна jobs (зі score/band), але БЕЗ пізніших
    колонок (status, run_id, sources, …) і без journal-таблиць — саме те, що
    догортає migrate()."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE jobs (hash TEXT PRIMARY KEY, source TEXT, url TEXT, title TEXT,"
        " company TEXT DEFAULT '', location TEXT DEFAULT '', salary TEXT DEFAULT '',"
        " description TEXT DEFAULT '', first_seen TEXT NOT NULL, l0_pass INTEGER DEFAULT 0,"
        " l0_reason TEXT DEFAULT '', score REAL, band TEXT DEFAULT '', verdict TEXT DEFAULT '',"
        " matched TEXT DEFAULT '', gaps TEXT DEFAULT '', rubric TEXT DEFAULT '',"
        " scored_at TEXT, notified_at TEXT)"
    )
    conn.execute(
        "INSERT INTO jobs(hash, source, url, title, first_seen)"
        " VALUES('h1','dou','u1','Стара вакансія','2026-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()


class TestMigration:
    def test_legacy_db_opens_and_keeps_data(self, tmp_path):
        paths.use_home(tmp_path)
        _legacy_db(paths.db_path())
        conn = db.db_connect()  # має догорнути схему, а не впасти
        row = conn.execute("SELECT title, status FROM jobs WHERE hash='h1'").fetchone()
        assert row["title"] == "Стара вакансія"
        assert row["status"] == "new"  # колонку додано з дефолтом

    def test_journal_tables_created(self, tmp_path):
        paths.use_home(tmp_path)
        _legacy_db(paths.db_path())
        conn = db.db_connect()
        names = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"runs", "run_dups", "meta"} <= names

    def test_migrate_is_idempotent(self, tmp_path):
        paths.use_home(tmp_path)
        conn = db.db_connect()
        db.migrate(conn)  # повторний прогін не має падати
        db.migrate(conn)


class TestMetaAndJournal:
    def test_meta_roundtrip(self, tmp_path):
        paths.use_home(tmp_path)
        conn = db.db_connect()
        db.meta_set(conn, "k", "v")
        assert db.meta_get(conn, "k") == "v"
        assert db.meta_get(conn, "absent", "default") == "default"

    def test_run_start_and_finish(self, tmp_path):
        paths.use_home(tmp_path)
        conn = db.db_connect()
        run_id = db.run_start(conn, "button")
        db.run_finish(
            conn,
            run_id,
            [{"feed": "x", "count": 1, "error": ""}],
            {"fetched": 1, "added": 1, "notified": 0},
        )
        row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        assert row["triggered_by"] == "button"
        assert row["finished_at"] and row["fetched"] == 1 and row["added"] == 1
