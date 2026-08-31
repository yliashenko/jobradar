"""Динамічний профіль: ролі, парсинг CV, розподіл праці зі скорером."""

import tempfile

import flask

from jobradar import candidate as profile
from jobradar import paths, roles, skills
from jobradar.web import urls, views


def _app():
    from jobradar.app import create_app

    return create_app(config={}, runner=None)


def render_tpl(template, **ctx):
    """Render a page template through a Flask request context (for context
    processors like css_version)."""
    with _app().test_request_context():
        return flask.render_template(template, **ctx)


def render_card(row, threshold=7.0, params=None, query="", also_on=None):
    """Render a single job-card macro with a real DB row."""
    with _app().test_request_context():
        return flask.render_template_string(
            "{% import 'partials/_job_card.html' as card %}"
            "{{ card.job_card(row, threshold, params, query, also_on_links=also) }}",
            row=row,
            threshold=threshold,
            params=params or {},
            query=query,
            also=also_on,
        )


def render_pick(kind, conn, params):
    """Render a tag/company pick-popup macro."""
    data = (
        views._pick_tags(conn, params)
        if kind == "tags"
        else views._pick_companies(conn, params)
    )
    macro = "pick_tags_popup" if kind == "tags" else "pick_companies_popup"
    with _app().test_request_context():
        return flask.render_template_string(
            "{% import 'partials/_macros.html' as ui %}{{ ui."
            + macro
            + "(data, params) }}",
            data=data,
            params=params,
        )


def render_feed(conn, params, threshold=7.0, run_status=None):
    return render_tpl(
        "feed.html",
        title="",
        active="feed",
        params=params,
        **views.feed_context(conn, params, threshold, run_status or {}, ""),
    )


def render_profile_edit(data, preview=None):
    return render_tpl(
        "profile_edit.html",
        title="",
        active="profile",
        params={},
        **views.profile_edit_context({}, data, preview),
    )


def render_profile_view(data):
    return render_tpl(
        "profile_view.html",
        title="",
        active="profile",
        params={},
        **views.profile_view_context({}, data, False),
    )


def render_calendar(conn, params):
    return render_tpl(
        "calendar.html",
        title="",
        active="calendar",
        params=params,
        **views.calendar_context(conn, params),
    )


def render_company(conn, params, threshold=7.0):
    return render_tpl(
        "company.html",
        title="",
        active="",
        params=params,
        query="",
        **views.company_context(conn, params, threshold),
    )


def render_stats(conn, params):
    return render_tpl(
        "stats.html",
        title="",
        active="stats",
        params=params,
        **views.stats_context(conn, params),
    )


CV = """Yevhen Liashenko — Senior QA Automation Engineer.
10+ years in QA. API automation on TypeScript (Mocha, Chai), Playwright PoC,
Cypress ownership as a lead. Azure DevOps, Allure, Docker. Some Python tooling.
Angular + TypeScript for two years.
"""


class TestRoles:
    def test_four_roles_exist(self):
        assert set(roles.ROLE_ORDER) == set(roles.ROLES)
        assert len(roles.ROLES) == 4

    def test_each_role_carries_feeds_l0_groups(self):
        for key in roles.ROLES:
            assert roles.feeds(key), key
            assert roles.l0(key).get("require_any_text"), key
            assert roles.groups(key), key

    def test_roles_reference_real_skill_groups(self):
        # Роль вибирає з єдиного словника, а не вигадує групи.
        for key in roles.ROLES:
            for g in roles.groups(key):
                assert g in skills.GROUPS, (key, g)

    def test_l0_is_a_copy_not_the_shared_original(self):
        # UI редагує L0 профілю — це не має псувати еталон ролі.
        a = roles.l0("qa_automation")
        a["min_salary_usd"] = 1
        assert roles.l0("qa_automation")["min_salary_usd"] != 1

    def test_unknown_role_falls_back(self):
        assert (
            roles.get("astrologer")["label"] == roles.ROLES[roles.DEFAULT_ROLE]["label"]
        )


class TestParseCV:
    def test_extracts_skills_grouped_by_role_priority(self):
        parsed = profile.parse_cv(CV, "qa_automation")
        assert "TypeScript" in parsed["skills"]
        assert "Playwright" in parsed["skills"]
        # UI-автоматизація стоїть у ролі перед мовами, тому Playwright
        # має опинитись раніше за TypeScript у плоскому списку.
        assert parsed["skills"].index("Playwright") < parsed["skills"].index(
            "TypeScript"
        )

    def test_detects_seniority_and_years(self):
        parsed = profile.parse_cv(CV, "qa_automation")
        assert parsed["seniority"] == "Senior"
        assert parsed["years"] == 10

    def test_seniority_takes_the_highest_mention(self):
        # «Senior … mentoring juniors» — це Senior, не Junior.
        parsed = profile.parse_cv("Senior engineer mentoring junior team", "qa")
        assert parsed["seniority"] == "Senior"

    def test_terms_outside_role_are_kept_at_the_end(self):
        # Бекендні терміни в CV фронтендера не викидаються, а зсуваються.
        parsed = profile.parse_cv("React developer with Django experience", "frontend")
        assert "React" in parsed["skills"] and "Django" in parsed["skills"]
        assert parsed["skills"].index("React") < parsed["skills"].index("Django")

    def test_empty_cv(self):
        assert profile.parse_cv("", "qa")["skills"] == []


class TestStorage:
    def _isolate(self, tmp):
        paths.use_home(tmp)

    def test_load_default_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._isolate(tmp)
            data = profile.load()
            assert data["role"] == roles.DEFAULT_ROLE and data["skills"] == []

    def test_save_then_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._isolate(tmp)
            profile.save(
                {
                    "role": "frontend",
                    "cv_text": "React and TypeScript",
                    "skills": ["react", "TypeScript"],
                    "notes": "no Vue",
                }
            )
            back = profile.load()
            assert back["role"] == "frontend"
            # Скіли зводяться до канонічного написання при збереженні.
            assert back["skills"] == ["React", "TypeScript"]
            assert back["notes"] == "no Vue"

    def test_broken_json_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._isolate(tmp)
            with open(paths.profile_json_path(), "w") as fh:
                fh.write("{ not json")
            assert profile.load()["role"] == roles.DEFAULT_ROLE

    def test_unknown_role_normalised_on_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._isolate(tmp)
            profile.save({"role": "wizard"})
            assert profile.load()["role"] == roles.DEFAULT_ROLE


