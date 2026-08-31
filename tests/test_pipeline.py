"""Пайплайн і його seam-и: підмінне джерело (#4) та скорер (#3).

Ці тести — демонстрація, що збір і оцінка тестуються БЕЗ мережі: джерело —
фікстура/ін'єктований http, скорер — fake. Разом вони покривають воронку
_store і повний run() детерміновано.
"""

import json

from jobradar import paths
from jobradar.core import pipeline, scoring, sources

L0 = {"exclude_title": [r"\bjunior\b"], "require_any_text": [r"\bQA\b"]}


class _Args:
    dry_run = True
    triggered_by = "test"


def _write_fixture(tmp, jobs):
    path = tmp / "jobs.json"
    path.write_text(json.dumps({"jobs": jobs}), encoding="utf-8")
    return str(path)


class TestFixtureSource:
    def test_reads_jobs_from_file(self, tmp_path):
        path = _write_fixture(tmp_path, [{"source": "dou", "url": "u", "title": "QA"}])
        cfg = {"sources": {"fixture": {"enabled": True, "path": path}}}
        built = sources.build_sources(cfg)
        assert len(built) == 1
        report = []
        jobs = built[0](report)
        assert jobs[0]["title"] == "QA"
        assert report[0]["count"] == 1  # фід потрапив у звіт для /runs

    def test_missing_file_is_survived(self, tmp_path):
        cfg = {
            "sources": {"fixture": {"enabled": True, "path": str(tmp_path / "nope")}}
        }
        assert sources.collect(cfg) == []  # битий шлях не валить прогін


class TestSourceHttpInjection:
    SAMPLE = (
        '<?xml version="1.0"?><rss><channel>'
        "<item><title>Senior QA Engineer в Acme, $4000, Київ</title>"
        "<link>https://jobs.dou.ua/x/1/</link>"
        "<description>Playwright</description></item>"
        "</channel></rss>"
    )

    def test_dou_source_uses_injected_http(self):
        cfg = {"sources": {"dou": {"enabled": True, "feeds": ["https://feed"]}}}
        jobs = sources.collect(cfg, http=lambda url, timeout=25: self.SAMPLE)
        assert len(jobs) == 1
        assert jobs[0]["company"] == "Acme" and jobs[0]["salary"] == "$4000"


class TestScorerSeam:
    def test_disabled_gives_null_scorer(self):
        scorer = scoring.build_scorer({"scorer": {"enabled": False}})
        assert isinstance(scorer, scoring.NullScorer)
        assert scorer.score({"title": "x"})["score"] is None

    def test_enabled_with_key_gives_anthropic(self):
        scorer = scoring.build_scorer(
            {"scorer": {"enabled": True, "api_key": "k"}}, profile="p"
        )
        assert isinstance(scorer, scoring.AnthropicScorer)

    def test_profile_api_key_wins_over_config(self, tmp_path):
        # Own-account use: the profile key powers scoring, not just cover letters.
        paths.use_home(str(tmp_path))
        from jobradar import candidate

        candidate.save({"role": "qa_automation", "api_key": "profile-key"})
        key = scoring.effective_api_key({"scorer": {"api_key": "config-key"}})
        assert key == "profile-key"

    def test_effective_api_key_falls_back_to_config(self, tmp_path):
        paths.use_home(str(tmp_path))  # no profile.json → no profile key
        key = scoring.effective_api_key({"scorer": {"api_key": "config-key"}})
        assert key == "config-key"

    def test_profile_key_enables_scorer_without_config_key(self, tmp_path):
        paths.use_home(str(tmp_path))
        from jobradar import candidate

        candidate.save({"role": "qa_automation", "api_key": "profile-key"})
        scorer = scoring.build_scorer({"scorer": {"enabled": True}}, profile="p")
        assert isinstance(scorer, scoring.AnthropicScorer)
        assert scorer.api_key == "profile-key"

    def test_parse_response_strips_markdown_fence(self):
        row = scoring.parse_scorer_response(
            '```json\n{"score": 8, "band": "strong", "verdict": "ок"}\n```'
        )
        assert row["score"] == 8.0 and row["band"] == "strong"

    def test_score_job_openai_provider(self):
        cap = {}

        def post(url, payload, headers, timeout=60):
            cap["url"] = url
            return {"choices": [{"message": {"content": '{"score": 6}'}}]}

        row = scoring.score_job(
            {
                "title": "QA",
                "company": "",
                "location": "",
                "salary": "",
                "description": "x",
            },
            "k",
            "gpt",
            "p",
            30,
            http_post=post,
            provider="openai",
        )
        assert row["score"] == 6.0
        assert cap["url"].endswith("/chat/completions")

    def test_llm_settings_profile_provider_wins(self, tmp_path):
        paths.use_home(str(tmp_path))
        from jobradar import candidate

        candidate.save(
            {
                "role": "qa_automation",
                "api_key": "pk",
                "llm_provider": "openai",
                "llm_base_url": "http://localhost:11434/v1",
            }
        )
        provider, base_url, api_key = scoring.llm_settings(
            {"scorer": {"provider": "anthropic", "api_key": "ck"}}
        )
        assert provider == "openai"
        assert base_url == "http://localhost:11434/v1"
        assert api_key == "pk"

    def test_score_job_injects_http_post(self):
        captured = {}

        def fake_post(url, payload, headers, timeout=60):
            captured["url"] = url
            return {"content": [{"type": "text", "text": '{"score": 7.5}'}]}

        row = scoring.score_job(
            {
                "title": "QA",
                "company": "",
                "location": "",
                "salary": "",
                "description": "x",
            },
            "key",
            "model",
            "profile",
            30,
            http_post=fake_post,
        )
        assert row["score"] == 7.5
        assert captured["url"] == scoring.API_URL


