"""C19 ranking v2 over C05/C06 eligibility and C18 economics bindings."""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_EVEN, Decimal
from itertools import pairwise
from typing import Annotated, Literal

from calculation_contracts import Digest, StableId, StrictContractModel
from pydantic import Field, model_validator

from calculation.constraints import (
    ConstraintCheck,
    ConstraintReportV2,
    load_constraint_rules,
)
from calculation.executability import RunExecutabilityResult

RANKING_ENGINE_VERSION = "ranking-v2"
RANKING_REQUEST_VERSION = "ranking-request-v2"
RANKING_RESULT_VERSION = "ranking-result-v2"
V2D_POLICY_VERSION = "hackathon-calculation-policy-v1+v2d-c19"
ZERO_DIGEST = "sha256:" + "0" * 64

DecimalString = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")]
MoneyString = Annotated[str, Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$")]

DATA_FIELDS: dict[str, Literal["CRITICAL", "IMPORTANT", "USEFUL"]] = {
    "noise_level": "CRITICAL", "time_restriction": "CRITICAL", "zone_restriction": "CRITICAL",
    "operating_temperature": "CRITICAL", "certificates": "CRITICAL", "apron_permission": "CRITICAL",
    "sterilization_support": "CRITICAL", "lift_protocols": "CRITICAL", "access_control_protocols": "CRITICAL",
    "floor_flatness": "CRITICAL", "floor_covering": "CRITICAL", "trl": "CRITICAL",
    "operating_speed": "IMPORTANT", "load_time": "IMPORTANT", "unload_time": "IMPORTANT",
    "units_per_trip": "IMPORTANT", "mtbf": "IMPORTANT", "mttr": "IMPORTANT",
    "expected_life": "IMPORTANT", "liquidity": "IMPORTANT", "warranty": "IMPORTANT",
    "fleet_license_cost": "IMPORTANT", "site_integration_cost": "IMPORTANT", "spare_parts_cost": "IMPORTANT",
    "wifi_requirement": "IMPORTANT", "communication_cost": "IMPORTANT", "consumables_cost": "IMPORTANT",
    "repair_cost": "IMPORTANT", "technical_staff_cost": "IMPORTANT",
    "accounting_integrations": "USEFUL", "industrial_protocols": "USEFUL", "allowed_zones": "USEFUL",
    "surface_material": "USEFUL", "explosion_protection": "USEFUL", "max_slope": "USEFUL",
    "outdoor_operation": "USEFUL",
}
DATA_WEIGHTS = {"CRITICAL": Decimal(3), "IMPORTANT": Decimal(2), "USEFUL": Decimal(1)}
APPLICABILITY_WEIGHTS = {
    "availability": Decimal("0.30"), "integrations": Decimal("0.25"),
    "aisle_margin": Decimal("0.20"), "trl": Decimal("0.15"), "payload_margin": Decimal("0.10"),
}


def _d(value: str | int | Decimal) -> Decimal:
    return Decimal(str(value))


def _plain(value: Decimal) -> str:
    if value == 0:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _score(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), "f")


