import pytest

from models import UserInput, Zone
from economics import (
    _energy_cost_per_robot, _battery_replacement, _cell_sizing,
    _boxes_per_pallet, DEFAULT_BOXES_PER_PALLET,
    _fleet_sizing, CELL_DESIGN_EFFICIENCY, TARGET_FLEET_UTILIZATION,
    LABOR_INFLATION, OPEX_INFLATION, EXCHANGE_OPERATIONS_PER_TRIP,
    FULLY_LOADED_MULT, RESIDUAL_SHARE, calc_recommendation, ASSUMPTIONS,
    _residual_share, _requested_headcount, _min_pult_per_shift,
    _horizon, DEFAULT_HORIZON_YEARS, MIN_HORIZON_YEARS, MAX_HORIZON_YEARS,
    manual_baseline, validate_mandatory,
    zone_to_input, calc_zone, calc_combined,
)
from auditor import _parse_money, _num, _fallback_extract
from fleet import as_dicts


# ═══════════════════════════════════════════════════════════════
# Вспомогательные утилиты
# ═══════════════════════════════════════════════════════════════
def _robot(picks=13, power=300, batt=300_000, cycles=3000, runtime=10):
    """Минимальный фиктивный робот для тестов чистых функций экономики."""
    return {
        "specs": {"picks_per_min_max": picks},
        "economics": {
            "avg_power_w": power, "battery_cost_rub": batt,
            "battery_cycles": cycles, "runtime_h": runtime,
        },
    }


def _robot_dict(robot_id: str) -> dict:
    """fleet.ROBOT_BY_ID хранит Pydantic-модели; economics ждёт dict."""
    for r in as_dicts():
        if r["id"] == robot_id:
            return r
    raise KeyError(robot_id)


# ═══════════════════════════════════════════════════════════════
# Энергия и батареи
# ═══════════════════════════════════════════════════════════════
class TestEnergyCost:
    def test_scales_with_operating_days(self):
        a = UserInput(process_type="transport", pallets_per_day=100,
                      operating_days=365, shifts_count=2, shift_hours=8)
        b = UserInput(process_type="transport", pallets_per_day=100,
                      operating_days=300, shifts_count=2, shift_hours=8)
        econ = {"avg_power_w": 300}
        ea = _energy_cost_per_robot(a, econ, 0.7)
        eb = _energy_cost_per_robot(b, econ, 0.7)
        assert eb == pytest.approx(ea * 300 / 365, rel=1e-6)


class TestBatteryReplacement:
    def test_fewer_days_delays_replacement(self):
        econ = {"battery_cost_rub": 300_000, "battery_cycles": 3000, "runtime_h": 10}
        full = UserInput(process_type="transport", pallets_per_day=10,
                         operating_days=365, shifts_count=1, shift_hours=8)
        part = UserInput(process_type="transport", pallets_per_day=10,
                         operating_days=300, shifts_count=1, shift_hours=8)
        y_full = _battery_replacement(full, econ, 0.7)
        y_part = _battery_replacement(part, econ, 0.7)
        assert y_part is None or y_full is None or y_part >= y_full

    def test_no_battery_no_replacement(self):
        econ = {"battery_cost_rub": 0, "battery_cycles": None, "runtime_h": None}
        inp = UserInput(process_type="transport", pallets_per_day=10,
                        shifts_count=2, shift_hours=8)
        assert _battery_replacement(inp, econ, 0.7) is None

    def test_replacement_beyond_horizon_is_none(self):
        econ = {"battery_cost_rub": 300_000, "battery_cycles": 3000, "runtime_h": 10}
        inp_short = UserInput(process_type="transport", pallets_per_day=10,
                              shifts_count=1, shift_hours=6, horizon_years=5)
        assert _battery_replacement(inp_short, econ, 0.3) is None


# ═══════════════════════════════════════════════════════════════
# Cell sizing
# ═══════════════════════════════════════════════════════════════
class TestCellSizing:
    def test_default_boxes_per_pallet(self):
        inp = UserInput(process_type="palletizing", pallets_per_day=800,
                        shifts_count=2, shift_hours=8)
        assert _boxes_per_pallet(inp) == DEFAULT_BOXES_PER_PALLET

    def test_more_boxes_per_pallet_needs_more_cells(self):
        robot = _robot(picks=13)
        inp20 = UserInput(process_type="palletizing", pallets_per_day=800,
                          shifts_count=2, shift_hours=8, boxes_per_pallet=20)
        inp40 = UserInput(process_type="palletizing", pallets_per_day=800,
                          shifts_count=2, shift_hours=8, boxes_per_pallet=40)
        q20, _ = _cell_sizing(inp20, robot, 0.7)
        q40, _ = _cell_sizing(inp40, robot, 0.7)
        assert q40 >= q20
        assert q40 <= 2 * q20 + 1

    def test_utilization_in_range(self):
        robot = _robot(picks=13)
        inp = UserInput(process_type="palletizing", pallets_per_day=800,
                        shifts_count=2, shift_hours=8)
        qty, util = _cell_sizing(inp, robot, 0.7)
        assert qty >= 1 and 0 < util <= 1

    def test_design_efficiency_reduces_capacity(self):
        robot = {"specs": {"picks_per_min_max": 13}}
        inp = UserInput(process_type="palletizing", pallets_per_day=2000,
                        shifts_count=2, shift_hours=8, boxes_per_pallet=20)
        qty, _ = _cell_sizing(inp, robot, 0.7)
        assert qty >= 7

    def test_efficiency_constant_is_reasonable(self):
        assert 0.5 <= CELL_DESIGN_EFFICIENCY <= 0.8


