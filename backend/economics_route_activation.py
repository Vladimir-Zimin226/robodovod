"""Operator-only C28 economics route activation and rollback service."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from auth import utcnow
from database import Database, DatabaseSettings
from economics_runtime_migration import (
    EconomicsDualRunReportV1,
    EconomicsMigrationError,
    LEGACY_VERSION,
    V2_VERSION,
    validate_activation,
)
from persistence_models import EconomicsRouteActivation


@dataclass(frozen=True)
class EconomicsActivationResult:
    economics_version: str
    activation_id: str
    changed: bool
    rollback_economics_version: str


def resolve_active_economics_version(database: Database) -> str:
    """Resolve the configured new-run route without an implicit legacy fallback."""

    try:
        with database.session() as session:
            active = session.scalar(
                select(EconomicsRouteActivation).where(
                    EconomicsRouteActivation.deactivated_at.is_(None)
                )
            )
            if active is None:
                raise EconomicsMigrationError("economics route is not active")
            return active.economics_version
    except EconomicsMigrationError:
        raise
    except SQLAlchemyError as exc:
        raise EconomicsMigrationError("economics route configuration is unavailable") from exc


def activate_economics_route(
    database: Database,
    report: EconomicsDualRunReportV1,
    *,
    actor_subject: str | None,
) -> EconomicsActivationResult:
    """Activate v2 only after the committed dual-run evidence passes policy."""

    validate_activation(report)
    actor = actor_subject.strip() if actor_subject else None
    if actor_subject is not None and not actor:
        raise EconomicsMigrationError("activation actor cannot be empty")
    try:
        with database.session() as session:
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('robodovod:economics-route'))")
            )
            current = session.scalar(
                select(EconomicsRouteActivation)
                .where(EconomicsRouteActivation.deactivated_at.is_(None))
                .with_for_update()
            )
            approval_sha = report.report_digest.removeprefix("sha256:")
            if current is not None and current.economics_version == V2_VERSION:
                if current.approval_report_sha256 != approval_sha:
                    raise EconomicsMigrationError("active route uses another approval report")
                return EconomicsActivationResult(
                    economics_version=V2_VERSION,
                    activation_id=str(current.id),
                    changed=False,
                    rollback_economics_version=current.rollback_economics_version,
                )
            rollback = current.economics_version if current is not None else LEGACY_VERSION
            now = utcnow()
            if current is not None:
                current.deactivated_at = now
                session.flush()
            activation = EconomicsRouteActivation(
                id=uuid.uuid4(),
                economics_version=V2_VERSION,
                policy_version=report.policy_version,
                approval_report_sha256=approval_sha,
                rollback_economics_version=rollback,
                actor_subject=actor,
                activated_at=now,
            )
            session.add(activation)
            session.commit()
            return EconomicsActivationResult(
                economics_version=V2_VERSION,
                activation_id=str(activation.id),
                changed=True,
                rollback_economics_version=rollback,
            )
    except EconomicsMigrationError:
        raise
    except (IntegrityError, SQLAlchemyError) as exc:
        raise EconomicsMigrationError("economics route activation failed database checks") from exc


def rollback_economics_route(
    database: Database, *, actor_subject: str | None
) -> EconomicsActivationResult:
    """Change only active configuration; persisted analysis runs are never updated."""

    actor = actor_subject.strip() if actor_subject else None
    if actor_subject is not None and not actor:
        raise EconomicsMigrationError("rollback actor cannot be empty")
    try:
        with database.session() as session:
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('robodovod:economics-route'))")
            )
            current = session.scalar(
                select(EconomicsRouteActivation)
                .where(EconomicsRouteActivation.deactivated_at.is_(None))
                .with_for_update()
            )
            if current is None:
                raise EconomicsMigrationError("economics route is not active")
            target = current.rollback_economics_version
            now = utcnow()
            current.deactivated_at = now
            session.flush()
            rollback = EconomicsRouteActivation(
                id=uuid.uuid4(),
                economics_version=target,
                policy_version=current.policy_version,
                approval_report_sha256=current.approval_report_sha256,
                rollback_economics_version=current.economics_version,
                actor_subject=actor,
                activated_at=now,
            )
            session.add(rollback)
            session.commit()
            return EconomicsActivationResult(
                economics_version=target,
                activation_id=str(rollback.id),
                changed=True,
                rollback_economics_version=current.economics_version,
            )
    except EconomicsMigrationError:
        raise
    except (IntegrityError, SQLAlchemyError) as exc:
        raise EconomicsMigrationError("economics route rollback failed database checks") from exc


def economics_route_status(database: Database) -> dict[str, object]:
    with database.session() as session:
        active = session.scalar(
            select(EconomicsRouteActivation).where(
                EconomicsRouteActivation.deactivated_at.is_(None)
            )
        )
        return {
            "active_version": active.economics_version if active is not None else None,
            "activation_id": str(active.id) if active is not None else None,
            "history_count": int(
                session.scalar(select(func.count()).select_from(EconomicsRouteActivation)) or 0
            ),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the versioned economics route")
    commands = parser.add_subparsers(dest="command", required=True)
    activate = commands.add_parser("activate")
    activate.add_argument("--approval-report", type=Path, required=True)
    activate.add_argument("--actor", default="economics-route-cli")
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--actor", default="economics-route-cli")
    commands.add_parser("status")
    args = parser.parse_args(argv)

    try:
        database = Database(DatabaseSettings.from_environment())
        try:
            if args.command == "activate":
                report = EconomicsDualRunReportV1.model_validate_json(
                    args.approval_report.read_text(encoding="utf-8")
                )
                result: object = activate_economics_route(
                    database, report, actor_subject=args.actor
                )
            elif args.command == "rollback":
                result = rollback_economics_route(database, actor_subject=args.actor)
            else:
                result = economics_route_status(database)
        finally:
            database.dispose()
    except Exception as exc:  # noqa: BLE001
        error_name = type(exc).__name__
        if not isinstance(exc, EconomicsMigrationError):
            error_name = "EconomicsMigrationError"
        print(f"economics route operation failed: {error_name}", file=sys.stderr)
        return 2
    payload = asdict(result) if hasattr(result, "__dataclass_fields__") else result
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
