"""Build/check C03 intake schemas and profile golden fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calculation.intake import (  # noqa: E402
    CalculationIntakeRequestV2,
    NormalizationResponseV2,
    adapt_project_file_v1,
    normalize_intake,
)
from project_file_intake import build_csv_template, inspect_project_file  # noqa: E402


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def outputs() -> dict[Path, str]:
    result = {
        ROOT / "contracts" / "calculation-intake-request-v2.schema.json": encoded(CalculationIntakeRequestV2.model_json_schema()),
        ROOT / "contracts" / "calculation-intake-normalization-v2.schema.json": encoded(NormalizationResponseV2.model_json_schema()),
    }
    names = {"warehouse": "warehouse", "airport": "airport", "medical_facility": "clinic"}
    for profile_code, name in names.items():
        filename, payload = build_csv_template(profile_code)
        legacy = inspect_project_file(filename, payload, profile_code)
        request = adapt_project_file_v1(legacy, input_revision=f"fixture.{name}.v2", object_id=f"fixture.{name}")
        response = normalize_intake(request)
        fixture = {"request": request.model_dump(mode="json"), "response": response.model_dump(mode="json")}
        result[ROOT / "contracts" / "fixtures" / f"calculation-intake-v2.{name}.json"] = encoded(fixture)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    drift: list[str] = []
    for path, content in outputs().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                drift.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if drift:
        print("C03 contract drift: " + ", ".join(drift))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