# ═══════════════════════════════════════════════════════════════
# Fleet sizing
# ═══════════════════════════════════════════════════════════════
class TestExchangeTimeDoubled:
    def test_doubled_exchange_increases_trip(self):
        robot = {
            "specs": {"max_speed_m_s": 1.0},
            "transport_profile": {"exchange_time_s": 90, "units_per_trip": 1},
        }
        inp = UserInput(process_type="transport", cargo_type="pallets",
                        pallets_per_day=800, area_m2=12000, avg_distance_m=180,
                        shifts_count=3, shift_hours=8)
        qty, _ = _fleet_sizing(inp, robot, 0.7)
        assert qty >= 10

    def test_higher_exchange_needs_more_robots(self):
        inp = UserInput(process_type="transport", cargo_type="pallets",
                        pallets_per_day=800, area_m2=12000, avg_distance_m=180,
                        shifts_count=3, shift_hours=8)
        robot_45 = {"specs": {"max_speed_m_s": 1.0},
                    "transport_profile": {"exchange_time_s": 45, "units_per_trip": 1}}
        robot_120 = {"specs": {"max_speed_m_s": 1.0},
                     "transport_profile": {"exchange_time_s": 120, "units_per_trip": 1}}
        qty_45, _ = _fleet_sizing(inp, robot_45, 0.7)
        qty_120, _ = _fleet_sizing(inp, robot_120, 0.7)
        assert qty_120 > qty_45


class TestTargetUtilization:
    def test_target_keeps_util_below_threshold(self):
        robot = {"specs": {"max_speed_m_s": 1.0},
                 "transport_profile": {"exchange_time_s": 45, "units_per_trip": 1}}
        inp = UserInput(process_type="transport", cargo_type="pallets",
                        pallets_per_day=800, area_m2=12000, avg_distance_m=180,
                        shifts_count=3, shift_hours=8)
        qty, util = _fleet_sizing(inp, robot, 0.7)
        assert util <= 1.0
        assert util <= 0.95

    def test_target_adds_robot_when_utilization_high(self):
        robot = {"specs": {"max_speed_m_s": 1.0},
                 "transport_profile": {"exchange_time_s": 45, "units_per_trip": 1}}
        inp = UserInput(process_type="transport", cargo_type="pallets",
                        pallets_per_day=222, area_m2=12000, avg_distance_m=180,
                        shifts_count=3, shift_hours=8)
        qty, util = _fleet_sizing(inp, robot, 0.7)
        assert qty >= 3
        assert util <= TARGET_FLEET_UTILIZATION + 0.05


# ═══════════════════════════════════════════════════════════════
# Парсинг чисел и денег
# ═══════════════════════════════════════════════════════════════
class TestNum:
    @pytest.mark.parametrize("raw,expected", [
        ("12 000", 12_000.0),
        ("12\u00A0000", 12_000.0),
        ("12,5", 12.5),
        ("12.5", 12.5),
        ("80,000", 80_000.0),
        ("1,234,567", 1_234_567.0),
    ])
    def test_cleans_separators(self, raw, expected):
        assert _num(raw) == pytest.approx(expected)


class TestParseMoney:
    @pytest.mark.parametrize("text", [
        "зарплата 80 000 рублей",
        "зарплата 80000",
        "зарплата 80,000",
        "зп 80000 в месяц",
    ])
    def test_monthly_80k_uses_fully_loaded_mult(self, text):
        expected = round(80_000 * 12 * FULLY_LOADED_MULT, -3)
        assert _parse_money(text) == pytest.approx(expected, rel=1e-3)

    def test_thousand_shorthand(self):
        expected = round(80_000 * 12 * FULLY_LOADED_MULT, -3)
        assert _parse_money("зарплата 80 тыс") == pytest.approx(expected, rel=1e-3)

    def test_million(self):
        assert _parse_money("зарплата 1.5 млн") == pytest.approx(1_500_000, rel=1e-3)

    def test_nothing(self):
        assert _parse_money("нет данных") is None

    def test_too_small_is_rejected(self):
        assert _parse_money("зарплата 5 руб") is None

    def test_consistent_with_default(self):
        from economics import DEFAULT_SALARY_MONTH, _fte_cost
        from models import UserInput as UI
        parsed = _parse_money("зарплата 80 тыс")
        default_user = UI(process_type="transport", pallets_per_day=100)
        default_cost = _fte_cost(default_user)
        assert parsed == pytest.approx(default_cost, rel=1e-3)


