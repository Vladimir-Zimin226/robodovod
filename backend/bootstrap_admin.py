"""One-shot, idempotent first-administrator bootstrap.

Credentials are read only from environment variables; the password is never a
CLI argument and never appears in logs or output.
"""

from __future__ import annotations

import os
import sys
import uuid

from sqlalchemy import func, select, text

from auth import hash_password, normalize_email, normalize_name
from database import get_database
from persistence_models import AuditEntry, User


class BootstrapError(RuntimeError):
    pass


def bootstrap_admin() -> str:
    raw_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "")
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    raw_name = os.getenv("BOOTSTRAP_ADMIN_NAME")
    if not raw_email or not password:
        raise BootstrapError("bootstrap administrator credentials are not configured")
    try:
        email = normalize_email(raw_email)
        name = normalize_name(raw_name)
        password_hash = hash_password(password)
    except ValueError as exc:
        raise BootstrapError("bootstrap administrator credentials are invalid") from exc

    with get_database().session() as db:
        # A transaction-scoped lock makes concurrent one-shot invocations safe.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext('robodovod-admin-bootstrap'))"))
        admin_count = db.scalar(
            select(func.count()).select_from(User).where(User.role == "ADMIN")
        )
        if admin_count:
            db.rollback()
            return "already_initialized"
        collision = db.scalar(select(User).where(User.email_normalized == email))
        if collision is not None:
            db.rollback()
            raise BootstrapError("bootstrap email belongs to an existing non-admin account")
        user = User(
            id=uuid.uuid4(),
            email_normalized=email,
            password_hash=password_hash,
            name=name,
            role="ADMIN",
            status="ACTIVE",
        )
        db.add(user)
        db.add(
            AuditEntry(
                id=uuid.uuid4(),
                event_type="ADMIN_BOOTSTRAPPED",
                actor_user_id=user.id,
                subject_user_id=user.id,
                aggregate={},
            )
        )
        db.commit()
        return "created"


def main() -> int:
    try:
        result = bootstrap_admin()
    except BootstrapError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        # Database/driver errors can embed credentials; disclose only the type.
        print(f"administrator bootstrap failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    print(f"administrator bootstrap: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
