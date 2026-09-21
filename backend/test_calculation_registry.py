from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculation.registry import (
    CalculationParameterRegistryV1,
    RegistryManifestV1,
    RegistryParameter,
    load_registry,
    load_registry_manifest,
    registry_semantic_digest,
    verify_registry_artifacts,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_calculation_registry import expected_files  # noqa: E402

REGISTRY = ROOT / "data" / "calculation" / "registry-v1.json"
MANIFEST = ROOT / "data" / "calculation" / "registry-v1.manifest.json"


def _raw_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_generated_registry_schema_and_manifest_are_exact():
    stale = [
        str(path.relative_to(ROOT))
        for path, expected in expected_files()
        if not path.is_file() or path.read_bytes() != expected
    ]
    assert stale == []
    registry = verify_registry_artifacts()
    manifest = load_registry_manifest()
    assert len(registry.parameters) == manifest.parameter_count == 228
    assert len(registry.coverage) == manifest.coverage_count == 27
    assert len(registry.supersessions) == manifest.supersession_count == 5
    assert manifest.scenario_parameter_count == 39


def test_repeated_load_is_idempotent_and_registry_is_stably_ordered():
    load_registry.cache_clear()
    first = load_registry()
    second = load_registry()
    assert first is second
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    ids = [item.parameter_id for item in first.parameters]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))
    assert registry_semantic_digest(first) == first.registry_digest


def test_manifest_source_hashes_match_available_build_time_sources():
    manifest = RegistryManifestV1.model_validate_json(MANIFEST.read_text(encoding="utf-8"))
    for source in manifest.sources:
        path = ROOT / source.path
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == source.sha256
        assert source.runtime_dependency is False


def test_every_parameter_has_source_decision_consumer_and_coverage():
    registry = load_registry()
    source_hashes = {
        item.source_id: item.sha256 for item in load_registry_manifest().sources
    }
    covered = {
        parameter_id
        for record in registry.coverage
        if record.disposition == "REGISTRY_VALUES"
        for parameter_id in record.parameter_ids
    }
    for parameter in registry.parameters:
        assert parameter.source_refs
        assert parameter.decision_refs
        assert parameter.consumers
        assert {ref.source_id for ref in parameter.source_refs} <= source_hashes.keys()
        source_binding = [
            {
                "source_id": ref.source_id,
                "source_sha256": source_hashes[ref.source_id],
                "locator": ref.locator,
                "source_status": ref.source_status,
            }
            for ref in parameter.source_refs
        ]
        expected_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                source_binding,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        assert parameter.source_digest == expected_digest
        if parameter.provenance_kind != "UNIT_DEFINITION":
            assert parameter.parameter_id in covered


def test_all_r02_r06_sections_have_explicit_disposition():
    registry = load_registry()
    by_source = defaultdict(set)
    for record in registry.coverage:
        by_source[record.source_id].add(record.coverage_id)
    assert by_source["R02"] == {
        "r02.1.derived-labor",
        "r02.1.labor-values",
        "r02.1.salary",
        "r02.2.finance-formulas",
        "r02.2.finance-values",
        "r02.3.raas-zeroing",
        "r02.3.scenarios",
        "r02.4.technology",
        "r02.4.vendor-values",
        "r02.5-6.defaults",
        "r02.7.data-weight-75",
        "r02.7.ranking",
        "r02.8.misc",
        "r02.8.unsafe-vendor-defaults",
        "r02.9.completeness",
    }
    assert by_source["R06"] == {
        "r06.1.labor",
        "r06.1.robot-exchange",
        "r06.1.salary",
        "r06.2.finance",
        "r06.2.flow-rules",
        "r06.3.raas",
        "r06.3.scenarios",
        "r06.4.ranking",
        "r06.5.completeness-visual",
        "r06.5.unsafe-picks",
        "r06.5.vendor-trl-noise",
        "r06.6.priorities",
    }


def test_scenario_table_is_complete_and_ramp_extends_after_year_five():
    registry = load_registry()
    scenarios = ("PESSIMISTIC", "BASE", "OPTIMISTIC")
    for scenario in scenarios:
        entries = [item for item in registry.parameters if item.scenario == scenario]
        assert len(entries) == 13
        semantics = Counter(item.semantic_name for item in entries)
        assert semantics == {
            "availability": 1,
            "intraday_peak": 1,
            "peak_reserve": 1,
            "capex_multiplier": 1,
            "capex_reserve": 1,
            "service_multiplier": 1,
            "supervision_share": 1,
            "annual_ramp_share": 6,
        }
        ramp = [item for item in entries if item.semantic_name == "annual_ramp_share"]
        assert [item.value for item in ramp][-1] == "1.00"
        assert any(
            "year.6-plus" in item.applicability and item.year is None
            for item in ramp
        )

    assert registry.by_id("scenario.pessimistic.availability").value == "0.55"
    assert registry.by_id("scenario.base.availability").value == "0.70"
    assert registry.by_id("scenario.optimistic.availability").value == "0.80"
    assert registry.by_id("scenario.base.peak-reserve").value == "0.20"


