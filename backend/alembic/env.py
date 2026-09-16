from __future__ import annotations

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import DatabaseSettings  # noqa: E402
import catalog_models  # noqa: E402, F401
from storage_models import Base  # noqa: E402


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    settings = DatabaseSettings.from_environment()
    context.configure(
        url=settings.url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    settings = DatabaseSettings.from_environment()
    engine = create_engine(
        settings.url,
        poolclass=NullPool,
        hide_parameters=True,
    )

    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