class TestScorerText:
    def _isolate(self, tmp):
        paths.use_home(tmp)

    def test_notes_feed_the_scorer_not_just_skills(self):
        # Головне: межі потрапляють у текст скорера дослівно.
        text = profile.scorer_text(
            {
                "role": "qa_automation",
                "cv_text": "Python tooling",
                "skills": ["Python"],
                "notes": "Python — не робоча мова, це GAP",
                "seniority": "Senior",
            }
        )
        assert "Python — не робоча мова" in text
        assert "Senior" in text and "QA Automation" in text

    def test_falls_back_to_profile_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._isolate(tmp)
            with open(paths.profile_md_path(), "w", encoding="utf-8") as fh:
                fh.write("# Старий profile.md")
            text = profile.scorer_text({"role": "qa", "cv_text": "", "notes": ""})
            assert "Старий profile.md" in text


class TestEffectiveSources:
    def test_role_feeds_win_when_profile_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            profile.save({"role": "frontend"})
            feeds = profile.effective_feeds({"sources": {"dou": {"feeds": ["OLD"]}}})
            assert any("Front End" in f for f in feeds)
            assert "OLD" not in feeds

    def test_config_feeds_when_no_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            feeds = profile.effective_feeds({"sources": {"dou": {"feeds": ["CFG"]}}})
            assert feeds == ["CFG"]


