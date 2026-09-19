"""Controlled comparison of two explicit PostgreSQL catalog versions.

This module is intentionally not wired to a public endpoint. The command-line
entry point requires ``CATALOG_DUAL_RUN_ENABLED=true`` and an explicit database
catalog version.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalog_repository import (
    CatalogModelDTO,
    CatalogRepository,
    CatalogRepositoryError,
    PostgresCatalogRepository,
)
from database import Database, DatabaseConfigurationError, DatabaseSettings
from economics import calc_recommendation, check_constraints
from models import UserInput
from scenario_spec import build_scenario_spec


DIMENSIONS = ("identity", "rejection", "fleet", "economics", "scenario_spec")
CLASSIFICATIONS = (
    "MATCH",
    "EXPECTED_DIFFERENCE",
    "DEFECT",
    "BLOCKED_BY_EVIDENCE",
)


class DualRunConfigurationError(ValueError):
    """Raised when the service-only comparison is not explicitly configured."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelPair(_StrictModel):
    reference_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)


class ScenarioFixture(_StrictModel):
    id: str = Field(min_length=1)
    input: UserInput


class DifferenceExpectation(_StrictModel):
    scenario_id: str = Field(min_length=1)
    reference_id: str = Field(min_length=1)
    dimension: Literal[
        "identity", "rejection", "fleet", "economics", "scenario_spec"
    ]
    classification: Literal["EXPECTED_DIFFERENCE"]
    reason: str = Field(min_length=1)


class DualRunFixture(_StrictModel):
    schema_version: Literal["catalog-dual-run-fixture-v1"]
    model_pairs: list[ModelPair] = Field(min_length=1)
    scenarios: list[ScenarioFixture] = Field(min_length=1)
    expected_differences: list[DifferenceExpectation] = Field(default_factory=list)


