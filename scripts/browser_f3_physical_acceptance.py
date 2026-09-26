"""Reuse F1 physical/browser gate on the F3 active catalog, preserving old evidence.

Run browser_f3_acceptance.py first. F1_DATABASE_URL must name the local
stage11_f1_browser disposable DB. Output stays separate from F1 evidence.
"""

import json
import os
import runpy
from pathlib import Path
from urllib.parse import urlparse

import psycopg

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "scripts/browser_f1_acceptance.py"
url = os.environ["F1_DATABASE_URL"].replace("postgresql+psycopg:", "postgresql:")
parsed = urlparse(url)
assert (
    parsed.hostname == "127.0.0.1"
    and parsed.port == 5541
    and parsed.path == "/stage11_f1_browser"
)


def rows(table):
    assert table in {"analysis_runs", "simulation_artifacts"}
    with psycopg.connect(url) as database:
        return {
            str(row[0]): row[1]
            for row in database.execute(f"SELECT id,row_to_json(r) FROM {table} r")
        }


before = {table: rows(table) for table in ("analysis_runs", "simulation_artifacts")}
# Use pre-existing organizer runs to verify old PDF/C23 identity, while the three
# additional recalculations resolve the active F3 capacity source server-side.
os.environ["F1_ACCEPTANCE_STAGE"] = "F3"
runpy.run_path(str(SOURCE_PATH), run_name="__main__")
for table, previous in before.items():
    current = rows(table)
    assert all(current[key] == value for key, value in previous.items()), table
(ROOT / ".tmp/f3/physical/history-check.json").write_text(
    json.dumps({table: len(values) for table, values in before.items()}, indent=2),
    encoding="utf-8",
)
print("ALL previously existing runs/artifacts unchanged", flush=True)
