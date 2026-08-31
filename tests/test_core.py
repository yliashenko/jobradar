"""Перша цеглина pytest-шару (ADR-0004): дублює ключові перевірки
selftest.py для подвійного прогону. selftest.py лишається чинним."""

from jobradar import engine as jobradar


class TestDedupHash:
    def test_same_vacancy_across_sources_collapses(self):
        a = jobradar.job_hash("Ciklum", "Senior Automation QA Engineer")
        b = jobradar.job_hash("ciklum ", "Senior  Automation QA Engineer (remote)")
        assert a == b

    def test_different_companies_stay_apart(self):
        a = jobradar.job_hash("Ciklum", "Senior Automation QA Engineer")
        c = jobradar.job_hash("Nortal", "Senior Automation QA Engineer")
        assert a != c

    def test_internal_number_change_is_a_new_vacancy_by_design(self):
        # Свідомо зафіксований компроміс (CLAUDE.md §4): у ZONE3000
        # #1205 і #1301 можуть бути різними ролями, тому цифри з назви
        # НЕ викидаються. Якщо цей тест упав — хтось «виправив» дедуп,
        # не перечитавши обґрунтування.
        a = jobradar.job_hash("Ciklum", "Senior Automation QA Engineer (4210)")
        b = jobradar.job_hash("Ciklum", "Senior Automation QA Engineer (4315)")
        assert a != b


class TestL0Filter:
    RULES = {
        "exclude_title": [r"\b(junior|intern|trainee|стажер|джун)\b"],
        "exclude_text": [],
        "require_any_text": [r"\bQA\b", r"\bautomation\b"],
        "min_salary_usd": 3000,
    }

    def test_missing_keys_do_not_crash(self):
        # Регрес реального бага: l0_filter падав на записі без ключів.
        passed, reason = jobradar.l0_filter(
            {"title": "QA Automation Engineer"}, self.RULES
        )
        assert passed is True and reason == ""

    def test_junior_is_rejected(self):
        passed, reason = jobradar.l0_filter(
            {"title": "Junior QA Engineer", "company": "X", "description": "QA"},
            self.RULES,
        )
        assert passed is False and "exclude" in reason

    def test_unknown_salary_is_not_rejected(self):
        job = {
            "title": "QA Automation Engineer",
            "company": "Z",
            "description": "test automation",
            "salary": "",
        }
        passed, _ = jobradar.l0_filter(job, self.RULES)
        assert passed is True


class TestDouTitleParsing:
    def test_full_title_with_salary_and_location(self):
        title, company, salary, location = jobradar.parse_dou_title(
            "Senior Automation QA Engineer (4210) в Ciklum, $4000–5000, Київ, віддалено"
        )
        assert title == "Senior Automation QA Engineer (4210)"
        assert company == "Ciklum"
        assert salary == "$4000–5000"
        assert location == "Київ, віддалено"

    def test_bare_title_without_extras(self):
        title, company, salary, _ = jobradar.parse_dou_title("QA Engineer в Netpeak")
        assert (title, company, salary) == ("QA Engineer", "Netpeak", "")
