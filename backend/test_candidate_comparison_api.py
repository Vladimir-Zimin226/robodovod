from __future__ import annotations

import uuid
from dataclasses import replace
from types import SimpleNamespace

import pytest
from auth import require_auth_context, require_csrf
from calculation.service import analyze_capacity
from candidate_comparison_api import (
    CompareRequest,
    _data_fields,
    _money_from_run,
    _sha,
    compare_candidates,
    create_comparison_router,
    rank_cohort,
)
from database import database_session
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_capacity_analysis_service import request, snapshot


def cohort():
    original = snapshot()
    first = original.positions[0]
    second_model = replace(first.model, id="model.synthetic.second", name="Synthetic second")
    second = replace(first, id="position.synthetic.second", model=second_model)
    rnd_model = replace(first.model, id="model.synthetic.rnd", name="Research arm", maturity_status="RND")
    rnd = replace(first, id="position.synthetic.rnd", model=rnd_model)
    return replace(original, models=(first.model, second_model, rnd_model), positions=(first, second, rnd))


def selection(ids):
    return CompareRequest(source_run_id=uuid.uuid4(), position_ids=ids)


def test_two_positions_get_same_220_pallets_and_120_metres_with_stable_scores():
    raw = request().model_dump(mode="json")
    raw["process"]["demand"]["raw_value"] = raw["process"]["demand"]["normalized_value"] = "220"
    raw["process"]["route_distance"]["raw_value"] = raw["process"]["route_distance"]["normalized_value"] = "120"
    raw.update(execution_mode="PRELIMINARY_DEMO", demo_assumptions_confirmed=True)
    base = type(request()).model_validate(raw)
    ids = ["position.synthetic.transport", "position.synthetic.second"]
    first = compare_candidates(base, cohort(), selection(ids))
    second = compare_candidates(base, cohort(), selection(list(reversed(ids))))
    assert first == second
    assert len(first["candidates"]) == 2
    assert all(item["capacity"]["status"] == "WITH_ASSUMPTIONS" for item in first["candidates"])
    assert all(item["technical_score"] is not None for item in first["candidates"])
    assert first["financial_recommendation"]["status"] == "INCOMPLETE"
    assert first["role_scope"]["affected_role_code"] == "forklift_driver"
    assert "picker" in first["role_scope"]["excluded_role_codes"]
    with_finance = compare_candidates(base, cohort(), selection(ids), {
        ids[0]: {"npv_project": "100", "run_id": "finance.first", "basis_digest": "same"},
        ids[1]: {"npv_project": "200", "run_id": "finance.second", "basis_digest": "same"},
    })
    assert all(item["financial_score"] is not None for item in with_finance["candidates"])
    assert with_finance["financial_recommendation"]["status"] == "PRELIMINARY"


def test_research_candidate_never_gets_fleet_or_npv():
    ids = ["position.synthetic.transport", "position.synthetic.rnd"]
    result = compare_candidates(request(), cohort(), selection(ids))
    rnd = next(item for item in result["candidates"] if item["position_id"].endswith("rnd"))
    assert rnd["status"] == "INFORMATION_ONLY"
    assert rnd["capacity"] is None
    assert rnd["npv_project"] is None
    assert "RESEARCH_NOT_PURCHASE_READY" in rnd["reason_codes"]


def test_confirmed_payload_constraint_excludes_overloaded_candidates():
    ids = ["position.synthetic.transport", "position.synthetic.second"]
    selected = CompareRequest(source_run_id=uuid.uuid4(), position_ids=ids,
                              max_payload_kg="2000", constraints_confirmed=True)
    result = compare_candidates(request(), cohort(), selected)
    assert all(item["status"] == "EXCLUDED" for item in result["candidates"])
    assert all(item["technical_score"] is None for item in result["candidates"])
    assert result["technical_recommendation"]["status"] == "NONE"


def test_catalog_evidence_fills_real_fields_and_unknown_remains_unknown():
    fields = {item.field_id: item for item in _data_fields(snapshot().positions[0])}
    assert fields["operating_speed"].status == "VERIFIED"
    assert fields["operating_speed"].provenance_ref == "evidence.speed"
    assert fields["floor_flatness"].status == "MISSING"


def test_negative_or_missing_finance_cannot_be_positive_recommendation():
    rows = [{"position_id": pid, "technical_score": "50.00", "readiness": "UNVERIFIED",
             "applicability_score": "50", "data_score": {"value": "50"}, "penalty": "0",
             "npv_project": None, "finance_run_id": None} for pid in ("a", "b")]
    assert rank_cohort(rows)["financial_recommendation"]["status"] == "INCOMPLETE"
    result = rank_cohort(rows, {pid: {"npv_project": "-100", "run_id": pid, "basis_digest": "same"}
                                for pid in ("a", "b")})
    assert result["financial_recommendation"]["status"] == "NO_POSITIVE_CASE"
    assert result["financial_recommendation"]["position_id"] is None
    positive = rank_cohort(rows, {"a": {"npv_project": "100", "run_id": "a", "basis_digest": "same"},
                                  "b": {"npv_project": "200", "run_id": "b", "basis_digest": "same"}})
    assert positive["financial_recommendation"]["status"] == "PRELIMINARY"
    assert positive["financial_recommendation"]["position_id"] == "b"
    assert all(row["financial_score"] is not None for row in positive["candidates"])
    mismatched = rank_cohort(rows, {"a": {"npv_project": "100", "run_id": "a", "basis_digest": "first"},
                                    "b": {"npv_project": "200", "run_id": "b", "basis_digest": "second"}})
    assert mismatched["financial_recommendation"]["status"] == "INCOMPLETE"
    assert all(row["npv_project"] is None for row in mismatched["candidates"])


