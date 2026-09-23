"""Operator-only C28 economics route activation and rollback service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from auth import utcnow
from database import Database
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
