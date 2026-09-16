"""Explicit transactional importer for the committed organizer catalog bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from catalog_import_contract import (
    CatalogBundle,
    CatalogBundleError,
    SourceArtifactContract,
    load_catalog_bundle,
)
from catalog_models import (
    SAFE_AUTOMATIC_STATUSES,
    CatalogSourceRow,
    EquipmentApplicability,
    EquipmentModel,
    FieldEvidence,
    Manufacturer,
    ProcurementOption,
    ResolvedSpecFact,
    ResolvedSpecFactEvidence,
    SpecObservation,
)
from database import Database, DatabaseSettings
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from storage_models import (
    CatalogVersion,
    CatalogVersionSource,
    ImportRun,
    SourceArtifact,
)

Phase = Literal["BASE", "ENRICHMENT"]
Mode = Literal["VALIDATE_ONLY", "COMMIT"]
DEFAULT_BUNDLE = (
    Path(__file__).resolve().parents[1] / "data" / "import" / "organizer-catalog-v4"
)


class CatalogImportError(RuntimeError):
    """Safe importer error that never embeds DSNs or source row contents."""


@dataclass(frozen=True)
class ImportResult:
    run_id: uuid.UUID
    catalog_version_id: uuid.UUID
    phase: Phase
    mode: Mode
    status: str
    bundle_sha256: str
    counts: dict[str, int]
    idempotent: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": str(self.run_id),
            "catalog_version_id": str(self.catalog_version_id),
            "phase": self.phase,
            "mode": self.mode,
            "status": self.status,
            "bundle_sha256": self.bundle_sha256,
            "counts": self.counts,
            "idempotent": self.idempotent,
        }


def _uuid(version_id: uuid.UUID, kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(version_id, f"robodovod:{kind}:{key}")


def _artifact_uuid(sha256: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"robodovod:source-artifact:{sha256}")


def _manifest_sha(bundle_path: Path) -> str:
    manifest = bundle_path.resolve() / "manifest.json"
    try:
        return hashlib.sha256(manifest.read_bytes()).hexdigest()
    except OSError as exc:
        raise CatalogImportError("bundle manifest is missing or unreadable") from exc


def _safe_message(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, CatalogBundleError):
        return "BUNDLE_VALIDATION_FAILED", str(exc)[:500]
    if isinstance(exc, CatalogImportError):
        return "IMPORT_POLICY_FAILED", str(exc)[:500]
    if isinstance(exc, IntegrityError):
        return (
            "DATABASE_CONSTRAINT_FAILED",
            "catalog import violated a database constraint",
        )
    return "IMPORT_FAILED", "catalog import failed"


def _ensure_version(database: Database, code: str) -> uuid.UUID:
    with database.session() as session:
        version = session.scalar(
            select(CatalogVersion).where(CatalogVersion.code == code)
        )
        if version is None:
            version = CatalogVersion(
                id=uuid.uuid4(), code=code, status="DRAFT", schema_version="2"
            )
            session.add(version)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                version = session.scalar(
                    select(CatalogVersion).where(CatalogVersion.code == code)
                )
                if version is None:
                    raise
        if version.schema_version != "2":
            raise CatalogImportError(
                "catalog version schema is not compatible with bundle"
            )
        return version.id


def _existing_result(
    database: Database,
    version_id: uuid.UUID,
    phase: Phase,
    mode: Mode,
    bundle_sha256: str,
    request_key: str | None,
) -> ImportResult | None:
    with database.session() as session:
        run: ImportRun | None = None
        if request_key:
            run = session.scalar(
                select(ImportRun).where(ImportRun.request_key == request_key)
            )
            if run is not None and (
                run.catalog_version_id != version_id
                or run.phase != phase
                or run.mode != mode
                or run.bundle_sha256 != bundle_sha256
            ):
                raise CatalogImportError(
                    "request key is already used by another import"
                )
        if run is None and mode == "COMMIT":
            run = session.scalar(
                select(ImportRun).where(
                    ImportRun.catalog_version_id == version_id,
                    ImportRun.phase == phase,
                    ImportRun.mode == "COMMIT",
                    ImportRun.status == "SUCCEEDED",
                    ImportRun.bundle_sha256 == bundle_sha256,
                )
            )
        if run is None:
            return None
        return ImportResult(
            run_id=run.id,
            catalog_version_id=version_id,
            phase=phase,
            mode=mode,
            status=run.status,
            bundle_sha256=bundle_sha256,
            counts=dict(run.counts),
            idempotent=True,
        )


def _start_run(
    database: Database,
    version_id: uuid.UUID,
    phase: Phase,
    mode: Mode,
    bundle_sha256: str,
    request_key: str | None,
) -> uuid.UUID:
    run_id = uuid.uuid4()
    with database.session() as session:
        session.add(
            ImportRun(
                id=run_id,
                catalog_version_id=version_id,
                phase=phase,
                mode=mode,
                status="RUNNING",
                bundle_sha256=bundle_sha256,
                request_key=request_key,
                started_at=datetime.now(UTC),
                counts={},
                diagnostics={},
            )
        )
        session.commit()
    return run_id


def _finish_failed(database: Database, run_id: uuid.UUID, exc: Exception) -> None:
    code, message = _safe_message(exc)
    with database.session() as session:
        run = session.get(ImportRun, run_id)
        if run is None:
            return
        run.status = "FAILED"
        run.finished_at = datetime.now(UTC)
        run.diagnostics = {"error_code": code, "message": message}
        session.commit()


def _finish_validated(
    database: Database, run_id: uuid.UUID, counts: dict[str, int]
) -> None:
    with database.session() as session:
        run = session.get(ImportRun, run_id)
        if run is None:
            raise CatalogImportError("import run disappeared")
        run.status = "SUCCEEDED"
        run.finished_at = datetime.now(UTC)
        run.counts = counts
        run.diagnostics = {"validation": "PASS"}
        session.commit()


def _expected_counts(bundle: CatalogBundle, phase: Phase) -> dict[str, int]:
    expected = bundle.manifest.expected_counts
    if phase == "BASE":
        return {
            key: expected[key]
            for key in (
                "products",
                "catalog_source_rows",
                "applicability_rows",
                "price_rows",
                "base_evidence_rows",
                "base_spec_fields",
                "object_profiles",
                "object_profile_parameters",
            )
        }
    return {
        key: expected[key]
        for key in (
            "enrichment_products",
            "overlay_fields",
            "external_evidence_rows",
        )
    }


def _parse_json_value(raw: str) -> Any | None:
    value = raw.strip()
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value
    return None if parsed is None else parsed


def _typed_columns(value: Any | None) -> dict[str, Any]:
    result = {
        "numeric_value": None,
        "text_value": None,
        "boolean_value": None,
        "json_value": None,
    }
    if value is None:
        return result
    if isinstance(value, bool):
        result["boolean_value"] = value
    elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        result["numeric_value"] = Decimal(str(value))
    elif isinstance(value, str):
        result["text_value"] = value
    else:
        result["json_value"] = value
    return result


def _source_artifacts_for_phase(
    bundle: CatalogBundle, phase: Phase
) -> list[SourceArtifactContract]:
    file_phases = {entry.path: entry.phase for entry in bundle.manifest.files}
    selected: list[SourceArtifactContract] = []
    for artifact in bundle.manifest.source_artifacts:
        if artifact.role == "IMPORT_BUNDLE":
            path = artifact.artifact_key.removeprefix("bundle:")
            artifact_phase = file_phases.get(path)
            if (
                phase == "BASE"
                and artifact_phase in {"BASE", "REFERENCE"}
                or phase == "ENRICHMENT"
                and artifact_phase == "ENRICHMENT"
            ):
                selected.append(artifact)
        elif (
            phase == "BASE"
            and artifact.role in {"BASE", "REFERENCE"}
            or phase == "ENRICHMENT"
            and artifact.role == "ENRICHMENT"
        ):
            selected.append(artifact)
    return selected


def _register_artifacts(
    session: Session,
    version_id: uuid.UUID,
    bundle: CatalogBundle,
    phase: Phase,
) -> dict[str, uuid.UUID]:
    selected = _source_artifacts_for_phase(bundle, phase)
    hashes = {artifact.sha256 for artifact in selected}
    existing = {
        artifact.sha256: artifact.id
        for artifact in session.scalars(
            select(SourceArtifact).where(SourceArtifact.sha256.in_(hashes))
        )
    }
    for artifact in selected:
        artifact_id = existing.get(artifact.sha256, _artifact_uuid(artifact.sha256))
        if artifact.sha256 not in existing:
            session.add(
                SourceArtifact(
                    id=artifact_id,
                    sha256=artifact.sha256,
                    original_name=artifact.original_name,
                    media_type=artifact.media_type,
                    byte_size=artifact.size_bytes,
                    storage_key=None,
                    provenance_status=artifact.provenance_status,
                    license_status=artifact.license_status,
                    observed_at=datetime.fromisoformat(artifact.observed_at),
                )
            )
            existing[artifact.sha256] = artifact_id
    # The mappings intentionally have no ORM relationships. Flush the artifact
    # rows before inserting the association rows that reference them.
    session.flush()
    for artifact in selected:
        artifact_id = existing[artifact.sha256]
        session.add(
            CatalogVersionSource(
                catalog_version_id=version_id,
                source_artifact_id=artifact_id,
                role=artifact.role,
                ordinal=artifact.ordinal,
            )
        )
    return {artifact.artifact_key: existing[artifact.sha256] for artifact in selected}


def _manufacturer_key(name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:24]
    return f"manufacturer:{digest}"


def _product_value(spec: dict[str, Any]) -> Any:
    values = spec.get("values")
    if isinstance(values, list) and values:
        return values[0] if len(values) == 1 else values
    raw = spec.get("raw")
    return raw if isinstance(raw, str) and raw.strip() else None


def _evidence_links(
    session: Session,
    version_id: uuid.UUID,
    fact_id: uuid.UUID,
    evidence_ids: list[uuid.UUID],
) -> None:
    for evidence_id in dict.fromkeys(evidence_ids):
        session.add(
            ResolvedSpecFactEvidence(
                resolved_spec_fact_id=fact_id,
                field_evidence_id=evidence_id,
                catalog_version_id=version_id,
            )
        )


def _import_base(
    session: Session,
    version_id: uuid.UUID,
    bundle: CatalogBundle,
    artifacts: dict[str, uuid.UUID],
) -> dict[str, int]:
    namespace = bundle.manifest.catalog.source_namespace
    products_by_id = {str(row["organizer_id"]): row for row in bundle.products}
    model_ids = {
        organizer_id: _uuid(version_id, "equipment-model", organizer_id)
        for organizer_id in products_by_id
    }

    manufacturer_ids: dict[str, uuid.UUID] = {}
    for product in bundle.products:
        name = str(product.get("manufacturer", "")).strip()
        if not name or name in manufacturer_ids:
            continue
        key = _manufacturer_key(name)
        manufacturer_id = _uuid(version_id, "manufacturer", key)
        manufacturer_ids[name] = manufacturer_id
        session.add(
            Manufacturer(
                id=manufacturer_id,
                catalog_version_id=version_id,
                source_namespace=namespace,
                source_record_key=key,
                name=name,
            )
        )
    session.flush()

    for organizer_id, product in products_by_id.items():
        description = product.get("description")
        description_text = None
        if isinstance(description, dict):
            description_text = description.get("normalized") or description.get("raw")
        attributes = {
            "name_raw_variants": product.get("name_raw_variants", []),
            "manufacturer_raw_variants": product.get("manufacturer_raw_variants", []),
            "market_potential": product.get("market_potential"),
            "industries": product.get("industries", []),
            "use_cases": product.get("use_cases", []),
            "regions": product.get("regions", []),
            "data_quality": product.get("data_quality", {}),
        }
        session.add(
            EquipmentModel(
                id=model_ids[organizer_id],
                catalog_version_id=version_id,
                manufacturer_id=manufacturer_ids.get(
                    str(product.get("manufacturer", "")).strip()
                ),
                organizer_id=uuid.UUID(organizer_id),
                source_namespace=namespace,
                source_record_key=str(product["product_id"]),
                name=str(product["name"]),
                system_family=str(product["system_family"]),
                type_code=str(product["type"]),
                subtype_code=product.get("subtype") or None,
                maturity_status=product.get("maturity_status") or None,
                trl=product.get("trl"),
                description=description_text,
                attributes=attributes,
            )
        )
    session.flush()

    app_by_row = {int(row["original_row"]): row for row in bundle.applicability}
    price_by_row = {int(row["original_row"]): row for row in bundle.prices}
    source_artifact_id = artifacts["organizer-catalog-v4-csv"]
    source_row_ids: dict[int, uuid.UUID] = {}
    app_ids: dict[str, uuid.UUID] = {}
    price_ids: dict[str, uuid.UUID] = {}
    for row_number in sorted(app_by_row):
        app = app_by_row[row_number]
        price = price_by_row[row_number]
        source_key = f"catalog-v4-row-{row_number:04d}"
        source_row_id = _uuid(version_id, "source-row", source_key)
        source_row_ids[row_number] = source_row_id
        session.add(
            CatalogSourceRow(
                id=source_row_id,
                catalog_version_id=version_id,
                source_artifact_id=source_artifact_id,
                source_row_number=row_number,
                source_namespace=namespace,
                source_record_key=source_key,
                raw_payload={"applicability": app, "price": price},
            )
        )
        price_ids[price["price_offer_id"]] = _uuid(
            version_id, "procurement-option", price["price_offer_id"]
        )
    session.flush()

    for row_number in sorted(app_by_row):
        app = app_by_row[row_number]
        app_id = _uuid(version_id, "applicability", app["applicability_id"])
        app_ids[app["applicability_id"]] = app_id
        session.add(
            EquipmentApplicability(
                id=app_id,
                catalog_version_id=version_id,
                equipment_model_id=model_ids[app["organizer_id"]],
                catalog_source_row_id=source_row_ids[row_number],
                industry=app["industry"] or None,
                scenario=app["scenario"] or None,
                region=app["region"] or None,
                case_text=app["case"] or None,
                attributes={"source_note": app["source_note"]},
            )
        )
    session.flush()

    artifact_by_name = {
        artifact.original_name: artifacts[artifact.artifact_key]
        for artifact in _source_artifacts_for_phase(bundle, "BASE")
        if artifact.artifact_key in artifacts
    }
    row_by_app_id = {
        row["applicability_id"]: int(row["original_row"])
        for row in bundle.applicability
    }
    row_by_price_id = {
        row["price_offer_id"]: int(row["original_row"]) for row in bundle.prices
    }
    evidence_by_subject: dict[tuple[str, str, str], list[tuple[uuid.UUID, str]]] = {}
    for index, row in enumerate(bundle.base_evidence, start=1):
        entity_type = row["entity_type"]
        entity_id = row["entity_id"]
        model_id: uuid.UUID | None = None
        source_row_id: uuid.UUID | None = None
        if entity_type == "product":
            model_id = model_ids[entity_id]
        elif entity_type == "applicability":
            row_number = row_by_app_id[entity_id]
            source_row_id = source_row_ids[row_number]
            model_id = model_ids[app_by_row[row_number]["organizer_id"]]
        else:
            row_number = row_by_price_id[entity_id]
            source_row_id = source_row_ids[row_number]
            model_id = model_ids[price_by_row[row_number]["organizer_id"]]
        evidence_id = _uuid(version_id, "base-evidence", f"{index:04d}")
        key = (entity_type, entity_id, row["field_path"])
        evidence_by_subject.setdefault(key, []).append(
            (evidence_id, row["evidence_status"])
        )
        normalized_value = _parse_json_value(row["normalized_value"])
        session.add(
            FieldEvidence(
                id=evidence_id,
                catalog_version_id=version_id,
                source_artifact_id=artifact_by_name[row["source_file"]],
                catalog_source_row_id=source_row_id,
                equipment_model_id=model_id,
                source_namespace=namespace,
                source_record_key=f"base-evidence-{index:04d}",
                subject_type={
                    "product": "PRODUCT",
                    "applicability": "APPLICABILITY",
                    "price_offer": "PRICE_OFFER",
                }[entity_type],
                subject_key=entity_id,
                field_path=row["field_path"],
                raw_value=row["normalized_value"] or None,
                normalized_value=normalized_value,
                normalized_unit=None,
                source_locator=" / ".join(
                    part
                    for part in (
                        row["source_sheet_or_page"],
                        row["source_row_or_fragment"],
                    )
                    if part
                )
                or None,
                evidence_status=row["evidence_status"],
                confidence_label=row["confidence"] or None,
                observed_at=datetime(2026, 9, 15, tzinfo=UTC),
                notes=row["notes"] or None,
            )
        )
    session.flush()

    observation_count = 0
    resolved_count = 0
    pending_fact_links: list[tuple[uuid.UUID, list[uuid.UUID]]] = []
    for organizer_id, product in products_by_id.items():
        for spec_code, spec in product["specs"].items():
            field_path = f"specs.{spec_code}"
            evidence = evidence_by_subject.get(
                ("product", organizer_id, field_path), []
            )
            if not evidence:
                raise CatalogImportError("base spec has no evidence")
            primary_id = next(
                (
                    evidence_id
                    for evidence_id, status in evidence
                    if status == spec["status"]
                ),
                evidence[0][0],
            )
            value = _product_value(spec)
            typed = _typed_columns(value)
            observation_id = _uuid(
                version_id, "base-observation", f"{organizer_id}:{spec_code}"
            )
            session.add(
                SpecObservation(
                    id=observation_id,
                    catalog_version_id=version_id,
                    equipment_model_id=model_ids[organizer_id],
                    field_evidence_id=primary_id,
                    spec_code=spec_code,
                    scope_code="GLOBAL",
                    raw_value=spec.get("raw"),
                    canonical_unit=spec.get("unit") or "1",
                    observation_status=spec["status"],
                    observed_at=datetime(2026, 9, 15, tzinfo=UTC),
                    **typed,
                )
            )
            observation_count += 1
            if spec["status"] in SAFE_AUTOMATIC_STATUSES and value is not None:
                fact_id = _uuid(
                    version_id, "base-resolved-fact", f"{organizer_id}:{spec_code}"
                )
                session.add(
                    ResolvedSpecFact(
                        id=fact_id,
                        catalog_version_id=version_id,
                        equipment_model_id=model_ids[organizer_id],
                        primary_evidence_id=primary_id,
                        spec_code=spec_code,
                        scope_code="GLOBAL",
                        canonical_unit=spec.get("unit") or "1",
                        resolution_status=spec["status"],
                        usable_for_matching=True,
                        resolved_at=datetime.now(UTC),
                        **typed,
                    )
                )
                pending_fact_links.append((fact_id, [item[0] for item in evidence]))
                resolved_count += 1
    session.flush()
    for fact_id, evidence_ids in pending_fact_links:
        _evidence_links(session, version_id, fact_id, evidence_ids)

    policy = bundle.manifest.pricing_policy
    for row_number, price in price_by_row.items():
        evidence = evidence_by_subject.get(
            ("price_offer", price["price_offer_id"], "raw_price"), []
        ) or evidence_by_subject.get(
            ("price_offer", price["price_offer_id"], "normalized_amount"), []
        )
        if not evidence:
            raise CatalogImportError("price offer has no evidence")
        try:
            amount = Decimal(price["normalized_amount"])
        except InvalidOperation as exc:
            raise CatalogImportError("price amount is not a decimal") from exc
        session.add(
            ProcurementOption(
                id=price_ids[price["price_offer_id"]],
                catalog_version_id=version_id,
                equipment_model_id=model_ids[price["organizer_id"]],
                catalog_source_row_id=source_row_ids[row_number],
                field_evidence_id=evidence[0][0],
                procurement_mode="PURCHASE",
                raw_price=price["raw_price"],
                amount=amount,
                currency=policy.currency,
                currency_provenance=policy.currency_provenance,
                vat_status=policy.vat_status,
                vat_rate=None,
                vat_provenance=policy.vat_provenance,
                price_status="NORMALIZED",
                included_costs=[
                    item.strip()
                    for item in price["included_costs"].split("|")
                    if item.strip()
                ],
                excluded_costs=policy.excluded_costs,
            )
        )

    return {
        "manufacturers": len(manufacturer_ids),
        "equipment_models": len(model_ids),
        "catalog_source_rows": len(source_row_ids),
        "equipment_applicability": len(app_ids),
        "field_evidence": len(bundle.base_evidence),
        "spec_observations": observation_count,
        "resolved_spec_facts": resolved_count,
        "procurement_options": len(price_ids),
    }


def _parse_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _import_enrichment(
    session: Session,
    version_id: uuid.UUID,
    bundle: CatalogBundle,
    artifacts: dict[str, uuid.UUID],
) -> dict[str, int]:
    namespace = "external-enrichment-run-1"
    model_ids = {
        str(organizer_id): model_id
        for organizer_id, model_id in session.execute(
            select(EquipmentModel.organizer_id, EquipmentModel.id).where(
                EquipmentModel.catalog_version_id == version_id
            )
        )
        if organizer_id is not None
    }
    if len(model_ids) != bundle.manifest.expected_counts["products"]:
        raise CatalogImportError("BASE phase is incomplete")
    source_artifact_id = artifacts["bundle:catalog_external_evidence.csv"]
    evidence_by_field: dict[tuple[str, str], list[tuple[uuid.UUID, str]]] = {}
    for index, row in enumerate(bundle.external_evidence, start=1):
        organizer_id = row["organizer_id"]
        evidence_id = _uuid(version_id, "external-evidence", f"{index:04d}")
        key = (organizer_id, row["field_path"])
        evidence_by_field.setdefault(key, []).append(
            (evidence_id, row["evidence_status"])
        )
        normalized_value = _parse_json_value(row["normalized_value"])
        locator = " | ".join(
            item for item in (row["url"], row["page_section_table"]) if item
        )
        session.add(
            FieldEvidence(
                id=evidence_id,
                catalog_version_id=version_id,
                source_artifact_id=source_artifact_id,
                catalog_source_row_id=None,
                equipment_model_id=model_ids[organizer_id],
                source_namespace=namespace,
                source_record_key=f"external-evidence-{index:04d}",
                subject_type="PRODUCT",
                subject_key=organizer_id,
                field_path=row["field_path"],
                raw_value=row["raw_value"] or None,
                normalized_value=normalized_value,
                normalized_unit=row["normalized_unit"] or None,
                source_locator=locator or None,
                evidence_status=row["evidence_status"],
                confidence_score=Decimal(row["confidence"]),
                publication_or_update_date=_parse_date(
                    row["publication_or_update_date"]
                ),
                observed_at=datetime.combine(
                    date.fromisoformat(row["accessed_at"]),
                    datetime.min.time(),
                    tzinfo=UTC,
                ),
                notes=" | ".join(
                    item for item in (row["model_match_note"], row["notes"]) if item
                )
                or None,
            )
        )
    session.flush()

    existing_fact_keys = set(
        session.execute(
            select(
                ResolvedSpecFact.equipment_model_id,
                ResolvedSpecFact.spec_code,
                ResolvedSpecFact.scope_code,
            ).where(ResolvedSpecFact.catalog_version_id == version_id)
        ).all()
    )
    observation_count = 0
    resolved_count = 0
    pending_fact_links: list[tuple[uuid.UUID, list[uuid.UUID]]] = []
    for product in bundle.enrichment:
        organizer_id = str(product["organizer_id"])
        for spec_code, field in product["fields"].items():
            field_path = f"specs.{spec_code}"
            evidence = evidence_by_field.get((organizer_id, field_path), [])
            if not evidence:
                raise CatalogImportError("enrichment field has no evidence")
            status = field["evidence_status"]
            primary_id = next(
                (
                    evidence_id
                    for evidence_id, evidence_status in evidence
                    if evidence_status == status
                ),
                evidence[0][0],
            )
            value = field.get("normalized_value")
            typed = _typed_columns(value)
            observation_id = _uuid(
                version_id,
                "enrichment-observation",
                f"{organizer_id}:{spec_code}",
            )
            session.add(
                SpecObservation(
                    id=observation_id,
                    catalog_version_id=version_id,
                    equipment_model_id=model_ids[organizer_id],
                    field_evidence_id=primary_id,
                    spec_code=spec_code,
                    scope_code="GLOBAL",
                    raw_value=field.get("raw_value"),
                    canonical_unit=field.get("normalized_unit") or "1",
                    observation_status=status,
                    observed_at=datetime(2026, 9, 15, tzinfo=UTC),
                    **typed,
                )
            )
            observation_count += 1
            if status in SAFE_AUTOMATIC_STATUSES and value is not None:
                fact_key = (model_ids[organizer_id], spec_code, "GLOBAL")
                if fact_key in existing_fact_keys:
                    raise CatalogImportError(
                        "enrichment would overwrite an existing resolved fact"
                    )
                fact_id = _uuid(
                    version_id,
                    "enrichment-resolved-fact",
                    f"{organizer_id}:{spec_code}",
                )
                session.add(
                    ResolvedSpecFact(
                        id=fact_id,
                        catalog_version_id=version_id,
                        equipment_model_id=model_ids[organizer_id],
                        primary_evidence_id=primary_id,
                        spec_code=spec_code,
                        scope_code="GLOBAL",
                        canonical_unit=field.get("normalized_unit") or "1",
                        resolution_status=status,
                        usable_for_matching=True,
                        resolved_at=datetime.now(UTC),
                        **typed,
                    )
                )
                pending_fact_links.append(
                    (
                        fact_id,
                        [
                            evidence_id
                            for evidence_id, evidence_status in evidence
                            if evidence_status == status
                        ],
                    )
                )
                existing_fact_keys.add(fact_key)
                resolved_count += 1
    session.flush()
    for fact_id, evidence_ids in pending_fact_links:
        _evidence_links(session, version_id, fact_id, evidence_ids)
    return {
        "field_evidence": len(bundle.external_evidence),
        "spec_observations": observation_count,
        "resolved_spec_facts": resolved_count,
    }


def _content_sha256(
    session: Session,
    version_id: uuid.UUID,
    phase: Phase,
    bundle_sha256: str,
) -> str:
    successful = {
        (run_phase, run_hash)
        for run_phase, run_hash in session.execute(
            select(ImportRun.phase, ImportRun.bundle_sha256).where(
                ImportRun.catalog_version_id == version_id,
                ImportRun.mode == "COMMIT",
                ImportRun.status == "SUCCEEDED",
            )
        )
    }
    successful.add((phase, bundle_sha256))
    canonical = json.dumps(sorted(successful), separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _commit_phase(
    database: Database,
    run_id: uuid.UUID,
    version_id: uuid.UUID,
    phase: Phase,
    bundle: CatalogBundle,
) -> dict[str, int]:
    with database.session() as session:
        version = session.scalar(
            select(CatalogVersion)
            .where(CatalogVersion.id == version_id)
            .with_for_update()
        )
        if version is None or version.status != "DRAFT":
            raise CatalogImportError("catalog import requires a DRAFT version")
        if phase == "ENRICHMENT":
            base_succeeded = session.scalar(
                select(ImportRun.id).where(
                    ImportRun.catalog_version_id == version_id,
                    ImportRun.phase == "BASE",
                    ImportRun.mode == "COMMIT",
                    ImportRun.status == "SUCCEEDED",
                    ImportRun.bundle_sha256 == bundle.bundle_sha256,
                )
            )
            if base_succeeded is None:
                raise CatalogImportError(
                    "ENRICHMENT requires successful BASE for the same bundle"
                )
        artifacts = _register_artifacts(session, version_id, bundle, phase)
        # Persist artifact/link prerequisites before rows that use the composite
        # catalog_version_sources foreign key. This is still the same phase
        # transaction and rolls back atomically on any later failure.
        session.flush()
        counts = (
            _import_base(session, version_id, bundle, artifacts)
            if phase == "BASE"
            else _import_enrichment(session, version_id, bundle, artifacts)
        )
        run = session.get(ImportRun, run_id)
        if run is None:
            raise CatalogImportError("import run disappeared")
        run.status = "SUCCEEDED"
        run.finished_at = datetime.now(UTC)
        run.counts = counts
        run.diagnostics = {"validation": "PASS", "transaction": "COMMITTED"}
        version.content_sha256 = _content_sha256(
            session, version_id, phase, bundle.bundle_sha256
        )
        version.updated_at = datetime.now(UTC)
        session.commit()
        return counts


def run_catalog_import(
    database: Database,
    bundle_path: str | Path,
    *,
    phase: Phase,
    mode: Mode,
    catalog_code: str = "organizer-catalog-v4",
    request_key: str | None = None,
) -> ImportResult:
    if phase not in {"BASE", "ENRICHMENT"}:
        raise CatalogImportError("phase must be BASE or ENRICHMENT")
    if mode not in {"VALIDATE_ONLY", "COMMIT"}:
        raise CatalogImportError("mode must be VALIDATE_ONLY or COMMIT")
    if request_key is not None and not request_key.strip():
        raise CatalogImportError("request key cannot be empty")
    bundle_path = Path(bundle_path)
    bundle_sha256 = _manifest_sha(bundle_path)
    version_id = _ensure_version(database, catalog_code)
    existing = _existing_result(
        database,
        version_id,
        phase,
        mode,
        bundle_sha256,
        request_key,
    )
    if existing is not None:
        return existing
    run_id = _start_run(
        database,
        version_id,
        phase,
        mode,
        bundle_sha256,
        request_key,
    )
    try:
        bundle = load_catalog_bundle(bundle_path)
        if bundle.manifest.catalog.code != catalog_code:
            raise CatalogImportError("catalog code does not match bundle")
        if bundle.bundle_sha256 != bundle_sha256:
            raise CatalogImportError("bundle manifest changed during import")
        if mode == "VALIDATE_ONLY":
            with database.session() as session:
                version = session.get(CatalogVersion, version_id)
                if version is None or version.status != "DRAFT":
                    raise CatalogImportError("catalog import requires a DRAFT version")
            counts = _expected_counts(bundle, phase)
            _finish_validated(database, run_id, counts)
        else:
            counts = _commit_phase(database, run_id, version_id, phase, bundle)
    # Every phase failure must leave a sanitized FAILED ImportRun, including
    # unexpected driver/runtime failures.
    except Exception as exc:  # noqa: BLE001
        _finish_failed(database, run_id, exc)
        if isinstance(exc, (CatalogBundleError, CatalogImportError)):
            raise CatalogImportError(str(exc)) from None
        if isinstance(exc, IntegrityError):
            diagnostic = getattr(getattr(exc, "orig", None), "diag", None)
            constraint_name = getattr(diagnostic, "constraint_name", None)
            suffix = f": {constraint_name}" if constraint_name else ""
            raise CatalogImportError(
                f"catalog import failed database constraint{suffix}"
            ) from None
        if isinstance(exc, SQLAlchemyError):
            raise CatalogImportError("catalog import failed database checks") from None
        raise CatalogImportError("catalog import failed") from None
    return ImportResult(
        run_id=run_id,
        catalog_version_id=version_id,
        phase=phase,
        mode=mode,
        status="SUCCEEDED",
        bundle_sha256=bundle_sha256,
        counts=counts,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or import catalog bundle")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--phase", choices=("BASE", "ENRICHMENT"), required=True)
    parser.add_argument("--mode", choices=("VALIDATE_ONLY", "COMMIT"), required=True)
    parser.add_argument("--catalog-code", default="organizer-catalog-v4")
    parser.add_argument("--request-key")
    args = parser.parse_args()
    try:
        database = Database(DatabaseSettings.from_environment())
        try:
            result = run_catalog_import(
                database,
                args.bundle,
                phase=args.phase,
                mode=args.mode,
                catalog_code=args.catalog_code,
                request_key=args.request_key,
            )
        finally:
            database.dispose()
    # The CLI is a trust boundary: emit one sanitized JSON error, never a
    # traceback that could contain SQL parameters or connection details.
    except Exception as exc:  # noqa: BLE001
        code, message = _safe_message(exc)
        print(json.dumps({"status": "FAILED", "error_code": code, "message": message}))
        return 1
    print(json.dumps(result.as_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