def test_precision_completeness_and_scoring_decisions_are_materialized():
    registry = load_registry()
    assert registry.by_id("labor.cost.direct-multiplier").value == "1.302"
    assert registry.by_id("labor.cost.full-multiplier").value == "1.55"
    assert registry.by_id("labor.staffing.vacation-factor").value == "1.090"

    intake_total = sum(
        int(item.value)
        for item in registry.parameters
        if item.semantic_name == "intake_completeness_weight"
    )
    assert intake_total == 100
    assert registry.by_id("completeness.card-important-count").value == "17"
    assert registry.by_id("completeness.card-full-weight").value == "77"

    final_weights = {
        item.applicability[0]: item.value
        for item in registry.parameters
        if item.semantic_name == "final_score_component_weight"
    }
    assert final_weights == {
        "score.final-component.applicability": "0.50",
        "score.final-component.data": "0.15",
        "score.final-component.economics": "0.35",
    }
    assert registry.by_id("score.curve.payload-margin.knot-4.output").value == "0.5"


def test_salary_and_unsafe_vendor_defaults_are_not_registry_values():
    registry = load_registry()
    semantic_names = {item.semantic_name for item in registry.parameters}
    parameter_ids = {item.parameter_id for item in registry.parameters}
    assert "monthly_gross_salary" not in semantic_names
    assert not any("salary-default" in parameter_id for parameter_id in parameter_ids)
    assert "robot_default_picks_per_minute" not in semantic_names
    assert "robot_default_cleaning_rate" not in semantic_names

    dispositions = {record.coverage_id: record.disposition for record in registry.coverage}
    assert dispositions["r02.1.salary"] == "USER_INPUT_REQUIRED"
    assert dispositions["r06.1.salary"] == "USER_INPUT_REQUIRED"
    assert dispositions["r02.8.unsafe-vendor-defaults"] == "FORBIDDEN_UNSAFE_DEFAULT"
    assert dispositions["r06.5.unsafe-picks"] == "FORBIDDEN_UNSAFE_DEFAULT"


def test_supersession_records_bind_replacements_and_removed_values_stay_absent():
    registry = load_registry()
    by_id = {item.supersession_id: item for item in registry.supersessions}
    assert set(by_id) == {
        "supersession.r04.51.applicability",
        "supersession.r04.58.raas",
        "supersession.r04.64.opex-base",
        "supersession.r04.66.penalties",
        "supersession.r04.d9.peak",
    }
    assert by_id["supersession.r04.d9.peak"].replacement_parameter_ids == [
        "scenario.base.intraday-peak",
        "scenario.base.peak-reserve",
    ]
    semantic_names = {item.semantic_name for item in registry.parameters}
    assert "target_fleet_utilization" not in semantic_names
    assert "default_salary" not in semantic_names


def test_schema_rejects_extra_fields_unknown_status_bad_domain_and_duplicate_id():
    raw = _raw_registry()
    with pytest.raises(ValidationError, match="extra_forbidden"):
        CalculationParameterRegistryV1.model_validate({**raw, "runtime": True})

    bad_status = copy.deepcopy(raw["parameters"][0])
    bad_status["provenance_kind"] = "VENDOR_GUESS"
    with pytest.raises(ValidationError):
        RegistryParameter.model_validate(bad_status)

    bad_domain = copy.deepcopy(raw["parameters"][0])
    bad_domain["domain"]["maximum"] = "0"
    with pytest.raises(ValidationError, match="above domain"):
        RegistryParameter.model_validate(bad_domain)

    duplicate = copy.deepcopy(raw)
    duplicate["parameters"].insert(1, copy.deepcopy(duplicate["parameters"][0]))
    with pytest.raises(ValidationError, match="parameter_id must be unique"):
        CalculationParameterRegistryV1.model_validate(duplicate)


def test_tampering_is_detected_by_semantic_and_file_digests():
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary_directory:
        temp_path = Path(temporary_directory)
        raw = _raw_registry()
        raw["parameters"][0]["description_key"] += ".tampered"
        tampered_registry = temp_path / "registry.json"
        tampered_registry.write_text(json.dumps(raw), encoding="utf-8")
        with pytest.raises(ValueError, match="semantic digest mismatch"):
            load_registry(tampered_registry)

        registry_copy = temp_path / "registry-copy.json"
        registry_copy.write_bytes(REGISTRY.read_bytes() + b"\n")
        with pytest.raises(ValueError, match="file digest mismatch"):
            verify_registry_artifacts(registry_copy, MANIFEST)
