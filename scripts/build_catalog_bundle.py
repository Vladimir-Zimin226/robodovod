"""Build the committed organizer catalog bundle from the ignored staging area.

This is a maintainer command. Runtime import consumes only the committed bundle
and never reads ``data/staging``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGING = ROOT / "data" / "staging"
DEFAULT_OUTPUT = ROOT / "data" / "import" / "organizer-catalog-v4"

DATA_FILES = {
    "catalog_products.json": "catalog_products.json",
    "catalog_applicability.csv": "catalog_applicability.csv",
    "catalog_prices.csv": "catalog_prices.csv",
    "catalog_field_evidence.csv": "catalog_field_evidence.csv",
    "object_profiles.json": "object_profiles.json",
    "catalog_external_enrichment.json": (
        "enrichment-run-1/catalog_external_enrichment.json"
    ),
    "catalog_external_evidence.csv": ("enrichment-run-1/catalog_external_evidence.csv"),
}

FILE_CONTRACTS = {
    "catalog_products.json": ("BASE", "products", 187),
    "catalog_applicability.csv": ("BASE", "rows", 223),
    "catalog_prices.csv": ("BASE", "rows", 223),
    "catalog_field_evidence.csv": ("BASE", "rows", 3635),
    "object_profiles.json": ("REFERENCE", "parameters", 138),
    "catalog_external_enrichment.json": ("ENRICHMENT", "fields", 140),
    "catalog_external_evidence.csv": ("ENRICHMENT", "rows", 156),
}

IMPORT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://robodovod.local/schemas/catalog-import-bundle-v1.json",
    "title": "ROBODOVOD catalog import bundle manifest",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "catalog",
        "pricing_policy",
        "expected_counts",
        "files",
        "source_artifacts",
    ],
    "properties": {
        "schema_version": {"const": "robodovod-catalog-import-bundle-v1"},
        "catalog": {
            "type": "object",
            "additionalProperties": False,
            "required": ["code", "schema_version", "source_namespace"],
            "properties": {
                "code": {"const": "organizer-catalog-v4"},
                "schema_version": {"const": "2"},
                "source_namespace": {"const": "organizer-v4"},
            },
        },
        "pricing_policy": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "currency",
                "currency_provenance",
                "vat_status",
                "vat_rate",
                "vat_provenance",
                "excluded_costs",
            ],
            "properties": {
                "currency": {"const": "RUB"},
                "currency_provenance": {"type": "string", "minLength": 1},
                "vat_status": {"const": "ORGANIZER_ASSUMPTION_INCLUDED"},
                "vat_rate": {"type": "null"},
                "vat_provenance": {"type": "string", "minLength": 1},
                "excluded_costs": {
                    "type": "array",
                    "minItems": 3,
                    "items": {"type": "string", "minLength": 1},
                },
            },
        },
        "expected_counts": {
            "type": "object",
            "additionalProperties": {"type": "integer", "minimum": 0},
        },
        "files": {
            "type": "array",
            "minItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "phase", "sha256", "size_bytes"],
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "phase": {"enum": ["BASE", "ENRICHMENT", "REFERENCE"]},
                    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "size_bytes": {"type": "integer", "minimum": 1},
                    "record_kind": {"type": ["string", "null"]},
                    "records": {"type": ["integer", "null"], "minimum": 0},
                },
            },
        },
        "source_artifacts": {
            "type": "array",
            "minItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "artifact_key",
                    "original_name",
                    "sha256",
                    "size_bytes",
                    "media_type",
                    "provenance_status",
                    "license_status",
                    "role",
                    "ordinal",
                    "observed_at",
                ],
                "properties": {
                    "artifact_key": {"type": "string", "minLength": 1},
                    "original_name": {"type": "string", "minLength": 1},
                    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "size_bytes": {"type": "integer", "minimum": 1},
                    "media_type": {"type": "string", "minLength": 1},
                    "provenance_status": {"const": "VERIFIED"},
                    "license_status": {"enum": ["PERMITTED", "RESTRICTED"]},
                    "role": {
                        "enum": ["BASE", "ENRICHMENT", "REFERENCE", "IMPORT_BUNDLE"]
                    },
                    "ordinal": {"type": "integer", "minimum": 0},
                    "observed_at": {"type": "string", "format": "date-time"},
                },
            },
        },
    },
}

README = """# Organizer catalog v4 import bundle