# ═══════════════════════════════════════════════════════════════
# Инфляция в потоках
# ═══════════════════════════════════════════════════════════════
class TestInflationInFlows:
    def test_inflation_constants_registered(self):
        assert ASSUMPTIONS["labor_inflation"] == LABOR_INFLATION
        assert ASSUMPTIONS["opex_inflation"] == OPEX_INFLATION
        assert ASSUMPTIONS["target_fleet_utilization"] == TARGET_FLEET_UTILIZATION
        assert ASSUMPTIONS["exchange_operations_per_trip"] == EXCHANGE_OPERATIONS_PER_TRIP
        assert ASSUMPTIONS["cell_design_efficiency"] == CELL_DESIGN_EFFICIENCY
        assert ASSUMPTIONS["fully_loaded_mult"] == FULLY_LOADED_MULT

    def test_npv_includes_labor_inflation(self):
        robot = {
            "id": "test", "category": "internal_mobile",
            "object_types": ["retail"],
            "name": "Test", "description": "",
            "specs": {"payload_kg": 1500, "max_speed_m_s": 0.8,
                      "min_aisle_width_m": 1.2, "autonomy_hours": 10,
                      "navigation_type": "QR"},
            "compatible_cargo": ["pallets"],
            "economics": {
                "robot_capex_rub": 3_000_000, "charger_cost_rub": 300_000,
                "chargers_per_robot": 0.34, "integration_per_robot_rub": 600_000,
                "site_fixed_warehouse_rub": 1_800_000,
                "site_fixed_zone_rub": 400_000,
                "annual_service_rub": 200_000,
                "annual_software_rub": 80_000, "avg_power_w": 300,
                "battery_cost_rub": 300_000, "battery_cycles": 3000,
                "runtime_h": 10, "fte_replace_per_shift": 1.0,
            },
            "price": {"basis": "sourced_estimate", "confidence": 0.4, "note": ""},
        }
        inp = UserInput(object_type="retail", process_type="transport",
                        cargo_type="pallets", pallets_per_day=800,
                        area_m2=12000, avg_distance_m=180, shifts_count=3,
                        shift_hours=8, staff_headcount=12,
                        fte_cost_rub=1_400_000, aisle_width_m=2.4, payload_kg=700)
        rec = calc_recommendation(inp, robot)
        base = rec.scenarios[1]
        undiscounted = (base.savings_annual * 4 - base.opex_annual * 4) - base.capex
        assert base.npv >= undiscounted * 0.5


# ═══════════════════════════════════════════════════════════════
# Горизонт расчёта
# ═══════════════════════════════════════════════════════════════
class TestHorizon:
    def _inp(self, horizon=None):
        return UserInput(object_type="retail", process_type="transport",
                         cargo_type="pallets", pallets_per_day=800,
                         area_m2=12000, avg_distance_m=180, shifts_count=3,
                         shift_hours=8, staff_headcount=12,
                         fte_cost_rub=1_674_000, aisle_width_m=2.4, payload_kg=700,
                         horizon_years=horizon)

    def test_default_horizon_is_5(self):
        rec = calc_recommendation(self._inp(None), _robot_dict("amr_heavy_1350"))
        assert rec.horizon_years == 5
        assert rec.scenarios[1].horizon_years == 5

    def test_custom_horizon_in_result(self):
        for h in (5, 7, 10):
            rec = calc_recommendation(self._inp(h), _robot_dict("amr_heavy_1350"))
            assert rec.horizon_years == h
            for s in rec.scenarios:
                assert s.horizon_years == h

    def test_longer_horizon_increases_npv(self):
        rec5 = calc_recommendation(self._inp(5), _robot_dict("amr_heavy_1350"))
        rec10 = calc_recommendation(self._inp(10), _robot_dict("amr_heavy_1350"))
        assert rec10.npv > rec5.npv

    def test_longer_horizon_increases_tco(self):
        rec5 = calc_recommendation(self._inp(5), _robot_dict("amr_heavy_1350"))
        rec10 = calc_recommendation(self._inp(10), _robot_dict("amr_heavy_1350"))
        assert rec10.tco > rec5.tco

    def test_horizon_does_not_change_capex(self):
        rec5 = calc_recommendation(self._inp(5), _robot_dict("amr_heavy_1350"))
        rec10 = calc_recommendation(self._inp(10), _robot_dict("amr_heavy_1350"))
        assert rec5.capex == rec10.capex

    def test_horizon_battery_within_bounds(self):
        rec10 = calc_recommendation(self._inp(10), _robot_dict("amr_heavy_1350"))
        for s in rec10.scenarios:
            if s.battery_replacement_year is not None:
                assert s.battery_replacement_year <= 10

    def test_manual_baseline_horizon(self):
        mb5 = manual_baseline(self._inp(5))
        mb10 = manual_baseline(self._inp(10))
        assert mb5.horizon_years == 5
        assert mb10.horizon_years == 10
        assert mb10.total_horizon == pytest.approx(mb5.total_horizon * 2, rel=1e-2)

    def test_horizon_out_of_range_rejected(self):
        with pytest.raises(Exception):
            UserInput(process_type="transport", pallets_per_day=100,
                      horizon_years=4)
        with pytest.raises(Exception):
            UserInput(process_type="transport", pallets_per_day=100,
                      horizon_years=11)

    def test_resolver_helper(self):
        inp = UserInput(process_type="transport", pallets_per_day=100)
        assert _horizon(inp) == DEFAULT_HORIZON_YEARS
        inp7 = UserInput(process_type="transport", pallets_per_day=100,
                         horizon_years=7)
        assert _horizon(inp7) == 7

    def test_horizon_constants_in_assumptions(self):
        assert ASSUMPTIONS["horizon_years_default"] == DEFAULT_HORIZON_YEARS
        assert ASSUMPTIONS["horizon_years_min"] == MIN_HORIZON_YEARS
        assert ASSUMPTIONS["horizon_years_max"] == MAX_HORIZON_YEARS

    def test_warning_mentions_horizon(self):
        rec = calc_recommendation(self._inp(7), _robot_dict("amr_heavy_1350"))
        joined = " ".join(rec.warnings)
        assert "Горизонт расчёта: 7 лет" in joined


