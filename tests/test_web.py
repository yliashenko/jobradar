"""Web layer smoke tests via the Flask test client.

Black-box: hit routes and assert on responses. Covers routing, auth, DB wiring,
static/resource serving, and the POST actions. As pages move from the el() layer
to Jinja templates, page-content assertions live here rather than against render
internals.
"""

import json
from datetime import datetime

import pytest

from jobradar import clock, paths
from jobradar.app import create_app
from jobradar.core import db as dbmod
from jobradar.web import routes

_JOB_COLS = [
    "hash",
    "source",
    "url",
    "title",
    "company",
    "location",
    "salary",
    "description",
    "description_html",
    "first_seen",
    "l0_pass",
    "score",
    "band",
    "notified_at",
    "status",
]


def _insert(conn, **kw):
    row = dict.fromkeys(_JOB_COLS, "")
    row.update(l0_pass=1, status="new", score=None, band="")
    row.update(kw)
    cols = ", ".join(_JOB_COLS)
    placeholders = ", ".join("?" for _ in _JOB_COLS)
    conn.execute(
        f"INSERT INTO jobs ({cols}) VALUES ({placeholders})",
        [row[c] for c in _JOB_COLS],
    )


def _seed(home):
    paths.use_home(home)
    clock.freeze(datetime(2026, 8, 20, 12, 0, 0))
    conn = dbmod.db_connect()
    _insert(
        conn,
        hash="h1",
        source="dou",
        url="https://jobs.dou.ua/1",
        title="Senior QA Automation Engineer",
        company="Ciklum",
        location="Kyiv",
        salary="$5000",
        description="Playwright, pytest.",
        description_html="<p>Playwright, pytest.</p>",
        first_seen="2026-08-19",
        score=8.0,
        band="great",
        notified_at="2026-08-19T09:00",
    )
    _insert(
        conn,
        hash="h2",
        source="djinni",
        url="https://djinni.co/2",
        title="Middle QA",
        company="Nortal",
        description="Selenium, Java.",
        description_html="<p>Selenium, Java.</p>",
        first_seen="2026-08-20",
        score=6.0,
        band="ok",
        notified_at="2026-08-20T09:00",
    )
    conn.commit()
    conn.close()


@pytest.fixture
def client(tmp_path):
    _seed(str(tmp_path))
    return create_app(config={}, runner=None).test_client()


@pytest.fixture
def empty_client(tmp_path):
    paths.use_home(str(tmp_path))
    return create_app(config={}, runner=None).test_client()


class TestPages:
    def test_health(self, empty_client):
        resp = empty_client.get("/health")
        assert resp.status_code == 200 and b"ok" in resp.data

    @pytest.mark.parametrize(
        "path",
        [
            "/",
            "/runs",
            "/tags",
            "/stats",
            "/calendar",
            "/company?name=Ciklum",
            "/profile",
        ],
    )
    def test_page_ok(self, client, path):
        resp = client.get(path)
        assert resp.status_code == 200 and resp.mimetype == "text/html"

    def test_feed_lists_jobs(self, client):
        html = client.get("/").get_data(as_text=True)
        assert 'class="job' in html
        assert "Senior QA Automation Engineer" in html

    def test_unknown_page_404(self, client):
        assert client.get("/nope").status_code == 404

    def test_search_matches_location(self, client):
        # h1 is in Kyiv, h2 has no location — searching a place must find h1.
        html = client.get("/?q=kyiv").get_data(as_text=True)
        assert "Senior QA Automation Engineer" in html
        assert "Middle QA" not in html

    def test_score_filter_is_dropdown_and_narrows(self, client):
        page = client.get("/").get_data(as_text=True)
        assert 'name="min"' in page and '<option value="7"' in page
        filtered = client.get("/?status=all&min=7").get_data(as_text=True)
        assert "Senior QA Automation Engineer" in filtered  # 8.0 >= 7
        assert "Middle QA" not in filtered  # 6.0 < 7

    def test_card_shows_status_update_date(self, client):
        conn = dbmod.db_connect()
        conn.execute(
            "UPDATE jobs SET status = 'applied', status_at = '2026-08-25T10:00' "
            "WHERE hash = 'h1'"
        )
        conn.commit()
        conn.close()
        html = client.get("/?status=applied").get_data(as_text=True)
        assert "date upd" in html
        assert "25.08" in html

    def test_empty_db_shows_empty_state(self, empty_client):
        assert "No scan yet" in empty_client.get("/").get_data(as_text=True)


