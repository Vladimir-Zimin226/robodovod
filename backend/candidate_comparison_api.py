"""Read-only comparison of catalog alternatives on one saved C11 input."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from auth import AuthContext, require_auth_context, require_csrf
from calculation.constraints import (
    CandidateConstraintFacts,
    ConstraintEvaluationRequest,
    EvidenceBinding,
    ObjectConstraintContext,
    RequirementSource,
    evaluate_constraints,
)
from calculation.ranking import (
    DATA_FIELDS,
    DataFieldStatusV1,
    IntegrationCoverageV1,
    PenaltyContextV1,
    TrlFactV1,
    score_financial_components,
    score_technical_candidate,
)
from calculation.service import CapacityExecutionSnapshotV2, analyze_capacity, conservative_constraints
from calculation_contracts import parse_capacity_analysis_request, semantic_digest
from catalog_repository import CatalogPositionDTO, CatalogSnapshotDTO
from database import database_session
from fastapi import APIRouter, Depends, HTTPException
from persistence_models import AnalysisRun, Project
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

VERSION = "candidate-comparison-v1"
RULES_VERSION = "ranking-v2+candidate-cohort-v1"
MAX_CANDIDATES = 8
SAFE_FACT_STATUSES = {"CORROBORATED", "CROSS_DOCUMENT_ENRICHED", "ORGANIZER_NAME",
                      "VERIFIED_OFFICIAL", "VERIFIED_AUTHORIZED_PARTNER", "MANUALLY_APPROVED"}
AUTH = Depends(require_auth_context)
CSRF = Depends(require_csrf)
DB = Depends(database_session)


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_run_id: uuid.UUID
    position_ids: list[str] = Field(min_length=1, max_length=MAX_CANDIDATES)
    max_payload_kg: str | None = None
    min_aisle_width_m: str | None = None
    required_integrations: list[str] = Field(default_factory=list, max_length=12)
    constraints_confirmed: bool = False
    finance_run_ids: dict[str, uuid.UUID] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid(self) -> CompareRequest:
        if len(set(self.position_ids)) != len(self.position_ids):
            raise ValueError("position ids must be unique")
        if any(not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,127}", item) for item in
               [*self.position_ids, *self.required_integrations]):
            raise ValueError("position and integration ids must use stable lowercase identifiers")
        if len(set(self.required_integrations)) != len(self.required_integrations):
            raise ValueError("required integrations must be unique")
        for value in (self.max_payload_kg, self.min_aisle_width_m):
            if value is not None:
                try:
                    valid = bool(re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d+)?", value)) and len(value) <= 16
                    valid = valid and Decimal(value) > 0
                except InvalidOperation:
                    valid = False
                if not valid:
                    raise ValueError("physical constraint must be positive")
        if (self.max_payload_kg or self.min_aisle_width_m or self.required_integrations) and not self.constraints_confirmed:
            raise ValueError("selected physical constraints need user confirmation")
        if set(self.finance_run_ids) - set(self.position_ids):
            raise ValueError("finance run must belong to a selected position")
        return self


def _sha(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _fact(position: CatalogPositionDTO, codes: tuple[str, ...]) -> tuple[str | None, str | None]:
    for fact in position.model.facts:
        if fact.code in codes and fact.value is not None and fact.resolution_status in SAFE_FACT_STATUSES:
            return str(fact.value), fact.evidence_id
    return None, None


def _constraints(request: Any, position: CatalogPositionDTO, selected: CompareRequest):
    if getattr(request, 'object_constraint_context', None) is not None:
        saved = request.object_constraint_context
        for field in ('max_payload_kg', 'min_aisle_width_m', 'required_integrations'):
            value = getattr(selected, field)
            if value and value != saved.get(field):
                raise HTTPException(409, 'comparison requirements differ from saved object context')
        return conservative_constraints(request, position)
    known: dict[str, Any] = {}
    evidence: dict[str, EvidenceBinding] = {}
    for field in ("supported_object_kinds", "supported_process_scopes"):
        fact = next((item for item in position.model.facts if item.code == field and
                     item.value is not None and item.evidence_id and
                     item.resolution_status in SAFE_FACT_STATUSES), None)
        if fact is not None:
            known[field] = fact.value
            evidence[field] = EvidenceBinding(evidence_status="MATCHING_SAFE", source_ref=fact.evidence_id)
    for field, codes in (("payload_kg", ("payload_kg", "payload")),
                         ("min_aisle_width_m", ("min_aisle_width_m", "min_aisle_width")),
                         ("availability", ("availability",))):
        value, ref = _fact(position, codes)
        if value is not None:
            known[field] = value
            evidence[field] = EvidenceBinding(evidence_status="MATCHING_SAFE", source_ref=ref)
    sources = {field: RequirementSource(kind="USER", source_ref=f"comparison.user.{field}", user_confirmed=True)
               for field in ("max_payload_kg", "min_aisle_width_m", "required_integrations")
               if getattr(selected, field)}
    context = ObjectConstraintContext(
        object_kind=request.process.object_kind, max_payload_kg=selected.max_payload_kg,
        min_aisle_width_m=selected.min_aisle_width_m,
        required_integrations=selected.required_integrations, requirement_sources=sources,
    )
    return evaluate_constraints(ConstraintEvaluationRequest(
        input_revision=request.input_revision, process_id=request.process.process_id,
        process_code=request.process.process_code, process_scope=request.process.scope,
        context=context, candidate=CandidateConstraintFacts(model_id=position.model.id,
                                                             position_id=position.id, evidence=evidence, **known),
    ))


def _data_fields(position: CatalogPositionDTO) -> list[DataFieldStatusV1]:
    by_code = {fact.code: fact for fact in position.model.facts if fact.value is not None}
    aliases = {"operating_speed": ("operating_speed", "max_speed"),
               "units_per_trip": ("units_per_trip", "batch_size"),
               "expected_life": ("expected_life", "expected_life_years")}
    rows = []
    for code, importance in DATA_FIELDS.items():
        fact = next((by_code[name] for name in aliases.get(code, (code,)) if name in by_code), None)
        safe = fact is not None and fact.resolution_status in SAFE_FACT_STATUSES
        model_trl = code == "trl" and fact is None and position.model.trl is not None
        rows.append(DataFieldStatusV1(
            field_id=code, importance=importance,
            status="VERIFIED" if safe else "UNVERIFIED" if fact is not None or model_trl else "MISSING",
            matching_safe=safe, provenance_ref=fact.evidence_id if fact is not None else
            f"catalog-model:{position.model.id}:trl" if model_trl else None,
        ))
    return rows


def _trl(position: CatalogPositionDTO) -> TrlFactV1:
    value, ref = _fact(position, ("trl",))
    if value is not None and ref is not None and position.model.trl == int(Decimal(value)):
        return TrlFactV1(status="VERIFIED", value=position.model.trl, matching_safe=True, provenance_ref=ref)
    return TrlFactV1(status="UNKNOWN", value=None, matching_safe=False)


def _same_input(left: Any, right: Any) -> bool:
    a = left.model_dump(mode="json")
    b = right.model_dump(mode="json")
    for value in (a, b):
        value.pop("model_id", None)
        value.pop("position_id", None)
    return a == b


def _money_from_run(run: AnalysisRun, process_code: str) -> str | None:
    if run.run_kind != "FULL_ANALYSIS" or run.status != "SUCCEEDED" or not isinstance(run.result_snapshot, dict):
        return None
    if run.result_snapshot.get("schema_version") not in {"commercial-scenarios-bundle-v2", "commercial-scenarios-bundle-v3"}:
        return None
    if process_code == "warehouse_receiving_shipping":
        roles = {item.get("role_id"): item for item in run.result_snapshot.get("roles", [])}
        forbidden = {"picker", "sorter", "packaging_line_operator", "packer"}
        for scenario in run.result_snapshot.get("scenarios", []):
            conservation = scenario.get("allocation", {}).get("role_conservation", [])
            if not conservation or not any((roles.get(item.get("role_id")) or {}).get("role_code") == "forklift_driver"
                                           for item in conservation):
                return None
            for item in conservation:
                role = roles.get(item.get("role_id")) or {}
                try:
                    released = Decimal(str(item.get("released")))
                    headcount = Decimal(str(role.get("headcount")))
                except InvalidOperation:
                    return None
                if released < 0 or headcount < 0 or released > headcount:
                    return None
                if role.get("role_code") in forbidden and released > 0:
                    return None
    for scenario in run.result_snapshot.get("scenarios", []):
        if scenario.get("acquisition") == "PURCHASE" and scenario.get("uncertainty") == "BASE":
            if not scenario.get("procurement", {}).get("procurement_ready"):
                return None
            value = (scenario.get("report_facts", {}).get("project_npv") or {}).get("value")
            try:
                return value if value is not None and Decimal(value).is_finite() else None
            except (InvalidOperation, TypeError):
                return None
    return None


def rank_cohort(rows: list[dict[str, Any]], finance: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    """Stable technical ranking; money only when every eligible case shares one basis."""
    finance = finance or {}
    for row in rows:
        row["npv_project"] = None
        row["finance_run_id"] = None
        row["economy_score"] = None
        row["financial_score"] = None
        row["financial_rank"] = None
    eligible = [row for row in rows if row["technical_score"] is not None]
    ordered = sorted(eligible, key=lambda row: (-Decimal(row["technical_score"]), row["position_id"]))
    ranks = {row["position_id"]: index for index, row in enumerate(ordered, 1)}
    for row in rows:
        row["technical_rank"] = ranks.get(row["position_id"])
    technical = {"status": "NONE", "position_id": None, "reason": "Нет допустимого технического кандидата"}
    if ordered:
        best = ordered[0]
        technical = {"status": "PRELIMINARY" if best["readiness"] != "VERIFIED" else "RECOMMENDED",
                     "position_id": best["position_id"], "reason": "Оценка пригодности; условия закупки требуют отдельного подтверждения"}
    financial = {"status": "INCOMPLETE", "position_id": None,
                 "reason": "Для всех допустимых позиций нужны сопоставимые подтверждённые финансовые расчёты"}
    if len(eligible) >= 2 and all(row["position_id"] in finance for row in eligible):
        cases = [finance[row["position_id"]] for row in eligible]
        if len({case["basis_digest"] for case in cases}) == 1:
            npvs = [Decimal(case["npv_project"]) for case in cases]
            low, high = str(min(npvs)), str(max(npvs))
            for row in rows:
                if row["position_id"] in finance:
                    row["npv_project"] = finance[row["position_id"]]["npv_project"]
                    row["finance_run_id"] = finance[row["position_id"]]["run_id"]
            for row in eligible:
                economy, final = score_financial_components(
                    row["applicability_score"], row["data_score"]["value"],
                    row["npv_project"], low, high, row["penalty"],
                )
                row["economy_score"] = format(economy.quantize(Decimal("0.01")), "f")
                row["financial_score"] = None if final is None else format(final.quantize(Decimal("0.01")), "f")
            ordered_finance = sorted((row for row in eligible if row["financial_score"] is not None),
                                     key=lambda row: (-Decimal(row["financial_score"]), row["position_id"]))
            for index, row in enumerate(ordered_finance, 1):
                row["financial_rank"] = index
            positive = [row for row in ordered_finance if Decimal(row["npv_project"]) > 0]
            financial = ({"status": "PRELIMINARY", "position_id": positive[0]["position_id"],
                          "reason": "Положительный NPV; пригодность и закупка требуют проверки"}
                         if positive else {"status": "NO_POSITIVE_CASE", "position_id": None,
                                           "reason": "У всех сопоставимых позиций NPV неположительный"})
        else:
            financial["reason"] = "У финансовых расчётов различаются подтверждённые условия"
    return {"technical_recommendation": technical, "financial_recommendation": financial,
            "candidates": sorted(rows, key=lambda row: row["position_id"])}


def _finance_basis(raw: dict[str, Any]) -> str:
    terms = dict(raw)
    terms.pop("input_revision", None)
    return semantic_digest(terms)


def _role_scope(process_code: str) -> dict[str, Any]:
    if process_code == "warehouse_receiving_shipping":
        return {"operation": "prepared_pallet_transport", "affected_role_code": "forklift_driver",
                "excluded_role_codes": ["picker", "sorter", "packaging_line_operator", "packer"],
                "labour_status": "FROM_CONFIRMED_C14_ONLY"}
    return {"operation": process_code, "affected_role_code": None,
            "excluded_role_codes": [], "labour_status": "NO_LABOUR_IN_COMPARISON"}


def compare_candidates(base: Any, snapshot: CatalogSnapshotDTO, selected: CompareRequest,
                       finance: dict[str, dict[str, str]] | None = None,
                       analyze: Callable[..., CapacityExecutionSnapshotV2] = analyze_capacity) -> dict[str, Any]:
    by_id = {item.id: item for item in snapshot.positions}
    source_position = by_id.get(base.position_id)
    if source_position is None:
        raise HTTPException(409, "source position is absent from the active catalog")
    profile = source_position.model.capacity_runtime.calculation_profile
    rows: list[dict[str, Any]] = []
    for position_id in sorted(selected.position_ids):
        position = by_id.get(position_id)
        if position is None:
            raise HTTPException(422, f"unknown active position {position_id}")
        runtime = position.model.capacity_runtime
        reasons: list[str] = []
        if runtime.calculation_profile != profile:
            reasons.append("OTHER_OPERATION_OR_PHYSICAL_PROFILE")
        if position.model.maturity_status == "RND":
            reasons.append("RESEARCH_NOT_PURCHASE_READY")
        if not runtime.calculation_ready:
            reasons.append("NO_SUPPORTED_CALCULATION_FORMULA")
        row: dict[str, Any] = {
            "position_id": position.id, "model_id": position.model.id, "name": position.model.name,
            "maturity_status": position.model.maturity_status, "calculation_profile": runtime.calculation_profile,
            "price_status": position.procurement_option.price_status,
            "status": "INFORMATION_ONLY" if reasons else "NEEDS_VALIDATION",
            "readiness": "UNVERIFIED", "reason_codes": reasons,
            "technical_score": None, "technical_rank": None, "applicability_score": None,
            "penalty": "0", "npv_project": None, "finance_run_id": None,
            "economy_score": None, "financial_score": None, "financial_rank": None,
            "capacity": None, "components": [], "data_score": None, "data_fields": [],
            "constraints": None, "executability": None, "source_refs": [],
        }
        if not reasons:
            candidate_request = base.model_copy(update={"model_id": position.model.id, "position_id": position.id})
            if not _same_input(base, candidate_request):
                raise HTTPException(409, "candidate C11 inputs differ from the source")
            execution = analyze(candidate_request, snapshot, f"comparison.{position.id}",
                                constraint_provider=lambda request, current: _constraints(request, current, selected))
            report = execution.constraints
            fields = _data_fields(position)
            scored = score_technical_candidate(SimpleNamespace(
                constraint_report=report, executability=execution.executability,
                trl=_trl(position), integrations=IntegrationCoverageV1(
                    required_ids=selected.required_integrations, supported_matching_safe_ids=[],
                    unknown_ids=selected.required_integrations, provenance_refs=[]),
                data_fields=fields, penalty_context=PenaltyContextV1(
                    equipment_class="FIXED_CELL" if profile == "PALLETIZING_THROUGHPUT_V1" else "AMR",
                    quantity_kind="M2" if str(base.process.quantity_kind) == "SQUARE_METER" else str(base.process.quantity_kind),
                    demand_per_day=base.process.demand.normalized_value,
                    demand_provenance_ref=base.process.demand.provenance_ref),
            ))
            capacity = execution.response.capacity
            score = scored["technical"]
            if capacity.status not in {"COMPLETE", "WITH_ASSUMPTIONS"}:
                score = None
                reasons.append("CAPACITY_NOT_COMPUTED")
            reasons.extend(sorted(scored["reasons"]))
            if position.procurement_option.price_status != "NORMALIZED":
                reasons.append("PRICE_NOT_CONFIRMED")
            row.update(status="EXCLUDED" if report.eligibility == "BLOCKED" else
                       "TECHNICAL_ONLY" if score is not None else "INFORMATION_ONLY",
                       readiness="VERIFIED" if report.eligibility == "ELIGIBLE" and
                       execution.executability.status == "EXECUTABLE" and not reasons else "UNVERIFIED",
                       reason_codes=sorted(set(reasons)),
                       technical_score=None if score is None else format(score.quantize(Decimal("0.01")), "f"),
                       applicability_score=None if scored["applicability"] is None else
                       format(scored["applicability"], "f"),
                       penalty=format(scored["penalty"], "f"),
                       capacity=capacity.model_dump(mode="json"),
                       components=[item.model_dump(mode="json") for item in scored["components"]],
                       data_score=scored["data"].model_dump(mode="json"),
                       data_fields=[item.model_dump(mode="json") for item in fields],
                       constraints=report.model_dump(mode="json"),
                       executability=execution.executability.model_dump(mode="json"),
                       source_refs=[semantic_digest(execution.response), semantic_digest(report),
                                    semantic_digest(execution.executability)])
        rows.append(row)
    ranked = rank_cohort(rows, finance)
    return {"schema_version": VERSION, "ranking_rules_version": RULES_VERSION,
            "catalog_version": snapshot.version.code, "input_revision": base.input_revision,
            "process_id": base.process.process_id, "shared_input_digest": semantic_digest(base.model_dump(mode="json") | {
                "model_id": "cohort", "position_id": "cohort"}),
            "role_scope": _role_scope(base.process.process_code),
            "selected_constraints": {"max_payload_kg": selected.max_payload_kg,
                                     "min_aisle_width_m": selected.min_aisle_width_m,
                                     "required_integrations": selected.required_integrations,
                                     "confirmed": selected.constraints_confirmed},
            **ranked}


def create_comparison_router(discovery_loader: Callable[[], CatalogSnapshotDTO]) -> APIRouter:
    router = APIRouter(prefix="/api/candidate-comparisons")

    @router.post("/preview")
    def preview(payload: dict[str, Any], context: AuthContext = CSRF):
        """Rank every active position with the same physical profile, without writing a run."""
        raw = payload.get("capacity_request")
        if not isinstance(raw, dict):
            raise HTTPException(422, "capacity_request is required")
        try:
            request = parse_capacity_analysis_request(raw)
        except ValueError as exc:
            raise HTTPException(422, "invalid capacity request") from exc
        snapshot = discovery_loader()
        source_position = next((item for item in snapshot.positions if item.id == request.position_id), None)
        if source_position is None or source_position.model.id != request.model_id:
            raise HTTPException(422, "source position is absent from the active catalog")
        profile = source_position.model.capacity_runtime.calculation_profile
        if not profile or not source_position.model.capacity_runtime.calculation_ready:
            raise HTTPException(422, "source position has no supported calculation formula")
        ids = [item.id for item in snapshot.positions
               if item.model.capacity_runtime.calculation_profile == profile]
        mass = request.process.item_mass
        payload_kg = mass.normalized_value if mass is not None and mass.status == "KNOWN" else None
        selected = CompareRequest.model_construct(
            source_run_id=uuid.UUID(int=0), position_ids=ids,
            max_payload_kg=payload_kg, min_aisle_width_m=None,
            required_integrations=[], constraints_confirmed=bool(payload_kg),
            finance_run_ids={})
        result = compare_candidates(request, snapshot, selected)
        result["catalog_position_count"] = len(snapshot.positions)
        result["profile_position_count"] = len(ids)
        result["result_digest"] = semantic_digest(result)
        return result

    def source(db: Session, project_id: uuid.UUID, run_id: uuid.UUID, context: AuthContext):
        project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == context.user.id,
                                                  Project.status == "ACTIVE"))
        if project is None:
            raise HTTPException(404, "project not found")
        run = db.scalar(select(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.project_id == project_id,
                                                  AnalysisRun.run_kind == "CAPACITY_ANALYSIS", AnalysisRun.status == "SUCCEEDED"))
        if run is None:
            raise HTTPException(404, "source capacity run not found")
        if (not isinstance(run.input_snapshot, dict) or not isinstance(run.result_snapshot, dict)
                or _sha(run.input_snapshot) != run.input_sha256
                or _sha(run.result_snapshot) != run.result_sha256
                or not isinstance(run.trace_snapshot, dict)
                or _sha(run.trace_snapshot) != run.trace_sha256
                or run.result_snapshot.get("trace") != run.trace_snapshot
                or not isinstance(run.version_bindings_snapshot, dict)
                or _sha(run.version_bindings_snapshot) != run.version_bindings_sha256
                or run.trace_snapshot.get("versions") != run.version_bindings_snapshot):
            raise HTTPException(409, "source run checksum mismatch")
        snapshot = discovery_loader()
        if run.catalog_version_code != snapshot.version.code or str(run.catalog_version_id) != str(snapshot.version.id):
            raise HTTPException(409, "source catalog is no longer active; use its historical view")
        request = parse_capacity_analysis_request(run.input_snapshot)
        if request.project_id != str(project_id):
            raise HTTPException(409, "source project binding mismatch")
        return run, request, snapshot

    @router.get("/projects/{project_id}/sources/{run_id}")
    def options(project_id: uuid.UUID, run_id: uuid.UUID, context: AuthContext = AUTH,
                db: Session = DB):
        _, request, snapshot = source(db, project_id, run_id, context)
        base = next((item for item in snapshot.positions if item.id == request.position_id), None)
        if base is None:
            raise HTTPException(409, "source position is absent")
        profile = base.model.capacity_runtime.calculation_profile
        items = [item for item in snapshot.positions if item.model.capacity_runtime.calculation_profile == profile]
        financial_runs = db.scalars(select(AnalysisRun).where(
            AnalysisRun.project_id == project_id, AnalysisRun.run_kind == "FULL_ANALYSIS",
            AnalysisRun.status == "SUCCEEDED",
        ).order_by(AnalysisRun.created_at.desc()).limit(50)).all()
        finance_options = []
        for finance_run in financial_runs:
            if (not isinstance(finance_run.input_snapshot, dict)
                    or not isinstance(finance_run.result_snapshot, dict)
                    or _sha(finance_run.input_snapshot) != finance_run.input_sha256
                    or _sha(finance_run.result_snapshot) != finance_run.result_sha256):
                continue
            linked_id = finance_run.input_snapshot.get("capacity_run_id")
            try:
                linked_uuid = uuid.UUID(linked_id)
            except (TypeError, ValueError):
                continue
            linked = db.scalar(select(AnalysisRun).where(
                AnalysisRun.id == linked_uuid, AnalysisRun.project_id == project_id,
                AnalysisRun.run_kind == "CAPACITY_ANALYSIS", AnalysisRun.status == "SUCCEEDED"))
            if (linked is None or not isinstance(linked.input_snapshot, dict)
                    or not isinstance(linked.result_snapshot, dict)
                    or _sha(linked.input_snapshot) != linked.input_sha256
                    or _sha(linked.result_snapshot) != linked.result_sha256
                    or linked.catalog_version_code != snapshot.version.code
                    or str(linked.catalog_version_id) != str(snapshot.version.id)):
                continue
            try:
                linked_request = parse_capacity_analysis_request(linked.input_snapshot)
            except ValueError:
                continue
            if not _same_input(request, linked_request):
                continue
            npv = _money_from_run(finance_run, linked_request.process.process_code)
            basis = finance_run.input_snapshot.get("economics")
            if npv is None or not isinstance(basis, dict):
                continue
            finance_options.append({"run_id": str(finance_run.id), "position_id": linked_request.position_id,
                                    "npv_project": npv, "basis_digest": _finance_basis(basis),
                                    "conditions": {"horizon_years": basis.get("horizon_years"), "discount_rate": basis.get("discount_rate")},
                                    "created_at": finance_run.created_at})
        return {"catalog_version": snapshot.version.code, "source_position_id": request.position_id,
                "process_id": request.process.process_id,
                "object_constraint_context": getattr(request, 'object_constraint_context', None),
                "items": [{"position_id": item.id, "name": item.model.name,
                           "media": ({"url": f"/api/catalog/media/{snapshot.version.code}/{item.media.sha256}",
                                      "width_px": item.media.width_px, "height_px": item.media.height_px}
                                     if item.media else None),
                           "maturity_status": item.model.maturity_status,
                           "calculation_ready": item.model.capacity_runtime.calculation_ready,
                           "price_status": item.procurement_option.price_status,
                           "comparison_note": "Исследовательская позиция: только сведения" if item.model.maturity_status == "RND" else
                           "Нет поддержанной расчётной формулы: только сведения" if not item.model.capacity_runtime.calculation_ready else
                           "Цена не подтверждена; денежный вывод недоступен" if item.procurement_option.price_status != "NORMALIZED" else
                           "Пригодность и ограничения будут проверены при сравнении"}
                          for item in sorted(items, key=lambda item: (item.model.name, item.id))],
                "finance_options": finance_options}

    @router.post("/projects/{project_id}")
    def compare(project_id: uuid.UUID, payload: CompareRequest, context: AuthContext = CSRF,
                db: Session = DB):
        source_run, request, snapshot = source(db, project_id, payload.source_run_id, context)
        finance: dict[str, dict[str, str]] = {}
        for position_id, run_id in payload.finance_run_ids.items():
            run = db.scalar(select(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.project_id == project_id))
            if (run is None or not isinstance(run.input_snapshot, dict) or not isinstance(run.result_snapshot, dict)
                    or _sha(run.input_snapshot) != run.input_sha256 or _sha(run.result_snapshot) != run.result_sha256):
                raise HTTPException(409, "financial run missing or checksum mismatch")
            linked_id = (run.input_snapshot or {}).get("capacity_run_id")
            if not linked_id:
                raise HTTPException(422, "financial run is not bound to C11")
            _, linked_request, _ = source(db, project_id, uuid.UUID(linked_id), context)
            if linked_request.position_id != position_id or not _same_input(request, linked_request):
                raise HTTPException(422, "financial run has different operation or inputs")
            npv = _money_from_run(run, linked_request.process.process_code)
            if npv is None:
                raise HTTPException(422, "financial run has no confirmed purchase/base NPV")
            if not isinstance(run.input_snapshot.get("economics"), dict):
                raise HTTPException(422, "financial run has no comparable economic basis")
            finance[position_id] = {"run_id": str(run.id), "npv_project": npv,
                                    "basis_digest": _finance_basis(run.input_snapshot["economics"])}
        result = compare_candidates(request, snapshot, payload, finance)
        result["source_run_id"] = str(payload.source_run_id)
        result["source_input_sha256"] = source_run.input_sha256
        result["result_digest"] = semantic_digest(result)
        return result

    return router
