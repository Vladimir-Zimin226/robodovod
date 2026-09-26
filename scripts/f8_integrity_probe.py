"""Read-only digests of retained disposable historical rows and sample files."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg

ROOT = Path(__file__).resolve().parents[1]
URL = os.getenv("F8_DATABASE_URL", "")
target = urlparse(URL)
assert target.hostname == "127.0.0.1" and target.port == 5541 and target.path == "/stage11_f1_browser"
tables = ("analysis_runs", "simulation_artifacts")
rows = {}
with psycopg.connect(URL) as connection:
    for table in tables:
        values = [item[0] for item in connection.execute(
            f"SELECT row_to_json(r)::text FROM {table} r ORDER BY id").fetchall()]
        rows[table] = {"count": len(values), "sha256": hashlib.sha256(
            "\n".join(values).encode()).hexdigest()}
files = {}
for relative in (
    "docs/planning/assets/f5/sample-220-pallets-120m.zip",
    "frontend/public/demo/warehouse-pallet-v1/evidence.zip",
    "contracts/fixtures/production-economics-orchestrator-v2.golden.json",
):
    files[relative] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
output = ROOT / "docs" / "delivery" / "f8" / "integrity-probe.json"
output.write_text(json.dumps({"source": "retained local disposable DB and tracked sample files",
    "rows": rows, "files": files}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(output)