class TestStaticAndResources:
    def test_css(self, empty_client):
        resp = empty_client.get("/static/app.css")
        assert resp.status_code == 200 and resp.mimetype == "text/css"

    def test_logo(self, empty_client):
        resp = empty_client.get("/resources/dou_logo.png")
        assert resp.status_code == 200 and resp.mimetype == "image/png"

    def test_logo_whitelist_blocks_others(self, empty_client):
        assert empty_client.get("/resources/secret.png").status_code == 404


class TestActions:
    def test_status_change_writes_db(self, client):
        resp = client.post(
            "/status", data={"hash": "h1", "status": "applied", "back": ""}
        )
        assert resp.status_code == 303
        conn = dbmod.db_connect()
        row = conn.execute("SELECT status FROM jobs WHERE hash = 'h1'").fetchone()
        conn.close()
        assert row["status"] == "applied"

    def test_status_bad_value_400(self, client):
        assert (
            client.post("/status", data={"hash": "h1", "status": "bogus"}).status_code
            == 400
        )

    def test_run_without_runner_503(self, client):
        assert client.post("/run", data={"back": ""}).status_code == 503

    def test_profile_save_redirects(self, client):
        resp = client.post("/profile", data={"action": "save", "role": "qa_automation"})
        assert resp.status_code == 303
        assert "/profile?saved=1" in resp.headers["Location"]

    def test_profile_edit_has_llm_access_fields(self, client):
        html = client.get("/profile?edit=1").get_data(as_text=True)
        assert 'name="api_key"' in html and 'name="llm_model"' in html

    def test_profile_save_persists_llm_access(self, client):
        client.post(
            "/profile",
            data={
                "action": "save",
                "role": "qa_automation",
                "api_key": "sk-ant-1",
                "llm_model": "claude-sonnet-5",
            },
        )
        view = client.get("/profile").get_data(as_text=True)
        assert "key set" in view
        assert "claude-sonnet-5" in view

    def test_profile_save_persists_skill_absent_from_cv(self, client):
        # "Add a skill" accepts terms not in the CV; they show under Added skills.
        client.post(
            "/profile",
            data={
                "action": "save",
                "role": "qa_automation",
                "cv_text": "Playwright automation",
                "extra": "Scrum, HTTP",
            },
        )
        view = client.get("/profile").get_data(as_text=True)
        assert "Added skills" in view
        assert "Scrum, HTTP" in view


class TestAuth:
    def test_token_required_when_configured(self, tmp_path):
        _seed(str(tmp_path))
        client = create_app(
            config={"webui": {"token": "secret"}}, runner=None
        ).test_client()
        assert client.get("/").status_code == 403
        assert client.get("/?token=secret").status_code == 200