# ═══════════════════════════════════════════════════════════════
# StaffBreakdown
# ═══════════════════════════════════════════════════════════════
class TestStaffBreakdown:
    def _inp(self, staff=12, n=None):
        return UserInput(object_type="retail", process_type="transport",
                         cargo_type="pallets", pallets_per_day=800,
                         area_m2=12000, avg_distance_m=180, shifts_count=3,
                         shift_hours=8, staff_headcount=staff,
                         fte_cost_rub=1_674_000, aisle_width_m=2.4, payload_kg=700,
                         released_headcount=n)

    def test_slider_enabled_when_staff_given(self):
        rec = calc_recommendation(self._inp(), _robot_dict("amr_heavy_1350"))
        assert rec.staff_breakdown.slider_enabled
        assert rec.staff_breakdown.slider_max == 12
        assert rec.staff_breakdown.staff_total == 12

    def test_slider_disabled_when_staff_missing(self):
        inp = UserInput(object_type="retail", process_type="transport",
                        cargo_type="pallets", pallets_per_day=800,
                        area_m2=12000, avg_distance_m=180, shifts_count=3,
                        shift_hours=8, fte_cost_rub=1_674_000,
                        aisle_width_m=2.4, payload_kg=700)
        rec = calc_recommendation(inp, _robot_dict("amr_heavy_1350"))
        assert not rec.staff_breakdown.slider_enabled
        assert rec.staff_breakdown.slider_max == 0

    def test_full_release_by_default(self):
        rec = calc_recommendation(self._inp(n=None), _robot_dict("amr_heavy_1350"))
        sb = rec.staff_breakdown
        assert sb.staff_requested is None
        assert sb.staff_applied == sb.staff_replaceable
        assert not sb.is_clamped

    def test_partial_request_applied(self):
        rec = calc_recommendation(self._inp(n=6), _robot_dict("amr_heavy_1350"))
        sb = rec.staff_breakdown
        assert sb.staff_requested == 6
        assert sb.staff_applied == 6.0
        assert not sb.is_clamped

    def test_request_above_replaceable_is_clamped(self):
        rec = calc_recommendation(self._inp(n=50), _robot_dict("amr_heavy_1350"))
        sb = rec.staff_breakdown
        assert sb.staff_requested == 50
        assert sb.staff_applied == sb.staff_replaceable
        assert sb.is_clamped

    def test_zero_request_no_labor_savings(self):
        rec = calc_recommendation(self._inp(n=0), _robot_dict("amr_heavy_1350"))
        sb = rec.staff_breakdown
        assert sb.staff_applied == 0.0
        assert sb.staff_released == 0.0

    def test_below_pult_flag(self):
        rec = calc_recommendation(self._inp(n=2), _robot_dict("amr_heavy_1350"))
        sb = rec.staff_breakdown
        assert sb.is_below_pult
        assert sb.staff_released == 0.0

    def test_monotonic_increase(self):
        sav = lambda n: calc_recommendation(
            self._inp(n=n), _robot_dict("amr_heavy_1350")
        ).scenarios[1].savings_annual
        assert sav(0) < sav(4) < sav(6) < sav(9) < sav(12)

    def test_warning_mentions_partial(self):
        rec = calc_recommendation(self._inp(n=6), _robot_dict("amr_heavy_1350"))
        joined = " ".join(rec.warnings)
        assert "Замена персонала: 6 из 12 человек" in joined
        assert "Реально высвобождается 3 FTE" in joined

    def test_warning_mentions_clamp(self):
        rec = calc_recommendation(self._inp(n=50), _robot_dict("amr_heavy_1350"))
        joined = " ".join(rec.warnings)
        assert "может заменить только" in joined
        assert "Применено к расчёту" in joined

    def test_warning_mentions_below_pult(self):
        rec = calc_recommendation(self._inp(n=2), _robot_dict("amr_heavy_1350"))
        joined = " ".join(rec.warnings)
        assert "не покрывает пульт" in joined
        assert "Экономии на ФОТ нет" in joined
        assert "потребуется дополнительный перевод из незаменённых" in joined

    def test_negative_rejected(self):
        with pytest.raises(Exception):
            UserInput(process_type="transport", pallets_per_day=100,
                      released_headcount=-1)

    def test_pult_shortage_when_insufficient_release(self):
        rec = calc_recommendation(self._inp(n=2), _robot_dict("amr_heavy_1350"))
        sb = rec.staff_breakdown
        assert sb.pult_shortage == pytest.approx(1.0)
        assert sb.pult_source == "from_staff"

    def test_no_shortage_when_enough_released(self):
        rec = calc_recommendation(self._inp(n=6), _robot_dict("amr_heavy_1350"))
        sb = rec.staff_breakdown
        assert sb.pult_shortage == 0.0
        assert sb.pult_source == "from_released"

    def test_no_shortage_when_released_equals_pult(self):
        rec = calc_recommendation(self._inp(n=3), _robot_dict("amr_heavy_1350"))
        sb = rec.staff_breakdown
        assert sb.pult_shortage == 0.0
        assert sb.pult_source == "from_released"
        assert sb.staff_released == 0.0

    def test_pult_shortage_only_when_below_pult(self):
        rec = calc_recommendation(self._inp(n=4), _robot_dict("amr_heavy_1350"))
        sb = rec.staff_breakdown
        assert sb.pult_shortage == 0.0
        assert sb.pult_source == "from_released"
        assert sb.staff_released == pytest.approx(1.0, abs=0.1)


