"""Generate the strict C24 simulation lifecycle polling schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from simulation_api import SimulationRunStateV1  # noqa: E402


TARGET = ROOT / "contracts" / "simulation-run-state-v1.schema.json"


def expected_bytes() -> bytes:
    body = SimulationRunStateV1.model_json_schema(
        ref_template="#/$defs/{model}", mode="serialization"
    )
    body["$id"] = "https://robomera.local/contracts/simulation-run-state-v1.schema.json"
    body["title"] = "Robomera SimulationRunState v1"
    return (json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = expected_bytes()
    if args.check:
        return 0 if TARGET.is_file() and TARGET.read_bytes() == expected else 1
    TARGET.write_bytes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