def dual_run_enabled() -> bool:
    return os.getenv("CATALOG_DUAL_RUN_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def require_dual_run_enabled() -> None:
    if not dual_run_enabled():
        raise DualRunConfigurationError(
            "catalog dual-run is disabled; set CATALOG_DUAL_RUN_ENABLED=true"
        )


def load_dual_run_fixture(path: Path) -> DualRunFixture:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DualRunConfigurationError("dual-run fixture is unreadable") from exc
    fixture = DualRunFixture.model_validate(raw)
    scenario_ids = [scenario.id for scenario in fixture.scenarios]
    if len(scenario_ids) != len(set(scenario_ids)):
        raise DualRunConfigurationError("dual-run scenario ids must be unique")
    reference_ids = [pair.reference_id for pair in fixture.model_pairs]
    candidate_ids = [pair.candidate_id for pair in fixture.model_pairs]
    if len(reference_ids) != len(set(reference_ids)):
        raise DualRunConfigurationError("dual-run reference ids must be unique")
    if len(candidate_ids) != len(set(candidate_ids)):
        raise DualRunConfigurationError("dual-run candidate ids must be unique")
    expectation_keys = [
        (item.scenario_id, item.reference_id, item.dimension)
        for item in fixture.expected_differences
    ]
    if len(expectation_keys) != len(set(expectation_keys)):
        raise DualRunConfigurationError("dual-run expectations must be unique")
    valid_scenarios = {"*", *scenario_ids}
    if any(item.scenario_id not in valid_scenarios for item in fixture.expected_differences):
        raise DualRunConfigurationError("dual-run expectation has unknown scenario id")
    if any(item.reference_id not in set(reference_ids) for item in fixture.expected_differences):
        raise DualRunConfigurationError("dual-run expectation has unknown reference id")
    return fixture


def _identity(model: CatalogModelDTO) -> dict[str, Any]:
    runtime = model.runtime_robot or {}
    return {
        "name": model.name,
        "manufacturer": model.manufacturer,
        "system_family": model.system_family,
        "type_code": model.type_code,
        "subtype_code": model.subtype_code,
        "runtime_category": runtime.get("category"),
    }


def _engine_outcome(inp: UserInput, robot: dict[str, Any]) -> dict[str, Any]:
    rejection = check_constraints(inp, robot)
    if rejection is not None:
        return {
            "rejection": rejection,
            "fleet": None,
            "economics": None,
            "scenario_spec": None,
        }

    recommendation = calc_recommendation(inp, robot, is_zone=False)
    if recommendation.economic_status != "NOT_ACCEPTABLE":
        recommendation.is_best = True
    _, scenario_spec, _ = build_scenario_spec(
        inp,
        [recommendation],
        [],
        None,
        {robot["id"]: robot},
    )
    recommendation_payload = recommendation.model_dump(mode="json")
    return {
        "rejection": None,
        "fleet": {
            key: recommendation_payload[key]
            for key in (
                "quantity",
                "fleet_utilization",
                "fte_displaced",
                "fte_retained",
                "fte_released",
            )
        },
        "economics": {
            key: recommendation_payload[key]
            for key in (
                "horizon_years",
                "capex",
                "opex",
                "savings_per_year",
                "payback_years",
                "npv",
                "tco",
                "cost_per_move",
                "economic_status",
                "capex_breakdown",
                "opex_breakdown",
                "scenarios",
            )
        },
        "scenario_spec": scenario_spec.model_dump(mode="json"),
    }


def _expectation_map(
    fixture: DualRunFixture,
) -> dict[tuple[str, str, str], DifferenceExpectation]:
    return {
        (item.scenario_id, item.reference_id, item.dimension): item
        for item in fixture.expected_differences
    }


def _comparison(
    *,
    scenario_id: str,
    reference_id: str,
    candidate_id: str,
    dimension: str,
    reference: Any,
    candidate: Any,
    expectations: dict[tuple[str, str, str], DifferenceExpectation],
    used_expectations: set[tuple[str, str, str]],
) -> dict[str, Any]:
    if reference == candidate:
        classification = "MATCH"
        reason = "canonical values are equal"
    else:
        key = (scenario_id, reference_id, dimension)
        wildcard_key = ("*", reference_id, dimension)
        expectation = expectations.get(key) or expectations.get(wildcard_key)
        if expectation is None:
            classification = "DEFECT"
            reason = "unapproved difference"
        else:
            used_key = key if key in expectations else wildcard_key
            used_expectations.add(used_key)
            classification = expectation.classification
            reason = expectation.reason
    return {
        "scenario_id": scenario_id,
        "reference_id": reference_id,
        "candidate_id": candidate_id,
        "dimension": dimension,
        "classification": classification,
        "reason": reason,
        "reference": reference,
        "candidate": candidate,
    }


def _blocked_comparison(
    scenario_id: str,
    pair: ModelPair,
    reference_blockers: tuple[str, ...],
    candidate_blockers: tuple[str, ...],
    dimension: str,
) -> dict[str, Any]:
    reasons = {
        "reference": list(reference_blockers),
        "candidate": list(candidate_blockers),
    }
    return {
        "scenario_id": scenario_id,
        "reference_id": pair.reference_id,
        "candidate_id": pair.candidate_id,
        "dimension": dimension,
        "classification": "BLOCKED_BY_EVIDENCE",
        "reason": "runtime projection is incomplete; no value was assumed",
        "reference": reasons["reference"],
        "candidate": reasons["candidate"],
    }


def run_dual_run(
    reference_repository: CatalogRepository,
    candidate_repository: CatalogRepository,
    fixture: DualRunFixture,
    *,
    require_feature_flag: bool = True,
) -> dict[str, Any]:
    if require_feature_flag:
        require_dual_run_enabled()

    reference_snapshot = reference_repository.load()
    candidate_snapshot = candidate_repository.load()
    reference_models = reference_snapshot.by_source_key()
    candidate_models = candidate_snapshot.by_source_key()
    expectations = _expectation_map(fixture)
    used_expectations: set[tuple[str, str, str]] = set()
    comparisons: list[dict[str, Any]] = []

    for pair in fixture.model_pairs:
        reference_model = reference_models.get(pair.reference_id)
        candidate_model = candidate_models.get(pair.candidate_id)
        if reference_model is None or candidate_model is None:
            missing = []
            if reference_model is None:
                missing.append("reference model")
            if candidate_model is None:
                missing.append("candidate model")
            missing_dimensions = [("*", "identity")]
            missing_dimensions.extend(
                (scenario.id, dimension)
                for scenario in fixture.scenarios
                for dimension in DIMENSIONS[1:]
            )
            for scenario_id, dimension in missing_dimensions:
                comparisons.append(
                    {
                        "scenario_id": scenario_id,
                        "reference_id": pair.reference_id,
                        "candidate_id": pair.candidate_id,
                        "dimension": dimension,
                        "classification": "DEFECT",
                        "reason": f"paired {' and '.join(missing)} not found",
                        "reference": None,
                        "candidate": None,
                    }
                )
            continue

        comparisons.append(
            _comparison(
                scenario_id="*",
                reference_id=pair.reference_id,
                candidate_id=pair.candidate_id,
                dimension="identity",
                reference=_identity(reference_model),
                candidate=_identity(candidate_model),
                expectations=expectations,
                used_expectations=used_expectations,
            )
        )

        reference_robot = reference_model.runtime_dict()
        candidate_robot = candidate_model.runtime_dict()
        for scenario in fixture.scenarios:
            if reference_robot is None or candidate_robot is None:
                for dimension in DIMENSIONS[1:]:
                    comparisons.append(
                        _blocked_comparison(
                            scenario.id,
                            pair,
                            reference_model.runtime_blockers,
                            candidate_model.runtime_blockers,
                            dimension,
                        )
                    )
                continue
            reference_outcome = _engine_outcome(scenario.input, reference_robot)
            candidate_outcome = _engine_outcome(scenario.input, candidate_robot)
            for dimension in DIMENSIONS[1:]:
                comparisons.append(
                    _comparison(
                        scenario_id=scenario.id,
                        reference_id=pair.reference_id,
                        candidate_id=pair.candidate_id,
                        dimension=dimension,
                        reference=reference_outcome[dimension],
                        candidate=candidate_outcome[dimension],
                        expectations=expectations,
                        used_expectations=used_expectations,
                    )
                )

    unused_expectations = [
        {
            "scenario_id": key[0],
            "reference_id": key[1],
            "dimension": key[2],
            "reason": expectations[key].reason,
        }
        for key in sorted(set(expectations) - used_expectations)
    ]
    counts = {classification: 0 for classification in CLASSIFICATIONS}
    for item in comparisons:
        counts[item["classification"]] += 1
    counts["DEFECT"] += len(unused_expectations)

    paired_reference = {pair.reference_id for pair in fixture.model_pairs}
    paired_candidate = {pair.candidate_id for pair in fixture.model_pairs}
    return {
        "schema_version": "catalog-dual-run-report-v1",
        "reference_version": reference_snapshot.version.code,
        "candidate_version": candidate_snapshot.version.code,
        "fixture_schema_version": fixture.schema_version,
        "coverage": {
            "reference_models": len(reference_snapshot.models),
            "candidate_models": len(candidate_snapshot.models),
            "paired_models": len(fixture.model_pairs),
            "unpaired_reference_models": len(
                set(reference_models) - paired_reference
            ),
            "unpaired_candidate_models": len(
                set(candidate_models) - paired_candidate
            ),
            "note": "only explicit model pairs are compared; no name-based identity is inferred",
        },
        "summary": counts,
        "comparisons": comparisons,
        "unused_expectations": unused_expectations,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run controlled catalog dual-run")
    parser.add_argument("--reference-catalog-code", required=True)
    parser.add_argument("--candidate-catalog-code", required=True)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).with_name("fixtures")
        / "catalog-dual-run-warehouse-v1.json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    database: Database | None = None
    try:
        require_dual_run_enabled()
        fixture = load_dual_run_fixture(args.fixture)
        database = Database(DatabaseSettings.from_environment())
        report = run_dual_run(
            PostgresCatalogRepository(database, args.reference_catalog_code),
            PostgresCatalogRepository(database, args.candidate_catalog_code),
            fixture,
            require_feature_flag=False,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if report["summary"]["DEFECT"] else 0
    except (
        DualRunConfigurationError,
        CatalogRepositoryError,
        DatabaseConfigurationError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error_code": type(exc).__name__,
                    "message": str(exc),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 3
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error_code": "DUAL_RUN_FAILED",
                    "error_type": type(exc).__name__,
                    "message": "catalog dual-run failed",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 3
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