# ═══════════════════════════════════════════════════════════════
# Минимум на пульте
# ═══════════════════════════════════════════════════════════════
class TestMinPultPerShift:
    def _inp(self, n=None, min_per_shift=None, shifts=3, staff=12):
        return UserInput(object_type="retail", process_type="transport",
                         cargo_type="pallets", pallets_per_day=800,
                         area_m2=12000, avg_distance_m=180, shifts_count=shifts,
                         shift_hours=8, staff_headcount=staff,
                         fte_cost_rub=1_674_000, aisle_width_m=2.4, payload_kg=700,
                         released_headcount=n,
                         min_pult_fte_per_shift=min_per_shift)

    def test_default_min_is_one_per_shift(self):
        rec = calc_recommendation(self._inp(), _robot_dict("amr_heavy_1350"))
        sb = rec.staff_breakdown
        assert sb.min_pult_per_shift == 1.0
        assert sb.pult_minimum == 3

    def test_min_reason_when_percent_lower(self):
        rec = calc_recommendation(
            self._inp(n=6, min_per_shift=1.0, shifts=3),
            _robot_dict("amr_heavy_1350"))
        sb = rec.staff_breakdown
        assert sb.pult_reason == "min_per_shift"
        assert sb.staff_on_pult == 3.0

    def test_pct_reason_when_percent_higher(self):
        rec = calc_recommendation(
            self._inp(n=12, min_per_shift=0.0, shifts=3),
            _robot_dict("amr_heavy_1350"))
        sb = rec.staff_breakdown
        assert sb.pult_reason == "supervision_pct"
        assert sb.staff_on_pult == pytest.approx(2.4, abs=0.1)

    def test_min_zero_disables_floor(self):
        rec_1 = calc_recommendation(
            self._inp(n=6, min_per_shift=1.0, shifts=3),
            _robot_dict("amr_heavy_1350"))
        rec_0 = calc_recommendation(
            self._inp(n=6, min_per_shift=0.0, shifts=3),
            _robot_dict("amr_heavy_1350"))
        assert rec_0.staff_breakdown.staff_on_pult < rec_1.staff_breakdown.staff_on_pult
        assert rec_0.staff_breakdown.staff_released > rec_1.staff_breakdown.staff_released

    def test_min_doubled_increases_retained(self):
        rec_1 = calc_recommendation(
            self._inp(n=12, min_per_shift=1.0, shifts=3),
            _robot_dict("amr_heavy_1350"))
        rec_2 = calc_recommendation(
            self._inp(n=12, min_per_shift=2.0, shifts=3),
            _robot_dict("amr_heavy_1350"))
        assert rec_2.staff_breakdown.staff_on_pult == 6.0
        assert rec_1.staff_breakdown.staff_on_pult == 3.0

    def test_warning_mentions_min_when_fires(self):
        rec = calc_recommendation(
            self._inp(n=6, min_per_shift=1.0, shifts=3),
            _robot_dict("amr_heavy_1350"))
        joined = " ".join(rec.warnings)
        assert "сработал жёсткий минимум" in joined
        assert "min_pult_fte_per_shift=0" in joined

    def test_warning_mentions_pct_when_fires(self):
        rec = calc_recommendation(
            self._inp(n=12, min_per_shift=0.0, shifts=3),
            _robot_dict("amr_heavy_1350"))
        joined = " ".join(rec.warnings)
        assert "процент supervision" in joined
        assert "20%" in joined

    def test_out_of_range_rejected(self):
        with pytest.raises(Exception):
            UserInput(process_type="transport", pallets_per_day=100,
                      min_pult_fte_per_shift=-0.1)
        with pytest.raises(Exception):
            UserInput(process_type="transport", pallets_per_day=100,
                      min_pult_fte_per_shift=6.0)

    def test_resolver_helper(self):
        inp = UserInput(process_type="transport", pallets_per_day=100)
        assert _min_pult_per_shift(inp) == 1.0
        inp2 = UserInput(process_type="transport", pallets_per_day=100,
                         min_pult_fte_per_shift=0.0)
        assert _min_pult_per_shift(inp2) == 0.0


