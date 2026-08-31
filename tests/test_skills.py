"""Словник технологій і підсвітка стеку в описі вакансії."""

import re

from jobradar import skills


class TestVocabulary:
    def test_named_technologies_are_present(self):
        # Мінімум, названий замовником словника.
        expected = [
            "TypeScript",
            "JavaScript",
            "UI/API",
            "Playwright",
            "Cypress",
            "Python",
            "Java",
            "REST",
            "Selenium",
        ]
        lower = {t.lower() for t in skills.ALL_TERMS}
        assert [t for t in expected if t.lower() not in lower] == []

    def test_groups_cover_tools_and_approaches(self):
        # Словник — не лише інструменти: підходи шукаються в тексті так само.
        assert "BDD" in skills.APPROACHES
        assert "shift-left" in skills.APPROACHES
        assert "Playwright" in skills.UI_AUTOMATION

    def test_no_duplicates_across_groups(self):
        flat = [t.lower() for group in skills.GROUPS.values() for t in group]
        assert len(flat) == len(set(flat))


class TestHighlight:
    def test_wraps_known_term(self):
        assert (
            skills.highlight_html("Досвід з Playwright")
            == 'Досвід з <b class="tech">Playwright</b>'
        )

    def test_keeps_original_case(self):
        assert ">PyTest<" in skills.highlight_html("знання PyTest")
        assert ">PYTEST<" in skills.highlight_html("знання PYTEST")

    def test_does_not_match_inside_longer_word(self):
        # Класична пастка: Java всередині JavaScript.
        out = skills.highlight_html("JavaScript")
        assert out == '<b class="tech">JavaScript</b>'

    def test_longest_term_wins(self):
        out = skills.highlight_html("REST Assured")
        assert out == '<b class="tech">REST Assured</b>'

    def test_terms_with_special_characters(self):
        for term in ("C#", "C++", ".NET", "k6", "CI/CD"):
            out = skills.highlight_html(f"стек: {term} тут")
            assert f'<b class="tech">{term}</b>' in out, term

    def test_markup_is_never_touched(self):
        # Регрес-захист: якби підсвічували весь рядок, а не текстові шматки,
        # «API» всередині тега перетворило б розмітку на сміття.
        source = '<p class="api">API</p>'
        out = skills.highlight_html(source)
        assert out == '<p class="api"><b class="tech">API</b></p>'
        assert out.count("<p") == 1

    def test_existing_bold_survives(self):
        out = skills.highlight_html("<strong>Playwright</strong>")
        assert out == '<strong><b class="tech">Playwright</b></strong>'

    def test_empty_input(self):
        assert skills.highlight_html("") == ""
        assert skills.highlight_html(None) is None

    def test_unknown_words_are_left_alone(self):
        assert skills.highlight_html("вигулювати песика") == "вигулювати песика"


class TestFoundTerms:
    def test_collects_unique_terms(self):
        found = skills.found_terms("Playwright, TypeScript і playwright знову")
        assert [t.lower() for t in found] == ["playwright", "typescript"]

    def test_empty_text(self):
        assert skills.found_terms("") == []


class TestRealisticDescription:
    TEXT = (
        "<p>Ми шукаємо Senior QA Automation Engineer.</p>"
        "<ul><li>3+ роки з Playwright або Cypress</li>"
        "<li>TypeScript чи JavaScript</li>"
        "<li>REST API, Postman, CI/CD (GitHub Actions)</li>"
        "<li>розуміння BDD і піраміди тестування</li></ul>"
    )

    def test_stack_is_highlighted(self):
        out = skills.highlight_html(self.TEXT)
        for term in (
            "Playwright",
            "Cypress",
            "TypeScript",
            "JavaScript",
            "REST",
            "Postman",
            "CI/CD",
            "GitHub Actions",
            "BDD",
        ):
            assert f'<b class="tech">{term}</b>' in out, term

    def test_structure_is_preserved(self):
        out = skills.highlight_html(self.TEXT)
        assert out.count("<li>") == out.count("</li>") == 4
        assert re.sub(r"<b class=\"tech\">|</b>", "", out) == self.TEXT


