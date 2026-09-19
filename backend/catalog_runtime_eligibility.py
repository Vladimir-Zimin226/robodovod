"""Deterministic local-only runtime eligibility audit for organizer catalog v4."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal

from catalog_import_contract import CatalogBundleError, load_catalog_bundle
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "data" / "import" / "organizer-catalog-v4"
DEFAULT_CONTRACT = ROOT / "contracts" / "runtime-eligibility-contract-v1.json"
DEFAULT_CONTRACT_SCHEMA = ROOT / "contracts" / "runtime-eligibility-contract-v1.schema.json"
DEFAULT_REPORT_SCHEMA = ROOT / "contracts" / "catalog-runtime-eligibility-audit-v1.schema.json"
DEFAULT_REPORT = ROOT / "data" / "review" / "catalog-runtime-eligibility-report-v1.json"
DEFAULT_SUMMARY = ROOT / "data" / "review" / "catalog-runtime-eligibility-summary-v1.md"

Status = Literal[
    "RUNTIME_READY",
    "NEEDS_FACTS",
    "CONFLICT_REVIEW",
    "UNSUPPORTED_CAPACITY_PROFILE",
    "NOT_EQUIPMENT",
]
Recommendation = Literal["LOCAL_ADAPTER", "DEEP_RESEARCH", "HYBRID", "NO_ACTION"]
Availability = Literal["MATCHING_SAFE", "LOCAL_CANDIDATE", "CONFLICT", "MISSING"]


class AuditError(ValueError):
    """Raised when the committed audit inputs or outputs violate their contract."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Selector(StrictModel):
    type: str = Field(min_length=1)
    subtypes: list[str] = Field(min_length=1)


class CapacityProfile(StrictModel):
    code: str = Field(min_length=1)
    required_fields: list[str] = Field(min_length=1)


class EquipmentClass(StrictModel):
    code: str = Field(min_length=1)
    runtime_category: str = Field(min_length=1)
    selectors: list[Selector] = Field(min_length=1)
    required_runtime_fields: list[str] = Field(min_length=1)
    capacity_profile: CapacityProfile


class Policy(StrictModel):
    safe_evidence_statuses: list[str] = Field(min_length=1)
    conflict_evidence_statuses: list[str] = Field(min_length=1)
    non_equipment_system_families: list[str] = Field(min_length=1)
    status_precedence: list[Status]
    description_overlay_runtime_eligible: Literal[False]
    runtime_switch_allowed: Literal[False]
    capacity_formulas_in_scope: Literal[False]


class RuntimeEligibilityContract(StrictModel):
    schema_version: Literal["runtime-eligibility-contract-v1"]
    catalog_code: Literal["organizer-catalog-v4"]
    policy: Policy
    equipment_classes: list[EquipmentClass] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_values(self) -> "RuntimeEligibilityContract":
        expected = [
            "NOT_EQUIPMENT",
            "CONFLICT_REVIEW",
            "UNSUPPORTED_CAPACITY_PROFILE",
            "NEEDS_FACTS",
            "RUNTIME_READY",
        ]
        if self.policy.status_precedence != expected:
            raise ValueError("status precedence differs from v1 policy")
        class_codes = [item.code for item in self.equipment_classes]
        profiles = [item.capacity_profile.code for item in self.equipment_classes]
        if len(class_codes) != len(set(class_codes)) or len(profiles) != len(set(profiles)):
            raise ValueError("equipment class and capacity profile codes must be unique")
        for item in self.equipment_classes:
            fields = item.required_runtime_fields + item.capacity_profile.required_fields
            if len(fields) != len(set(fields)):
                raise ValueError(f"duplicate required field in {item.code}")
        return self


class SourceReference(StrictModel):
    source_id: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    evidence_status: str = Field(min_length=1)
    locator: str = Field(min_length=1)


class FieldAssessment(StrictModel):
    field: str = Field(min_length=1)
    availability: Availability
    sources: list[SourceReference]


