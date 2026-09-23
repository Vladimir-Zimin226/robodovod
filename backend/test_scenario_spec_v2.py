from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculation.capacity.trace import finalize_trace
from calculation.economics.allocation import MultiprocessAllocationResultV1
from calculation.service import analyze_capacity
from models import ScenarioSpec
from scenario_spec_v2 import (
    ScenarioAssumptionV2,
    ScenarioBatchV2,
    ScenarioOperatingWindowV2,
    ScenarioRouteBindingV2,
    ScenarioSpecV2,
    ScenarioZoneV2,
    build_scenario_spec_v2,
)
from test_capacity_analysis_service import eligible_constraints, request, snapshot


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "contracts" / "fixtures"


def _components():
    return {
        "tenant_id": "tenant.c22",
        "operating_windows": [ScenarioOperatingWindowV2(
            window_id="window.main",
            start_time={"value": "0", "unit": "s", "quantity_kind": "TIME"},
            duration={"value": "20", "unit": "h", "quantity_kind": "TIME"},
            timezone="Europe/Moscow", source="USER", provenance_ref="prov.user",
        )],
        "zone": ScenarioZoneV2(
            zone_id="zone.main", label="Основная зона", geometry_source="SYNTHETIC",
            assumption_ref="assumption.geometry",
        ),
        "route": ScenarioRouteBindingV2(
            route_id="route.main", geometry_source="SYNTHETIC",
            one_way_distance={"value": "100", "unit": "m", "quantity_kind": "DISTANCE"},
            assumption_ref="assumption.route",
        ),
        "batch": ScenarioBatchV2(
            semantics="PHYSICAL_BATCH",
            units_per_cycle={"value": "1", "unit": "unit/cycle", "quantity_kind": "RATE"},
            provenance_ref="prov.user",
        ),
        "assumptions": [
            ScenarioAssumptionV2(
                assumption_id="assumption.geometry", version="synthetic-geometry-v1",
                provenance_ref="prov.user", scope="VISUALIZATION_ONLY",
                message="Synthetic geometry does not replace analytical route.",
            ),
            ScenarioAssumptionV2(
                assumption_id="assumption.route", version="synthetic-route-v1",
                provenance_ref="prov.user", scope="VISUALIZATION_ONLY",
                message="Synthetic route preserves analytical distance.",
            ),
        ],
    }


def _capacity_pair():
    capacity_request = request()
    response = analyze_capacity(
        capacity_request, snapshot(), "run.c22.golden", constraint_provider=eligible_constraints,
    ).response
    return capacity_request, response


def test_capacity_only_cleaner_fixture_is_strict_and_has_no_payload_or_finance():
    raw = json.loads((FIXTURES / "scenario-spec-v2.capacity-only-cleaner.golden.json").read_text(encoding="utf-8"))
    spec = ScenarioSpecV2.model_validate(raw)
    assert spec.model_dump(mode="json") == raw
    assert spec.profile.calculation_profile == "CLEANING_AREA_V1"
    assert spec.finance is None
    assert "payload" not in json.dumps(raw, sort_keys=True)
    assert spec.tasks[0].exchange.mode == "NOT_APPLICABLE"


def test_v2_builder_is_deterministic_and_version_bindings_change_revision():
    capacity_request, response = _capacity_pair()
    first = build_scenario_spec_v2(capacity_request, response, **_components())
    same = build_scenario_spec_v2(capacity_request, response, **_components())
    assert first.model_dump(mode="json") == same.model_dump(mode="json")

    versions = response.trace.versions.model_copy(update={
        "catalog_version_id": "persistence-test-capacity-v2",
        "catalog_content_digest": "sha256:" + "d" * 64,
    })
    trace = finalize_trace(response.trace.model_copy(update={"versions": versions}, deep=True))
    changed = response.model_copy(update={"trace": trace}, deep=True)
    changed_spec = build_scenario_spec_v2(capacity_request, changed, **_components())
    assert first.revision_id != changed_spec.revision_id
    assert first.analysis.capacity_result_digest == changed_spec.analysis.capacity_result_digest
    assert first.analysis.capacity_trace_digest != changed_spec.analysis.capacity_trace_digest


