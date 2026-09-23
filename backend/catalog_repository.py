"""Catalog repository boundary for versioned and activated snapshots.

The PostgreSQL adapter requires an explicit immutable version and reads matching
facts only from the evidence-gated ``matching_spec_facts`` view.  Slot lookup is
separate so one request always calculates against one resolved snapshot.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from catalog_models import (
    CatalogMediaAsset,
    CatalogPositionEnrichment,
    CatalogPositionMedia,
    CatalogSourceRow,
    EquipmentApplicability,
    EquipmentModel,
    FieldEvidence,
    Manufacturer,
    ProcurementOption,
)
from database import Database
from models import Robot
from sqlalchemy import select, text
from storage_models import CatalogActivation, CatalogVersion


class CatalogRepositoryError(RuntimeError):
    """Raised when a requested catalog snapshot cannot be loaded safely."""


@dataclass(frozen=True)
class CatalogVersionDTO:
    id: str
    code: str
    status: str
    schema_version: str
    content_sha256: str | None = None


@dataclass(frozen=True)
class CatalogFactDTO:
    code: str
    scope_code: str
    value: Any
    canonical_unit: str
    resolution_status: str
    evidence_id: str


@dataclass(frozen=True)
class CatalogApplicabilityDTO:
    industry: str | None
    scenario: str | None
    region: str | None
    case_text: str | None
    id: str | None = None
    source_row_id: str | None = None


@dataclass(frozen=True)
class ProcurementOptionDTO:
    mode: str
    amount: Decimal | None
    currency: str | None
    price_status: str
    vat_status: str
    included_costs: tuple[Any, ...]
    excluded_costs: tuple[Any, ...]
    evidence_id: str | None
    id: str | None = None
    source_row_id: str | None = None
    raw_price: str | None = None
    vat_rate: Decimal | None = None
    currency_provenance: str | None = None
    vat_provenance: str | None = None
    evidence_status: str | None = None
    observed_on: date | None = None
    valid_until: date | None = None
    verified_quotes: tuple[dict[str, Any], ...] = ()
    procurement_assertions: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class CapacityRuntimeDTO:
    calculation_readiness_status: str
    calculation_ready: bool
    calculation_requires_assumptions: bool
    calculation_profile: str | None
    calculation_blockers: tuple[str, ...]
    runtime_catalog_version: str | None
    calculation_model_fields: tuple[str, ...] = ()
    vendor_facts: tuple[CatalogFactDTO, ...] = ()
    scenario_assumptions: tuple[dict[str, Any], ...] = ()
    provenance: dict[str, Any] | None = None
    deployment_readiness_status: str | None = None


@dataclass(frozen=True)
class FormulaExecutabilityCatalogDTO:
    """Cost-free repository projection consumed by the C06 resolver."""

    model_id: str
    position_id: str | None
    name: str
    system_family: str
    profile_id: str | None
    readiness_v2_status: str
    calculation_model_fields: tuple[str, ...]
    vendor_facts: tuple[CatalogFactDTO, ...]


@dataclass(frozen=True)
class CatalogModelDTO:
    id: str
    source_namespace: str
    source_record_key: str
    organizer_id: str | None
    manufacturer: str | None
    name: str
    system_family: str
    type_code: str
    subtype_code: str | None
    maturity_status: str | None
    trl: int | None
    description: str | None
    attributes: dict[str, Any]
    facts: tuple[CatalogFactDTO, ...]
    applicability: tuple[CatalogApplicabilityDTO, ...]
    procurement_options: tuple[ProcurementOptionDTO, ...]
    runtime_robot: dict[str, Any] | None
    runtime_blockers: tuple[str, ...]
    capacity_runtime: CapacityRuntimeDTO = field(
        default_factory=lambda: CapacityRuntimeDTO(
            calculation_readiness_status="CALCULATION_BLOCKED",
            calculation_ready=False,
            calculation_requires_assumptions=False,
            calculation_profile=None,
            calculation_blockers=("capacity_runtime",),
            runtime_catalog_version=None,
        )
    )

    def runtime_dict(self) -> dict[str, Any] | None:
        """Return an isolated mutable value for the existing calculation core."""

        return copy.deepcopy(self.runtime_robot)

    def formula_executability_dto(
        self, *, position_id: str | None = None
    ) -> FormulaExecutabilityCatalogDTO:
        return FormulaExecutabilityCatalogDTO(
            model_id=self.id,
            position_id=position_id,
            name=self.name,
            system_family=self.system_family,
            profile_id=self.capacity_runtime.calculation_profile,
            readiness_v2_status=self.capacity_runtime.calculation_readiness_status,
            calculation_model_fields=self.capacity_runtime.calculation_model_fields,
            vendor_facts=self.capacity_runtime.vendor_facts,
        )


@dataclass(frozen=True)
class CatalogMediaDTO:
    id: str
    sha256: str
    media_type: str
    byte_size: int
    width_px: int
    height_px: int
    storage_key: str
    source_page: int
    source_slot: int


@dataclass(frozen=True)
class CatalogEnrichmentDTO:
    description_raw: str
    description_normalized: str
    existing_description: str | None
    description_status: str
    mapping_status: str
    source_page: int
    source_slot: int
    transcript_sha256: str
    media_sha256: str
    adapter: str
    fields: dict[str, Any]
    limitation: str


@dataclass(frozen=True)
class CatalogPositionDTO:
    id: str
    source_record_key: str
    source_row_number: int
    model: CatalogModelDTO
    applicability: CatalogApplicabilityDTO
    procurement_option: ProcurementOptionDTO
    media: CatalogMediaDTO | None
    runtime_robot: dict[str, Any] | None
    runtime_blockers: tuple[str, ...]
    enrichment: CatalogEnrichmentDTO | None = None

    def runtime_dict(self) -> dict[str, Any] | None:
        return copy.deepcopy(self.runtime_robot)

    def formula_executability_dto(self) -> FormulaExecutabilityCatalogDTO:
        return self.model.formula_executability_dto(position_id=self.id)


@dataclass(frozen=True)
class CatalogSnapshotDTO:
    version: CatalogVersionDTO
    models: tuple[CatalogModelDTO, ...]
    positions: tuple[CatalogPositionDTO, ...] = ()

    def by_source_key(self) -> dict[str, CatalogModelDTO]:
        return {model.source_record_key: model for model in self.models}

    def runtime_robots(self) -> list[dict[str, Any]]:
        robots: list[dict[str, Any]] = []
        candidates: tuple[CatalogPositionDTO | CatalogModelDTO, ...]
        candidates = self.positions or self.models
        for candidate in candidates:
            runtime_robot = candidate.runtime_dict()
            if runtime_robot is not None:
                robots.append(runtime_robot)
        return robots

    def calculation_ready_models(self) -> tuple[CatalogModelDTO, ...]:
        return tuple(model for model in self.models if model.capacity_runtime.calculation_ready)

    def calculation_ready_positions(self) -> tuple[CatalogPositionDTO, ...]:
        return tuple(
            position
            for position in self.positions
            if position.model.capacity_runtime.calculation_ready
        )


class CatalogRepository(Protocol):
    def load(self) -> CatalogSnapshotDTO:
        """Load one immutable, explicitly scoped catalog snapshot."""


_DEFAULT_FACT_BINDINGS: dict[str, tuple[str, ...]] = {
    "payload_kg": ("payload", "payload_kg"),
    "max_speed_m_s": ("max_speed", "max_speed_m_s"),
    "min_aisle_width_m": ("min_aisle_width", "min_aisle_width_m"),
    "autonomy_hours": ("autonomy", "autonomy_hours"),
    "navigation_type": ("navigation", "navigation_type"),
}


def _fact_value(row: dict[str, Any]) -> Any:
    for column in ("numeric_value", "text_value", "boolean_value", "json_value"):
        value = row[column]
        if value is not None:
            return copy.deepcopy(value)
    raise CatalogRepositoryError("matching fact has no typed value")


def _capacity_runtime(
    attributes: dict[str, Any], facts: tuple[CatalogFactDTO, ...]
) -> CapacityRuntimeDTO:
    raw = copy.deepcopy(attributes.get("capacity_runtime"))
    if not isinstance(raw, dict):
        return CapacityRuntimeDTO(
            calculation_readiness_status="CALCULATION_BLOCKED",
            calculation_ready=False,
            calculation_requires_assumptions=False,
            calculation_profile=None,
            calculation_blockers=("capacity_runtime",),
            runtime_catalog_version=None,
        )
    status = raw.get("calculation_readiness_status")
    ready = raw.get("calculation_ready") is True
    requires_assumptions = raw.get("calculation_requires_assumptions") is True
    profile = raw.get("calculation_profile")
    blockers = raw.get("calculation_blockers")
    model_fields = raw.get("calculation_model_fields")
    assumptions = raw.get("scenario_assumptions")
    runtime_version = raw.get("runtime_catalog_version")
    provenance = raw.get("provenance")
    deployment_status = raw.get("deployment_readiness_status")
    ready_statuses = {
        "CALCULATION_READY",
        "CALCULATION_READY_WITH_ASSUMPTIONS",
    }
    if (
        not isinstance(status, str)
        or status
        not in {
            *ready_statuses,
            "CALCULATION_BLOCKED",
            "UNSUPPORTED_CAPACITY_PROFILE",
            "NOT_EQUIPMENT",
        }
        or ready != (status in ready_statuses)
        or requires_assumptions
        != (status == "CALCULATION_READY_WITH_ASSUMPTIONS")
        or (ready and not isinstance(profile, str))
        or (ready and blockers)
        or (not ready and not blockers)
        or not isinstance(blockers, list)
        or not all(isinstance(item, str) and item for item in blockers)
        or not isinstance(model_fields, list)
        or not all(isinstance(item, str) and item for item in model_fields)
        or not isinstance(assumptions, list)
        or not all(isinstance(item, dict) for item in assumptions)
        or requires_assumptions != bool(assumptions)
        or any(
            item.get("vendor_fact") is not False
            or not isinstance(item.get("provenance"), str)
            for item in assumptions
        )
        or not isinstance(runtime_version, str)
        or deployment_status == "DEPLOYMENT_READY"
    ):
        return CapacityRuntimeDTO(
            calculation_readiness_status="CALCULATION_BLOCKED",
            calculation_ready=False,
            calculation_requires_assumptions=False,
            calculation_profile=None,
            calculation_blockers=("capacity_runtime:invalid_contract",),
            runtime_catalog_version=None,
        )
    facts_by_code = {fact.code: fact for fact in facts}
    required_codes = [field.split(".", 1)[-1] for field in model_fields]
    missing = [code for code in required_codes if code not in facts_by_code]
    if ready and missing:
        return CapacityRuntimeDTO(
            calculation_readiness_status="CALCULATION_BLOCKED",
            calculation_ready=False,
            calculation_requires_assumptions=False,
            calculation_profile=profile if isinstance(profile, str) else None,
            calculation_blockers=tuple(
                f"matching_fact:{code}" for code in sorted(missing)
            ),
            runtime_catalog_version=runtime_version,
            calculation_model_fields=tuple(model_fields),
            provenance=provenance if isinstance(provenance, dict) else None,
            deployment_readiness_status=(
                deployment_status if isinstance(deployment_status, str) else None
            ),
        )
    vendor_facts = tuple(
        facts_by_code[code] for code in required_codes if code in facts_by_code
    )
    return CapacityRuntimeDTO(
        calculation_readiness_status=status,
        calculation_ready=ready,
        calculation_requires_assumptions=requires_assumptions,
        calculation_profile=profile if isinstance(profile, str) else None,
        calculation_blockers=tuple(blockers),
        runtime_catalog_version=runtime_version,
        calculation_model_fields=tuple(model_fields),
        vendor_facts=vendor_facts,
        scenario_assumptions=tuple(assumptions),
        provenance=provenance if isinstance(provenance, dict) else None,
        deployment_readiness_status=(
            deployment_status if isinstance(deployment_status, str) else None
        ),
    )


def _as_runtime_number(value: Any, unit: str, target: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("value is not numeric")
    number = float(value)
    normalized_unit = unit.strip().lower()
    if target == "payload_kg":
        factors = {"kg": 1.0, "g": 0.001, "t": 1000.0}
    elif target == "max_speed_m_s":
        factors = {"m/s": 1.0, "m_s": 1.0, "km/h": 1.0 / 3.6}
    elif target == "min_aisle_width_m":
        factors = {"m": 1.0, "cm": 0.01, "mm": 0.001}
    elif target == "autonomy_hours":
        factors = {"h": 1.0, "hour": 1.0, "min": 1.0 / 60.0}
    else:
        return number
    if normalized_unit not in factors:
        raise ValueError("unsupported canonical unit")
    return number * factors[normalized_unit]


def _project_runtime_robot(
    model: EquipmentModel,
    facts: tuple[CatalogFactDTO, ...],
    procurement: tuple[ProcurementOptionDTO, ...],
    *,
    runtime_id: str | None = None,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Build an engine payload only from an explicit projection plus safe facts."""

    attributes = copy.deepcopy(model.attributes or {})
    projection = attributes.get("runtime_projection")
    if not isinstance(projection, dict):
        return None, ("runtime_projection",)

    payload = copy.deepcopy(projection)
    payload.setdefault("id", runtime_id or model.source_record_key)
    payload.setdefault("name", model.name)
    payload.setdefault("description", model.description or "")
    specs = payload.get("specs")
    if not isinstance(specs, dict):
        specs = {}
        payload["specs"] = specs

    custom_bindings = attributes.get("runtime_fact_bindings", {})
    if not isinstance(custom_bindings, dict):
        custom_bindings = {}
    facts_by_code = {fact.code: fact for fact in facts}
    blockers: list[str] = []
    for target, defaults in _DEFAULT_FACT_BINDINGS.items():
        configured = custom_bindings.get(target)
        codes = (configured,) if isinstance(configured, str) else defaults
        fact = next(
            (facts_by_code[code] for code in codes if code in facts_by_code), None
        )
        if fact is None:
            blockers.append(f"matching_fact:{target}")
            continue
        try:
            if target == "navigation_type":
                if not isinstance(fact.value, str) or not fact.value.strip():
                    raise ValueError("navigation is not text")
                specs[target] = fact.value
            else:
                specs[target] = _as_runtime_number(
                    fact.value, fact.canonical_unit, target
                )
        except ValueError:
            blockers.append(f"matching_fact:{target}:invalid_value_or_unit")

    economics = payload.get("economics")
    if not isinstance(economics, dict):
        blockers.append("runtime_projection:economics")
    else:
        amounts = {
            option.amount
            for option in procurement
            if option.mode == "PURCHASE"
            and option.price_status == "NORMALIZED"
            and option.currency == "RUB"
            and option.amount is not None
        }
        if len(amounts) == 1:
            economics["robot_capex_rub"] = float(next(iter(amounts)))
        elif len(amounts) > 1:
            blockers.append("procurement_option:ambiguous_purchase_amount")

    if blockers:
        return None, tuple(sorted(set(blockers)))
    try:
        validated = Robot.model_validate(payload).model_dump(mode="json")
    except Exception:
        return None, ("runtime_projection:invalid_robot_contract",)
    return validated, ()