class TestHiring:
    """The /hiring pipeline: only applied vacancies, stage moves, per-stage notes."""

    def _apply(self, digest="h1"):
        conn = dbmod.db_connect()
        conn.execute("UPDATE jobs SET status = 'applied' WHERE hash = ?", (digest,))
        conn.commit()
        conn.close()

    def test_lists_only_applied(self, client):
        self._apply("h1")
        html = client.get("/hiring").get_data(as_text=True)
        assert "Applied" in html
        assert "Senior QA Automation Engineer" in html  # h1 — applied
        assert "Middle QA" not in html  # h2 — still 'new'

    def test_empty_when_none_applied(self, client):
        assert "Nothing here yet" in client.get("/hiring").get_data(as_text=True)

    def test_card_shows_pub_and_upd_dates(self, client):
        conn = dbmod.db_connect()
        conn.execute(
            "UPDATE jobs SET status = 'applied', status_at = '2026-08-25T10:00', "
            "published_at = '2026-08-19T08:00' WHERE hash = 'h1'"
        )
        conn.commit()
        conn.close()
        html = client.get("/hiring").get_data(as_text=True)
        assert 'class="dates"' in html  # shared card_dates macro
        assert "date upd" in html  # status_at present
        assert "19.08" in html  # published date, short form

    def test_stage_move_saves_note_of_stage_left(self, client):
        self._apply("h1")
        resp = client.post(
            "/hiring/update",
            data={
                "hash": "h1",
                "stage": "waiting_hr",
                "note": "left a message",
                "go": "pre_screen",
            },
        )
        assert resp.status_code == 303
        conn = dbmod.db_connect()
        row = conn.execute(
            "SELECT hiring_status, hiring_notes FROM jobs WHERE hash = 'h1'"
        ).fetchone()
        conn.close()
        assert row["hiring_status"] == "pre_screen"
        assert json.loads(row["hiring_notes"]) == {"waiting_hr": "left a message"}

    def test_save_notes_keeps_current_stage(self, client):
        self._apply("h1")
        client.post(
            "/hiring/update",
            data={
                "hash": "h1",
                "stage": "waiting_hr",
                "note": "",
                "go": "tech_interview",
            },
        )
        client.post(
            "/hiring/update",
            data={"hash": "h1", "stage": "tech_interview", "note": "passed", "go": ""},
        )
        conn = dbmod.db_connect()
        row = conn.execute(
            "SELECT hiring_status, hiring_notes FROM jobs WHERE hash = 'h1'"
        ).fetchone()
        conn.close()
        assert row["hiring_status"] == "tech_interview"
        assert json.loads(row["hiring_notes"])["tech_interview"] == "passed"

    def test_bad_stage_400(self, client):
        assert (
            client.post(
                "/hiring/update", data={"hash": "h1", "go": "bogus"}
            ).status_code
            == 400
        )

    def test_finish_archive_moves_to_archived(self, client):
        self._apply("h1")
        resp = client.post("/hiring/update", data={"hash": "h1", "archive": "1"})
        assert resp.status_code == 303
        conn = dbmod.db_connect()
        row = conn.execute(
            "SELECT status, hiring_status FROM jobs WHERE hash = 'h1'"
        ).fetchone()
        conn.close()
        assert row["status"] == "archived"
        assert row["hiring_status"] == "finish"

    def test_archived_hidden_by_default_shown_with_toggle(self, client):
        self._apply("h1")
        client.post("/hiring/update", data={"hash": "h1", "archive": "1"})
        default = client.get("/hiring").get_data(as_text=True)
        assert "Senior QA Automation Engineer" not in default
        assert "Show archived" in default  # the toggle offers the archived view
        shown = client.get("/hiring?archived=1").get_data(as_text=True)
        assert "Senior QA Automation Engineer" in shown
        assert 'data-testid="hiring-archived-badge"' in shown

    def test_archived_absent_from_feed(self, client):
        self._apply("h1")
        client.post("/hiring/update", data={"hash": "h1", "archive": "1"})
        applied = client.get("/?status=applied").get_data(as_text=True)
        assert "Senior QA Automation Engineer" not in applied
        all_feed = client.get("/?status=all").get_data(as_text=True)
        assert "Senior QA Automation Engineer" not in all_feed

    def test_restore_returns_to_applied(self, client):
        self._apply("h1")
        client.post("/hiring/update", data={"hash": "h1", "archive": "1"})
        resp = client.post("/hiring/update", data={"hash": "h1", "restore": "1"})
        assert resp.status_code == 303
        conn = dbmod.db_connect()
        row = conn.execute("SELECT status FROM jobs WHERE hash = 'h1'").fetchone()
        conn.close()
        assert row["status"] == "applied"

    def test_archive_preserves_status_at(self, client):
        """Archiving must not touch status_at — the activity calendar counts the
        application on the day it was sent, not the day it was archived."""
        conn = dbmod.db_connect()
        conn.execute(
            "UPDATE jobs SET status = 'applied', status_at = '2026-08-10T09:00' "
            "WHERE hash = 'h1'"
        )
        conn.commit()
        conn.close()
        client.post("/hiring/update", data={"hash": "h1", "archive": "1"})
        conn = dbmod.db_connect()
        row = conn.execute("SELECT status_at FROM jobs WHERE hash = 'h1'").fetchone()
        conn.close()
        assert row["status_at"] == "2026-08-10T09:00"


_FAKE_COVER = {
    "letter": "Dear hiring team, this is the tailored letter.",
    "evaluation": "Requirement matrix and fit score here.",
    "traceability": "Paragraph-to-requirement table here.",
    "fit_score": 7.0,
    "band": "GREEN EDGE",
}