class Conflict(StrictModel):
    field: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    sources: list[SourceReference]


class AuditItem(StrictModel):
    id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source_row_number: int | None = None
    equipment_class: str | None
    capacity_profile: str | None
    status: Status
    recommendation: Recommendation
    required_fields: list[str]
    present_fields: list[FieldAssessment]
    missing_fields: list[str]
    conflicts: list[Conflict]
    source_files: list[str]


class Coverage(StrictModel):
    required_field_checks: int = Field(ge=0)
    matching_safe_field_checks: int = Field(ge=0)
    local_candidate_field_checks: int = Field(ge=0)
    conflict_field_checks: int = Field(ge=0)
    missing_field_checks: int = Field(ge=0)
    matching_safe_percent: float = Field(ge=0, le=100)


class InputFile(StrictModel):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    role: Literal["BASE", "OVERLAY", "EVIDENCE", "PROVENANCE", "CONTRACT"]
    runtime_eligible: bool


class AuditReport(StrictModel):
    schema_version: Literal["catalog-runtime-eligibility-audit-v1"]
    contract_version: Literal["runtime-eligibility-contract-v1"]
    catalog_code: Literal["organizer-catalog-v4"]
    deterministic_order: Literal["models:organizer_id;positions:source_row_number"]
    inputs: list[InputFile]
    counts: dict[str, int]
    model_status_counts: dict[str, int]
    position_status_counts: dict[str, int]
    recommendation_counts: dict[str, dict[str, int]]
    equipment_class_counts: dict[str, int]
    model_coverage: Coverage
    position_coverage: Coverage
    exclusions: list[str]
    models: list[AuditItem]
    positions: list[AuditItem]

    @model_validator(mode="after")
    def validate_exact_coverage(self) -> "AuditReport":
        if self.counts != {"models": 187, "positions": 223}:
            raise ValueError("audit must cover exactly 187 models and 223 positions")
        if len(self.models) != 187 or len(self.positions) != 223:
            raise ValueError("audit item counts differ")
        if sum(self.model_status_counts.values()) != 187:
            raise ValueError("model status counts differ")
        if sum(self.position_status_counts.values()) != 223:
            raise ValueError("position status counts differ")
        model_ids = [item.id for item in self.models]
        position_rows = [item.source_row_number for item in self.positions]
        if model_ids != sorted(model_ids) or position_rows != list(range(2, 225)):
            raise ValueError("audit ordering differs")
        return self


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"invalid JSON input: {path.name}") from exc
    if not isinstance(value, dict):
        raise AuditError(f"JSON input must be an object: {path.name}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter=";"))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise AuditError(f"invalid CSV input: {path.name}") from exc
    if any(None in row for row in rows):
        raise AuditError(f"malformed CSV input: {path.name}")
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_contract(path: Path = DEFAULT_CONTRACT) -> RuntimeEligibilityContract:
    try:
        return RuntimeEligibilityContract.model_validate(_read_json(path))
    except ValidationError as exc:
        raise AuditError("runtime eligibility contract validation failed") from exc


def _source_ref(
    *, source_id: str, source_file: str, evidence_status: str, locator: str
) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        source_file=source_file,
        evidence_status=evidence_status,
        locator=locator,
    )


def _field_sources(
    organizer_id: str,
    field: str,
    base_evidence: dict[tuple[str, str], list[dict[str, str]]],
    external_evidence: dict[tuple[str, str], list[dict[str, str]]],
) -> list[SourceReference]:
    refs: list[SourceReference] = []
    for row in base_evidence.get((organizer_id, field), []):
        refs.append(
            _source_ref(
                source_id=f"base:{organizer_id}:{field}",
                source_file=row["source_file"],
                evidence_status=row["evidence_status"],
                locator=f"{row['source_sheet_or_page']}:{row['source_row_or_fragment']}",
            )
        )
    for row in external_evidence.get((organizer_id, field), []):
        refs.append(
            _source_ref(
                source_id=row["source_id"],
                source_file="catalog_external_evidence.csv",
                evidence_status=row["evidence_status"],
                locator=row["field_path"],
            )
        )
    unique = {
        (ref.source_id, ref.source_file, ref.evidence_status, ref.locator): ref
        for ref in refs
    }
    return [unique[key] for key in sorted(unique)]


