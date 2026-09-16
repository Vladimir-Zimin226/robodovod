"""Password, session-cookie and authorization primitives."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type
from fastapi import Depends, Header, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import database_session
from persistence_models import User, UserSession


SESSION_COOKIE = "robodovod_session"
CSRF_COOKIE = "robodovod_csrf"
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PASSWORD_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash("nonexistent-account-timing-guard")


@dataclass(frozen=True)
class SessionSettings:
    ttl_seconds: int = 60 * 60 * 12
    secure_cookie: bool = False

    @classmethod
    def from_environment(cls) -> "SessionSettings":
        try:
            ttl = int(os.getenv("SESSION_TTL_SECONDS", str(cls.ttl_seconds)))
        except ValueError:
            raise RuntimeError("SESSION_TTL_SECONDS must be an integer") from None
        if ttl < 300 or ttl > 60 * 60 * 24 * 30:
            raise RuntimeError("SESSION_TTL_SECONDS is outside the supported range")
        secure = os.getenv("SESSION_COOKIE_SECURE", "false").strip().lower()
        if secure not in {"true", "false"}:
            raise RuntimeError("SESSION_COOKIE_SECURE must be true or false")
        return cls(ttl_seconds=ttl, secure_cookie=secure == "true")


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: UserSession


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 320 or not _EMAIL_RE.fullmatch(email):
        raise ValueError("invalid email")
    return email


def normalize_name(value: str | None) -> str | None:
    if value is None:
        return None
    name = " ".join(value.strip().split())
    if not name or len(name) > 200:
        raise ValueError("invalid name")
    return name


def validate_password(password: str) -> None:
    if len(password) < 12 or len(password) > 128:
        raise ValueError("password must contain from 12 to 128 characters")


def hash_password(password: str) -> str:
    validate_password(password)
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash or _DUMMY_PASSWORD_HASH, password)
    except (InvalidHashError, VerificationError):
        return False


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User) -> tuple[UserSession, str, str]:
    settings = SessionSettings.from_environment()
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = utcnow()
    record = UserSession(
        id=uuid.uuid4(),
        user_id=user.id,
        token_sha256=_digest(token),
        csrf_sha256=_digest(csrf),
        created_at=now,
        expires_at=now + timedelta(seconds=settings.ttl_seconds),
    )
    db.add(record)
    return record, token, csrf


def set_session_cookies(response: Response, token: str, csrf: str) -> None:
    settings = SessionSettings.from_environment()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.ttl_seconds,
        secure=settings.secure_cookie,
        httponly=True,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=settings.ttl_seconds,
        secure=settings.secure_cookie,
        httponly=False,
        samesite="strict",
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    settings = SessionSettings.from_environment()
    for name, httponly in ((SESSION_COOKIE, True), (CSRF_COOKIE, False)):
        response.delete_cookie(
            name,
            secure=settings.secure_cookie,
            httponly=httponly,
            samesite="strict",
            path="/",
        )


def require_auth_context(
    request: Request,
    db: Session = Depends(database_session),
) -> AuthContext:
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        raise HTTPException(status_code=401, detail="authentication required")
    now = utcnow()
    row = db.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(
            UserSession.token_sha256 == _digest(raw_token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
            User.status == "ACTIVE",
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=401, detail="authentication required")
    user_session, user = row
    user_session.last_used_at = now
    return AuthContext(user=user, session=user_session)


def require_csrf(
    request: Request,
    context: AuthContext = Depends(require_auth_context),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> AuthContext:
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    if (
        not csrf_header
        or not csrf_cookie
        or not hmac.compare_digest(csrf_header, csrf_cookie)
        or not hmac.compare_digest(_digest(csrf_header), context.session.csrf_sha256)
    ):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    return context


def require_admin(context: AuthContext = Depends(require_auth_context)) -> AuthContext:
    if context.user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="administrator role required")
    return context