class TestMarkdown:
    """render_markdown: the cover eval/traceability preview."""

    def test_renders_table_heading_and_bold(self):
        from jobradar.web.format import render_markdown

        html = str(
            render_markdown("## Fit\n\n| A | B |\n| - | - |\n| x | y |\n\n**ok**")
        )
        assert "<table>" in html and "<h2>" in html and "<strong>" in html

    def test_escapes_raw_html(self):
        from jobradar.web.format import render_markdown

        html = str(render_markdown("safe <script>alert(1)</script>"))
        assert "<script>" not in html and "&lt;script&gt;" in html

    def test_empty_is_empty(self):
        from jobradar.web.format import render_markdown

        assert str(render_markdown("")) == ""
        assert str(render_markdown(None)) == ""


class TestCoverLetter:
    """POST /hiring/cover: generate, cache, regenerate, and the graceful errors
    that become popup text (missing career-facts.md, no API key). The LLM call
    itself is monkeypatched, so no network."""

    def _client(
        self, tmp_path, monkeypatch, *, facts="Yevhen, Kyiv. 13y QA.", api_key="k"
    ):
        _seed(str(tmp_path))
        conn = dbmod.db_connect()
        conn.execute("UPDATE jobs SET status = 'applied' WHERE hash = 'h1'")
        conn.commit()
        conn.close()
        if facts is not None:
            with open(paths.career_facts_path(), "w", encoding="utf-8") as fh:
                fh.write(facts)
        captured = {}

        def _fake_generate(
            job,
            facts_arg,
            key,
            model,
            timeout,
            http_post=None,
            provider="anthropic",
            base_url="",
        ):
            captured["facts"] = facts_arg
            captured["model"] = model
            captured["key"] = key
            captured["provider"] = provider
            captured["base_url"] = base_url
            return dict(_FAKE_COVER)

        monkeypatch.setattr(routes, "generate_cover", _fake_generate)
        cfg = {"scorer": {"api_key": api_key}} if api_key else {}
        client = create_app(config=cfg, runner=None).test_client()
        return client, captured

    def test_generate_saves_and_returns(self, tmp_path, monkeypatch):
        client, captured = self._client(tmp_path, monkeypatch)
        resp = client.post("/hiring/cover", data={"hash": "h1"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True and body["cached"] is False
        assert body["letter"] == _FAKE_COVER["letter"]
        assert body["band"] == "GREEN EDGE"
        # The eval/traceability markdown is pre-rendered so the JS fill matches the
        # server render — the raw text stays too, for the copy affordance.
        assert "<p>" in body["evaluation_html"]
        assert "<p>" in body["traceability_html"]
        # career-facts.md reached the generator; the letter is saved on the row.
        assert captured["facts"] == "Yevhen, Kyiv. 13y QA."
        conn = dbmod.db_connect()
        row = conn.execute("SELECT cover_data FROM jobs WHERE hash = 'h1'").fetchone()
        conn.close()
        assert json.loads(row["cover_data"])["letter"] == _FAKE_COVER["letter"]

    def test_second_call_returns_cache_without_regenerating(
        self, tmp_path, monkeypatch
    ):
        client, _ = self._client(tmp_path, monkeypatch)
        client.post("/hiring/cover", data={"hash": "h1"})
        # If the cache is honoured, generate_cover is never reached — make it fail.
        monkeypatch.setattr(
            routes,
            "generate_cover",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("regenerated")),
        )
        resp = client.post("/hiring/cover", data={"hash": "h1"})
        assert resp.status_code == 200 and resp.get_json()["cached"] is True

    def test_regenerate_flag_calls_again(self, tmp_path, monkeypatch):
        client, _ = self._client(tmp_path, monkeypatch)
        client.post("/hiring/cover", data={"hash": "h1"})
        calls = {"n": 0}

        def _again(
            job,
            facts_arg,
            key,
            model,
            timeout,
            http_post=None,
            provider="anthropic",
            base_url="",
        ):
            calls["n"] += 1
            return dict(_FAKE_COVER, letter="regenerated letter")

        monkeypatch.setattr(routes, "generate_cover", _again)
        resp = client.post("/hiring/cover", data={"hash": "h1", "regenerate": "1"})
        assert calls["n"] == 1
        assert resp.get_json()["letter"] == "regenerated letter"

    def test_missing_career_facts_is_popup_text(self, tmp_path, monkeypatch):
        client, _ = self._client(tmp_path, monkeypatch, facts=None)
        body = client.post("/hiring/cover", data={"hash": "h1"}).get_json()
        assert body["ok"] is False and "career-facts.md" in body["error"]

    def test_no_api_key_is_popup_text(self, tmp_path, monkeypatch):
        client, _ = self._client(tmp_path, monkeypatch, api_key="")
        body = client.post("/hiring/cover", data={"hash": "h1"}).get_json()
        assert body["ok"] is False and "API key" in body["error"]
        assert "Profile" in body["error"]  # points the user where to set it

    def test_profile_key_and_model_take_priority(self, tmp_path, monkeypatch):
        # config has no key; the key/model come from the profile (own-account use).
        from jobradar import candidate

        client, captured = self._client(tmp_path, monkeypatch, api_key="")
        candidate.save(
            {
                "role": "qa_automation",
                "api_key": "profile-key",
                "llm_model": "claude-haiku-4-5-20251001",
            }
        )
        resp = client.post("/hiring/cover", data={"hash": "h1"})
        assert resp.status_code == 200 and resp.get_json()["ok"] is True
        assert captured["key"] == "profile-key"
        assert captured["model"] == "claude-haiku-4-5-20251001"

    def test_unknown_vacancy_404(self, tmp_path, monkeypatch):
        client, _ = self._client(tmp_path, monkeypatch)
        assert client.post("/hiring/cover", data={"hash": "nope"}).status_code == 404

    def test_button_present_when_no_letter(self, tmp_path, monkeypatch):
        client, _ = self._client(tmp_path, monkeypatch)
        html = client.get("/hiring").get_data(as_text=True)
        assert 'data-testid="hiring-cover-open"' in html
        assert "Generate cover letter" in html

    def test_saved_letter_renders_in_modal(self, tmp_path, monkeypatch):
        client, _ = self._client(tmp_path, monkeypatch)
        client.post("/hiring/cover", data={"hash": "h1"})
        html = client.get("/hiring").get_data(as_text=True)
        assert _FAKE_COVER["letter"] in html
        assert "Regenerate" in html  # the button flips once a letter exists
        assert "GREEN EDGE" in html


class TestKeylessUI:
    """No API key: scoring/cover-letter affordances stay visible but click through
    to an explanation (#llm-nokey) instead of running."""

    def _client(self, tmp_path, *, api_key=""):
        _seed(str(tmp_path))
        conn = dbmod.db_connect()
        _insert(
            conn,
            hash="u1",
            source="dou",
            url="https://jobs.dou.ua/u",
            title="Unscored QA",
            first_seen="2026-08-20",
            score=None,
        )
        conn.commit()
        conn.close()
        cfg = {"scorer": {"api_key": api_key}} if api_key else {}
        return create_app(config=cfg, runner=None).test_client()

    def test_no_key_shows_score_gate(self, tmp_path):
        html = self._client(tmp_path).get("/?status=all").get_data(as_text=True)
        assert 'data-testid="score-nokey"' in html
        assert 'href="#llm-nokey"' in html
        assert 'data-testid="llm-nokey-modal"' in html

    def test_key_present_no_gate(self, tmp_path):
        html = (
            self._client(tmp_path, api_key="k")
            .get("/?status=all")
            .get_data(as_text=True)
        )
        assert 'data-testid="score-nokey"' not in html
        assert 'data-testid="llm-nokey-modal"' not in html

    def test_hiring_cover_button_gated_without_key(self, tmp_path):
        client = self._client(tmp_path)  # no key
        conn = dbmod.db_connect()
        conn.execute("UPDATE jobs SET status = 'applied' WHERE hash = 'h1'")
        conn.commit()
        conn.close()
        html = client.get("/hiring").get_data(as_text=True)
        assert 'href="#llm-nokey"' in html  # ✍ points at the explanation
        assert 'data-testid="llm-nokey-modal"' in html


class TestFeedSort:
    """Score sorting in the feed filter (both directions)."""

    def test_default_sort_is_score_high_to_low(self, client):
        # h1 scores 8.0, h2 scores 6.0 — the stronger match comes first.
        html = client.get("/?status=all").get_data(as_text=True)
        assert html.index("Senior QA Automation Engineer") < html.index("Middle QA")

    def test_sort_score_ascending(self, client):
        html = client.get("/?status=all&sort=score_asc").get_data(as_text=True)
        assert html.index("Middle QA") < html.index("Senior QA Automation Engineer")
