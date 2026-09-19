"""Catalog lifecycle validation, publication and atomic slot activation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from catalog_import_contract import CatalogBundleError, load_catalog_bundle
from catalog_importer import DEFAULT_BUNDLE
from catalog_repository import CatalogRepositoryError, PostgresCatalogRepository
from database import Database, DatabaseSettings
from object_profiles import ObjectProfileError, load_official_profiles
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from storage_models import CatalogActivation, CatalogVersion, ImportRun

CatalogSlot = Literal["discovery", "runtime"]
ALLOWED_SLOTS = {"discovery", "runtime"}


class CatalogActivationError(RuntimeError):
    """Safe lifecycle error that does not include database or source payloads."""


@dataclass(frozen=True)
class LifecycleResult:
    catalog_code: str
    status: str
    content_sha256: str | None
    checks: dict[str, Any]


@dataclass(frozen=True)
class ActivationResult:
    slot: str
    catalog_code: str | None
    activation_id: str | None
    changed: bool
    runtime_ready_models: int | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _expected_content_sha(bundle_sha256: str) -> str:
    phases = sorted((phase, bundle_sha256) for phase in ("BASE", "ENRICHMENT"))
    canonical = json.dumps(phases, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _phase_runs(
    session, version_id: uuid.UUID, bundle_sha256: str
) -> dict[str, ImportRun]:
    runs = session.scalars(
        select(ImportRun).where(
            ImportRun.catalog_version_id == version_id,
            ImportRun.mode == "COMMIT",
            ImportRun.status == "SUCCEEDED",
            ImportRun.bundle_sha256 == bundle_sha256,
            ImportRun.phase.in_(("BASE", "ENRICHMENT")),
        )
    ).all()
    by_phase = {run.phase: run for run in runs}
    if set(by_phase) != {"BASE", "ENRICHMENT"}:
        raise CatalogActivationError(
            "catalog publication requires successful BASE and ENRICHMENT imports"
        )
    return by_phase


def _actual_count(session, table_name: str, version_id: uuid.UUID) -> int:
    allowed = {
        "equipment_models",
        "catalog_source_rows",
        "equipment_applicability",
        "procurement_options",
        "field_evidence",
        "spec_observations",
        "resolved_spec_facts",
    }
    if table_name not in allowed:
        raise AssertionError("unsupported reconciliation table")
    return int(
        session.scalar(
            text(
                f"SELECT count(*) FROM {table_name} "
                "WHERE catalog_version_id = :version_id"
            ),
            {"version_id": version_id},
        )
        or 0
    )


def _reconcile(session, version: CatalogVersion, bundle) -> dict[str, Any]:
    runs = _phase_runs(session, version.id, bundle.bundle_sha256)
    base = dict(runs["BASE"].counts)
    enrichment = dict(runs["ENRICHMENT"].counts)
    expected = bundle.manifest.expected_counts
    expected_run_counts = {
        "equipment_models": expected["products"],
        "catalog_source_rows": expected["catalog_source_rows"],
        "equipment_applicability": expected["applicability_rows"],
        "procurement_options": expected["price_rows"],
        "base_field_evidence": expected["base_evidence_rows"],
        "enrichment_field_evidence": expected["external_evidence_rows"]
        + expected["capacity_enrichment_evidence_rows"],
        "enrichment_spec_observations": expected["overlay_fields"]
        + expected["capacity_enrichment_facts"],
        "capacity_enrichment_models": expected["capacity_enrichment_models"],
        "capacity_runtime_models": expected["capacity_runtime_models"],
        "capacity_runtime_pool_models": expected["capacity_runtime_pool_models"],
        "capacity_runtime_pool_positions": expected[
            "capacity_runtime_pool_positions"
        ],
    }
    actual_run_counts = {
        "equipment_models": base.get("equipment_models"),
        "catalog_source_rows": base.get("catalog_source_rows"),
        "equipment_applicability": base.get("equipment_applicability"),
        "procurement_options": base.get("procurement_options"),
        "base_field_evidence": base.get("field_evidence"),
        "enrichment_field_evidence": enrichment.get("field_evidence"),
        "enrichment_spec_observations": enrichment.get("spec_observations"),
        "capacity_enrichment_models": enrichment.get("capacity_enrichment_models"),
        "capacity_runtime_models": enrichment.get("capacity_runtime_models"),
        "capacity_runtime_pool_models": enrichment.get(
            "capacity_runtime_pool_models"
        ),
        "capacity_runtime_pool_positions": enrichment.get(
            "capacity_runtime_pool_positions"
        ),
    }
    if actual_run_counts != expected_run_counts:
        raise CatalogActivationError("successful import counts do not match manifest")

    expected_database_counts = {
        "equipment_models": expected["products"],
        "catalog_source_rows": expected["catalog_source_rows"],
        "equipment_applicability": expected["applicability_rows"],
        "procurement_options": expected["price_rows"],
        "field_evidence": expected["base_evidence_rows"]
        + expected["external_evidence_rows"]
        + expected["capacity_enrichment_evidence_rows"],
        "spec_observations": int(base.get("spec_observations", -1))
        + int(enrichment.get("spec_observations", -1)),
        "resolved_spec_facts": int(base.get("resolved_spec_facts", -1))
        + int(enrichment.get("resolved_spec_facts", -1)),
    }
    actual_database_counts = {
        table: _actual_count(session, table, version.id)
        for table in expected_database_counts
    }
    if actual_database_counts != expected_database_counts:
        raise CatalogActivationError("catalog database reconciliation failed")
    expected_sha256 = _expected_content_sha(bundle.bundle_sha256)
    if version.content_sha256 != expected_sha256:
        raise CatalogActivationError("catalog content checksum differs from imports")
    return {
        "bundle_sha256": bundle.bundle_sha256,
        "database_counts": actual_database_counts,
        "object_profile_counts": {
            profile.code: len(profile.parameters())
            for profile in load_official_profiles(bundle.root).object_types
        },
    }


def validate_catalog_version(
    database: Database,
    catalog_code: str,
    bundle_path: str | Path = DEFAULT_BUNDLE,
) -> LifecycleResult:
    try:
        bundle = load_catalog_bundle(bundle_path)
        if bundle.manifest.catalog.code != catalog_code:
            raise CatalogActivationError("catalog code does not match bundle")
        # Performs stronger runtime metadata validation in addition to import checks.
        load_official_profiles(bundle.root)
        with database.session() as session:
            version = session.scalar(
                select(CatalogVersion)
                .where(CatalogVersion.code == catalog_code)
                .with_for_update()
            )
            if version is None:
                raise CatalogActivationError("catalog version was not found")
            if version.status not in {"DRAFT", "VALIDATED", "PUBLISHED"}:
                raise CatalogActivationError("retired catalog cannot be validated")
            checks = _reconcile(session, version, bundle)
            if version.status == "DRAFT":
                now = _now()
                version.status = "VALIDATED"
                version.validated_at = now
                version.updated_at = now
                session.commit()
            return LifecycleResult(
                catalog_code=version.code,
                status=version.status,
                content_sha256=version.content_sha256,
                checks=checks,
            )
    except (CatalogBundleError, ObjectProfileError) as exc:
        raise CatalogActivationError("catalog bundle validation failed") from exc
    except CatalogActivationError:
        raise
    except (IntegrityError, SQLAlchemyError) as exc:
        raise CatalogActivationError(
            "catalog validation failed database checks"
        ) from exc


def publish_catalog_version(
    database: Database,
    catalog_code: str,
    bundle_path: str | Path = DEFAULT_BUNDLE,
) -> LifecycleResult:
    validated = validate_catalog_version(database, catalog_code, bundle_path)
    if validated.status == "PUBLISHED":
        return validated
    try:
        with database.session() as session:
            version = session.scalar(
                select(CatalogVersion)
                .where(CatalogVersion.code == catalog_code)
                .with_for_update()
            )
            if version is None or version.status != "VALIDATED":
                raise CatalogActivationError(
                    "catalog publication requires a VALIDATED version"
                )
            now = _now()
            version.status = "PUBLISHED"
            version.published_at = now
            version.updated_at = now
            session.commit()
            return LifecycleResult(
                catalog_code=version.code,
                status=version.status,
                content_sha256=version.content_sha256,
                checks=validated.checks,
            )
    except CatalogActivationError:
        raise
    except (IntegrityError, SQLAlchemyError) as exc:
        raise CatalogActivationError(
            "catalog publication failed database checks"
        ) from exc


def activate_catalog_version(
    database: Database,
    catalog_code: str,
    *,
    slot: CatalogSlot,
    actor_subject: str | None,
) -> ActivationResult:
    if slot not in ALLOWED_SLOTS:
        raise CatalogActivationError("catalog activation slot is unsupported")
    actor = actor_subject.strip() if actor_subject else None
    if actor_subject is not None and not actor:
        raise CatalogActivationError("activation actor cannot be empty")

    try:
        snapshot = PostgresCatalogRepository(database, catalog_code).load()
    except (CatalogRepositoryError, SQLAlchemyError) as exc:
        raise CatalogActivationError("catalog snapshot could not be loaded") from exc
    if snapshot.version.status != "PUBLISHED":
        raise CatalogActivationError("catalog activation requires a PUBLISHED version")
    runtime_ready = len(snapshot.runtime_robots())
    if slot == "runtime" and runtime_ready == 0:
        raise CatalogActivationError(
            "runtime activation requires at least one evidence-backed runtime model"
        )

    try:
        with database.session() as session:
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": f"robodovod:catalog-activation:{slot}"},
            )
            version = session.scalar(
                select(CatalogVersion)
                .where(CatalogVersion.code == catalog_code)
                .with_for_update()
            )
            if version is None or version.status != "PUBLISHED":
                raise CatalogActivationError(
                    "catalog activation requires a PUBLISHED version"
                )
            current = session.scalar(
                select(CatalogActivation)
                .where(
                    CatalogActivation.slot == slot,
                    CatalogActivation.deactivated_at.is_(None),
                )
                .with_for_update()
            )
            if current is not None and current.catalog_version_id == version.id:
                return ActivationResult(
                    slot=slot,
                    catalog_code=catalog_code,
                    activation_id=str(current.id),
                    changed=False,
                    runtime_ready_models=runtime_ready,
                )
            now = _now()
            if current is not None:
                current.deactivated_at = now
                session.flush()
            activation = CatalogActivation(
                id=uuid.uuid4(),
                slot=slot,
                catalog_version_id=version.id,
                activated_at=now,
                actor_subject=actor,
            )
            session.add(activation)
            session.commit()
            return ActivationResult(
                slot=slot,
                catalog_code=catalog_code,
                activation_id=str(activation.id),
                changed=True,
                runtime_ready_models=runtime_ready,
            )
    except CatalogActivationError:
        raise
    except (IntegrityError, SQLAlchemyError) as exc:
        raise CatalogActivationError(
            "catalog activation failed database checks"
        ) from exc


def deactivate_catalog_slot(
    database: Database, *, slot: CatalogSlot
) -> ActivationResult:
    if slot not in ALLOWED_SLOTS:
        raise CatalogActivationError("catalog activation slot is unsupported")
    try:
        with database.session() as session:
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": f"robodovod:catalog-activation:{slot}"},
            )
            current = session.scalar(
                select(CatalogActivation)
                .where(
                    CatalogActivation.slot == slot,
                    CatalogActivation.deactivated_at.is_(None),
                )
                .with_for_update()
            )
            if current is None:
                return ActivationResult(slot, None, None, False)
            version = session.get(CatalogVersion, current.catalog_version_id)
            current.deactivated_at = _now()
            session.commit()
            return ActivationResult(
                slot=slot,
                catalog_code=version.code if version is not None else None,
                activation_id=str(current.id),
                changed=True,
            )
    except (IntegrityError, SQLAlchemyError) as exc:
        raise CatalogActivationError(
            "catalog deactivation failed database checks"
        ) from exc


def catalog_activation_status(database: Database) -> dict[str, Any]:
    with database.session() as session:
        rows = session.execute(
            select(CatalogActivation, CatalogVersion)
            .join(
                CatalogVersion,
                CatalogVersion.id == CatalogActivation.catalog_version_id,
            )
            .where(CatalogActivation.deactivated_at.is_(None))
            .order_by(CatalogActivation.slot)
        ).all()
        return {
            "active": [
                {
                    "slot": activation.slot,
                    "catalog_code": version.code,
                    "catalog_status": version.status,
                    "activation_id": str(activation.id),
                    "activated_at": activation.activated_at.isoformat(),
                }
                for activation, version in rows
            ],
            "history_count": int(
                session.scalar(select(func.count()).select_from(CatalogActivation)) or 0
            ),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish and activate catalog versions"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "publish"):
        child = subparsers.add_parser(command)
        child.add_argument("--catalog-code", default="organizer-catalog-v4")
        child.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    activate = subparsers.add_parser("activate")
    activate.add_argument("--catalog-code", default="organizer-catalog-v4")
    activate.add_argument("--slot", choices=sorted(ALLOWED_SLOTS), required=True)
    activate.add_argument("--actor", default="catalog-activation-cli")
    deactivate = subparsers.add_parser("deactivate")
    deactivate.add_argument("--slot", choices=sorted(ALLOWED_SLOTS), required=True)
    subparsers.add_parser("status")
    args = parser.parse_args(argv)

    try:
        database = Database(DatabaseSettings.from_environment())
        try:
            if args.command == "validate":
                result: Any = validate_catalog_version(
                    database, args.catalog_code, args.bundle
                )
            elif args.command == "publish":
                result = publish_catalog_version(
                    database, args.catalog_code, args.bundle
                )
            elif args.command == "activate":
                result = activate_catalog_version(
                    database,
                    args.catalog_code,
                    slot=args.slot,
                    actor_subject=args.actor,
                )
            elif args.command == "deactivate":
                result = deactivate_catalog_slot(database, slot=args.slot)
            else:
                result = catalog_activation_status(database)
        finally:
            database.dispose()
    except Exception as exc:  # noqa: BLE001
        error_name = type(exc).__name__
        if not isinstance(exc, CatalogActivationError):
            error_name = "CatalogActivationError"
        print(f"catalog activation failed: {error_name}", file=sys.stderr)
        return 2
    payload = asdict(result) if hasattr(result, "__dataclass_fields__") else result
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