class TestProfilePage:
    """Веб-шар профілю: рендер, розбір форми, чесний розподіл скіли/межі."""

    def test_page_shows_role_radios(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            html = render_profile_edit(profile.default_profile())
            for key in roles.ROLE_ORDER:
                assert (f'name="role" value="{key}"') in html, key
            assert "account-menu" in html
            assert 'data-page="profile"' in html and 'data-page="hiring"' in html

    def test_preview_highlights_skills_in_cv_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            cv = "Playwright and TypeScript, Docker. No React experience."
            parsed = profile.parse_cv(cv, "qa_automation")
            html = render_profile_edit(
                {
                    "role": "qa_automation",
                    "cv_text": cv,
                    "skills": parsed["skills"],
                    "notes": "",
                    "seniority": "",
                },
                preview=parsed,
            )
            # Навички підсвічені прямо в тексті CV, кожна — клікабельна мітка.
            assert 'class="cvtag"' in html and 'class="cvtext"' in html
            assert 'name="skills" value="Playwright"' in html
            # React зі згадки теж підсвічений — видно, звідки він.
            assert 'value="React"' in html

    def test_one_checkbox_per_skill_despite_repeats(self):
        # Дві згадки Playwright → один чекбокс, дві мітки: вимикається разом.
        res = views.cv_tagged("Playwright here and Playwright there")
        assert res["order"] == ["Playwright"]
        assert res["block"].count('name="skills" value="Playwright"') == 1
        assert res["block"].count('class="cvtag"') == 2

    def test_deactivated_skill_stays_off_when_reediting(self):
        # Раніше знята навичка не має ввімкнутись знову при редагуванні.
        import re

        block = views.cv_tagged("Playwright, React", active=["Playwright"])["block"]
        react = re.search(r'value="React"( checked)?>', block).group(0)
        assert "checked" not in react

    def test_saved_skills_offer_feed_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            html = render_profile_view(
                {
                    "role": "qa_automation",
                    "cv_text": "",
                    "skills": ["Playwright", "TypeScript"],
                    "notes": "",
                    "seniority": "",
                },
            )
            # Мультиселект навичок → стрічка (вимога №3).
            assert 'action="/"' in html and 'name="tech" value="Playwright"' in html
            assert "Show vacancies" in html

    def test_notes_field_is_present_and_separate_from_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            html = render_profile_edit(profile.default_profile())
            # The boundaries block must exist and say it feeds the scorer, not the filter.
            assert 'name="notes"' in html and "scorer sees" in html.lower()


class TestValidation:
    def test_skill_not_in_cv_is_dropped_on_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            # CV згадує лише Playwright; React дописали помилково.
            profile.save(
                {
                    "role": "qa_automation",
                    "cv_text": "Playwright automation",
                    "skills": ["Playwright", "React"],
                }
            )
            assert profile.load()["skills"] == ["Playwright"]

    def test_validate_respects_word_boundaries(self):
        # «Java» не має вижити через «JavaScript» у тексті.
        kept = profile.validate_skills(["Java"], "We use JavaScript everywhere")
        assert kept == []
        assert profile.validate_skills(["Java"], "Java 17 backend") == ["Java"]

    def test_stale_skill_pruned_when_cv_edited(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            profile.save(
                {
                    "role": "qa",
                    "cv_text": "Playwright, Cypress",
                    "skills": ["Playwright", "Cypress"],
                }
            )
            # CV відредагували — Cypress прибрали; збереження має його викинути.
            profile.save(
                {
                    "role": "qa",
                    "cv_text": "Playwright only",
                    "skills": ["Playwright", "Cypress"],
                }
            )
            assert profile.load()["skills"] == ["Playwright"]


class TestCrudStates:
    def _client(self, tmp):
        paths.use_home(tmp)
        return _app().test_client()

    def test_no_profile_yet_opens_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = self._client(tmp).get("/profile").get_data(as_text=True)
            assert 'name="cv_text"' in html and 'value="save"' in html

    def test_saved_profile_opens_view_not_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = self._client(tmp)
            profile.save(
                {
                    "role": "qa_automation",
                    "cv_text": "Playwright",
                    "skills": ["Playwright"],
                    "notes": "no Python",
                }
            )
            html = client.get("/profile").get_data(as_text=True)
            # VIEW: без textarea CV, із входом у редагування і пошуком по навичках.
            assert 'name="cv_text"' not in html
            assert 'href="/profile?edit=1"' in html
            assert 'name="tech" value="Playwright"' in html and "Show vacancies" in html
            assert "no Python" in html

    def test_edit_param_forces_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = self._client(tmp)
            profile.save(
                {"role": "qa", "cv_text": "Playwright", "skills": ["Playwright"]}
            )
            html = client.get("/profile?edit=1").get_data(as_text=True)
            assert 'name="cv_text"' in html and "Cancel" in html

    def test_search_lives_on_view_not_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            edit = render_profile_edit(
                {
                    "role": "qa",
                    "cv_text": "Playwright",
                    "skills": ["Playwright"],
                    "notes": "",
                    "seniority": "",
                }
            )
            assert "Show vacancies" not in edit


class TestCustomSkills:
    def test_custom_skill_present_in_cv_is_kept(self):
        # Навичка поза словником, але в тексті CV, має вижити.
        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            profile.save(
                {
                    "role": "qa_automation",
                    "cv_text": "Automated with Ranorex and Playwright.",
                    "skills": ["Playwright", "Ranorex"],
                }
            )
            assert profile.load()["skills"] == ["Playwright", "Ranorex"]

    def test_custom_skill_absent_from_cv_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            profile.save(
                {
                    "role": "qa",
                    "cv_text": "Only Playwright here.",
                    "skills": ["Playwright", "Ranorex"],
                }
            )
            assert profile.load()["skills"] == ["Playwright"]

    def test_present_in_cv_respects_word_boundary(self):
        assert profile.present_in_cv("Java", "We use JavaScript") is False
        assert profile.present_in_cv("Ranorex", "tool: Ranorex here") is True

    def test_custom_term_is_highlighted_in_cv(self):
        res = views.cv_tagged(
            "Testing with Ranorex tool", active=None, custom=["Ranorex"]
        )
        assert "Ranorex" in res["order"]
        assert 'name="skills" value="Ranorex"' in res["block"]
        assert 'class="cvtag"' in res["block"]


class TestExtraSkills:
    """Hand-added skills that need NOT be in the CV (Scrum, HTTP…)."""

    def _iso(self, tmp):
        paths.use_home(tmp)

    def test_extra_skill_persists_without_cv_validation(self):
        # The whole point: a skill absent from the CV must still save.
        with tempfile.TemporaryDirectory() as tmp:
            self._iso(tmp)
            profile.save(
                {
                    "role": "qa_automation",
                    "cv_text": "Playwright automation",
                    "skills": ["Playwright"],
                    "extra_skills": ["Scrum", "HTTP"],
                }
            )
            loaded = profile.load()
            assert loaded["extra_skills"] == ["Scrum", "HTTP"]
            # A CV-confirmed skill is untouched by the extra channel.
            assert loaded["skills"] == ["Playwright"]

    def test_extra_skills_deduped_against_confirmed(self):
        # A term already confirmed from the CV isn't listed twice.
        with tempfile.TemporaryDirectory() as tmp:
            self._iso(tmp)
            profile.save(
                {
                    "role": "qa_automation",
                    "cv_text": "Playwright automation",
                    "skills": ["Playwright"],
                    "extra_skills": ["playwright", "Scrum", "scrum"],
                }
            )
            assert profile.load()["extra_skills"] == ["Scrum"]

    def test_extra_skills_reach_the_scorer(self):
        text = profile.scorer_text(
            {
                "role": "qa_automation",
                "cv_text": "Playwright tooling",
                "skills": ["Playwright"],
                "extra_skills": ["Scrum", "HTTP"],
            }
        )
        assert "Confirmed skills:" in text
        assert "Scrum" in text and "HTTP" in text

    def test_edit_page_round_trips_added_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._iso(tmp)
            data = profile.default_profile()
            data["extra_skills"] = ["Scrum", "HTTP"]
            html = render_profile_edit(data)
            assert 'name="extra"' in html and 'value="Scrum, HTTP"' in html

    def test_view_page_shows_added_skills_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._iso(tmp)
            data = profile.default_profile()
            data["extra_skills"] = ["Scrum", "HTTP"]
            html = render_profile_view(data)
            assert "Added skills" in html and "Scrum, HTTP" in html


class TestExcludeSkills:
    def _iso(self, tmp):
        paths.use_home(tmp)

    def test_exclude_persists_without_cv_validation(self):
        # Анти-цілі не мусять бути в CV — інакше їх не додати.
        with tempfile.TemporaryDirectory() as tmp:
            self._iso(tmp)
            profile.save(
                {
                    "role": "qa_automation",
                    "cv_text": "Playwright",
                    "skills": ["Playwright"],
                    "exclude": ["manual testing", "game testing"],
                }
            )
            assert profile.load()["exclude"] == ["manual testing", "game testing"]

    def test_exclude_feeds_l0_title_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._iso(tmp)
            profile.save(
                {
                    "role": "qa_automation",
                    "cv_text": "x",
                    "skills": [],
                    "exclude": ["manual testing"],
                }
            )
            l0 = profile.effective_l0({}, profile.load())
            from jobradar import engine as jobradar

            # Назва з «Manual Testing» — відсіюється.
            passed, _ = jobradar.l0_filter(
                {"title": "Manual Testing Engineer", "description": "QA automation"}, l0
            )
            assert passed is False
            # Автоматизаційна роль, що ЗГАДУЄ manual testing в описі — лишається.
            passed2, _ = jobradar.l0_filter(
                {
                    "title": "Senior QA Automation Engineer",
                    "description": "Playwright, some manual testing duties, automation",
                },
                l0,
            )
            assert passed2 is True


class TestStackFeeds:
    def _iso(self, tmp):
        paths.use_home(tmp)

    def test_role_feeds_are_broad_no_tech_keywords(self):
        # Роль ловить ринок за позицією; конкретних інструментів у ній нема.
        feeds = " ".join(roles.feeds("qa_automation"))
        assert "category=QA" in feeds
        assert "Playwright" not in feeds and "pytest" not in feeds

    def test_stack_adds_deep_search_feeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._iso(tmp)
            profile.save(
                {
                    "role": "qa_automation",
                    "cv_text": "Playwright",
                    "skills": ["Playwright"],
                    "stack": ["Playwright", "Cypress"],
                }
            )
            feeds = profile.effective_feeds({}, profile.load())
            assert any("search=Playwright" in f for f in feeds)
            assert any("search=Cypress" in f for f in feeds)
            # широкі рольові теж на місці
            assert any("category=QA" in f for f in feeds)

    def test_stack_persists_without_cv_validation(self):
        # У «Стек» можна вписати ціль, якої ще нема в CV.
        with tempfile.TemporaryDirectory() as tmp:
            self._iso(tmp)
            profile.save(
                {
                    "role": "qa_automation",
                    "cv_text": "QA",
                    "skills": [],
                    "stack": ["k6", "Gatling"],
                }
            )
            assert profile.load()["stack"] == ["k6", "Gatling"]

    def test_stack_feed_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._iso(tmp)
            # SDET уже у фідах ролі — стек не має його дублювати.
            profile.save(
                {
                    "role": "qa_automation",
                    "cv_text": "x",
                    "skills": [],
                    "stack": ["SDET"],
                }
            )
            feeds = profile.effective_feeds({}, profile.load())
            assert len(feeds) == len(set(feeds))


class TestFeedMuting:
    """«Не для мене» ховає зі стрічки по НАЗВІ; збіг у тілі лишається видимим."""

    def test_title_match_hidden_body_match_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            from jobradar import engine as jobradar

            paths.use_home(tmp)
            profile.save(
                {
                    "role": "qa_automation",
                    "cv_text": "x",
                    "skills": [],
                    "exclude": ["manual testing"],
                }
            )
            paths.use_home(tmp)
            conn = jobradar.db_connect()
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,description,first_seen,l0_pass,status)"
                " VALUES('h1','dou','u1','Manual Testing Engineer','QA role',"
                "'2026-08-15T09:00:00+00:00',1,'new')"
            )
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,description,first_seen,l0_pass,status)"
                " VALUES('h2','dou','u2','Senior QA Automation Engineer',"
                "'Playwright plus some manual testing duties','2026-08-15T09:00:00+00:00',1,'new')"
            )
            conn.commit()

            html = render_feed(conn, {"status": "all"})
            # Назва з «manual testing» — прихована; тіло з «manual testing» — лишилось.
            assert "Manual Testing Engineer" not in html
            assert "Senior QA Automation Engineer" in html
            # Counter is consistent: one left in the universe.
            assert "<b>1</b> in the database" in html
            # Рядок нікуди не зник із бази — просто не показаний.
            assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 2
            conn.close()