This directory is the committed, text-only derived bundle for the explicit
catalog importer. It is not read by backend startup and it contains no original
PDF, XLSX, DOCX, or organizer CSV binaries.

`manifest.json` is the authority for file hashes, byte sizes, record counts,
source-artifact metadata, and the versioned RUB/VAT product decision. The
importer verifies every entry before creating an `ImportRun`.

Import order:

1. `BASE` validates/imports 187 products, 223 source rows, 223 applicability
   rows, 223 price offers, 3635 base evidence rows, and 65 base spec facts.
2. `ENRICHMENT` validates/imports 140 overlay observations and 156 external
   evidence rows. It never updates organizer observations.

Only safe resolved statuses can enter `matching_spec_facts`. `CONFLICT`,
`AMBIGUOUS_MODEL_MATCH`, `NOT_FOUND`, and `UNKNOWN` remain observations.

The v4 price currency is RUB by a versioned product decision, not by inference
from the source CSV. VAT is marked `ORGANIZER_ASSUMPTION_INCLUDED`, with
`vat_rate = null`. Delivery, commissioning/start-up, and deep IT integration
remain excluded costs.

Rebuild from the ignored maintainer staging area:

```bash
python scripts/build_catalog_bundle.py
python scripts/build_catalog_bundle.py --check
```
"""


ORIGINAL_ARTIFACTS = [
    {
        "artifact_key": "official-main-requirements",
        "original_name": "1. ФЦ БАС.pdf",
        "sha256": "acc5feed8f8686ee9928839a56c9b084e1bd577db55ef1e63b5c5b42278d4713",
        "size_bytes": 565739,
        "media_type": "application/pdf",
        "provenance_status": "VERIFIED",
        "license_status": "RESTRICTED",
        "role": "REFERENCE",
        "ordinal": 0,
        "observed_at": "2026-09-15T00:00:00+00:00",
    },
    {
        "artifact_key": "official-addendum",
        "original_name": "Дополнения для участников.pdf",
        "sha256": "64eac97cc4c985035286ebbedfcd5b356c4aba4af1d1d69f2ac0ca1f20adc456",
        "size_bytes": 172735,
        "media_type": "application/pdf",
        "provenance_status": "VERIFIED",
        "license_status": "RESTRICTED",
        "role": "BASE",
        "ordinal": 2,
        "observed_at": "2026-09-15T00:00:00+00:00",
    },
    {
        "artifact_key": "official-object-profiles",
        "original_name": "Датасеты_хакатон.xlsx",
        "sha256": "6649c501464135e6c0b43809e4461b4a74b63d2b211f5b6aaf3a33ced0fed2a0",
        "size_bytes": 29823,
        "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "provenance_status": "VERIFIED",
        "license_status": "RESTRICTED",
        "role": "REFERENCE",
        "ordinal": 1,
        "observed_at": "2026-09-15T00:00:00+00:00",
    },
    {
        "artifact_key": "organizer-catalog-v4-csv",
        "original_name": "catalog_export_v4.csv",
        "sha256": "1521b9c886a706eda3a65cd697ec78018ad41d501713333e834266879dedb5d9",
        "size_bytes": 170058,
        "media_type": "text/csv",
        "provenance_status": "VERIFIED",
        "license_status": "RESTRICTED",
        "role": "BASE",
        "ordinal": 0,
        "observed_at": "2026-09-15T00:00:00+00:00",
    },
    {
        "artifact_key": "official-solution-examples",
        "original_name": "Примеры_решений_типы_объектов.docx",
        "sha256": "2ced71f9d0c633d8f0baecd53413bfe6e5595599279349bcad7812e87d8c3d95",
        "size_bytes": 890297,
        "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "provenance_status": "VERIFIED",
        "license_status": "RESTRICTED",
        "role": "BASE",
        "ordinal": 1,
        "observed_at": "2026-09-15T00:00:00+00:00",
    },
    {
        "artifact_key": "official-visual-catalog-91-pages",
        "original_name": "ФЦ БАС — Каталог внедрения 2008 1247.pdf",
        "sha256": "9567641d3a3a7bed9d2e470240b17cefacba047257b5f0b4a5311c159c580369",
        "size_bytes": 84906007,
        "media_type": "application/pdf",
        "provenance_status": "VERIFIED",
        "license_status": "RESTRICTED",
        "role": "REFERENCE",
        "ordinal": 2,
        "observed_at": "2026-09-16T00:00:00+00:00",
    },
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build(staging: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for target_name, source_name in DATA_FILES.items():
        source = staging / source_name
        if not source.is_file():
            raise FileNotFoundError(f"required staging file is missing: {source_name}")
        shutil.copyfile(source, output / target_name)

    schema_path = output / "import-schema.json"
    _write_json(schema_path, IMPORT_SCHEMA)
    (output / "README.md").write_text(README, encoding="utf-8", newline="\n")

    files = []
    for name in (*DATA_FILES.keys(), "import-schema.json"):
        path = output / name
        contract = FILE_CONTRACTS.get(name)
        phase, record_kind, records = contract or ("REFERENCE", None, None)
        files.append(
            {
                "path": name,
                "phase": phase,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
                "record_kind": record_kind,
                "records": records,
            }
        )

    artifacts = list(ORIGINAL_ARTIFACTS)
    for ordinal, file_entry in enumerate(files):
        artifacts.append(
            {
                "artifact_key": f"bundle:{file_entry['path']}",
                "original_name": file_entry["path"],
                "sha256": file_entry["sha256"],
                "size_bytes": file_entry["size_bytes"],
                "media_type": (
                    "application/json"
                    if file_entry["path"].endswith(".json")
                    else "text/csv"
                ),
                "provenance_status": "VERIFIED",
                "license_status": "PERMITTED",
                "role": "IMPORT_BUNDLE",
                "ordinal": ordinal,
                "observed_at": "2026-09-16T00:00:00+00:00",
            }
        )

    manifest = {
        "schema_version": "robodovod-catalog-import-bundle-v1",
        "catalog": {
            "code": "organizer-catalog-v4",
            "schema_version": "2",
            "source_namespace": "organizer-v4",
        },
        "pricing_policy": {
            "currency": "RUB",
            "currency_provenance": "product-decision:organizer-catalog-v4-rub-v1",
            "vat_status": "ORGANIZER_ASSUMPTION_INCLUDED",
            "vat_rate": None,
            "vat_provenance": "official-addendum-page-4:included-unless-qa;rate-unspecified",
            "excluded_costs": [
                "delivery",
                "commissioning/start-up",
                "deep IT integration",
            ],
        },
        "expected_counts": {
            "products": 187,
            "catalog_source_rows": 223,
            "applicability_rows": 223,
            "price_rows": 223,
            "base_evidence_rows": 3635,
            "base_spec_fields": 65,
            "object_profiles": 3,
            "object_profile_parameters": 138,
            "enrichment_products": 11,
            "overlay_fields": 140,
            "external_evidence_rows": 156,
        },
        "files": files,
        "source_artifacts": artifacts,
    }
    _write_json(output / "manifest.json", manifest)


def check(staging: Path, output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="robodovod-bundle-") as temporary:
        candidate = Path(temporary) / "organizer-catalog-v4"
        build(staging, candidate)
        expected = {p.name: p.read_bytes() for p in candidate.iterdir() if p.is_file()}
        actual = {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
        if expected != actual:
            missing = sorted(expected.keys() - actual.keys())
            extra = sorted(actual.keys() - expected.keys())
            changed = sorted(
                name
                for name in expected.keys() & actual.keys()
                if expected[name] != actual[name]
            )
            raise SystemExit(
                f"bundle differs: missing={missing}, extra={extra}, changed={changed}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check(args.staging.resolve(), args.output.resolve())
    else:
        build(args.staging.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
