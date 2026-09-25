"""Publish additive stage 6 simulation contracts without rewriting v1 evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calculation.scheduling import SimulationReportV3, SimulationRequestV2  # noqa: E402

CONTRACTS = {
    "simulation-request-v2": SimulationRequestV2,
    "simulation-report-v3": SimulationReportV3,
}


def expected(name, model):
    schema = model.model_json_schema(ref_template="#/$defs/{model}", mode="serialization")
    schema["$id"] = f"https://robomera.local/contracts/{name}.schema.json"
    return (json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    valid = True
    for name, model in CONTRACTS.items():
        target = ROOT / "contracts" / f"{name}.schema.json"
        data = expected(name, model)
        if args.check:
            valid &= target.is_file() and target.read_bytes() == data
        else:
            target.write_bytes(data)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
