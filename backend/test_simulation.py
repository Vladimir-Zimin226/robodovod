import math
import pytest

from models import UserInput
from simulation import (
    _corridor_count,
    _route_length,
    generate_simulation,
    PATTERNS,
)


def _robot(speed=0.8):
    return {"specs": {"max_speed_m_s": speed}}


def _inp(**overrides):
    base = dict(process_type="transport", cargo_type="pallets",
                pallets_per_day=800, area_m2=12_000,
                shifts_count=2, shift_hours=8)
    base.update(overrides)
    return UserInput(**base)


class TestCorridorCount:
    @pytest.mark.parametrize("area,expected", [
        (500, 2),
        (1_999, 2),
        (2_000, 3),
        (9_999, 3),
        (10_000, 4),
        (39_999, 4),
        (40_000, 5),
        (200_000, 5),
    ])
    def test_scales_with_area(self, area, expected):
        assert _corridor_count(area) == expected


class TestRouteLength:
    def test_math(self):
        # прямоугольный треугольник 3-4-5
        route = [[0, 0], [3, 0], [3, 4]]
        assert _route_length(route) == pytest.approx(7.0)

    def test_closed_loop(self):
        route = [[0, 0], [4, 0], [4, 3], [0, 3], [0, 0]]
        assert _route_length(route) == pytest.approx(14.0)


class TestDiversity:
    def test_routes_are_not_all_identical(self):
        sim = generate_simulation(_inp(), _robot(), qty=6)
        signatures = {
            tuple(tuple(p) for p in u.route) for u in sim.units
        }
        assert len(signatures) >= 3   # минимум 3 уникальных геометрии

    def test_patterns_are_shuffled(self):
        sim = generate_simulation(_inp(), _robot(), qty=4)
        patterns = {u.pattern for u in sim.units}
        assert patterns == set(PATTERNS)

    def test_patterns_are_from_known_set(self):
        sim = generate_simulation(_inp(), _robot(), qty=8)
        for u in sim.units:
            assert u.pattern in PATTERNS


class TestDocks:
    def test_docks_are_spread_along_y(self):
        sim = generate_simulation(_inp(), _robot(), qty=5)
        ys = [d[1] for d in sim.docks]
        assert len(set(ys)) == 5           # все разные
        assert ys == sorted(ys)            # монотонно

    def test_docks_inside_warehouse(self):
        sim = generate_simulation(_inp(area_m2=2000), _robot(), qty=10)
        for x, y in sim.docks:
            assert 0 <= x <= sim.width_m
            assert 0 <= y <= sim.height_m

    def test_single_robot_center(self):
        sim = generate_simulation(_inp(), _robot(), qty=1)
        y = sim.docks[0][1]
        assert 0.3 * sim.height_m < y < 0.7 * sim.height_m


class TestPhaseOffsets:
    def test_phase_bounded_by_cycle(self):
        sim = generate_simulation(_inp(), _robot(speed=2.0), qty=5)
        for u in sim.units:
            assert 0 <= u.phase_offset_s <= u.cycle_time_s

    def test_first_has_no_phase(self):
        sim = generate_simulation(_inp(), _robot(), qty=4)
        assert sim.units[0].phase_offset_s == 0.0

    def test_phases_monotonic(self):
        sim = generate_simulation(_inp(), _robot(), qty=5)
        phases = [u.phase_offset_s for u in sim.units]
        assert phases == sorted(phases)


class TestCycleTime:
    @pytest.mark.parametrize("speed", [0.5, 1.0, 2.0])
    def test_matches_length_over_speed(self, speed):
        sim = generate_simulation(_inp(), _robot(speed=speed), qty=3)
        for u in sim.units:
            assert u.cycle_time_s == pytest.approx(u.route_length_m / speed, rel=1e-3)


class TestRouteClosure:
    def test_start_equals_end(self):
        sim = generate_simulation(_inp(), _robot(), qty=6)
        for u in sim.units:
            assert u.route[0] == u.route[-1]

    def test_route_has_min_length(self):
        sim = generate_simulation(_inp(), _robot(), qty=6)
        for u in sim.units:
            assert u.route_length_m > 0


class TestAspect:
    @pytest.mark.parametrize("obj,aspect", [
        ("retail", 0.60),
        ("airport", 0.35),
        ("clinic", 0.75),
        ("other", 0.60),
    ])
    def test_aspect_per_object(self, obj, aspect):
        sim = generate_simulation(_inp(object_type=obj), _robot(), qty=2)
        assert sim.aspect == pytest.approx(aspect)
        assert sim.width_m / sim.height_m == pytest.approx(aspect, rel=1e-2)


class TestRobotsCount:
    def test_robots_count_matches_units(self):
        sim = generate_simulation(_inp(), _robot(), qty=7)
        assert sim.robots_count == len(sim.units) == 7
        assert sim.robots_count == len(sim.docks)