class PostgresCatalogRepository:
    """Read one explicit PostgreSQL catalog version."""

    def __init__(self, database: Database, catalog_version_code: str) -> None:
        code = catalog_version_code.strip()
        if not code:
            raise CatalogRepositoryError("catalog version code is required")
        self._database = database
        self._catalog_version_code = code

    def load(self) -> CatalogSnapshotDTO:
        with self._database.session() as session:
            version = session.scalar(
                select(CatalogVersion).where(
                    CatalogVersion.code == self._catalog_version_code
                )
            )
            if version is None:
                raise CatalogRepositoryError("catalog version was not found")

            model_rows = session.execute(
                select(EquipmentModel, Manufacturer.name)
                .outerjoin(
                    Manufacturer,
                    (Manufacturer.id == EquipmentModel.manufacturer_id)
                    & (
                        Manufacturer.catalog_version_id
                        == EquipmentModel.catalog_version_id
                    ),
                )
                .where(EquipmentModel.catalog_version_id == version.id)
                .order_by(EquipmentModel.source_record_key)
            ).all()
            source_rows = session.scalars(
                select(CatalogSourceRow)
                .where(CatalogSourceRow.catalog_version_id == version.id)
                .order_by(CatalogSourceRow.source_row_number)
            ).all()
            applicability_rows = session.scalars(
                select(EquipmentApplicability)
                .where(EquipmentApplicability.catalog_version_id == version.id)
                .order_by(
                    EquipmentApplicability.equipment_model_id,
                    EquipmentApplicability.id,
                )
            ).all()
            procurement_rows = session.scalars(
                select(ProcurementOption)
                .where(ProcurementOption.catalog_version_id == version.id)
                .order_by(
                    ProcurementOption.equipment_model_id,
                    ProcurementOption.id,
                )
            ).all()
            procurement_evidence_rows = session.scalars(
                select(FieldEvidence).where(
                    FieldEvidence.catalog_version_id == version.id,
                    FieldEvidence.subject_type == "PRICE_OFFER",
                )
            ).all()
            matching_rows = (
                session.execute(
                    text(
                        """
                    SELECT id, equipment_model_id, spec_code, scope_code,
                           numeric_value, text_value, boolean_value, json_value,
                           canonical_unit, resolution_status, primary_evidence_id
                    FROM matching_spec_facts
                    WHERE catalog_version_id = :version_id
                    ORDER BY equipment_model_id, spec_code, scope_code, id
                    """
                    ),
                    {"version_id": version.id},
                )
                .mappings()
                .all()
            )
            media_rows = session.execute(
                select(CatalogPositionMedia, CatalogMediaAsset)
                .join(
                    CatalogMediaAsset,
                    (CatalogMediaAsset.id == CatalogPositionMedia.media_asset_id)
                    & (
                        CatalogMediaAsset.catalog_version_id
                        == CatalogPositionMedia.catalog_version_id
                    ),
                )
                .where(CatalogPositionMedia.catalog_version_id == version.id)
            ).all()
            enrichment_rows = session.scalars(
                select(CatalogPositionEnrichment).where(
                    CatalogPositionEnrichment.catalog_version_id == version.id
                )
            ).all()

            applicability_by_model: dict[uuid.UUID, list[CatalogApplicabilityDTO]] = {}
            applicability_by_source: dict[uuid.UUID, CatalogApplicabilityDTO] = {}
            applicability_model_by_source: dict[uuid.UUID, uuid.UUID] = {}
            for row in applicability_rows:
                item = CatalogApplicabilityDTO(
                    industry=row.industry,
                    scenario=row.scenario,
                    region=row.region,
                    case_text=row.case_text,
                    id=str(row.id),
                    source_row_id=str(row.catalog_source_row_id),
                )
                applicability_by_model.setdefault(row.equipment_model_id, []).append(
                    item
                )
                if row.catalog_source_row_id in applicability_by_source:
                    raise CatalogRepositoryError(
                        "source row has duplicate applicability"
                    )
                applicability_by_source[row.catalog_source_row_id] = item
                applicability_model_by_source[row.catalog_source_row_id] = (
                    row.equipment_model_id
                )

            procurement_by_model: dict[uuid.UUID, list[ProcurementOptionDTO]] = {}
            procurement_by_source: dict[uuid.UUID, ProcurementOptionDTO] = {}
            procurement_model_by_source: dict[uuid.UUID, uuid.UUID] = {}
            procurement_evidence = {row.id: row for row in procurement_evidence_rows}
            for row in procurement_rows:
                evidence = procurement_evidence.get(row.field_evidence_id)
                item = ProcurementOptionDTO(
                    mode=row.procurement_mode,
                    amount=row.amount,
                    currency=row.currency,
                    price_status=row.price_status,
                    vat_status=row.vat_status,
                    included_costs=tuple(copy.deepcopy(row.included_costs)),
                    excluded_costs=tuple(copy.deepcopy(row.excluded_costs)),
                    evidence_id=(
                        str(row.field_evidence_id)
                        if row.field_evidence_id is not None
                        else None
                    ),
                    id=str(row.id),
                    source_row_id=str(row.catalog_source_row_id),
                    raw_price=row.raw_price,
                    vat_rate=row.vat_rate,
                    currency_provenance=row.currency_provenance,
                    vat_provenance=row.vat_provenance,
                    evidence_status=None if evidence is None else evidence.evidence_status,
                    observed_on=None if evidence is None else evidence.observed_at.date(),
                )
                procurement_by_model.setdefault(row.equipment_model_id, []).append(item)
                if row.catalog_source_row_id in procurement_by_source:
                    raise CatalogRepositoryError(
                        "source row has duplicate procurement option"
                    )
                procurement_by_source[row.catalog_source_row_id] = item
                procurement_model_by_source[row.catalog_source_row_id] = (
                    row.equipment_model_id
                )

            media_by_source: dict[uuid.UUID, CatalogMediaDTO] = {}
            for link, asset in media_rows:
                media_by_source[link.catalog_source_row_id] = CatalogMediaDTO(
                    id=str(asset.id),
                    sha256=asset.sha256,
                    media_type=asset.media_type,
                    byte_size=asset.byte_size,
                    width_px=asset.width_px,
                    height_px=asset.height_px,
                    storage_key=asset.storage_key,
                    source_page=link.source_page,
                    source_slot=link.source_slot,
                )

            enrichment_by_source = {
                row.catalog_source_row_id: CatalogEnrichmentDTO(
                    description_raw=row.description_raw,
                    description_normalized=row.description_normalized,
                    existing_description=row.existing_description_snapshot,
                    description_status=row.description_status,
                    mapping_status=row.mapping_status,
                    source_page=row.source_page,
                    source_slot=row.source_slot,
                    transcript_sha256=row.transcript_sha256,
                    media_sha256=row.media_sha256,
                    adapter=row.adapter,
                    fields=copy.deepcopy(row.normalized_fields),
                    limitation=row.limitation,
                )
                for row in enrichment_rows
            }

            facts_by_model: dict[uuid.UUID, list[CatalogFactDTO]] = {}
            for row in matching_rows:
                raw = dict(row)
                facts_by_model.setdefault(raw["equipment_model_id"], []).append(
                    CatalogFactDTO(
                        code=raw["spec_code"],
                        scope_code=raw["scope_code"],
                        value=_fact_value(raw),
                        canonical_unit=raw["canonical_unit"],
                        resolution_status=raw["resolution_status"],
                        evidence_id=str(raw["primary_evidence_id"]),
                    )
                )

            models: list[CatalogModelDTO] = []
            model_entities: dict[uuid.UUID, EquipmentModel] = {}
            model_dtos: dict[uuid.UUID, CatalogModelDTO] = {}
            for model, manufacturer_name in model_rows:
                facts = tuple(facts_by_model.get(model.id, ()))
                applicability = tuple(applicability_by_model.get(model.id, ()))
                procurement = tuple(procurement_by_model.get(model.id, ()))
                capacity_runtime = _capacity_runtime(model.attributes or {}, facts)
                runtime_robot, blockers = _project_runtime_robot(
                    model, facts, procurement
                )
                item = CatalogModelDTO(
                    id=str(model.id),
                    source_namespace=model.source_namespace,
                    source_record_key=model.source_record_key,
                    organizer_id=(
                        str(model.organizer_id)
                        if model.organizer_id is not None
                        else None
                    ),
                    manufacturer=manufacturer_name,
                    name=model.name,
                    system_family=model.system_family,
                    type_code=model.type_code,
                    subtype_code=model.subtype_code,
                    maturity_status=model.maturity_status,
                    trl=model.trl,
                    description=model.description,
                    attributes=copy.deepcopy(model.attributes),
                    facts=facts,
                    applicability=applicability,
                    procurement_options=procurement,
                    runtime_robot=runtime_robot,
                    runtime_blockers=blockers,
                    capacity_runtime=capacity_runtime,
                )
                models.append(item)
                model_entities[model.id] = model
                model_dtos[model.id] = item

            positions: list[CatalogPositionDTO] = []
            for source_row in source_rows:
                applicability = applicability_by_source.get(source_row.id)
                procurement = procurement_by_source.get(source_row.id)
                if applicability is None or procurement is None:
                    raise CatalogRepositoryError(
                        "source row must have one applicability and procurement option"
                    )
                model_id = applicability_model_by_source[source_row.id]
                if model_id != procurement_model_by_source[source_row.id]:
                    raise CatalogRepositoryError("source row model links disagree")
                model_entity = model_entities[model_id]
                model_dto = model_dtos[model_id]
                runtime_robot, blockers = _project_runtime_robot(
                    model_entity,
                    model_dto.facts,
                    (procurement,),
                    runtime_id=source_row.source_record_key,
                )
                positions.append(
                    CatalogPositionDTO(
                        id=str(source_row.id),
                        source_record_key=source_row.source_record_key,
                        source_row_number=source_row.source_row_number,
                        model=model_dto,
                        applicability=applicability,
                        procurement_option=procurement,
                        media=media_by_source.get(source_row.id),
                        runtime_robot=runtime_robot,
                        runtime_blockers=blockers,
                        enrichment=enrichment_by_source.get(source_row.id),
                    )
                )

            return CatalogSnapshotDTO(
                version=CatalogVersionDTO(
                    id=str(version.id),
                    code=version.code,
                    status=version.status,
                    schema_version=version.schema_version,
                    content_sha256=version.content_sha256,
                ),
                models=tuple(models),
                positions=tuple(positions),
            )


class ActivatedCatalogRepository:
    """Resolve the current atomic activation, then load that immutable version."""

    def __init__(self, database: Database, slot: str) -> None:
        normalized = slot.strip()
        if normalized not in {"capacity", "discovery", "runtime"}:
            raise CatalogRepositoryError("catalog activation slot is unsupported")
        self._database = database
        self._slot = normalized

    def load(self) -> CatalogSnapshotDTO:
        with self._database.session() as session:
            row = session.execute(
                select(CatalogActivation, CatalogVersion)
                .join(
                    CatalogVersion,
                    CatalogVersion.id == CatalogActivation.catalog_version_id,
                )
                .where(
                    CatalogActivation.slot == self._slot,
                    CatalogActivation.deactivated_at.is_(None),
                )
            ).one_or_none()
            if row is None:
                raise CatalogRepositoryError("catalog activation was not found")
            _, version = row
            if version.status != "PUBLISHED":
                raise CatalogRepositoryError("active catalog is not published")
            version_code = version.code
        # Published domain rows are immutable.  Loading outside the short slot
        # lookup transaction cannot produce a mixed-version snapshot.
        return PostgresCatalogRepository(self._database, version_code).load()