# ═══════════════════════════════════════════════════════════════
# fte_released vs fte_displaced
# ═══════════════════════════════════════════════════════════════
class TestFteReleased:
    def _inp(self, n=None):
        return UserInput(object_type="retail", process_type="transport",
                         cargo_type="pallets", pallets_per_day=800,
                         area_m2=12000, avg_distance_m=180, shifts_count=3,
                         shift_hours=8, staff_headcount=12,
                         fte_cost_rub=1_674_000, aisle_width_m=2.4, payload_kg=700,
                         released_headcount=n)

    def test_fte_released_matches_staff_breakdown(self):
        rec = calc_recommendation(self._inp(n=6), _robot_dict("amr_heavy_1350"))
        assert rec.fte_released == rec.staff_breakdown.staff_released

    def test_fte_displaced_is_potential(self):
        rec = calc_recommendation(self._inp(n=6), _robot_dict("amr_heavy_1350"))
        assert rec.fte_displaced >= rec.fte_released

    def test_full_release_displaced_gt_released(self):
        rec = calc_recommendation(self._inp(n=None), _robot_dict("amr_heavy_1350"))
        assert rec.fte_displaced > rec.fte_released

    def test_zero_release_gives_zero(self):
        rec = calc_recommendation(self._inp(n=0), _robot_dict("amr_heavy_1350"))
        assert rec.fte_released == 0.0

    def test_monotonic_increasing(self):
        rel = lambda n: calc_recommendation(
            self._inp(n=n), _robot_dict("amr_heavy_1350")
        ).fte_released
        assert rel(0) < rel(4) <= rel(6) <= rel(12)


# ═══════════════════════════════════════════════════════════════
# residual_share
# ═══════════════════════════════════════════════════════════════
class TestResidualShare:
    def test_resolver_default(self):
        assert _residual_share({}) == RESIDUAL_SHARE
        assert _residual_share({"residual_share": None}) == RESIDUAL_SHARE

    def test_resolver_override(self):
        assert _residual_share({"residual_share": 0.25}) == 0.25
        assert _residual_share({"residual_share": 0.50}) == 0.50

    def test_all_robots_have_residual_share_in_json(self):
        for r in as_dicts():
            rs = r["economics"].get("residual_share")
            assert rs is not None, f"{r['id']}: residual_share отсутствует"
            assert 0.0 <= rs <= 1.0, f"{r['id']}: residual_share вне [0,1]"

    def test_residual_share_by_robot(self):
        expected = {
            "agv_pallet_qr": 0.30,
            "amr_light_250": 0.35,
            "amr_heavy_1350": 0.35,
            "agv_tug_k05": 0.30,
            "courier_flashbot": 0.45,
            "bella_bot": 0.45,
            "cleaner_cc1_pro": 0.35,
            "sweeper_mt1": 0.35,
            "palletizer_cell_21": 0.50,
            "drone_inventory": 0.20,
            "drone_inventory_pro": 0.25,
            "drone_inspection": 0.20,
            "drone_yard": 0.15,
        }
        for r in as_dicts():
            rs = r["economics"].get("residual_share")
            assert rs is not None, f"{r['id']}: residual_share отсутствует"
            if r["id"] in expected:
                assert rs == pytest.approx(expected[r["id"]]), (
                    f"{r['id']}: ожидалось {expected[r['id']]}, получено {rs}"
                )

    def test_residual_share_within_bounds(self):
        for r in as_dicts():
            rs = r["economics"].get("residual_share")
            assert 0.10 <= rs <= 0.60, f"{r['id']}: {rs} вне [0.10, 0.60]"

    def test_warning_uses_residual_share(self):
        inp = UserInput(object_type="retail", process_type="transport",
                        cargo_type="pallets", pallets_per_day=800,
                        area_m2=12000, avg_distance_m=180, shifts_count=3,
                        shift_hours=8, staff_headcount=12,
                        fte_cost_rub=1_674_000, aisle_width_m=2.4, payload_kg=700)
        rec = calc_recommendation(inp, _robot_dict("amr_heavy_1350"))
        joined = " ".join(rec.warnings)
        assert "Остаточная стоимость" in joined
        assert "35% CAPEX" in joined

    def test_residual_affects_npv(self):
        import copy
        inp = UserInput(object_type="retail", process_type="transport",
                        cargo_type="pallets", pallets_per_day=800,
                        area_m2=12000, avg_distance_m=180, shifts_count=3,
                        shift_hours=8, staff_headcount=12,
                        fte_cost_rub=1_674_000, aisle_width_m=2.4, payload_kg=700)
        robot_low = copy.deepcopy(_robot_dict("amr_heavy_1350"))
        robot_low["economics"]["residual_share"] = 0.10
        robot_high = copy.deepcopy(_robot_dict("amr_heavy_1350"))
        robot_high["economics"]["residual_share"] = 0.80
        rec_low = calc_recommendation(inp, robot_low)
        rec_high = calc_recommendation(inp, robot_high)
        assert rec_high.npv > rec_low.npv


# ═══════════════════════════════════════════════════════════════
# site_fixed: разбивка warehouse/zone
# ═══════════════════════════════════════════════════════════════
class TestSiteFixedSplit:
    def test_all_robots_have_split_site_fixed(self):
        """Каждый робот имеет warehouse и zone части site_fixed."""
        for r in as_dicts():
            e = r["economics"]
            wh = e.get("site_fixed_warehouse_rub")
            zn = e.get("site_fixed_zone_rub")
            assert wh is not None, f"{r['id']}: нет site_fixed_warehouse_rub"
            assert zn is not None, f"{r['id']}: нет site_fixed_zone_rub"
            assert wh >= 0 and zn >= 0

    def test_warehouse_greater_than_zone(self):
        """Warehouse часть должна быть больше zone (80/20)."""
        for r in as_dicts():
            e = r["economics"]
            wh = e.get("site_fixed_warehouse_rub", 0)
            zn = e.get("site_fixed_zone_rub", 0)
            if wh + zn > 0:
                assert wh > zn, f"{r['id']}: warehouse {wh} <= zone {zn}"


