import pytest

from auditor import _fallback_extract


class TestShifts:
    @pytest.mark.parametrize("text,expected", [
        ("3 смены в сутки", 3),
        ("работаем в 2 смены", 2),
        ("1 смена", 1),
    ])
    def test_valid_shifts(self, text, expected):
        assert _fallback_extract(text).get("shifts_count") == expected

    def test_12_smens_not_misparsed_as_2(self):
        # Регресс: раньше "12 смен" ловилось как 2 из-за узкого (\d)
        out = _fallback_extract("12 смен в сутки")
        assert out.get("shifts_count") != 2


class TestCleaningFrequency:
    @pytest.mark.parametrize("text,expected", [
        ("уборка 2 раза в день", 2),
        ("моют 1 раз в день", 1),
    ])
    def test_valid_frequency(self, text, expected):
        assert _fallback_extract(text).get("cleaning_frequency_per_day") == expected

    def test_12_raza_not_misparsed_as_2(self):
        out = _fallback_extract("уборка 12 раз в день")
        assert out.get("cleaning_frequency_per_day") != 2


class TestOtherFields:
    def test_area(self):
        assert _fallback_extract("площадь 12 000 м2").get("area_m2") == 12_000

    def test_pallets(self):
        assert _fallback_extract("800 паллет в сутки").get("pallets_per_day") == 800

    def test_money(self):
        # К1: множитель синхронизирован с economics.FULLY_LOADED_MULT = 1.55
        from economics import FULLY_LOADED_MULT
        out = _fallback_extract("зарплата 80 000 руб в месяц")
        expected = 80_000 * 12 * FULLY_LOADED_MULT
        assert out.get("fte_cost_rub") == pytest.approx(expected, rel=1e-3)

    def test_boxes_per_pallet(self):
        out = _fallback_extract("на паллету укладывается 24 короба")
        assert out.get("boxes_per_pallet") == 24


class TestHvAskedMovedToMeta:
    def test_meta_returns_flag(self):
        from auditor import conduct_interview
        r = conduct_interview(
            message="800 паллет в сутки, 3 смены по 8 часов",
            history=[],
            collected={},
            meta={},
        )
        assert "_hv_asked" not in r["collected"], "флаг не должен попадать в collected"
        # Если LLM отключён (нет ключей) - fallback тоже сработает,
        # и первый проход должен либо запросить HV, либо сразу быть готовым.
        assert "meta" in r