def _has_value(value: dict[str, Any]) -> bool:
    normalized = value.get("normalized_value")
    if normalized is not None:
        return True
    values = value.get("values")
    if isinstance(values, list) and values:
        return True
    raw = value.get("raw") or value.get("raw_value")
    return isinstance(raw, str) and bool(raw.strip())


def _equipment_class(
    product: dict[str, Any], contract: RuntimeEligibilityContract
) -> EquipmentClass | None:
    product_type = product.get("type")
    subtype = product.get("subtype")
    matches = [
        equipment_class
        for equipment_class in contract.equipment_classes
        for selector in equipment_class.selectors
        if selector.type == product_type and subtype in selector.subtypes
    ]
    if len(matches) > 1:
        raise AuditError(f"ambiguous equipment class for {product['organizer_id']}")
    return matches[0] if matches else None


def _assess_field(
    product: dict[str, Any],
    field: str,
    overlay: dict[str, Any] | None,
    contract: RuntimeEligibilityContract,
    base_evidence: dict[tuple[str, str], list[dict[str, str]]],
    external_evidence: dict[tuple[str, str], list[dict[str, str]]],
) -> FieldAssessment:
    organizer_id = str(product["organizer_id"])
    refs = _field_sources(organizer_id, field, base_evidence, external_evidence)
    spec_name = field.removeprefix("specs.")
    base_value = product.get("specs", {}).get(spec_name)
    overlay_value = (overlay or {}).get("fields", {}).get(spec_name)
    conflict_statuses = set(contract.policy.conflict_evidence_statuses)
    safe_statuses = set(contract.policy.safe_evidence_statuses)
    statuses = {
        value.get("evidence_status") or value.get("status")
        for value in (base_value, overlay_value)
        if isinstance(value, dict)
    }
    if statuses & conflict_statuses:
        availability: Availability = "CONFLICT"
    elif any(
        isinstance(value, dict)
        and (value.get("evidence_status") or value.get("status")) in safe_statuses
        and _has_value(value)
        for value in (base_value, overlay_value)
    ):
        availability = "MATCHING_SAFE"
    elif any(isinstance(value, dict) and _has_value(value) for value in (base_value, overlay_value)):
        availability = "LOCAL_CANDIDATE"
    else:
        availability = "MISSING"
    return FieldAssessment(field=field, availability=availability, sources=refs)


def _conflicts(
    assessments: list[FieldAssessment], overlay: dict[str, Any] | None
) -> list[Conflict]:
    result = [
        Conflict(
            field=item.field,
            reason="local evidence has conflicting or ambiguous model-specific values",
            sources=item.sources,
        )
        for item in assessments
        if item.availability == "CONFLICT"
    ]
    conflict_words = (" disagree", " differ", " versus ", " while ", " states both ")
    if overlay:
        all_sources = sorted(
            {
                (ref.source_id, ref.source_file, ref.evidence_status, ref.locator): ref
                for item in assessments
                for ref in item.sources
            }.values(),
            key=lambda ref: (ref.source_id, ref.source_file, ref.locator),
        )
        match_conflict = "CONFLICT" in str(overlay.get("match_status", ""))
        for reason in overlay.get("unresolved_issues", []):
            normalized = f" {str(reason).casefold()} "
            if result or match_conflict or any(word in normalized for word in conflict_words):
                result.append(
                    Conflict(
                        field="model_identity_or_revision",
                        reason=reason,
                        sources=all_sources,
                    )
                )
    return sorted(result, key=lambda item: (item.field, item.reason))