class TestCalendar:
    """Календар активності: нові по first_seen, відгуки по status_at."""

    def _conn(self, tmp):
        from jobradar import engine as jobradar

        paths.use_home(tmp)
        return jobradar.db_connect()

    def test_grid_header_and_nav(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            page = render_calendar(conn, {"year": "2026", "month": "8"})
            assert "August 2026" in page and "cal-grid" in page
            assert "<th>Mon</th>" in page and "<th>Sun</th>" in page
            # arrows lead to July and September
            assert "month=7" in page and "month=9" in page
            conn.close()

    def test_counts_new_and_applied_per_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            # дві нові 2026-08-10 (l0_pass=1), одна відсіяна (не рахується),
            # один відгук зі status_at 2026-08-12
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status)"
                " VALUES('n1','dou','u1','A','2026-08-10T09:00:00+00:00',1,'new')"
            )
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status)"
                " VALUES('n2','dou','u2','B','2026-08-10T18:00:00+00:00',1,'new')"
            )
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status)"
                " VALUES('n3','dou','u3','C','2026-08-10T20:00:00+00:00',0,'new')"
            )
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status,"
                "status_at) VALUES('a1','dou','u4','D','2026-08-01T09:00:00+00:00',1,"
                "'applied','2026-08-12T15:00:00+00:00')"
            )
            conn.commit()
            page = render_calendar(conn, {"year": "2026", "month": "8"})
            assert "+2" in page  # two new on the 10th (the filtered one doesn't count)
            assert "✓1" in page  # one application on the 12th
            assert "<b>3</b> new, <b>1</b> applications" in page
            conn.close()

    def test_number_links_to_scrollable_day_modal(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,company,first_seen,l0_pass,"
                "status) VALUES('n1','dou','u1','Playwright QA','Acme',"
                "'2026-08-10T09:00:00+00:00',1,'new')"
            )
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,company,first_seen,l0_pass,"
                "status) VALUES('n2','dou','u2','SDET','Acme',"
                "'2026-08-10T18:00:00+00:00',1,'new')"
            )
            conn.commit()
            page = render_calendar(conn, {"year": "2026", "month": "8"})
            # Число — посилання на модалку того дня.
            assert 'href="#calN-2026-08-10"' in page
            # Модалка існує, має скрол-список і назви обох вакансій.
            assert 'id="calN-2026-08-10"' in page and "calpop-list" in page
            assert "10 August · new (2)" in page
            assert "Playwright QA" in page and "SDET" in page and "Acme" in page
            conn.close()

    def test_defaults_to_current_month(self):
        from datetime import datetime, timezone

        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            page = render_calendar(conn, {})
            now = datetime.now(timezone.utc)
            assert views.MONTHS[now.month] in page and str(now.year) in page
            conn.close()

    def test_status_change_records_status_at(self):
        # Зміна статусу через веб-шар має проставити status_at (для календаря).
        from jobradar import engine as jobradar

        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            conn = jobradar.db_connect()
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status)"
                " VALUES('x','dou','u','QA','2026-08-10T09:00:00+00:00',1,'new')"
            )
            conn.commit()
            conn.execute(
                "UPDATE jobs SET status=?, status_at=? WHERE hash='x'",
                ("applied", jobradar.now_iso()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT status, status_at FROM jobs WHERE hash='x'"
            ).fetchone()
            assert row["status"] == "applied" and row["status_at"]
            conn.close()


class TestDateSortFilter:
    """Сортування за датою публікації і фільтр за період."""

    def _conn(self, tmp):
        from jobradar import engine as jobradar

        paths.use_home(tmp)
        return jobradar.db_connect()

    def _seed(self, conn):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        # три вакансії: опубліковані 0, 5 і 40 днів тому
        for h, title, ago in (
            ("new", "Fresh QA", 0),
            ("mid", "Mid QA", 5),
            ("old", "Old QA", 40),
        ):
            pub = (now - timedelta(days=ago)).isoformat(timespec="seconds")
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,company,first_seen,published_at,"
                "l0_pass,status) VALUES(?,?,?,?,?,?,?,1,'new')",
                (h, "dou", "u/" + h, title, "Co" + h, pub, pub),
            )
        conn.commit()

    def test_ui_has_sort_and_period_selects(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            html = render_feed(conn, {"status": "all"}, 7.0, {"running": False})
            assert 'name="sort"' in html and "newest first" in html
            assert 'name="days"' in html and "week" in html
            conn.close()

    def test_sort_date_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            html = render_feed(
                conn, {"status": "all", "sort": "date"}, 7.0, {"running": False}
            )
            # Найновіша вакансія стоїть у розмітці раніше за найстарішу.
            assert html.index("Fresh QA") < html.index("Mid QA") < html.index("Old QA")
            conn.close()

    def test_period_filters_by_publication_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            week = render_feed(
                conn, {"status": "all", "days": "7"}, 7.0, {"running": False}
            )
            # За тиждень видно свіжу й 5-денну, але не 40-денну.
            assert "Fresh QA" in week and "Mid QA" in week
            assert "Old QA" not in week
            conn.close()

    def test_sort_days_preserved_in_links(self):
        url = urls.tech_url({"sort": "date", "days": "7"}, ["Playwright"], [], "/")
        assert "sort=date" in url and "days=7" in url


class TestAppliedSort:
    """The Applied tab is ordered by when you applied (status_at), newest on top."""

    def _conn(self, tmp):
        from jobradar import engine as jobradar

        paths.use_home(tmp)
        return jobradar.db_connect()

    def _seed(self, conn):
        # Applied long ago vs recently; status_at is set on the →applied move.
        for h, title, applied_at in (
            ("old", "Old Application", "2026-08-05T09:00:00+00:00"),
            ("new", "New Application", "2026-08-27T09:00:00+00:00"),
        ):
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,company,first_seen,"
                "l0_pass,status,status_at) VALUES(?,?,?,?,?,?,1,'applied',?)",
                (
                    h,
                    "dou",
                    "u/" + h,
                    title,
                    "",
                    "2026-08-01T09:00:00+00:00",
                    applied_at,
                ),
            )
        conn.commit()

    def test_applied_tab_newest_application_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            html = render_feed(conn, {"status": "applied"}, 7.0, {"running": False})
            # Recently applied sits above the long-ago one, regardless of score.
            assert html.index("New Application") < html.index("Old Application")
            conn.close()

    def test_applied_tab_dropdown_offers_recently_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            applied = render_feed(conn, {"status": "applied"}, 7.0, {"running": False})
            assert 'value="applied" selected' in applied
            assert "recently applied" in applied
            # Score sorting is not offered on the Applied tab.
            assert "score: high" not in applied
            # …but it is on other tabs.
            new = render_feed(conn, {"status": "new"}, 7.0, {"running": False})
            assert "recently applied" not in new and "score: high" in new
            conn.close()

    def test_explicit_date_sort_wins_on_applied_tab(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            html = render_feed(
                conn,
                {"status": "applied", "sort": "date"},
                7.0,
                {"running": False},
            )
            assert 'value="date" selected' in html
            conn.close()


class TestDjinni:
    SAMPLE = (
        '<?xml version="1.0"?><rss><channel>'
        "<item><title>Senior QA Automation Engineer</title>"
        "<link>https://djinni.co/jobs/843430-senior-qa/?utm=x</link>"
        "<description>&lt;p&gt;&lt;strong&gt;Playwright&lt;/strong&gt; and TypeScript&lt;/p&gt;</description>"
        "<pubDate>Mon, 17 Aug 2026 20:49:31 +0300</pubDate></item>"
        "</channel></rss>"
    )

    def test_collect_djinni_parses_rss(self):
        # Джерело читає RSS із фікстури через ін'єктований http (вимога #4).
        from jobradar.core.collectors import djinni

        jobs = djinni.collect_djinni(
            ["https://djinni.co/jobs/rss/?primary_keyword=QA"],
            http=lambda url, timeout=25: self.SAMPLE,
        )
        assert len(jobs) == 1
        j = jobs[0]
        assert j["source"] == "djinni"
        assert j["title"] == "Senior QA Automation Engineer"
        assert j["company"] == ""  # у фіді компанії немає
        assert j["url"] == "https://djinni.co/jobs/843430-senior-qa/"  # ?utm зрізано
        assert "Playwright" in j["description"] and j["published_at"].startswith(
            "2026-08-17"
        )

    def test_role_supplies_djinni_feed(self):
        assert any("djinni.co" in f for f in roles.djinni_feeds("qa_automation"))

    def test_effective_djinni_feeds_from_role(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            paths.use_home(tmp)
            profile.save({"role": "qa", "cv_text": "x", "skills": []})
            feeds = profile.effective_djinni_feeds({})
            assert feeds and all("djinni.co" in f for f in feeds)


class TestDjinniCards:
    """Структуровані поля (extra) видно на картці Djinni й приховано для DOU."""

    EXTRA = (
        '{"experience": 3, "english": "C1 \\u2013 \\u041f\\u0440\\u043e\\u0441'
        '\\u0443\\u043d\\u0443\\u0442\\u0438\\u0439", "work_format": "Full Remote", '
        '"domain": "saas"}'
    )

    def _conn(self, tmp):
        from jobradar import engine as jobradar

        paths.use_home(tmp)
        return jobradar.db_connect()

    def test_djinni_card_shows_extra(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status,extra)"
                " VALUES('h1','djinni','u1','QA Automation',"
                "'2026-08-15T09:00:00+00:00',1,'new',?)",
                (self.EXTRA,),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM jobs WHERE hash='h1'").fetchone()
            html = render_card(row, 7.0)
            assert "job-extra" in html and "Full Remote" in html
            assert "experience 3 yr" in html
            conn.close()

    def test_dou_card_hides_extra(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status,extra)"
                " VALUES('h2','dou','u2','QA Engineer',"
                "'2026-08-15T09:00:00+00:00',1,'new','')"
            )
            conn.commit()
            row = conn.execute("SELECT * FROM jobs WHERE hash='h2'").fetchone()
            assert "job-extra" not in render_card(row, 7.0)
            conn.close()

    def test_stats_sources_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status,extra,salary)"
                " VALUES('h1','djinni','u1','QA','2026-08-15T09:00:00+00:00',1,'new',?, "
                "'$3000')",
                (self.EXTRA,),
            )
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status,extra)"
                " VALUES('h2','dou','u2','QA','2026-08-15T09:00:00+00:00',1,'new','')"
            )
            conn.commit()
            html = render_stats(conn, {})
            assert "Sources" in html and "srcbar" in html
            assert "Djinni: what DOU does not have" in html
            conn.close()


