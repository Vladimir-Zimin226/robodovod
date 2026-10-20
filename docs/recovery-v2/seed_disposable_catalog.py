"""Activate the published catalog bundle only in this disposable local PostgreSQL.

Run from backend with DATABASE_URL pointing to 127.0.0.1:55432/robodovod_recovery.
The strict address check prevents accidentally writing to another database.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from catalog_activation import activate_catalog_version, publish_catalog_version
from catalog_capacity_rollout import CapacityDualRunReportV1
from catalog_importer import run_catalog_import
from catalog_repository import ActivatedCatalogRepository
from database import Database, DatabaseSettings
from economics_route_activation import activate_economics_route
from economics_runtime_migration import EconomicsDualRunReportV1


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data/import/organizer-catalog-v4"
CODE = "organizer-catalog-v4"


def main():
    settings = DatabaseSettings.from_environment()
    url = settings.url
    if (url.host, url.port, url.database) != (
        "127.0.0.1", 55432, "robodovod_recovery"
    ):
        raise SystemExit("Refusing to seed a database outside the disposable local cluster")

    command.upgrade(Config(str(ROOT / "backend/alembic.ini")), "head")
    database = Database(settings)
    try:
        for phase in ("BASE", "ENRICHMENT"):
            run_catalog_import(database, BUNDLE, phase=phase, mode="COMMIT")
        publish_catalog_version(database, CODE, BUNDLE)
        capacity_approval = CapacityDualRunReportV1.model_validate_json(
            (ROOT / "contracts/fixtures/capacity-catalog-dual-run-report-v1.golden.json")
            .read_text(encoding="utf-8")
        )
        # This published bundle has no evidence-backed runtime robots; the
        # runtime slot must remain inactive rather than inventing eligibility.
        for slot in ("capacity", "discovery"):
            activate_catalog_version(
                database, CODE, slot=slot, actor_subject="local-recovery-v2",
                capacity_approval=capacity_approval if slot == "capacity" else None,
            )
        economics_approval = EconomicsDualRunReportV1.model_validate_json(
            (ROOT / "contracts/fixtures/economics-dual-run-report-v1.golden.json")
            .read_text(encoding="utf-8")
        )
        activate_economics_route(database, economics_approval,
                                 actor_subject="local-recovery-v2")
        snapshot = ActivatedCatalogRepository(database, "capacity").load()
        print({"catalog": snapshot.version.code,
               "models": len(snapshot.models), "positions": len(snapshot.positions),
               "capacity_ready_models": len(snapshot.calculation_ready_models()),
               "capacity_ready_positions": len(snapshot.calculation_ready_positions()),
               "runtime_slot": "INACTIVE_NO_EVIDENCE_BACKED_ROBOTS"})
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