def _recommendation(status: Status, assessments: list[FieldAssessment]) -> Recommendation:
    if status in {"NOT_EQUIPMENT", "UNSUPPORTED_CAPACITY_PROFILE", "RUNTIME_READY"}:
        return "NO_ACTION"
    gaps = [item for item in assessments if item.availability != "MATCHING_SAFE"]
    local = status == "CONFLICT_REVIEW" or any(
        item.availability in {"LOCAL_CANDIDATE", "CONFLICT"} for item in gaps
    )
    absent = any(item.availability == "MISSING" for item in gaps)
    if local and absent:
        return "HYBRID"
    if local:
        return "LOCAL_ADAPTER"
    return "DEEP_RESEARCH"


def _audit_model(
    product: dict[str, Any],
    contract: RuntimeEligibilityContract,
    overlay_by_id: dict[str, dict[str, Any]],
    base_evidence: dict[tuple[str, str], list[dict[str, str]]],
    external_evidence: dict[tuple[str, str], list[dict[str, str]]],
) -> AuditItem:
    organizer_id = str(product["organizer_id"])
    equipment_class = _equipment_class(product, contract)
    required = (
        sorted(
            equipment_class.required_runtime_fields
            + equipment_class.capacity_profile.required_fields
        )
        if equipment_class
        else []
    )
    overlay = overlay_by_id.get(organizer_id)
    observed = {
        f"specs.{field}" for field in product.get("specs", {})
    } | {
        f"specs.{field}" for field in (overlay or {}).get("fields", {})
    }
    assessments = [
        _assess_field(
            product, field, overlay, contract, base_evidence, external_evidence
        )
        for field in sorted(set(required) | observed)
    ]
    required_assessments = [item for item in assessments if item.field in required]
    conflicts = _conflicts(assessments, overlay)
    if product["system_family"] in contract.policy.non_equipment_system_families:
        status: Status = "NOT_EQUIPMENT"
    elif conflicts:
        status = "CONFLICT_REVIEW"
    elif equipment_class is None:
        status = "UNSUPPORTED_CAPACITY_PROFILE"
    elif all(item.availability == "MATCHING_SAFE" for item in required_assessments):
        status = "RUNTIME_READY"
    else:
        status = "NEEDS_FACTS"
    missing = sorted(
        item.field
        for item in required_assessments
        if item.availability in {"MISSING", "LOCAL_CANDIDATE"}
    )
    product_source_files = {
        row["source_file"]
        for (subject_id, _), rows in base_evidence.items()
        if subject_id == organizer_id
        for row in rows
    }
    source_files = sorted(
        {"catalog_products.json"}
        | product_source_files
        | {ref.source_file for item in assessments for ref in item.sources}
        | ({"catalog_external_enrichment.json"} if overlay else set())
    )
    return AuditItem(
        id=organizer_id,
        model_id=organizer_id,
        name=str(product["name"]),
        source_row_number=None,
        equipment_class=equipment_class.code if equipment_class else None,
        capacity_profile=(equipment_class.capacity_profile.code if equipment_class else None),
        status=status,
        recommendation=_recommendation(status, assessments),
        required_fields=required,
        present_fields=[item for item in assessments if item.availability != "MISSING"],
        missing_fields=missing,
        conflicts=conflicts,
        source_files=source_files,
    )


def _coverage(items: list[AuditItem]) -> Coverage:
    availability = Counter(
        assessment.availability
        for item in items
        for assessment in item.present_fields
        if assessment.field in item.required_fields
    )
    missing = sum(len(item.missing_fields) for item in items) - availability["LOCAL_CANDIDATE"]
    total = sum(len(item.required_fields) for item in items)
    safe = availability["MATCHING_SAFE"]
    return Coverage(
        required_field_checks=total,
        matching_safe_field_checks=safe,
        local_candidate_field_checks=availability["LOCAL_CANDIDATE"],
        conflict_field_checks=availability["CONFLICT"],
        missing_field_checks=missing,
        matching_safe_percent=round(100 * safe / total, 2) if total else 0.0,
    )