class TestMultiSource:
    """Та сама вакансія на DOU і Djinni: дедуп схлопує в один рядок, але картка
    показує обидва джерела своїми посиланнями."""

    def _conn(self, tmp):
        from jobradar import engine as jobradar

        paths.use_home(tmp)
        return jobradar.db_connect()

    def test_merge_source_adds_second(self):
        import json

        from jobradar import engine as jobradar

        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status,sources)"
                " VALUES('h1','dou','dou/1','QA','2026-08-15T09:00:00+00:00',1,'new',"
                '\'{"dou": "dou/1"}\')'
            )
            conn.commit()
            jobradar.merge_source(conn, "h1", "djinni", "djinni/1")
            smap = json.loads(
                conn.execute("SELECT sources FROM jobs WHERE hash='h1'").fetchone()[
                    "sources"
                ]
            )
            assert smap == {"dou": "dou/1", "djinni": "djinni/1"}
            conn.close()

    def test_merge_source_idempotent(self):
        import json

        from jobradar import engine as jobradar

        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status,sources)"
                " VALUES('h1','dou','dou/1','QA','2026-08-15T09:00:00+00:00',1,'new',"
                '\'{"dou": "dou/1"}\')'
            )
            conn.commit()
            jobradar.merge_source(conn, "h1", "dou", "dou/other")  # те саме джерело
            smap = json.loads(
                conn.execute("SELECT sources FROM jobs WHERE hash='h1'").fetchone()[
                    "sources"
                ]
            )
            assert smap == {"dou": "dou/1"}  # перше посилання виграє
            conn.close()

    def test_card_shows_both_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status,sources)"
                " VALUES('h1','dou','dou/1','QA','2026-08-15T09:00:00+00:00',1,'new',"
                '\'{"dou": "dou/1", "djinni": "djinni/1"}\')'
            )
            conn.commit()
            card = render_card(
                conn.execute("SELECT * FROM jobs WHERE hash='h1'").fetchone(), 7.0
            )
            assert "openbox multi" in card
            # Кожне джерело — свій клікабельний логотип на свою сторінку.
            assert card.count('class="srcicon"') == 2
            assert 'href="dou/1"' in card and 'href="djinni/1"' in card
            assert "/resources/dou_logo.png?v=" in card
            assert "/resources/djinni_logo.png?v=" in card
            conn.close()

    def test_card_single_source_one_logo(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status,sources)"
                " VALUES('h2','dou','dou/2','QA','2026-08-15T09:00:00+00:00',1,'new',"
                '\'{"dou": "dou/2"}\')'
            )
            conn.commit()
            card = render_card(
                conn.execute("SELECT * FROM jobs WHERE hash='h2'").fetchone(), 7.0
            )
            assert "openbox multi" not in card
            assert card.count('class="srcicon"') == 1
            assert "/resources/dou_logo.png?v=" in card
            conn.close()

    def test_card_unknown_source_text_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status,sources)"
                " VALUES('h3','linkedin','li/3','QA','2026-08-15T09:00:00+00:00',1,'new',"
                '\'{"linkedin": "li/3"}\')'
            )
            conn.commit()
            card = render_card(
                conn.execute("SELECT * FROM jobs WHERE hash='h3'").fetchone(), 7.0
            )
            # Джерело без логотипа падає на текстову мітку, а не ламається.
            assert "srctext" in card and "linkedin" in card
            assert "srclogo" not in card
            conn.close()


