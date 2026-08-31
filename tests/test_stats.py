"""Позиціонування проти ринку: покриття, прохідний мінімум, козирі, дірки."""

from jobradar import stats

# Ринок: 10 вакансій. API у 10/10 (прохідний мінімум), Playwright у 6/10,
# TypeScript у 3/10 (козир, якщо є), pytest у 4/10 (дірка, якщо нема).
MARKET = (
    ["API Playwright TypeScript pytest"] * 3
    + ["API Playwright pytest"] * 1
    + ["API Playwright"] * 2
    + ["API"] * 4
)


class TestAnalyse:
    def test_empty_market_returns_none(self):
        assert stats.analyse([], ["Playwright"]) is None

    def test_coverage_counts_owned_top_skills(self):
        res = stats.analyse(MARKET, ["Playwright", "API"])
        assert res["covered"] >= 2  # обидві — у топі попиту

    def test_table_stakes_flag_owned_and_missing(self):
        res = stats.analyse(MARKET, ["Playwright"])  # API нема
        stakes = {t: has for t, _, has in res["stakes"]}
        assert "API" in stakes  # 10/10 → прохідний мінімум
        assert stakes["API"] is False  # і його НЕМА — терміново

    def test_differentiator_is_owned_mid_demand(self):
        res = stats.analyse(MARKET, ["TypeScript"])  # 3/10 = 30%, є
        diff = [t for t, _ in res["differentiators"]]
        assert "TypeScript" in diff
        # API (100%) — не козир, це прохідний мінімум.
        assert "API" not in diff

    def test_gaps_are_missing_skills_by_demand(self):
        res = stats.analyse(MARKET, ["API"])  # усе інше — дірки
        gap_terms = [t for t, _ in res["gaps"]]
        # Playwright (6/10) має стояти вище за pytest (4/10) у дірках.
        assert gap_terms.index("Playwright") < gap_terms.index("pytest")

    def test_owned_skill_is_not_a_gap(self):
        res = stats.analyse(MARKET, ["Playwright", "API", "pytest", "TypeScript"])
        assert res["gaps"] == []

    def test_sample_size_reported(self):
        res = stats.analyse(MARKET, [])
        assert res["total"] == len(MARKET) and res["unique_terms"] >= 1


class TestPie:
    """Pie slice geometry: demand composition, tail folding, legend links."""

    def _pie(self, items, empty="x"):
        from jobradar.web import views

        return views.pie(items, {}, empty)

    def test_empty_shows_hint_not_svg(self):
        p = self._pie([], empty="порожньо")
        assert p["slices"] == [] and p["empty"] == "порожньо"

    def test_slices_match_items_up_to_limit(self):
        p = self._pie([("A", 5), ("B", 3), ("C", 2)])
        assert len(p["slices"]) == 3
        assert not any(s["label"] == "other" for s in p["slices"])

    def test_tail_folds_into_others(self):
        items = [(chr(65 + i), 10 - i) for i in range(9)]  # 9 skills
        p = self._pie(items)
        # 6 top + "other" = 7 slices.
        assert len(p["slices"]) == 7
        assert p["slices"][-1]["label"] == "other"

    def test_single_item_is_full_circle(self):
        p = self._pie([("A", 4)])
        assert len(p["slices"]) == 1 and p["slices"][0]["kind"] == "circle"

    def test_legend_links_to_feed(self):
        slice_ = self._pie([("Playwright", 5)])["slices"][0]
        assert "tech=Playwright" in slice_["href"] and slice_["count"] == 5


class TestExclude:
    def test_excluded_term_is_not_a_gap(self):
        res = stats.analyse(MARKET, ["API"], exclude=["pytest"])
        assert "pytest" not in [t for t, _ in res["gaps"]]

    def test_excluded_term_removed_from_market_entirely(self):
        base = stats.analyse(MARKET, [])
        muted = stats.analyse(MARKET, [], exclude=["API"])
        assert "API" not in [t for t, _, _ in muted["stakes"]]
        assert muted["unique_terms"] == base["unique_terms"] - 1

    def test_none_exclude_is_noop(self):
        assert stats.analyse(MARKET, ["API"], exclude=None)["total"] == len(MARKET)