# ═══════════════════════════════════════════════════════════════
# purpose — назначения
# ═══════════════════════════════════════════════════════════════
class TestRobotPurpose:
    def test_all_robots_have_purpose(self):
        for r in as_dicts():
            p = r.get("purpose")
            assert p is not None, f"{r['id']}: purpose отсутствует"
            assert isinstance(p, list), f"{r['id']}: purpose не массив"
            assert len(p) >= 2, f"{r['id']}: purpose содержит < 2 назначений"

    def test_purpose_has_no_duplicates_within_robot(self):
        for r in as_dicts():
            p = r["purpose"]
            assert len(p) == len(set(p)), f"{r['id']}: дубликаты в purpose"

    def test_purpose_entries_are_short_strings(self):
        for r in as_dicts():
            for item in r["purpose"]:
                assert isinstance(item, str), f"{r['id']}: назначение не строка"
                assert 3 <= len(item) <= 50, f"{r['id']}: '{item}' длина не подходит"

    def test_purpose_expected_by_robot(self):
        expected = {
            "agv_pallet_qr": "Транспортировка паллет",
            "amr_light_250": "Коробки и мелкие поддоны",
            "amr_heavy_1350": "Тяжёлые паллеты до 1.35 т",
            "agv_tug_k05": "Поезда тележек",
            "courier_flashbot": "Межэтажная доставка",
            "bella_bot": "Доставка внутри этажа",
            "cleaner_cc1_pro": "Влажная уборка",
            "sweeper_mt1": "Промышленные площади",
            "palletizer_cell_21": "Укладка коробов",
            "drone_inventory": "Инвентаризация склада",
            "drone_inventory_pro": "RFID-сканирование",
            "drone_inspection": "Инспекция стеллажей",
            "drone_yard": "Аэропорт и порт",
        }
        by_id = {r["id"]: r for r in as_dicts()}
        for rid, first_purpose in expected.items():
            assert rid in by_id
            assert first_purpose in by_id[rid]["purpose"], (
                f"{rid}: ожидалось '{first_purpose}'"
            )