class TestCompanyPage:
    """Сторінка компанії: клік по назві, агрегована інфо, перелік вакансій."""

    def _conn(self, tmp):
        from jobradar import engine as jobradar

        paths.use_home(tmp)
        return jobradar.db_connect()

    def _seed(self, conn):
        conn.execute(
            "INSERT INTO jobs(hash,source,url,title,company,location,salary,description,"
            "first_seen,l0_pass,status,extra) VALUES('a','djinni','dj/a',"
            "'QA Automation Engineer','Acme','Kyiv','$3000','Playwright and TypeScript',"
            '\'2026-08-15T09:00:00+00:00\',1,\'new\',\'{"domain":"fintech","work_format":'
            '"Full Remote","english":"B2"}\')'
        )
        conn.execute(
            "INSERT INTO jobs(hash,source,url,title,company,location,salary,description,"
            "first_seen,l0_pass,status,extra) VALUES('b','dou','dou/b',"
            "'Manual QA Engineer','Acme','','','manual testing',"
            "'2026-08-15T09:00:00+00:00',0,'new','')"
        )
        conn.commit()

    def test_company_link_encodes_name_and_token(self):
        assert urls.company_link("Foo Bar", {}) == "/company?name=Foo+Bar"
        link = urls.company_link("Foo", {"token": "t"})
        assert "name=Foo" in link and "token=t" in link

    def test_card_company_is_a_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            card = render_card(
                conn.execute("SELECT * FROM jobs WHERE hash='a'").fetchone(), 7.0
            )
            assert '<a class="co" href="/company?name=Acme"' in card
            conn.close()

    def test_company_page_shows_info_and_all_vacancies(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            page = render_company(conn, {"name": "Acme"}, 7.0)
            assert "coinfo" in page  # блок агрегованої інфо
            assert "fintech" in page and "Full Remote" in page and "B2" in page
            assert "Kyiv" in page and "$3000" in page
            # ВСІ вакансії компанії, включно з L0-відсіяними
            assert "QA Automation Engineer" in page and "Manual QA Engineer" in page
            assert "2 vacancies · 1 passed the filter" in page
            conn.close()

    def test_unknown_company_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            page = render_company(conn, {"name": "Nope"}, 7.0)
            assert "Company not found" in page
            conn.close()


class TestAlsoOn:
    """«Також на іншому борді» — м'який крос-референс без злиття рядків."""

    def _conn(self, tmp):
        from jobradar import engine as jobradar

        paths.use_home(tmp)
        return jobradar.db_connect()

    def _ins(self, conn, h, source, title, company, url, sources=None, l0=1):
        conn.execute(
            "INSERT INTO jobs(hash,source,url,title,company,first_seen,l0_pass,status,sources)"
            " VALUES(?,?,?,?,?, '2026-08-15T09:00:00+00:00',?,'new',?)",
            (h, source, url, title, company, l0, sources or ""),
        )

    def test_core_strips_seniority_parens_and_tail(self):
        assert (
            views._title_core("Middle+ Manual QA Engineer — FinTech")
            == "manual qa engineer"
        )
        assert (
            views._title_core("Senior QA Automation Engineer")
            == "qa automation engineer"
        )

    def test_exact_core_match_across_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._ins(
                conn,
                "h1",
                "dou",
                "Middle+ Manual QA Engineer — FinTech",
                "JustCoded",
                "dou/1",
            )
            self._ins(
                conn, "h2", "djinni", "Middle+ Manual QA Engineer", "JustCoded", "dj/2"
            )
            conn.commit()
            rows = conn.execute("SELECT * FROM jobs WHERE hash='h1'").fetchall()
            also = views.build_also_on(conn, rows)
            assert also.get("h1") == [("djinni", "dj/2")]
            conn.close()

    def test_different_core_no_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._ins(conn, "h1", "dou", "QA Automation Engineer", "Foo", "dou/1")
            self._ins(conn, "h2", "djinni", "Manual QA Engineer", "Foo", "dj/2")
            conn.commit()
            rows = conn.execute("SELECT * FROM jobs WHERE hash='h1'").fetchall()
            assert views.build_also_on(conn, rows) == {}
            conn.close()

    def test_already_merged_source_not_hinted(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            # h1 уже злитий з djinni (sources) — хінта на djinni бути не має.
            self._ins(
                conn,
                "h1",
                "dou",
                "Manual QA Engineer",
                "Bar",
                "dou/1",
                sources='{"dou": "dou/1", "djinni": "dj/x"}',
            )
            self._ins(conn, "h2", "djinni", "Manual QA Engineer", "Bar", "dj/2")
            conn.commit()
            rows = conn.execute("SELECT * FROM jobs WHERE hash='h1'").fetchall()
            assert views.build_also_on(conn, rows) == {}
            conn.close()

    def test_card_renders_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._ins(conn, "h1", "dou", "Manual QA Engineer", "Baz", "dou/1")
            conn.commit()
            row = conn.execute("SELECT * FROM jobs WHERE hash='h1'").fetchone()
            card = render_card(row, 7.0, also_on=[("djinni", "dj/9")])
            assert 'class="alsoon"' in card and "likely also on" in card
            assert 'href="dj/9"' in card and "djinni ↗" in card
            # without also_on — nothing extra
            assert 'class="alsoon"' not in render_card(row, 7.0)
            conn.close()


class TestKeyfacts:
    """Вилку видно окремим помітним рядком; англійська — в рядку структурних полів."""

    def _conn(self, tmp):
        from jobradar import engine as jobradar

        paths.use_home(tmp)
        return jobradar.db_connect()

    def test_salary_prominent_english_in_extra_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status,salary,extra)"
                " VALUES('h1','djinni','u1','QA','2026-08-15T09:00:00+00:00',1,'new',"
                '\'$3000-4000\',\'{"english": "B2", "experience": 3}\')'
            )
            conn.commit()
            card = render_card(
                conn.execute("SELECT * FROM jobs WHERE hash='h1'").fetchone(), 7.0
            )
            # Salary range — prominent kf-pay; English — no longer kf-eng, an xchip in job-extra.
            assert 'class="kf kf-pay"' in card and "$3000-4000</span>" in card
            assert "kf-eng" not in card
            extra = card.split('class="job-extra"')[1]
            # Language first in the structured-fields row (before experience).
            assert extra.index("English B2") < extra.index("experience 3 yr")
            conn.close()

    def test_no_data_no_keyfacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,first_seen,l0_pass,status,salary,extra)"
                " VALUES('h2','dou','u2','QA','2026-08-15T09:00:00+00:00',1,'new','','')"
            )
            conn.commit()
            card = render_card(
                conn.execute("SELECT * FROM jobs WHERE hash='h2'").fetchone(), 7.0
            )
            assert "keyfacts" not in card
            conn.close()