def test_unconfirmed_constraints_are_rejected():
    with pytest.raises(ValueError, match="confirmation"):
        CompareRequest(source_run_id=uuid.uuid4(), position_ids=["a", "b"], max_payload_kg="1000")
    with pytest.raises(ValueError, match="physical constraint"):
        CompareRequest(source_run_id=uuid.uuid4(), position_ids=["a", "b"],
                       max_payload_kg="1e3", constraints_confirmed=True)


def test_transport_money_rejects_savings_from_picker_role():
    report = {"schema_version": "commercial-scenarios-bundle-v2",
              "roles": [{"role_id": "driver", "role_code": "forklift_driver", "headcount": "2"},
                        {"role_id": "picker", "role_code": "picker", "headcount": "2"}],
              "scenarios": [{"acquisition": "PURCHASE", "uncertainty": "BASE",
                             "procurement": {"procurement_ready": True},
                             "allocation": {"role_conservation": [
                                 {"role_id": "driver", "released": 1}, {"role_id": "picker", "released": 2}]},
                             "report_facts": {"project_npv": {"value": "100"}}}]}
    run = SimpleNamespace(run_kind="FULL_ANALYSIS", status="SUCCEEDED", result_snapshot=report)
    assert _money_from_run(run, "warehouse_receiving_shipping") is None
    report["scenarios"][0]["allocation"]["role_conservation"][1]["released"] = 0
    assert _money_from_run(run, "warehouse_receiving_shipping") == "100"
    report["scenarios"][0]["allocation"]["role_conservation"][0]["released"] = 3
    assert _money_from_run(run, "warehouse_receiving_shipping") is None


def test_owned_http_comparison_reads_immutable_c11_and_returns_two_positions():
    catalog = cohort()
    project_id = uuid.UUID(request().project_id)
    run_id = uuid.uuid4()
    raw = request().model_dump(mode="json")
    raw.update(execution_mode="PRELIMINARY_DEMO", demo_assumptions_confirmed=True)
    base = type(request()).model_validate(raw)
    execution = analyze_capacity(base, catalog, str(run_id))
    result = execution.response.model_dump(mode="json")
    trace = execution.response.trace.model_dump(mode="json")
    bindings = trace["versions"]
    run = SimpleNamespace(input_snapshot=base.model_dump(mode="json"), result_snapshot=result,
                          trace_snapshot=trace, version_bindings_snapshot=bindings,
                          catalog_version_code=catalog.version.code, catalog_version_id=catalog.version.id)
    run.input_sha256 = _sha(run.input_snapshot)
    run.result_sha256 = _sha(result)
    run.trace_sha256 = _sha(trace)
    run.version_bindings_sha256 = _sha(bindings)
    finance_result = {"schema_version": "commercial-scenarios-bundle-v2",
                      "roles": [{"role_id": "driver", "role_code": "forklift_driver", "headcount": "2"}],
                      "scenarios": [{"acquisition": "PURCHASE", "uncertainty": "BASE",
                                     "procurement": {"procurement_ready": True},
                                     "allocation": {"role_conservation": [{"role_id": "driver", "released": 1}]},
                                     "report_facts": {"project_npv": {"value": "100"}}}]}
    finance = SimpleNamespace(id=uuid.uuid4(), created_at="2026-09-25T10:00:00Z",
                              run_kind="FULL_ANALYSIS", status="SUCCEEDED",
                              input_snapshot={"capacity_run_id": str(run_id), "economics": {"input_revision": base.input_revision}},
                              result_snapshot=finance_result)
    finance.input_sha256 = _sha(finance.input_snapshot)
    finance.result_sha256 = _sha(finance_result)
    project = SimpleNamespace(id=project_id)
    class Session:
        def scalar(self, query):
            entity = query.column_descriptions[0]["entity"].__name__
            return project if entity == "Project" else run
        def scalars(self, _query):
            return SimpleNamespace(all=lambda: [finance])
    app = FastAPI()
    app.include_router(create_comparison_router(lambda: catalog))
    app.dependency_overrides[require_auth_context] = lambda: SimpleNamespace(user=SimpleNamespace(id=uuid.uuid4()))
    app.dependency_overrides[require_csrf] = lambda: SimpleNamespace(user=SimpleNamespace(id=uuid.uuid4()))
    app.dependency_overrides[database_session] = lambda: Session()
    with TestClient(app) as client:
        path = f"/api/candidate-comparisons/projects/{project_id}"
        options = client.get(f"{path}/sources/{run_id}")
        assert options.status_code == 200
        assert len(options.json()["items"]) == 3
        assert options.json()["finance_options"][0]["run_id"] == str(finance.id)
        compared = client.post(path, json={"source_run_id": str(run_id), "position_ids": [
            "position.synthetic.second", "position.synthetic.transport"]})
        assert compared.status_code == 200, compared.text
        assert len(compared.json()["candidates"]) == 2
        assert compared.json()["source_input_sha256"] == run.input_sha256
