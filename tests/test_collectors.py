"""Колектори: розбір email-алертів (Djinni, LinkedIn) і заголовків DOU.

Парсери листів — найімовірніше місце, де все посиплеться при зміні розмітки
борду (CLAUDE.md §7), тому тримаємо їх під регресом на .eml-подібних фікстурах.
"""

import email

from jobradar.core.collectors import dou, email_alerts

DJINNI_EMAIL = """From: Djinni <no-reply@djinni.co>
Subject: =?utf-8?B?MyDQvdC+0LLRliDQstCw0LrQsNC90YHRltGX?=
Content-Type: text/html; charset="utf-8"
MIME-Version: 1.0

<html><body>
<p>Нові вакансії за вашим фільтром QA Automation:</p>
<table>
<tr><td><a href="https://djinni.co/jobs/712345-senior-qa-automation-engineer/?utm_source=email">
Senior QA Automation Engineer at Ciklum</a><br/>$4000-5500, Remote</td></tr>
<tr><td><a href="https://djinni.co/jobs/712999-sdet-typescript/?src=digest">
SDET (TypeScript) at Nortal</a><br/>Ukraine, remote</td></tr>
</table>
<a href="https://djinni.co/my/subscriptions/">Налаштування підписки</a>
</body></html>
"""

LINKEDIN_EMAIL = """From: LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>
Subject: 2 new jobs for "QA Automation Engineer"
Content-Type: text/html; charset="utf-8"
MIME-Version: 1.0

<html><body>
<a href="https://www.linkedin.com/comm/jobs/view/4123456789/?trackingId=abc">
Senior Automation Testing Engineer at Avenga</a>
<a href="https://www.linkedin.com/comm/jobs/view/4987654321/?refId=xyz">
QA Automation Engineer at SoftServe</a>
<a href="https://www.linkedin.com/comm/jobs/search/?keywords=qa">See all jobs</a>
</body></html>
"""


class TestDjinniEmail:
    def _jobs(self):
        msg = email.message_from_string(DJINNI_EMAIL)
        return email_alerts.extract_jobs_from_message(msg)

    def test_finds_exactly_two(self):
        assert len(self._jobs()) == 2

    def test_url_normalised(self):
        urls = {j["url"] for j in self._jobs()}
        assert "https://djinni.co/jobs/712345/" in urls  # ?utm зрізано

    def test_title_split_from_company(self):
        by_url = {j["url"]: j for j in self._jobs()}
        job = by_url["https://djinni.co/jobs/712345/"]
        assert job["title"] == "Senior QA Automation Engineer"
        assert job["company"] == "Ciklum"

    def test_subscription_link_ignored(self):
        assert all("subscriptions" not in j["url"] for j in self._jobs())


class TestLinkedInEmail:
    def _jobs(self):
        msg = email.message_from_string(LINKEDIN_EMAIL)
        return email_alerts.extract_jobs_from_message(msg)

    def test_finds_exactly_two(self):
        assert len(self._jobs()) == 2

    def test_comm_stripped_from_url(self):
        urls = {j["url"] for j in self._jobs()}
        assert "https://www.linkedin.com/jobs/view/4123456789/" in urls

    def test_company_extracted(self):
        by_url = {j["url"]: j for j in self._jobs()}
        assert (
            by_url["https://www.linkedin.com/jobs/view/4123456789/"]["company"]
            == "Avenga"
        )

    def test_search_link_not_a_job(self):
        assert all("/jobs/search" not in j["url"] for j in self._jobs())


class TestDouTitle:
    def test_full_title(self):
        title, company, salary, location = dou.parse_dou_title(
            "Senior Automation QA Engineer (4210) в Ciklum, $4000–5000, Київ, віддалено"
        )
        assert title == "Senior Automation QA Engineer (4210)"
        assert company == "Ciklum"
        assert salary == "$4000–5000"
        assert location == "Київ, віддалено"

    def test_bare_title(self):
        title, company, salary, _ = dou.parse_dou_title("QA Engineer в Netpeak")
        assert (title, company, salary) == ("QA Engineer", "Netpeak", "")
