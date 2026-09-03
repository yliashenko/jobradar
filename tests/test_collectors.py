"""Колектори: розбір заголовків DOU (Djinni RSS покрито в test_pipeline).

Парсер заголовка DOU — найімовірніше місце, де все посиплеться при зміні розмітки
борду (CLAUDE.md §7), тому тримаємо його під регресом.
"""

from jobradar.core.collectors import dou


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