# ═══════════════════════════════════════════════════════════════
# Zonal-режим
# ═══════════════════════════════════════════════════════════════
class TestZonal:
    def _shared(self):
        return UserInput(
            object_type="retail", mode="zonal",
            fte_cost_rub=1_674_000, operating_days=365,
            horizon_years=5, discount_rate=0.15,
        )

    def _zone_a(self):
        return Zone(
            id="A", name="Приёмка",
            process_type="transport", cargo_type="pallets",
            area_m2=150, shifts_count=1, shift_hours=8,
            volume_per_day=40, staff_headcount=2,
            aisle_width_m=2.4, avg_distance_m=60, payload_kg=700,
        )

    def _zone_b(self):
        return Zone(
            id="B", name="Отгрузка",
            process_type="transport", cargo_type="pallets",
            area_m2=200, shifts_count=2, shift_hours=8,
            volume_per_day=60, staff_headcount=3,
            aisle_width_m=2.4, avg_distance_m=80, payload_kg=700,
        )

    def test_zone_to_input_maps_fields(self):
        shared = self._shared()
        z = self._zone_a()
        zi = zone_to_input(shared, z)
        assert zi.process_type == "transport"
        assert zi.pallets_per_day == 40
        assert zi.staff_headcount == 2
        assert zi.shifts_count == 1
        assert zi.fte_cost_rub == shared.fte_cost_rub
        assert zi.horizon_years == shared.horizon_years
        assert zi.mode == "whole"

    def test_zone_to_input_uses_zone_cargo(self):
        shared = self._shared()
        z = Zone(
            id="C", name="Уборка", process_type="cleaning", cargo_type="pallets",
            area_m2=500, shifts_count=1, shift_hours=6,
            cleaning_frequency_per_day=1, staff_headcount=1,
        )
        zi = zone_to_input(shared, z)
        assert zi.process_type == "cleaning"
        assert zi.area_m2 == 500
        assert zi.cleaning_frequency_per_day == 1

    def test_calc_zone_returns_zone_result(self):
        shared = self._shared()
        result = calc_zone(shared, self._zone_a(), as_dicts())
        assert result.zone_id == "A"
        assert result.zone_name == "Приёмка"
        assert result.process_type == "transport"
        assert result.shifts_count == 1
        assert result.volume_per_day == 40
        assert result.best_robot_id is not None
        assert result.zone_capex > 0
        assert result.zone_payback_years > 0
        assert result.staff_breakdown is not None

    def test_calc_zone_with_small_volume(self):
        """Маленькая зона 40 паллет/сутки, 1 смена — парк не более 3 роботов."""
        shared = self._shared()
        result = calc_zone(shared, self._zone_a(), as_dicts())
        assert 1 <= result.zone_robots <= 3

    def test_calc_zone_larger_volume_more_robots(self):
        """Зона B с 60 паллетами должна дать не меньше роботов, чем A."""
        shared = self._shared()
        zr_a = calc_zone(shared, self._zone_a(), as_dicts())
        zr_b = calc_zone(shared, self._zone_b(), as_dicts())
        assert zr_b.zone_robots >= zr_a.zone_robots

    def test_combined_summary_aggregates(self):
        shared = self._shared()
        robots = as_dicts()
        zr_a = calc_zone(shared, self._zone_a(), robots)
        zr_b = calc_zone(shared, self._zone_b(), robots)
        combined = calc_combined([zr_a, zr_b], shared, robots)

        assert combined.zones_count == 2
        assert combined.total_robots == zr_a.zone_robots + zr_b.zone_robots
        assert combined.total_capex >= zr_a.zone_capex + zr_b.zone_capex
        assert combined.total_savings_annual == pytest.approx(
            zr_a.zone_savings_annual + zr_b.zone_savings_annual, rel=1e-3)
        assert combined.total_released == pytest.approx(
            zr_a.zone_released + zr_b.zone_released, rel=1e-3)
        assert combined.warehouse_fixed_rub > 0

    def test_warehouse_fixed_counted_once(self):
        """Warehouse fixed не удваивается при добавлении зоны."""
        shared = self._shared()
        robots = as_dicts()
        zr_a = calc_zone(shared, self._zone_a(), robots)
        zr_b = calc_zone(shared, self._zone_b(), robots)

        combined_two = calc_combined([zr_a, zr_b], shared, robots)
        combined_one = calc_combined([zr_a], shared, robots)

        assert combined_two.warehouse_fixed_rub == combined_one.warehouse_fixed_rub

    def test_combined_payback_computed(self):
        shared = self._shared()
        robots = as_dicts()
        zr_a = calc_zone(shared, self._zone_a(), robots)
        zr_b = calc_zone(shared, self._zone_b(), robots)
        combined = calc_combined([zr_a, zr_b], shared, robots)
        assert combined.combined_payback_years > 0
        assert combined.combined_payback_years <= 99

    def test_best_zone_selected(self):
        shared = self._shared()
        robots = as_dicts()
        zr_a = calc_zone(shared, self._zone_a(), robots)
        zr_b = calc_zone(shared, self._zone_b(), robots)
        combined = calc_combined([zr_a, zr_b], shared, robots)
        if combined.best_zone_id is not None:
            assert combined.best_zone_id in ("A", "B")
            assert combined.best_zone_payback is not None

    def test_validate_zonal_requires_zones(self):
        inp = UserInput(object_type="retail", mode="zonal", zones=[])
        err = validate_mandatory(inp)
        assert err is not None
        assert "зону" in err.lower() or "зона" in err.lower()

    def test_validate_zonal_checks_each_zone(self):
        inp = UserInput(
            object_type="retail", mode="zonal",
            zones=[Zone(id="A", name="Пустая",
                        process_type="transport", cargo_type="pallets",
                        shifts_count=2, shift_hours=8)],
        )
        err = validate_mandatory(inp)
        assert err is not None
        assert "A" in err or "Пустая" in err

    def test_validate_whole_still_works(self):
        inp = UserInput(object_type="retail", mode="whole",
                        process_type="transport", cargo_type="pallets",
                        pallets_per_day=800, shifts_count=3, shift_hours=8)
        err = validate_mandatory(inp)
        assert err is None

    def test_zonal_small_zones_still_get_result(self):
        """Одна маленькая зона — recommendations не пустой."""
        shared = self._shared()
        result = calc_zone(shared, self._zone_a(), as_dicts())
        assert len(result.recommendations) >= 1
        best = result.recommendations[0]
        assert best.quantity >= 1
        assert best.capex > 0


# ═══════════════════════════════════════════════════════════════
# Fallback-экстрактор
# ═══════════════════════════════════════════════════════════════
class TestFallbackOtherFields:
    def test_area(self):
        assert _fallback_extract("площадь 12 000 м2").get("area_m2") == 12_000

    def test_pallets(self):
        assert _fallback_extract("800 паллет в сутки").get("pallets_per_day") == 800

    def test_boxes_per_pallet(self):
        out = _fallback_extract("на паллету укладывается 24 короба")
        assert out.get("boxes_per_pallet") == 24

    def test_money(self):
        out = _fallback_extract("зарплата 80 000 руб в месяц")
        expected = 80_000 * 12 * FULLY_LOADED_MULT
        assert out.get("fte_cost_rub") == pytest.approx(expected, rel=1e-3)


class TestReleaseExtraction:
    def test_replace_pattern(self):
        assert _fallback_extract("заменим 8 человек").get("released_headcount") == 8

    def test_reduce_pattern(self):
        assert _fallback_extract("сократим 5 операторов").get("released_headcount") == 5

    def test_release_pattern(self):
        assert _fallback_extract("высвободим 6 сотрудников").get("released_headcount") == 6

    def test_no_layoffs_pattern(self):
        assert _fallback_extract("никого не увольняем").get("released_headcount") == 0

    def test_no_layoffs_variant(self):
        assert _fallback_extract("без сокращений").get("released_headcount") == 0

    def test_no_signal_no_field(self):
        out = _fallback_extract("800 паллет в сутки")
        assert "released_headcount" not in out