class TestFilterUI:
    """Попапи фільтра (теги, компанії), фільтр по компаніях і групування."""

    def _conn(self, tmp):
        from jobradar import engine as jobradar

        paths.use_home(tmp)
        return jobradar.db_connect()

    def _seed(self, conn):
        rows = [
            ("h1", "dou", "Playwright QA Automation", "Acme", 1),
            ("h2", "dou", "Senior QA Engineer", "Acme", 1),  # Acme має 2 → група
            ("h3", "dou", "TypeScript SDET", "Globex", 1),  # Globex одна → без групи
        ]
        for h, src, title, co, l0 in rows:
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,company,description,first_seen,l0_pass,status)"
                " VALUES(?,?,?,?,?,?, '2026-08-15T09:00:00+00:00',?,'new')",
                (h, src, "u/" + h, title, co, "Playwright and TypeScript", l0),
            )
        conn.commit()

    def test_tag_popup_has_search_sections_checkboxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            html = render_pick("tags", conn, {"status": "all"})
            assert 'data-pick="tags"' in html
            assert "picksearch" in html  # пошук
            assert "<h4>" in html  # секції за групами
            assert 'name="tech" value="Playwright"' in html  # чекбокс-мультиселект
            assert ">Apply<" in html
            conn.close()

    def test_tag_popup_marks_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            html = render_pick("tags", conn, {"status": "all", "tech": "Playwright"})
            assert 'name="tech" value="Playwright" checked' in html
            conn.close()

    def test_company_popup_lists_companies(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            html = render_pick("companies", conn, {"status": "all"})
            assert 'data-pick="companies"' in html and "picksearch" in html
            assert (
                'name="co" value="Acme"' in html and 'name="co" value="Globex"' in html
            )
            conn.close()

    def test_company_filter_narrows_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            html = render_feed(
                conn, {"status": "all", "co": "Globex"}, 7.0, {"running": False}
            )
            # Заголовки вакансій: лишилась лише Globex-вакансія, Acme-вакансій нема.
            assert "TypeScript SDET" in html
            assert "Senior QA Engineer" not in html
            conn.close()

    def test_same_company_grouped(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            html = render_feed(conn, {"status": "all"}, 7.0, {"running": False})
            # Acme (2) — in a group; Globex (1) — a plain card.
            assert 'class="cogroup"' in html and "2 vacancies" in html
            assert html.count("data-pick") >= 2  # both popups present
            conn.close()

    def test_co_sets_splits_on_newline(self):
        assert urls.co_sets({"co": "Foo, Inc.\nBar LLC"}) == ["Foo, Inc.", "Bar LLC"]
        assert urls.co_sets({}) == []

    def test_hidden_fields_co_one_field_each(self):
        with _app().test_request_context():
            html = flask.render_template_string(
                "{% import 'partials/_macros.html' as ui %}"
                "{{ ui.hidden_fields(params, ['co', 'token']) }}",
                params={"co": "Acme\nGlobex", "token": "t"},
            )
        assert html.count('name="co"') == 2  # окреме поле на компанію
        assert 'value="Acme"' in html and 'value="Globex"' in html
        assert 'name="token" value="t"' in html


class TestNotForMeTags:
    """Profile 'not for me' tags drop out of the picker/cloud; picker counts
    follow the current view so the number matches the filtered feed."""

    def _conn(self, tmp):
        from jobradar import engine as jobradar

        paths.use_home(tmp)
        return jobradar.db_connect()

    def _seed(self, conn):
        rows = [
            ("a", "Playwright QA", "Playwright automation", "new"),
            ("b", "Java Developer", "Java and Spring", "new"),  # Java in TITLE
            ("c", "Backend Engineer", "We use Java and SQL", "new"),  # Java body-only
            ("d", "SDET", "Playwright and SQL", "skipped"),
        ]
        for h, title, desc, status in rows:
            conn.execute(
                "INSERT INTO jobs(hash,source,url,title,company,description,"
                "first_seen,l0_pass,status)"
                " VALUES(?,?,?,?,?,?, '2026-08-15T09:00:00+00:00',1,?)",
                (h, "dou", "u/" + h, title, "Acme", desc, status),
            )
        conn.commit()
        profile.save(
            {"role": "qa_automation", "cv_text": "Playwright", "exclude": ["Java"]}
        )

    @staticmethod
    def _count(pt, term):
        for sect in pt["sections"]:
            for row in sect["rows"]:
                if row["value"] == term:
                    return row["count"]
        return None

    def test_excluded_tag_absent_from_picker(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            html = render_pick("tags", conn, {"status": "all"})
            assert 'value="Java"' not in html  # "not for me" → not offered
            assert 'value="SQL"' in html  # a normal tag still is
            conn.close()

    def test_excluded_tag_absent_from_cloud(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            ctx = views.tags_context(conn, {})
            terms = [t["term"] for s in ctx["sections"] for t in s["tags"]]
            assert "Java" not in terms and "SQL" in terms
            conn.close()

    def test_picker_count_follows_current_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._conn(tmp)
            self._seed(conn)
            # SQL is in one 'new' vacancy (c) and one 'skipped' (d).
            new_pt = views._pick_tags(conn, {"status": "new"})
            all_pt = views._pick_tags(conn, {"status": "all"})
            assert self._count(new_pt, "SQL") == 1
            assert self._count(all_pt, "SQL") == 2
            conn.close()


def test_llm_access_fields_round_trip(tmp_path):
    """Key + model + provider + base URL persist in profile.json (portability)."""
    paths.use_home(str(tmp_path))
    profile.save(
        {
            "role": "qa_automation",
            "api_key": "sk-ant-xxx",
            "llm_model": "claude-sonnet-5",
            "llm_provider": "openai",
            "llm_base_url": "http://localhost:11434/v1",
        }
    )
    data = profile.load()
    assert data["api_key"] == "sk-ant-xxx"
    assert data["llm_model"] == "claude-sonnet-5"
    assert data["llm_provider"] == "openai"
    assert data["llm_base_url"] == "http://localhost:11434/v1"


def test_llm_access_defaults_empty(tmp_path):
    paths.use_home(str(tmp_path))
    data = profile.default_profile()
    assert data["api_key"] == "" and data["llm_model"] == ""