class TestTagSearch:
    """Клік по тегу має давати рівно ті вакансії, де тег справді згадано."""

    def test_mentions_respects_word_boundaries(self):
        # Головна пастка пошуку: підрядок «Java» є в кожному «JavaScript».
        assert skills.mentions("стек: JavaScript, Node", "Java") is False
        assert skills.mentions("стек: Java 17, Spring", "Java") is True

    def test_mentions_is_case_insensitive(self):
        assert skills.mentions("знання PYTEST обов'язкове", "pytest") is True

    def test_mentions_handles_special_characters(self):
        assert skills.mentions("досвід з C# та .NET", "C#") is True
        assert skills.mentions("налаштований CI/CD", "CI/CD") is True

    def test_unknown_term_matches_nothing(self):
        # Довільний рядок із параметра URL не має раптом щось знаходити.
        assert skills.mentions("будь-який текст", "'; DROP TABLE jobs; --") is False

    def test_canonical_spelling(self):
        assert skills.canonical("PYTEST") == "pytest"
        assert skills.canonical("playwright") == "Playwright"
        assert skills.canonical("невідоме") == "невідоме"


class TestTally:
    def test_counts_vacancies_not_occurrences(self):
        texts = ["Playwright, Playwright і ще раз Playwright", "TypeScript"]
        counts = skills.tally(texts)
        assert counts["Playwright"] == 1
        assert counts["TypeScript"] == 1

    def test_case_variants_are_one_tag(self):
        counts = skills.tally(["pytest", "PyTest", "PYTEST"])
        assert counts == {"pytest": 3}

    def test_empty_corpus(self):
        assert skills.tally([]) == {}


class TestLinkedHighlight:
    def test_terms_become_links(self):
        out = skills.highlight_html("досвід з Playwright", lambda t: f"/?tech={t}")
        assert out == 'досвід з <a class="tech" href="/?tech=Playwright">Playwright</a>'

    def test_href_is_escaped(self):
        # Без екранування «&» розмітка бита, а «&copy» у параметрі
        # перетворився б на символ ©.
        out = skills.highlight_html("Playwright", lambda t: f"/?tech={t}&status=all")
        assert "&amp;status=all" in out

    def test_link_uses_canonical_spelling_but_keeps_text(self):
        out = skills.highlight_html("знання PYTEST", lambda t: f"/?tech={t}")
        assert "/?tech=pytest" in out and ">PYTEST</a>" in out


class TestCardTerms:
    """Теги на картці: небагато і найінформативніші."""

    TEXT = (
        "Senior QA Automation Engineer. Agile-команда, regression та smoke, "
        "стек: Playwright, TypeScript, REST API, CI/CD, Jira, BDD, Docker"
    )

    def test_stack_outranks_generic_approaches(self):
        terms, _ = skills.card_terms(self.TEXT, limit=4)
        # Мова і інструмент мають випередити «Agile» і «regression»,
        # які є майже в кожній вакансії й нічого не розрізняють.
        assert "TypeScript" in terms and "Playwright" in terms
        assert "Agile" not in terms and "regression" not in terms

    def test_hidden_terms_are_kept_not_dropped(self):
        # Приховані теги картка розгортає, тому вони мають повертатись.
        shown, hidden = skills.card_terms(self.TEXT, limit=3)
        assert len(shown) == 3 and hidden
        assert not set(shown) & set(hidden)

    def test_no_duplicates(self):
        shown, _ = skills.card_terms("Playwright, playwright, PLAYWRIGHT")
        assert shown == ["Playwright"]

    def test_empty_text(self):
        assert skills.card_terms("") == ([], [])

    def test_all_terms_fit_under_limit(self):
        shown, hidden = skills.card_terms("Playwright і TypeScript", limit=10)
        assert sorted(shown) == ["Playwright", "TypeScript"] and hidden == []


class TestCaseSensitiveTerms:
    """Терміни, що збігаються зі звичайними словами, знайдено на живих даних."""

    def test_lowercase_safe_is_not_the_framework(self):
        # «safe failure behaviour under edge cases» — не про SAFe.
        assert skills.found_terms("ensure safe failure behaviour") == []
        assert skills.mentions("ensure safe failure behaviour", "SAFe") is False

    def test_uppercase_safe_is_the_framework(self):
        assert skills.found_terms("work in SAFe") == ["SAFe"]
        assert skills.mentions("work in SAFe", "SAFe") is True

    def test_lowercase_go_is_a_verb(self):
        # «post go-live monitoring» — не про мову Go.
        assert skills.found_terms("support post go-live monitoring") == []

    def test_uppercase_go_is_the_language(self):
        assert skills.found_terms("backend in Go and Python") == ["Go", "Python"]

    def test_other_terms_stay_case_insensitive(self):
        # Це законні варіанти написання, а не збіг зі словом.
        for text, expected in (
            ("E2E tests", "e2e"),
            ("Pytest", "pytest"),
            ("JIRA", "Jira"),
            ("Typescript", "TypeScript"),
        ):
            found = skills.found_terms(text)
            assert found and skills.canonical(found[0]) == expected, text