def _inputs(bundle: Path, contract_path: Path) -> list[InputFile]:
    definitions = [
        (contract_path, "CONTRACT", False),
        (bundle / "manifest.json", "PROVENANCE", False),
        (bundle / "catalog_products.json", "BASE", True),
        (bundle / "catalog_applicability.csv", "BASE", False),
        (bundle / "catalog_prices.csv", "BASE", False),
        (bundle / "catalog_field_evidence.csv", "EVIDENCE", True),
        (bundle / "catalog_external_enrichment.json", "OVERLAY", True),
        (bundle / "catalog_external_evidence.csv", "EVIDENCE", True),
        (bundle / "catalog_description_overlay.json", "OVERLAY", False),
        (bundle / "catalog_description_report.json", "PROVENANCE", False),
    ]
    result = []
    for path, role, runtime_eligible in definitions:
        if not path.is_file():
            raise AuditError(f"required local audit input is missing: {path.name}")
        result.append(
            InputFile(
                path=path.relative_to(ROOT).as_posix(),
                sha256=_sha256(path),
                size_bytes=path.stat().st_size,
                role=role,
                runtime_eligible=runtime_eligible,
            )
        )
    return sorted(result, key=lambda item: item.path)


def build_report(
    bundle: Path = DEFAULT_BUNDLE, contract_path: Path = DEFAULT_CONTRACT
) -> AuditReport:
    contract = load_contract(contract_path)
    try:
        load_catalog_bundle(bundle)
    except CatalogBundleError as exc:
        raise AuditError("catalog bundle checksum/contract validation failed") from exc
    manifest = _read_json(bundle / "manifest.json")
    products = _read_json(bundle / "catalog_products.json").get("products")
    enrichment = _read_json(bundle / "catalog_external_enrichment.json").get("products")
    description_overlay = _read_json(bundle / "catalog_description_overlay.json")
    description_report = _read_json(bundle / "catalog_description_report.json")
    applicability = _read_csv(bundle / "catalog_applicability.csv")
    prices = _read_csv(bundle / "catalog_prices.csv")
    base_rows = _read_csv(bundle / "catalog_field_evidence.csv")
    external_rows = _read_csv(bundle / "catalog_external_evidence.csv")
    if not isinstance(products, list) or not isinstance(enrichment, list):
        raise AuditError("catalog product/enrichment collections are invalid")
    if len(products) != 187 or len(applicability) != 223 or len(prices) != 223:
        raise AuditError("catalog audit input counts differ from 187/223/223")
    if len(description_overlay.get("entries", [])) != 223:
        raise AuditError("description overlay must cover exactly 223 positions")
    if (
        description_report.get("positions_total") != 223
        or description_report.get("mapped") != 223
        or description_report.get("unresolved") != 0
        or description_report.get("runtime_facts_created") != 0
    ):
        raise AuditError("description coverage/provenance report differs")
    expected = manifest.get("expected_counts", {})
    if expected.get("products") != 187 or expected.get("catalog_source_rows") != 223:
        raise AuditError("manifest exact counts differ")

    overlays = {str(item["organizer_id"]): item for item in enrichment}
    base_evidence: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in base_rows:
        if row["entity_type"] == "product":
            base_evidence[(row["entity_id"], row["field_path"])].append(row)
    external_evidence: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in external_rows:
        external_evidence[(row["organizer_id"], row["field_path"])].append(row)

    models = sorted(
        (
            _audit_model(
                product, contract, overlays, base_evidence, external_evidence
            )
            for product in products
        ),
        key=lambda item: item.id,
    )
    model_by_id = {item.model_id: item for item in models}
    positions = []
    prices_by_row = {int(row["original_row"]): row for row in prices}
    for row in sorted(applicability, key=lambda value: int(value["original_row"])):
        row_number = int(row["original_row"])
        model = model_by_id[row["organizer_id"]]
        price = prices_by_row[row_number]
        position_sources = sorted(
            set(model.source_files) | {row["source_file"], price["source_file"]}
        )
        positions.append(
            model.model_copy(
                update={
                    "id": f"catalog-v4-row-{row_number:04d}",
                    "source_row_number": row_number,
                    "source_files": position_sources,
                },
                deep=True,
            )
        )

    statuses = [
        "RUNTIME_READY",
        "NEEDS_FACTS",
        "CONFLICT_REVIEW",
        "UNSUPPORTED_CAPACITY_PROFILE",
        "NOT_EQUIPMENT",
    ]
    recommendations = ["LOCAL_ADAPTER", "DEEP_RESEARCH", "HYBRID", "NO_ACTION"]
    model_status = Counter(item.status for item in models)
    position_status = Counter(item.status for item in positions)
    model_recommendations = Counter(item.recommendation for item in models)
    position_recommendations = Counter(item.recommendation for item in positions)
    class_counts = Counter(item.equipment_class or "UNSUPPORTED" for item in models)
    report = AuditReport(
        schema_version="catalog-runtime-eligibility-audit-v1",
        contract_version=contract.schema_version,
        catalog_code=contract.catalog_code,
        deterministic_order="models:organizer_id;positions:source_row_number",
        inputs=_inputs(bundle, contract_path),
        counts={"models": len(models), "positions": len(positions)},
        model_status_counts={key: model_status[key] for key in statuses},
        position_status_counts={key: position_status[key] for key in statuses},
        recommendation_counts={
            "models": {key: model_recommendations[key] for key in recommendations},
            "positions": {key: position_recommendations[key] for key in recommendations},
        },
        equipment_class_counts={key: class_counts[key] for key in sorted(class_counts)},
        model_coverage=_coverage(models),
        position_coverage=_coverage(positions),
        exclusions=[
            "catalog_description_overlay.json is presentation-only and creates no runtime facts",
            "catalog prices and economics are outside this audit",
            "capacity formulas and runtime activation are outside this audit",
            "no network, OCR, scraper, parser, or inferred specification was used",
        ],
        models=models,
        positions=positions,
    )
    return AuditReport.model_validate(report.model_dump(mode="json"))


