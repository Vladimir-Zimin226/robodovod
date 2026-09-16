"""Catalog repository boundary for legacy, versioned and activated snapshots.

The PostgreSQL adapter requires an explicit immutable version and reads matching
facts only from the evidence-gated ``matching_spec_facts`` view.  Slot lookup is
separate so one request always calculates against one resolved snapshot.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from catalog_models import (
    EquipmentApplicability,
    EquipmentModel,
    Manufacturer,
    ProcurementOption,
)
from database import Database
from fleet import ROBOTS as LEGACY_ROBOTS
from models import Robot
from sqlalchemy import select, text
from storage_models import CatalogActivation, CatalogVersion

LEGACY_CATALOG_VERSION = "legacy-fleet-v1"


class CatalogRepositoryError(RuntimeError):
    """Raised when a requested catalog snapshot cannot be loaded safely."""


@dataclass(frozen=True)
class CatalogVersionDTO:
    id: str
    code: str
    status: str
    schema_version: str


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

    def runtime_dict(self) -> dict[str, Any] | None:
        """Return an isolated mutable value for the existing calculation core."""

        return copy.deepcopy(self.runtime_robot)


@dataclass(frozen=True)
class CatalogSnapshotDTO:
    version: CatalogVersionDTO
    models: tuple[CatalogModelDTO, ...]

    def by_source_key(self) -> dict[str, CatalogModelDTO]:
        return {model.source_record_key: model for model in self.models}

    def runtime_robots(self) -> list[dict[str, Any]]:
        robots: list[dict[str, Any]] = []
        for model in self.models:
            runtime_robot = model.runtime_dict()
            if runtime_robot is not None:
                robots.append(runtime_robot)
        return robots


class CatalogRepository(Protocol):
    def load(self) -> CatalogSnapshotDTO:
        """Load one immutable, explicitly scoped catalog snapshot."""


def _legacy_fact(code: str, value: Any, unit: str) -> CatalogFactDTO:
    return CatalogFactDTO(
        code=code,
        scope_code="GLOBAL",
        value=copy.deepcopy(value),
        canonical_unit=unit,
        resolution_status="LEGACY_REFERENCE",
        evidence_id=f"legacy:{code}",
    )


class LegacyFleetCatalogRepository:
    """Reference adapter over the committed ``backend/fleet`` JSON records."""

    def load(self) -> CatalogSnapshotDTO:
        models: list[CatalogModelDTO] = []
        for robot in LEGACY_ROBOTS:
            payload = robot.model_dump(mode="json")
            specs = payload["specs"]
            facts = (
                _legacy_fact("payload", specs["payload_kg"], "kg"),
                _legacy_fact("max_speed", specs["max_speed_m_s"], "m/s"),
                _legacy_fact("min_aisle_width", specs["min_aisle_width_m"], "m"),
                _legacy_fact("autonomy", specs["autonomy_hours"], "h"),
                _legacy_fact("navigation", specs["navigation_type"], "1"),
            )
            models.append(
                CatalogModelDTO(
                    id=payload["id"],
                    source_namespace="legacy-fleet",
                    source_record_key=payload["id"],
                    organizer_id=None,
                    manufacturer=None,
                    name=payload["name"],
                    system_family=payload["category"],
                    type_code=payload["type_label"],
                    subtype_code=None,
                    maturity_status=None,
                    trl=None,
                    description=payload["description"],
                    attributes={},
                    facts=facts,
                    applicability=(),
                    procurement_options=(),
                    runtime_robot=copy.deepcopy(payload),
                    runtime_blockers=(),
                )
            )
        return CatalogSnapshotDTO(
            version=CatalogVersionDTO(
                id=LEGACY_CATALOG_VERSION,
                code=LEGACY_CATALOG_VERSION,
                status="REFERENCE",
                schema_version="legacy-json-v1",
            ),
            models=tuple(models),
        )


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
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Build an engine payload only from an explicit projection plus safe facts."""

    attributes = copy.deepcopy(model.attributes or {})
    projection = attributes.get("runtime_projection")
    if not isinstance(projection, dict):
        return None, ("runtime_projection",)

    payload = copy.deepcopy(projection)
    payload.setdefault("id", model.source_record_key)
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
        fact = next((facts_by_code[code] for code in codes if code in facts_by_code), None)
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
            matching_rows = session.execute(
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
            ).mappings().all()

            applicability_by_model: dict[
                uuid.UUID, list[CatalogApplicabilityDTO]
            ] = {}
            for row in applicability_rows:
                applicability_by_model.setdefault(row.equipment_model_id, []).append(
                    CatalogApplicabilityDTO(
                        industry=row.industry,
                        scenario=row.scenario,
                        region=row.region,
                        case_text=row.case_text,
                    )
                )

            procurement_by_model: dict[uuid.UUID, list[ProcurementOptionDTO]] = {}
            for row in procurement_rows:
                procurement_by_model.setdefault(row.equipment_model_id, []).append(
                    ProcurementOptionDTO(
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
                    )
                )

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
            for model, manufacturer_name in model_rows:
                facts = tuple(facts_by_model.get(model.id, ()))
                applicability = tuple(applicability_by_model.get(model.id, ()))
                procurement = tuple(procurement_by_model.get(model.id, ()))
                runtime_robot, blockers = _project_runtime_robot(
                    model, facts, procurement
                )
                models.append(
                    CatalogModelDTO(
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
                    )
                )

            return CatalogSnapshotDTO(
                version=CatalogVersionDTO(
                    id=str(version.id),
                    code=version.code,
                    status=version.status,
                    schema_version=version.schema_version,
                ),
                models=tuple(models),
            )


class ActivatedCatalogRepository:
    """Resolve the current atomic activation, then load that immutable version."""

    def __init__(self, database: Database, slot: str) -> None:
        normalized = slot.strip()
        if normalized not in {"discovery", "runtime"}:
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