def test_optional_c18_finance_binding_is_explicit_and_tenant_scoped():
    capacity_request, response = _capacity_pair()
    fixture = json.loads((FIXTURES / "multiprocess-allocation-v1.golden.json").read_text(encoding="utf-8"))["result"]
    raw = copy.deepcopy(fixture)
    raw["tenant_id"] = "tenant.c22"
    raw["project_id"] = capacity_request.project_id
    raw["input_revision"] = capacity_request.input_revision
    raw["processes"][0].update({
        "process_id": capacity_request.process.process_id,
        "model_id": capacity_request.model_id,
        "position_id": capacity_request.position_id,
        "acquisition": capacity_request.acquisition,
    })
    finance = MultiprocessAllocationResultV1.model_validate(raw)
    spec = build_scenario_spec_v2(capacity_request, response, finance=finance, **_components())
    assert spec.finance is not None
    assert spec.finance.source_result_digest.startswith("sha256:")
    assert spec.finance.versions.result_version == "multiprocess-allocation-result-v1"

    with pytest.raises(ValueError, match="tenant/project/revision"):
        build_scenario_spec_v2(
            capacity_request, response, finance=finance,
            **{**_components(), "tenant_id": "tenant.other"},
        )


def test_unknown_versions_extra_fields_and_tampered_snapshots_fail_closed():
    raw = json.loads((FIXTURES / "scenario-spec-v2.capacity-only-cleaner.golden.json").read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        ScenarioSpecV2.model_validate({**raw, "schema_version": "scenario-spec-v3"})
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ScenarioSpecV2.model_validate({**raw, "renderer_internal": {}})
    nested = copy.deepcopy(raw)
    nested["versions"]["calculation"]["formula_bundle_version"] = "calculation-formulas-v2"
    with pytest.raises(ValidationError):
        ScenarioSpecV2.model_validate(nested)
    stale_revision = copy.deepcopy(raw)
    stale_revision["versions"]["calculation"]["catalog_version_id"] = "catalog.c22.next"
    with pytest.raises(ValidationError, match="revision_id"):
        ScenarioSpecV2.model_validate(stale_revision)

    capacity_request, response = _capacity_pair()
    response.trace.replay.trace_content_digest = "sha256:" + "f" * 64
    with pytest.raises(ValueError, match="trace digest"):
        build_scenario_spec_v2(capacity_request, response, **_components())

    components = _components()
    components["route"] = ScenarioRouteBindingV2(
        route_id="route.main", geometry_source="SYNTHETIC",
        one_way_distance={"value": "99", "unit": "m", "quantity_kind": "DISTANCE"},
        assumption_ref="assumption.route",
    )
    with pytest.raises(ValueError, match="cannot overwrite"):
        build_scenario_spec_v2(capacity_request, analyze_capacity(
            capacity_request, snapshot(), "run.c22.golden", constraint_provider=eligible_constraints,
        ).response, **components)


def test_scenario_spec_v1_remains_byte_compatible_and_rejects_v2():
    raw = json.loads((FIXTURES / "scenario-spec-v1.golden.json").read_text(encoding="utf-8"))
    assert ScenarioSpec.model_validate(raw).model_dump(mode="json") == raw
    v2 = json.loads((FIXTURES / "scenario-spec-v2.capacity-only-cleaner.golden.json").read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        ScenarioSpec.model_validate(v2)


def test_generated_schema_and_fixture_are_exact():
    from scripts.build_scenario_spec_v2_contract import expected_files

    assert [str(path.relative_to(ROOT)) for path, expected in expected_files() if path.read_bytes() != expected] == []
