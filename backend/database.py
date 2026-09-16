"""Server-side PostgreSQL connection and SQLAlchemy session boundary."""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker


class DatabaseConfigurationError(RuntimeError):
    """Raised for a missing or unsupported DATABASE_URL without echoing it."""


@dataclass(frozen=True, repr=False)
class DatabaseSettings:
    url: URL

    def __repr__(self) -> str:
        return "DatabaseSettings(url=<redacted>)"

    @classmethod
    def from_environment(cls) -> "DatabaseSettings":
        raw_url = os.getenv("DATABASE_URL", "").strip()
        if not raw_url:
            raise DatabaseConfigurationError("DATABASE_URL is required")

        try:
            url = make_url(raw_url)
        except (ArgumentError, ValueError):
            raise DatabaseConfigurationError("DATABASE_URL is invalid") from None

        if url.drivername != "postgresql+psycopg":
            raise DatabaseConfigurationError(
                "DATABASE_URL must use the postgresql+psycopg driver"
            )
        if not url.database:
            raise DatabaseConfigurationError("DATABASE_URL must include a database name")
        return cls(url=url)


class Database:
    """Owns one engine and creates short-lived SQLAlchemy sessions."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self.engine: Engine = create_engine(
            settings.url,
            pool_pre_ping=True,
            hide_parameters=True,
        )
        self._session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            autoflush=False,
            expire_on_commit=False,
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def check_connection(self) -> None:
        # Closing the context always returns the pooled connection, including
        # when SELECT 1 fails.
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def dispose(self) -> None:
        self.engine.dispose()


_database: Database | None = None
_database_lock = threading.Lock()


def get_database() -> Database:
    global _database
    if _database is None:
        with _database_lock:
            if _database is None:
                _database = Database(DatabaseSettings.from_environment())
    return _database


def dispose_database() -> None:
    """Dispose the current engine; also used when tests change DATABASE_URL."""

    global _database
    with _database_lock:
        if _database is not None:
            _database.dispose()
            _database = None


def database_session() -> Iterator[Session]:
    """FastAPI-compatible dependency for future repository-backed endpoints."""

    with get_database().session() as session:
        yield session
