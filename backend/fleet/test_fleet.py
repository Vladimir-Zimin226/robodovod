import pytest

from fleet import (
    ROBOTS, ROBOT_BY_ID, BY_CATEGORY,
    CATEGORY_ORDER, CATEGORY_LABELS,
    as_dicts, by_category_dicts,
)


class TestLoading:
    def test_robots_not_empty(self):
        assert len(ROBOTS) >= 10

    def test_ids_unique(self):
        ids = [r.id for r in ROBOTS]
        assert len(ids) == len(set(ids))

    def test_index_matches(self):
        for r in ROBOTS:
            assert ROBOT_BY_ID[r.id] is r

    def test_all_categories_known(self):
        for r in ROBOTS:
            assert r.category in CATEGORY_LABELS


class TestCategories:
    def test_all_declared_categories_present(self):
        for cat in CATEGORY_ORDER:
            assert BY_CATEGORY[cat], f"Категория {cat} пуста"

    def test_category_order_matches_labels(self):
        assert set(CATEGORY_ORDER) == set(CATEGORY_LABELS.keys())

    def test_total_matches_sum(self):
        total = sum(len(v) for v in BY_CATEGORY.values())
        assert total == len(ROBOTS)


class TestNames:
    @pytest.mark.parametrize("forbidden", ["аналог", "Аналог", "бюджетный", "Бюджетный"])
    def test_no_forbidden_words_in_names(self, forbidden):
        for r in ROBOTS:
            assert forbidden not in r.name, f"'{forbidden}' осталось в имени {r.id}: {r.name}"

    def test_names_not_empty(self):
        for r in ROBOTS:
            assert r.name.strip()


class TestSerialization:
    def test_as_dicts(self):
        d = as_dicts()
        assert len(d) == len(ROBOTS)
        assert all(isinstance(x, dict) for x in d)
        assert all("id" in x for x in d)

    def test_by_category_dicts(self):
        d = by_category_dicts()
        for cat in CATEGORY_ORDER:
            assert cat in d
            assert d[cat]["label"] == CATEGORY_LABELS[cat]
            assert len(d[cat]["robots"]) == len(BY_CATEGORY[cat])


class TestSpecificRobots:
    def test_tug_is_only_carts_carrier(self):
        carts_robots = [r.id for r in ROBOTS if "carts" in r.compatible_cargo]
        assert carts_robots == ["agv_tug_k05"]

    def test_palletizer_is_only_fixed_cell(self):
        cells = [r.id for r in ROBOTS if r.category == "fixed_cell"]
        assert cells == ["palletizer_cell_21"]