class _FakeScorer:
    """Фіксований бал без мережі (вимога #3)."""

    def __init__(self, score):
        self._score = score

    def score(self, job):
        return {
            "score": self._score,
            "band": "strong",
            "matched": [],
            "gaps": [],
            "verdict": "",
        }


class TestPipelineRun:
    def _cfg(self, path):
        return {
            "telegram": {"bot_token": "", "chat_id": ""},
            "sources": {"fixture": {"enabled": True, "path": path}},
            "l0": L0,
            "notify_min_score": 7,
        }

    def test_store_funnel_dedup_and_l0(self, tmp_path):
        paths.use_home(tmp_path)
        path = _write_fixture(
            tmp_path,
            [
                {
                    "source": "dou",
                    "url": "u1",
                    "title": "Senior QA Engineer",
                    "company": "A",
                    "location": "",
                    "salary": "",
                    "description": "QA",
                },
                {
                    "source": "dou",
                    "url": "u2",
                    "title": "Junior QA Engineer",
                    "company": "B",
                    "location": "",
                    "salary": "",
                    "description": "QA",
                },
            ],
        )
        sent = []
        pipeline.run(
            self._cfg(path),
            _Args(),
            scorer=_FakeScorer(9.0),
            notify=lambda *a: sent.append(a) or True,
        )
        from jobradar.core.db import db_connect

        conn = db_connect()
        run = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        assert run["fetched"] == 2
        assert run["l0_dropped"] == 1  # джуніора відсіяв L0
        assert run["added"] == 1
        # воронка сходиться
        assert run["fetched"] == run["dup_skipped"] + run["l0_dropped"] + run["added"]

    def test_second_run_is_all_dupes(self, tmp_path):
        paths.use_home(tmp_path)
        path = _write_fixture(
            tmp_path,
            [
                {
                    "source": "dou",
                    "url": "u1",
                    "title": "Senior QA Engineer",
                    "company": "A",
                    "location": "",
                    "salary": "",
                    "description": "QA",
                }
            ],
        )
        cfg = self._cfg(path)
        pipeline.run(cfg, _Args(), scorer=_FakeScorer(9.0), notify=lambda *a: True)
        pipeline.run(cfg, _Args(), scorer=_FakeScorer(9.0), notify=lambda *a: True)
        from jobradar.core.db import db_connect

        second = (
            db_connect()
            .execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1")
            .fetchone()
        )
        assert second["dup_skipped"] == 1 and second["added"] == 0

    def test_fake_scorer_score_persisted(self, tmp_path):
        paths.use_home(tmp_path)
        path = _write_fixture(
            tmp_path,
            [
                {
                    "source": "dou",
                    "url": "u1",
                    "title": "Senior QA Engineer",
                    "company": "A",
                    "location": "",
                    "salary": "",
                    "description": "QA",
                }
            ],
        )
        pipeline.run(
            self._cfg(path), _Args(), scorer=_FakeScorer(8.5), notify=lambda *a: True
        )
        from jobradar.core.db import db_connect

        row = db_connect().execute("SELECT score, band FROM jobs").fetchone()
        assert row["score"] == 8.5 and row["band"] == "strong"