def _digest(value: object) -> str:
    if isinstance(value, StrictContractModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CohortAllocationBindingV1(StrictContractModel):
    cohort_id: StableId
    allocation_run_id: StableId
    allocation_result_version: Literal["multiprocess-allocation-result-v1"] = "multiprocess-allocation-result-v1"
    allocation_result_digest: Digest
    anchor_configuration_id: StableId
    weights_frozen: Literal[True] = True


class TrlFactV1(StrictContractModel):
    status: Literal["VERIFIED", "UNKNOWN", "N_A"]
    value: Annotated[int, Field(ge=1, le=9)] | None = None
    matching_safe: bool
    provenance_ref: StableId | None = None

    @model_validator(mode="after")
    def valid(self) -> TrlFactV1:
        if self.status == "VERIFIED":
            if self.value is None or not self.matching_safe or self.provenance_ref is None:
                raise ValueError("verified TRL requires matching-safe value and provenance")
        elif self.value is not None or self.matching_safe:
            raise ValueError("unknown/N_A TRL cannot carry a scoring value")
        return self


class IntegrationCoverageV1(StrictContractModel):
    required_ids: list[StableId]
    supported_matching_safe_ids: list[StableId]
    unknown_ids: list[StableId]
    provenance_refs: list[StableId]

    @model_validator(mode="after")
    def valid(self) -> IntegrationCoverageV1:
        for values in (self.required_ids, self.supported_matching_safe_ids, self.unknown_ids):
            if len(values) != len(set(values)):
                raise ValueError("integration identities must be unique")
        required = set(self.required_ids)
        supported = set(self.supported_matching_safe_ids)
        unknown = set(self.unknown_ids)
        if supported - required or unknown - required or supported & unknown:
            raise ValueError("integration coverage must partition required identities")
        return self


class DataFieldStatusV1(StrictContractModel):
    field_id: StableId
    importance: Literal["CRITICAL", "IMPORTANT", "USEFUL"]
    status: Literal["VERIFIED", "UNVERIFIED", "MISSING", "N_A"]
    matching_safe: bool
    provenance_ref: StableId | None = None

    @model_validator(mode="after")
    def evidence_semantics(self) -> DataFieldStatusV1:
        if self.status == "VERIFIED" and (not self.matching_safe or self.provenance_ref is None):
            raise ValueError("verified data field requires matching-safe provenance")
        if self.status != "VERIFIED" and self.matching_safe:
            raise ValueError("unverified/missing/N_A field cannot become matching-safe")
        if self.status == "UNVERIFIED" and self.provenance_ref is None:
            raise ValueError("filled-unverified field requires provenance")
        return self


class PenaltyContextV1(StrictContractModel):
    equipment_class: Literal["AMR", "FORKLIFT", "SHUTTLE", "FIXED_CELL", "MANIPULATOR", "CLEANER", "OTHER"]
    quantity_kind: Literal["PALLET", "BOX", "CASE", "CART", "DELIVERY", "PORTION", "KG", "SAMPLE", "SET", "BIN", "ITEM", "M2", "PICK"]
    demand_per_day: DecimalString
    demand_provenance_ref: StableId

    @model_validator(mode="after")
    def positive(self) -> PenaltyContextV1:
        if _d(self.demand_per_day) <= 0:
            raise ValueError("ranking demand must be positive")
        return self


class RankingCandidateV2(StrictContractModel):
    candidate_id: StableId
    configuration_id: StableId
    model_id: StableId
    position_id: StableId
    constraint_report: ConstraintReportV2
    constraint_report_digest: Digest
    executability: RunExecutabilityResult
    executability_digest: Digest
    trl: TrlFactV1
    integrations: IntegrationCoverageV1
    data_fields: list[DataFieldStatusV1]
    penalty_context: PenaltyContextV1
    finance_status: Literal["COMPLETE", "INCOMPLETE"]
    npv_project: MoneyString | None
    allocation_result_digest: Digest

    @model_validator(mode="after")
    def bind(self) -> RankingCandidateV2:
        if self.constraint_report_digest != _digest(self.constraint_report):
            raise ValueError("constraint report digest mismatch")
        if self.executability_digest != _digest(self.executability):
            raise ValueError("executability digest mismatch")
        identities = (self.model_id, self.position_id)
        if (self.constraint_report.model_id, self.constraint_report.position_id) != identities:
            raise ValueError("constraint report candidate identity mismatch")
        if (self.executability.model_id, self.executability.position_id) != identities:
            raise ValueError("executability candidate identity mismatch")
        if (self.finance_status == "COMPLETE") != (self.npv_project is not None):
            raise ValueError("complete finance requires NPV; incomplete finance forbids fake NPV")
        field_ids = [item.field_id for item in self.data_fields]
        if len(field_ids) != len(set(field_ids)) or set(field_ids) != set(DATA_FIELDS):
            raise ValueError("data completeness must contain the exact 36-field R08 set")
        if any(item.importance != DATA_FIELDS[item.field_id] for item in self.data_fields):
            raise ValueError("data field importance differs from the immutable R08/K16 registry")
        return self


class RankingRequestV2(StrictContractModel):
    schema_version: Literal["ranking-request-v2"] = RANKING_REQUEST_VERSION
    run_id: StableId
    project_id: StableId
    tenant_id: StableId
    input_revision: StableId
    process_id: StableId
    cohort: CohortAllocationBindingV1
    candidates: list[RankingCandidateV2]

    @model_validator(mode="after")
    def validate_cohort(self) -> RankingRequestV2:
        if not self.candidates:
            raise ValueError("ranking cohort cannot be empty")
        ids = [item.candidate_id for item in self.candidates]
        configs = [item.configuration_id for item in self.candidates]
        if len(ids) != len(set(ids)) or len(configs) != len(set(configs)):
            raise ValueError("candidate and configuration identities must be unique")
        for candidate in self.candidates:
            if candidate.constraint_report.input_revision != self.input_revision:
                raise ValueError("constraint report input revision mismatch")
            if candidate.constraint_report.process_id != self.process_id:
                raise ValueError("constraint report process identity mismatch")
            if candidate.allocation_result_digest != self.cohort.allocation_result_digest:
                raise ValueError("candidate allocation binding differs from frozen cohort")
        self.candidates = sorted(self.candidates, key=lambda item: item.candidate_id)
        return self


class ComponentTraceV2(StrictContractModel):
    component_id: Literal["availability", "integrations", "aisle_margin", "trl", "payload_margin"]
    status: Literal["VALUE", "UNKNOWN", "N_A"]
    raw_value: DecimalString | None
    normalized_value: DecimalString | None
    nominal_weight: DecimalString
    effective_weight: DecimalString
    numerator: DecimalString | None
    denominator: DecimalString | None
    knots: list[tuple[DecimalString, DecimalString]]
    provenance_refs: list[str]


class DataScoreTraceV2(StrictContractModel):
    status: Literal["VALUE", "N_A"]
    numerator: DecimalString
    denominator: DecimalString
    value: DecimalString | None
    verified_weight: DecimalString
    unverified_weight: DecimalString
    missing_weight: DecimalString
    applicable_field_count: Annotated[int, Field(ge=0, le=36)]


class CandidateScoreBreakdownV2(StrictContractModel):
    candidate_id: StableId
    configuration_id: StableId
    model_id: StableId
    position_id: StableId
    eligibility: Literal["EXCLUDED", "TECHNICAL_ONLY", "FULL"]
    recommendation_quality: Literal["FINAL", "PRELIMINARY", "EXCLUDED"]
    applicability_components: list[ComponentTraceV2]
    applicability_score: DecimalString | None
    data_score: DataScoreTraceV2
    economy_score: DecimalString | None
    npv_project: MoneyString | None
    penalty: DecimalString
    technical_score: DecimalString | None
    final_score: DecimalString | None
    rank: Annotated[int, Field(ge=1)] | None
    reason_codes: list[StableId]


class RecommendationV2(StrictContractModel):
    status: Literal["RECOMMENDED", "PRELIMINARY", "NO_POSITIVE_CASE", "INCOMPLETE", "NONE"]
    candidate_id: StableId | None
    reason_codes: list[StableId]


class RankingTraceNodeV2(StrictContractModel):
    node_id: StableId
    formula_id: Literal["F33", "F35"]
    operation: Literal["ELIGIBILITY", "INTERPOLATE", "REWEIGHT", "DATA_COMPLETENESS", "ECONOMY_MINMAX", "PENALTY", "FINAL_SCORE", "RECOMMENDATION"]
    input_refs: list[str]
    output_ref: StableId
    value: DecimalString | None
    numerator: DecimalString | None = None
    denominator: DecimalString | None = None


class RankingVersionsV2(StrictContractModel):
    engine_version: Literal["ranking-v2"] = RANKING_ENGINE_VERSION
    request_version: Literal["ranking-request-v2"] = RANKING_REQUEST_VERSION
    result_version: Literal["ranking-result-v2"] = RANKING_RESULT_VERSION
    calculation_policy_version: Literal["hackathon-calculation-policy-v1"] = "hackathon-calculation-policy-v1"
    policy_overlay_version: Literal["hackathon-calculation-policy-v1+v2d-c19"] = V2D_POLICY_VERSION
    constraint_rules_version: Literal["calculation-constraint-rules-v2"] = "calculation-constraint-rules-v2"
    executability_version: Literal["formula-run-executability-v3"] = "formula-run-executability-v3"
    allocation_result_version: Literal["multiprocess-allocation-result-v1"] = "multiprocess-allocation-result-v1"
    precision_policy_version: Literal["decimal-context-28-half-even-v1"] = "decimal-context-28-half-even-v1"
    data_field_registry_version: Literal["ranking-data-fields-r08-k16-v1"] = "ranking-data-fields-r08-k16-v1"


class RankingReplayV2(StrictContractModel):
    canonical_input_digest: Digest
    allocation_result_digest: Digest
    constraint_report_digests: list[Digest]
    executability_digests: list[Digest]
    trace_content_digest: Digest


class RankingResultV2(StrictContractModel):
    schema_version: Literal["ranking-result-v2"] = RANKING_RESULT_VERSION
    run_id: StableId
    project_id: StableId
    tenant_id: StableId
    input_revision: StableId
    process_id: StableId
    cohort_id: StableId
    anchor_configuration_id: StableId
    candidates: list[CandidateScoreBreakdownV2]
    technical_recommendation: RecommendationV2
    financial_recommendation: RecommendationV2
    warnings: list[StableId]
    trace: list[RankingTraceNodeV2]
    versions: RankingVersionsV2
    replay: RankingReplayV2


def _piecewise(value: Decimal, knots: list[tuple[Decimal, Decimal]]) -> Decimal:
    if value <= knots[0][0]:
        return knots[0][1]
    for (x0, y0), (x1, y1) in pairwise(knots):
        if value <= x1:
            return y0 + (value - x0) * (y1 - y0) / (x1 - x0)
    return knots[-1][1]


def _check(report: ConstraintReportV2, check_id: str) -> ConstraintCheck:
    return next(item for item in report.checks if item.check_id == check_id)


def _number(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise TypeError("ranking constraint value must be numeric")
    return _d(value)


def _constraint_component(check: ConstraintCheck, component: str) -> tuple[str, Decimal | None, list[str]]:
    if check.status == "N_A":
        return "N_A", None, check.source_refs
    if check.status in ("UNKNOWN", "FAIL") or check.available is None:
        return "UNKNOWN", None, check.source_refs
    available = _number(check.available.value)
    if component == "availability":
        return "VALUE", available, check.source_refs
    if check.required is None:
        return "UNKNOWN", None, check.source_refs
    required = _number(check.required.value)
    if component == "aisle_margin":
        return "VALUE", required - available, check.source_refs
    if component == "payload_margin":
        return "VALUE", (available - required) / available if available > 0 else Decimal(-1), check.source_refs
    raise ValueError(component)


def _applicability(candidate: RankingCandidateV2) -> tuple[Decimal | None, list[ComponentTraceV2], list[str]]:
    report = candidate.constraint_report
    specs: list[tuple[str, str, list[tuple[Decimal, Decimal]]]] = [
        ("availability", "availability", [(Decimal(".4"), Decimal(0)), (Decimal(".55"), Decimal(".5")),
         (Decimal(".7"), Decimal(".8")), (Decimal(".85"), Decimal(1)),
         (Decimal(".92"), Decimal(".9")), (Decimal(1), Decimal(".5"))]),
        ("aisle_margin", "aisle", [(Decimal(0), Decimal(0)), (Decimal(".15"), Decimal(".3")),
         (Decimal(".4"), Decimal(".7")), (Decimal(".6"), Decimal(1))]),
        ("payload_margin", "payload", [(Decimal(0), Decimal(0)), (Decimal(".15"), Decimal(".5")),
         (Decimal(".5"), Decimal(1)), (Decimal(1), Decimal(".5"))]),
    ]
    raw: dict[str, tuple[str, Decimal | None, Decimal | None, list[tuple[Decimal, Decimal]], list[str]]] = {}
    reasons: list[str] = []
    for component, check_id, knots in specs:
        status, value, refs = _constraint_component(_check(report, check_id), component)
        if value is not None and ((component == "availability" and value < Decimal(".4")) or (component != "availability" and value < 0)):
            reasons.append(f"ranking-hard-threshold-{component}")
        normalized = None if status == "N_A" else Decimal(0) if status == "UNKNOWN" else _piecewise(value, knots)
        raw[component] = status, value, normalized, knots, refs

    if candidate.trl.status == "N_A":
        raw["trl"] = "N_A", None, None, [(Decimal(6), Decimal(0)), (Decimal(7), Decimal(".3")), (Decimal(8), Decimal(".7")), (Decimal(9), Decimal(1))], []
    elif candidate.trl.status == "UNKNOWN":
        raw["trl"] = "UNKNOWN", None, Decimal(0), [(Decimal(6), Decimal(0)), (Decimal(7), Decimal(".3")), (Decimal(8), Decimal(".7")), (Decimal(9), Decimal(1))], []
    else:
        knots = [(Decimal(6), Decimal(0)), (Decimal(7), Decimal(".3")), (Decimal(8), Decimal(".7")), (Decimal(9), Decimal(1))]
        raw["trl"] = "VALUE", Decimal(candidate.trl.value), _piecewise(Decimal(candidate.trl.value), knots), knots, [candidate.trl.provenance_ref]

    integrations = candidate.integrations
    if not integrations.required_ids:
        integration_value = Decimal(1)
    else:
        integration_value = Decimal(len(integrations.supported_matching_safe_ids)) / Decimal(len(integrations.required_ids))
    raw["integrations"] = "VALUE", integration_value, integration_value, [(Decimal(0), Decimal(0)), (Decimal(1), Decimal(1))], integrations.provenance_refs

    denominator = sum((weight for key, weight in APPLICABILITY_WEIGHTS.items() if raw[key][0] != "N_A"), Decimal(0))
    if denominator == 0:
        return None, [], reasons + ["applicability-no-applicable-components"]
    rows: list[ComponentTraceV2] = []
    total = Decimal(0)
    for key in ("availability", "integrations", "aisle_margin", "trl", "payload_margin"):
        status, value, normalized, knots, refs = raw[key]
        weight = APPLICABILITY_WEIGHTS[key]
        effective = Decimal(0) if status == "N_A" else weight / denominator
        if normalized is not None:
            total += normalized * effective
        rows.append(ComponentTraceV2(
            component_id=key, status=status, raw_value=None if value is None else _plain(value),
            normalized_value=None if normalized is None else _plain(normalized), nominal_weight=_plain(weight),
            effective_weight=_plain(effective), numerator=None if normalized is None else _plain(normalized * weight),
            denominator=_plain(denominator), knots=[(_plain(x), _plain(y)) for x, y in knots], provenance_refs=refs,
        ))
    return total * 100, rows, reasons


def _data_score(fields: list[DataFieldStatusV1]) -> DataScoreTraceV2:
    totals = {"VERIFIED": Decimal(0), "UNVERIFIED": Decimal(0), "MISSING": Decimal(0)}
    denominator = Decimal(0)
    numerator = Decimal(0)
    applicable = 0
    for item in fields:
        if item.status == "N_A":
            continue
        applicable += 1
        weight = DATA_WEIGHTS[item.importance]
        denominator += weight
        totals[item.status] += weight
        numerator += weight if item.status == "VERIFIED" else weight * Decimal(".5") if item.status == "UNVERIFIED" else Decimal(0)
    value = None if denominator == 0 else numerator / denominator * 100
    return DataScoreTraceV2(
        status="N_A" if value is None else "VALUE", numerator=_plain(numerator), denominator=_plain(denominator),
        value=None if value is None else _plain(value), verified_weight=_plain(totals["VERIFIED"]),
        unverified_weight=_plain(totals["UNVERIFIED"]), missing_weight=_plain(totals["MISSING"]),
        applicable_field_count=applicable,
    )


def _weighted_score(parts: list[tuple[Decimal | None, Decimal]], penalty: Decimal = Decimal(0)) -> Decimal | None:
    active = [(value, weight) for value, weight in parts if value is not None]
    denominator = sum((weight for _, weight in active), Decimal(0))
    if denominator == 0:
        return None
    value = sum((value * weight for value, weight in active), Decimal(0)) / denominator + penalty
    return min(Decimal(100), max(Decimal(0), value))


def calculate_ranking(request: RankingRequestV2) -> RankingResultV2:
    expected_rules = [item.rule_id for item in load_constraint_rules().rules]
    work: list[dict[str, object]] = []
    trace: list[RankingTraceNodeV2] = []
    for candidate in request.candidates:
        report_ids = [item.check_id for item in candidate.constraint_report.checks]
        if report_ids != expected_rules:
            raise ValueError("constraint report must contain the exact ordered versioned C05 rule set")
        integration_check = _check(candidate.constraint_report, "integrations")
        if integration_check.severity != "ADVISORY":
            raise ValueError("V2-D integrations must remain advisory, not hard fail")
        if (not candidate.integrations.required_ids) != (integration_check.status == "N_A"):
            raise ValueError("integration scoring scope differs from C05 report")
        reasons = set(candidate.constraint_report.blocker_codes + candidate.executability.blocker_codes)
        excluded = candidate.constraint_report.eligibility == "BLOCKED" or candidate.executability.status in {
            "MISSING_INPUT", "BLOCKED", "UNSUPPORTED_PROFILE"
        }
        applicability, components, local_reasons = _applicability(candidate)
        reasons.update(local_reasons)
        if local_reasons:
            excluded = True
        data = _data_score(candidate.data_fields)
        preliminary = candidate.constraint_report.eligibility == "NEEDS_VALIDATION" or candidate.executability.status == "NEEDS_VALIDATION"
        penalty = Decimal(-5) if (
            candidate.penalty_context.equipment_class == "AMR"
            and candidate.penalty_context.quantity_kind == "PALLET"
            and _d(candidate.penalty_context.demand_per_day) > 5000
        ) else Decimal(0)
        technical = None if excluded else _weighted_score([
            (applicability, Decimal(".50")),
            (None if data.value is None else _d(data.value), Decimal(".15")),
        ], penalty)
        work.append({"candidate": candidate, "excluded": excluded, "preliminary": preliminary,
                     "applicability": applicability, "components": components, "data": data,
                     "penalty": penalty, "technical": technical, "reasons": reasons})
        trace.append(RankingTraceNodeV2(node_id=f"eligibility.{candidate.candidate_id}", formula_id="F33", operation="ELIGIBILITY",
            input_refs=[candidate.constraint_report_digest, candidate.executability_digest], output_ref=f"candidate.{candidate.candidate_id}.eligible",
            value="0" if excluded else "1"))

    financial = [item for item in work if not item["excluded"] and item["candidate"].finance_status == "COMPLETE"]
    npvs = [_d(item["candidate"].npv_project) for item in financial]
    npv_min = min(npvs) if npvs else None
    npv_max = max(npvs) if npvs else None
    for item in work:
        candidate = item["candidate"]
        economy = None
        if not item["excluded"] and candidate.finance_status == "COMPLETE":
            value = _d(candidate.npv_project)
            economy = Decimal(50) if npv_min == npv_max else (value - npv_min) / (npv_max - npv_min) * 100
        data_value = None if item["data"].value is None else _d(item["data"].value)
        final = None if economy is None else _weighted_score([
            (item["applicability"], Decimal(".50")), (economy, Decimal(".35")), (data_value, Decimal(".15")),
        ], item["penalty"])
        item["economy"] = economy
        item["final"] = final
        trace.append(RankingTraceNodeV2(node_id=f"economy.{candidate.candidate_id}", formula_id="F33", operation="ECONOMY_MINMAX",
            input_refs=[candidate.allocation_result_digest, f"cohort.{request.cohort.cohort_id}.npv-range"],
            output_ref=f"candidate.{candidate.candidate_id}.economy", value=None if economy is None else _plain(economy),
            numerator=None if economy is None or npv_min == npv_max else _plain(_d(candidate.npv_project) - npv_min),
            denominator=None if economy is None or npv_min == npv_max else _plain(npv_max - npv_min)))

    ranked = sorted((item for item in work if item["final"] is not None),
                    key=lambda item: (-item["final"], item["candidate"].candidate_id))
    ranks = {item["candidate"].candidate_id: index for index, item in enumerate(ranked, 1)}
    technical_ranked = sorted((item for item in work if item["technical"] is not None),
                              key=lambda item: (-item["technical"], item["candidate"].candidate_id))
    warnings: list[str] = []
    if technical_ranked:
        best = technical_ranked[0]
        technical_rec = RecommendationV2(status="PRELIMINARY" if best["preliminary"] else "RECOMMENDED",
            candidate_id=best["candidate"].candidate_id, reason_codes=["needs-validation"] if best["preliminary"] else [])
    else:
        technical_rec = RecommendationV2(status="NONE", candidate_id=None, reason_codes=["no-technically-eligible-candidate"])
    positive = [item for item in ranked if _d(item["candidate"].npv_project) > 0]
    if positive:
        best = positive[0]
        financial_rec = RecommendationV2(status="PRELIMINARY" if best["preliminary"] else "RECOMMENDED",
            candidate_id=best["candidate"].candidate_id, reason_codes=["needs-validation"] if best["preliminary"] else [])
    elif ranked:
        financial_rec = RecommendationV2(status="NO_POSITIVE_CASE", candidate_id=None, reason_codes=["all-complete-npv-non-positive"])
        warnings.append("all-complete-npv-non-positive")
    elif technical_ranked:
        financial_rec = RecommendationV2(status="INCOMPLETE", candidate_id=None, reason_codes=["no-complete-finance"])
    else:
        financial_rec = RecommendationV2(status="NONE", candidate_id=None, reason_codes=["no-eligible-candidate"])

    results = [CandidateScoreBreakdownV2(
        candidate_id=item["candidate"].candidate_id, configuration_id=item["candidate"].configuration_id,
        model_id=item["candidate"].model_id, position_id=item["candidate"].position_id,
        eligibility="EXCLUDED" if item["excluded"] else "FULL" if item["final"] is not None else "TECHNICAL_ONLY",
        recommendation_quality="EXCLUDED" if item["excluded"] else "PRELIMINARY" if item["preliminary"] else "FINAL",
        applicability_components=item["components"], applicability_score=None if item["applicability"] is None else _score(item["applicability"]),
        data_score=item["data"], economy_score=None if item["economy"] is None else _score(item["economy"]),
        npv_project=item["candidate"].npv_project, penalty=_score(item["penalty"]),
        technical_score=None if item["technical"] is None else _score(item["technical"]),
        final_score=None if item["final"] is None else _score(item["final"]), rank=ranks.get(item["candidate"].candidate_id),
        reason_codes=sorted(item["reasons"]),
    ) for item in work]
    for result in results:
        trace.append(RankingTraceNodeV2(node_id=f"score.{result.candidate_id}", formula_id="F33", operation="FINAL_SCORE",
            input_refs=[f"candidate.{result.candidate_id}.applicability", f"candidate.{result.candidate_id}.economy",
                        f"candidate.{result.candidate_id}.data", f"candidate.{result.candidate_id}.penalty"],
            output_ref=f"candidate.{result.candidate_id}.score", value=result.final_score))

    replay = RankingReplayV2(canonical_input_digest=_digest(request), allocation_result_digest=request.cohort.allocation_result_digest,
        constraint_report_digests=sorted(item.constraint_report_digest for item in request.candidates),
        executability_digests=sorted(item.executability_digest for item in request.candidates), trace_content_digest=ZERO_DIGEST)
    result = RankingResultV2(run_id=request.run_id, project_id=request.project_id, tenant_id=request.tenant_id,
        input_revision=request.input_revision, process_id=request.process_id, cohort_id=request.cohort.cohort_id,
        anchor_configuration_id=request.cohort.anchor_configuration_id, candidates=results,
        technical_recommendation=technical_rec, financial_recommendation=financial_rec,
        warnings=warnings, trace=trace, versions=RankingVersionsV2(), replay=replay)
    payload = result.model_dump(mode="json")
    payload["replay"]["trace_content_digest"] = None
    result.replay.trace_content_digest = _digest(payload)
    return result


__all__ = ["RankingRequestV2", "RankingResultV2", "calculate_ranking"]