def report_bytes(report: AuditReport) -> bytes:
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def schema_bytes(model: type[BaseModel]) -> bytes:
    return (
        json.dumps(
            model.model_json_schema(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def summary_text(report: AuditReport) -> str:
    status_rows = "\n".join(
        f"| {status} | {report.model_status_counts[status]} | {report.position_status_counts[status]} |"
        for status in report.model_status_counts
    )
    recommendation_rows = "\n".join(
        f"| {value} | {report.recommendation_counts['models'][value]} | {report.recommendation_counts['positions'][value]} |"
        for value in report.recommendation_counts["models"]
    )
    class_rows = "\n".join(
        f"| {code} | {count} |" for code, count in report.equipment_class_counts.items()
    )
    model_missing = Counter(field for item in report.models for field in item.missing_fields)
    position_missing = Counter(field for item in report.positions for field in item.missing_fields)
    missing_rows = "\n".join(
        f"| {field} | {model_missing[field]} | {position_missing[field]} |"
        for field in sorted(set(model_missing) | set(position_missing))
    )
    conflict_models = [item for item in report.models if item.conflicts]
    conflict_lines = []
    for item in conflict_models:
        fields = sorted(
            {conflict.field for conflict in item.conflicts if conflict.field != "model_identity_or_revision"}
        )
        issues = [
            conflict.reason
            for conflict in item.conflicts
            if conflict.field == "model_identity_or_revision"
        ]
        details = ([f"fields: {', '.join(fields)}"] if fields else []) + issues
        conflict_lines.append(f"- `{item.model_id}` — {item.name}: " + "; ".join(details))
    conflict_rows = "\n".join(conflict_lines) or "- Конфликтов не найдено."
    model = report.model_coverage
    position = report.position_coverage
    return f"""# Runtime eligibility gap audit — organizer catalog v4

Версии: `{report.contract_version}` / `{report.schema_version}`. Аудит использует только коммитнутые локальные base/overlay/evidence/provenance данные. Порядок детерминирован: модели по `organizer_id`, позиции по `source_row_number`.

## Точное покрытие

- 187 model identities из 187.
- 223 catalog positions из 223; позиции не склеены и наследуют аудит своей model identity.
- Description overlay проверен для всех 223 позиций, но исключён из runtime facts по контракту.
- Runtime source не переключён; capacity formulas, economics и procurement не выполнялись.

| Статус | Модели | Позиции |
|---|---:|---:|
{status_rows}

## Классы и capacity profiles

| Класс | Модели |
|---|---:|
{class_rows}

Контракт фиксирует profiles `TRANSPORT_CYCLE_V1`, `DELIVERY_CYCLE_V1`, `CLEANING_AREA_V1` и `PALLETIZING_THROUGHPUT_V1`. Он определяет только обязательные входы; формул в этой итерации нет.

## Покрытие обязательных полей

| Уровень | Проверок полей | Matching-safe | Local candidate | Conflict | Missing | Safe coverage |
|---|---:|---:|---:|---:|---:|---:|
| Models | {model.required_field_checks} | {model.matching_safe_field_checks} | {model.local_candidate_field_checks} | {model.conflict_field_checks} | {model.missing_field_checks} | {model.matching_safe_percent:.2f}% |
| Positions | {position.required_field_checks} | {position.matching_safe_field_checks} | {position.local_candidate_field_checks} | {position.conflict_field_checks} | {position.missing_field_checks} | {position.matching_safe_percent:.2f}% |

### Пробелы по обязательным полям

| Поле | Модели | Позиции |
|---|---:|---:|
{missing_rows}

## Следующее обогащение

| Рекомендация | Модели | Позиции |
|---|---:|---:|
{recommendation_rows}

`LOCAL_ADAPTER` означает, что все блокирующие поля уже имеют локальные candidate observations; `DEEP_RESEARCH` — локальных значений для пробелов нет; `HYBRID` — нужны и разбор локального evidence/conflicts, и поиск отсутствующих фактов; `NO_ACTION` — enrichment не снимает текущий тип блокировки или не нужен.

## Конфликты

{conflict_rows}

## Decision gate

Следующий этап: `catalog/official-source-enrichment`. Он должен брать точный список полей и рекомендации из machine-readable отчёта. После него — `engine/capacity-formula-trace`; runtime требует явно активированную безопасную projection.
"""


def _check(path: Path, expected: bytes) -> None:
    if not path.is_file() or path.read_bytes() != expected:
        raise AuditError(f"generated artifact differs: {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report(args.bundle.resolve(), args.contract.resolve())
    report_payload = report_bytes(report)
    summary_payload = summary_text(report).encode("utf-8")
    if args.check:
        _check(DEFAULT_REPORT, report_payload)
        _check(DEFAULT_SUMMARY, summary_payload)
        _check(DEFAULT_CONTRACT_SCHEMA, schema_bytes(RuntimeEligibilityContract))
        _check(DEFAULT_REPORT_SCHEMA, schema_bytes(AuditReport))
    else:
        DEFAULT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_REPORT.write_bytes(report_payload)
        DEFAULT_SUMMARY.write_bytes(summary_payload)
        DEFAULT_CONTRACT_SCHEMA.write_bytes(schema_bytes(RuntimeEligibilityContract))
        DEFAULT_REPORT_SCHEMA.write_bytes(schema_bytes(AuditReport))
    print(
        json.dumps(
            {
                "models": report.counts["models"],
                "positions": report.counts["positions"],
                "model_status_counts": report.model_status_counts,
                "position_status_counts": report.position_status_counts,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
