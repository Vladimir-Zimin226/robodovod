"""Seed only a new localhost stage11_* PostgreSQL database for browser acceptance."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from catalog_activation import activate_catalog_version, publish_catalog_version  # noqa: E402
from catalog_capacity_rollout import CapacityDualRunReportV1  # noqa: E402
from catalog_importer import run_catalog_import  # noqa: E402
from database import Database, DatabaseSettings  # noqa: E402
from economics_route_activation import activate_economics_route  # noqa: E402
from economics_runtime_migration import EconomicsDualRunReportV1  # noqa: E402


def main() -> None:
    raw_url = os.getenv("DATABASE_URL", "")
    url = make_url(raw_url)
    if url.drivername != "postgresql+psycopg" or url.host not in {"localhost", "127.0.0.1"} or not url.database.startswith("stage11_"):
        raise SystemExit("Refusing to seed anything except a localhost stage11_* PostgreSQL database")
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            table = connection.execute(text("SELECT to_regclass('public.users')")).scalar()
            if table is not None:
                user_count = connection.execute(text("SELECT count(*) FROM users")).scalar_one()
                catalog_count = connection.execute(text("SELECT count(*) FROM catalog_versions")).scalar_one()
                if user_count or catalog_count:
                    raise SystemExit("Disposable database is not empty; create a new stage11_* database")
        command.upgrade(Config(str(ROOT / "backend" / "alembic.ini")), "head")
        database = Database(DatabaseSettings(url=url))
        try:
            bundle = ROOT / "data" / "import" / "organizer-catalog-v4"
            run_catalog_import(database, bundle, phase="BASE", mode="COMMIT")
            run_catalog_import(database, bundle, phase="ENRICHMENT", mode="COMMIT")
            publish_catalog_version(database, "organizer-catalog-v4", bundle)
            capacity_approval = CapacityDualRunReportV1.model_validate_json((
                ROOT / "contracts" / "fixtures" / "capacity-catalog-dual-run-report-v1.golden.json"
            ).read_text(encoding="utf-8"))
            activate_catalog_version(database, "organizer-catalog-v4", slot="capacity",
                                     actor_subject="stage11-local-acceptance", capacity_approval=capacity_approval)
            activate_catalog_version(database, "organizer-catalog-v4", slot="discovery",
                                     actor_subject="stage11-local-acceptance")
            economics_approval = EconomicsDualRunReportV1.model_validate_json((
                ROOT / "contracts" / "fixtures" / "economics-dual-run-report-v1.golden.json"
            ).read_text(encoding="utf-8"))
            activate_economics_route(database, economics_approval, actor_subject="stage11-local-acceptance")
            print("Disposable stage11 catalog, capacity and economics routes activated")
        finally:
            database.dispose()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
