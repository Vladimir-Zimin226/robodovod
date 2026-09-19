from __future__ import annotations

from pathlib import Path

import pytest

from catalog_dual_run import (
    DualRunConfigurationError,
    DualRunFixture,
    main as dual_run_main,
    run_dual_run,
)
from catalog_repository import CatalogRepository
from test_robot_fixtures import synthetic_snapshot


class StaticRepository:
    def load(self):
        return synthetic_snapshot()


def _fixture(*scenario_inputs):
    return DualRunFixture.model_validate(
        {
            "schema_version": "catalog-dual-run-fixture-v1",
            "model_pairs": [
                {
                    "reference_id": "synthetic-transport-heavy",
                    "candidate_id": "synthetic-transport-heavy",
                }
            ],
            "scenarios": [
                {"id": f"scenario-{index}", "input": value}
                for index, value in enumerate(scenario_inputs, start=1)
            ],
        }
    )


def test_snapshot_runtime_values_are_isolated_copies():
    snapshot = synthetic_snapshot()
    first = snapshot.runtime_robots()
    first[0]["name"] = "changed outside DTO"

    assert snapshot.runtime_robots()[0]["name"] != "changed outside DTO"


def test_dual_run_feature_flag_is_closed_by_default(monkeypatch):
    monkeypatch.delenv("CATALOG_DUAL_RUN_ENABLED", raising=False)
    fixture = _fixture(
        {
            "object_type": "retail",
            "process_type": "transport",
            "cargo_type": "pallets",
            "pallets_per_day": 800,
        }
    )

    with pytest.raises(DualRunConfigurationError, match="dual-run is disabled"):
        run_dual_run(
            StaticRepository(),
            StaticRepository(),
            fixture,
        )


def test_dual_run_cli_reports_missing_database_without_dsn(
    monkeypatch, capsys
):
    monkeypatch.setenv("CATALOG_DUAL_RUN_ENABLED", "true")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    exit_code = dual_run_main(
        [
            "--reference-catalog-code",
            "reference-v1",
            "--candidate-catalog-code",
            "organizer-catalog-v4",
            "--fixture",
            str(Path(__file__).with_name("fixtures") / "catalog-dual-run-warehouse-v1.json"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "DatabaseConfigurationError" in captured.err
    assert "postgresql" not in captured.err.lower()


def test_dual_run_compares_all_dimensions_for_golden_scenarios(monkeypatch):
    monkeypatch.setenv("CATALOG_DUAL_RUN_ENABLED", "true")
    fixture = _fixture(
        {
            "object_type": "retail",
            "process_type": "transport",
            "cargo_type": "pallets",
            "pallets_per_day": 800,
            "area_m2": 12000,
            "avg_distance_m": 180,
            "shifts_count": 3,
            "shift_hours": 8,
            "staff_headcount": 12,
            "aisle_width_m": 2.4,
            "payload_kg": 700,
            "fte_cost_rub": 1674000,
            "horizon_years": 5,
        },
        {
            "object_type": "retail",
            "process_type": "transport",
            "cargo_type": "pallets",
            "pallets_per_day": 800,
            "aisle_width_m": 2.4,
            "payload_kg": 1600,
        },
    )

    report = run_dual_run(
        StaticRepository(),
        StaticRepository(),
        fixture,
    )

    assert report["summary"] == {
        "MATCH": 9,
        "EXPECTED_DIFFERENCE": 0,
        "DEFECT": 0,
        "BLOCKED_BY_EVIDENCE": 0,
    }
    assert {item["dimension"] for item in report["comparisons"]} == {
        "identity",
        "rejection",
        "fleet",
        "economics",
        "scenario_spec",
    }
    rejected = [
        item
        for item in report["comparisons"]
        if item["scenario_id"] == "scenario-2"
        and item["dimension"] == "rejection"
    ]
    assert rejected[0]["reference"] == rejected[0]["candidate"]
    assert "грузоподъёмности" in rejected[0]["reference"]
