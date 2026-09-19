"""Strict contract loader for committed catalog import bundles."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from catalog_models import EVIDENCE_STATUSES, REVIEWED_STATUSES, SAFE_AUTOMATIC_STATUSES
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_FILES = {
    "catalog_products.json",
    "catalog_applicability.csv",
    "catalog_prices.csv",
    "catalog_field_evidence.csv",
    "object_profiles.json",
    "catalog_external_enrichment.json",
    "catalog_external_evidence.csv",
    "catalog_capacity_enrichment.json",
    "catalog_capacity_runtime.json",
    "import-schema.json",
}


class CatalogBundleError(ValueError):
    """A safe, user-facing bundle validation error."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CatalogInfo(StrictModel):
    code: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    source_namespace: str = Field(min_length=1)


class PricingPolicy(StrictModel):
    currency: Literal["RUB"]
    currency_provenance: str = Field(min_length=1)
    vat_status: Literal["ORGANIZER_ASSUMPTION_INCLUDED"]
    vat_rate: None
    vat_provenance: str = Field(min_length=1)
    excluded_costs: list[str] = Field(min_length=3)


class BundleFile(StrictModel):
    path: str = Field(min_length=1)
    phase: Literal["BASE", "ENRICHMENT", "REFERENCE"]
    sha256: str
    size_bytes: int = Field(gt=0)
    record_kind: str | None = None
    records: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_checksum(self) -> BundleFile:
        if not SHA256_RE.fullmatch(self.sha256):
            raise ValueError("sha256 must be lowercase hexadecimal")
        return self


class SourceArtifactContract(StrictModel):
    artifact_key: str = Field(min_length=1)
    original_name: str = Field(min_length=1)
    sha256: str
    size_bytes: int = Field(gt=0)
    media_type: str = Field(min_length=1)
    provenance_status: Literal["VERIFIED"]
    license_status: Literal["PERMITTED", "RESTRICTED"]
    role: Literal["BASE", "ENRICHMENT", "REFERENCE", "IMPORT_BUNDLE"]
    ordinal: int = Field(ge=0)
    observed_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_checksum(self) -> SourceArtifactContract:
        if not SHA256_RE.fullmatch(self.sha256):
            raise ValueError("sha256 must be lowercase hexadecimal")
        try:
            datetime.fromisoformat(self.observed_at)
        except ValueError as exc:
            raise ValueError("observed_at must be an ISO-8601 timestamp") from exc
        return self


class BundleManifest(StrictModel):
    schema_version: Literal["robodovod-catalog-import-bundle-v1"]
    catalog: CatalogInfo
    pricing_policy: PricingPolicy
    expected_counts: dict[str, int]
    files: list[BundleFile]
    source_artifacts: list[SourceArtifactContract]

    @model_validator(mode="after")
    def validate_identity(self) -> BundleManifest:
        if self.catalog.code != "organizer-catalog-v4":
            raise ValueError("unsupported catalog code")
        if self.catalog.schema_version != "2":
            raise ValueError("unsupported catalog schema version")
        if self.catalog.source_namespace != "organizer-v4":
            raise ValueError("unsupported source namespace")
        file_paths = [entry.path for entry in self.files]
        if len(file_paths) != len(set(file_paths)):
            raise ValueError("duplicate file path")
        if set(file_paths) != REQUIRED_FILES:
            raise ValueError("manifest file set is incomplete or unexpected")
        artifact_keys = [entry.artifact_key for entry in self.source_artifacts]
        if len(artifact_keys) != len(set(artifact_keys)):
            raise ValueError("duplicate source artifact key")
        artifact_hashes = [entry.sha256 for entry in self.source_artifacts]
        if len(artifact_hashes) != len(set(artifact_hashes)):
            raise ValueError("duplicate source artifact checksum")
        role_ordinals = [(entry.role, entry.ordinal) for entry in self.source_artifacts]
        if len(role_ordinals) != len(set(role_ordinals)):
            raise ValueError("duplicate source artifact role/ordinal")
        artifacts_by_key = {
            entry.artifact_key: entry for entry in self.source_artifacts
        }
        for file_entry in self.files:
            artifact = artifacts_by_key.get(f"bundle:{file_entry.path}")
            if (
                artifact is None
                or artifact.original_name != file_entry.path
                or artifact.sha256 != file_entry.sha256
                or artifact.size_bytes != file_entry.size_bytes
            ):
                raise ValueError("bundle file artifact metadata differs")
        visual_catalog = artifacts_by_key.get("official-visual-catalog-91-pages")
        if (
            visual_catalog is None
            or visual_catalog.sha256
            != "9567641d3a3a7bed9d2e470240b17cefacba047257b5f0b4a5311c159c580369"
        ):
            raise ValueError("91-page official catalog artifact is missing")
        required_exclusions = {
            "delivery",
            "commissioning/start-up",
            "deep IT integration",
        }
        if set(self.pricing_policy.excluded_costs) != required_exclusions:
            raise ValueError("organizer v4 excluded cost policy differs")
        return self


class CapacityScenarioAssumption(StrictModel):
    field: str = Field(min_length=1)
    input_path: str = Field(min_length=1)
    fallback_value: int | float | str | bool
    unit: str = Field(min_length=1)
    policy: Literal["SCENARIO_INPUT_THEN_EXPLICIT_FALLBACK"]
    provenance: str = Field(min_length=1)
    vendor_fact: Literal[False]


class CapacityRuntimeModel(StrictModel):
    model_id: str = Field(min_length=1)
    calculation_readiness_status: Literal[
        "CALCULATION_READY",
        "CALCULATION_READY_WITH_ASSUMPTIONS",
        "CALCULATION_BLOCKED",
        "UNSUPPORTED_CAPACITY_PROFILE",
        "NOT_EQUIPMENT",
    ]
    calculation_ready: bool
    calculation_requires_assumptions: bool
    calculation_profile: str | None
    calculation_model_fields: list[str]
    calculation_blockers: list[str]
    scenario_assumptions: list[CapacityScenarioAssumption]
    deployment_readiness_status: Literal[
        "DEPLOYMENT_READY",
        "DEPLOYMENT_REVIEW_REQUIRED",
        "UNSUPPORTED_CAPACITY_PROFILE",
        "NOT_EQUIPMENT",
    ]

    @model_validator(mode="after")
    def validate_readiness(self) -> CapacityRuntimeModel:
        ready = self.calculation_readiness_status in {
            "CALCULATION_READY",
            "CALCULATION_READY_WITH_ASSUMPTIONS",
        }
        requires = self.calculation_readiness_status == (
            "CALCULATION_READY_WITH_ASSUMPTIONS"
        )
        if self.calculation_ready != ready:
            raise ValueError("calculation_ready differs from readiness status")
        if self.calculation_requires_assumptions != requires:
            raise ValueError("assumption flag differs from readiness status")
        if requires != bool(self.scenario_assumptions):
            raise ValueError("scenario assumptions differ from readiness status")
        if ready and (not self.calculation_profile or self.calculation_blockers):
            raise ValueError("ready capacity runtime profile is incomplete")
        if not ready and not self.calculation_blockers:
            raise ValueError("blocked capacity runtime profile has no blocker")
        if self.deployment_readiness_status == "DEPLOYMENT_READY":
            raise ValueError("deployment-ready models are not allowed in this bundle")
        return self


class CapacityRuntimeContract(StrictModel):
    schema_version: Literal["catalog-capacity-runtime-v1"]
    runtime_catalog_version: Literal["organizer-catalog-v4-capacity-runtime-v1"]
    catalog_code: Literal["organizer-catalog-v4"]
    contract_version: Literal["runtime-calculation-readiness-contract-v2"]
    source_sha256: dict[str, str]
    counts: dict[str, int]
    deterministic_order: Literal["model_id"]
    models: list[CapacityRuntimeModel]

    @model_validator(mode="after")
    def validate_exact_pool(self) -> CapacityRuntimeContract:
        ids = [item.model_id for item in self.models]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("capacity runtime models must be unique and sorted")
        statuses = [item.calculation_readiness_status for item in self.models]
        actual = {
            "models": len(self.models),
            "calculation_ready_models": statuses.count("CALCULATION_READY"),
            "calculation_ready_with_assumptions_models": statuses.count(
                "CALCULATION_READY_WITH_ASSUMPTIONS"
            ),
            "calculation_pool_models": sum(item.calculation_ready for item in self.models),
            "deployment_ready_models": sum(
                item.deployment_readiness_status == "DEPLOYMENT_READY"
                for item in self.models
            ),
        }
        for key, value in actual.items():
            if self.counts.get(key) != value:
                raise ValueError(f"capacity runtime count mismatch: {key}")
        if actual != {
            "models": 187,
            "calculation_ready_models": 6,
            "calculation_ready_with_assumptions_models": 15,
            "calculation_pool_models": 21,
            "deployment_ready_models": 0,
        }:
            raise ValueError("capacity runtime pool differs from the approved gate")
        if set(self.source_sha256) != {"contract", "audit", "products"} or any(
            not SHA256_RE.fullmatch(value) for value in self.source_sha256.values()
        ):
            raise ValueError("capacity runtime provenance hashes are invalid")
        return self


class CapacityEnrichmentEvidence(StrictModel):
    source_url: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    publication_or_update_date: str | None
    accessed_at: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    raw_value: str = Field(min_length=1)


class CapacityEnrichmentFact(StrictModel):
    decision_id: str = Field(min_length=1)
    organizer_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    field_path: str = Field(pattern=r"^(specs|capacity)\.[a-z0-9_]+$")
    normalized_value: Any
    normalized_unit: str | None
    resolution_status: str = Field(min_length=1)
    usable_for_matching: bool
    rationale: str = Field(min_length=1)
    applicability_note: str = Field(min_length=1)
    evidence: list[CapacityEnrichmentEvidence] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence_status(self) -> CapacityEnrichmentFact:
        if self.resolution_status not in EVIDENCE_STATUSES:
            raise ValueError("unknown capacity enrichment evidence status")
        if self.usable_for_matching and (
            self.resolution_status
            not in SAFE_AUTOMATIC_STATUSES + REVIEWED_STATUSES
            or self.normalized_value is None
        ):
            raise ValueError("matching capacity enrichment fact is unsafe")
        return self


class CapacityEnrichmentContract(StrictModel):
    schema_version: Literal["catalog-capacity-enrichment-v1"]
    catalog_code: Literal["organizer-catalog-v4"]
    source_overlay_sha256: str
    reviewed_by_subject: Literal[
        "catalog-official-source-enrichment-reviewed-decisions-v1"
    ]
    reviewed_at: str = Field(min_length=1)
    deterministic_order: Literal["organizer_id,field_path,decision_id"]
    counts: dict[str, int]
    facts: list[CapacityEnrichmentFact]

    @model_validator(mode="after")
    def validate_exact_enrichment(self) -> CapacityEnrichmentContract:
        keys = [
            (item.organizer_id, item.field_path, item.decision_id)
            for item in self.facts
        ]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ValueError("capacity enrichment facts must be unique and sorted")
        actual = {
            "facts": len(self.facts),
            "matching_facts": sum(item.usable_for_matching for item in self.facts),
            "evidence_rows": sum(len(item.evidence) for item in self.facts),
            "models": len({item.organizer_id for item in self.facts}),
        }
        if actual != {
            "facts": 131,
            "matching_facts": 129,
            "evidence_rows": 154,
            "models": 26,
        } or any(self.counts.get(key) != value for key, value in actual.items()):
            raise ValueError("capacity enrichment counts differ from reviewed staging")
        if not SHA256_RE.fullmatch(self.source_overlay_sha256):
            raise ValueError("capacity enrichment source hash is invalid")
        try:
            datetime.fromisoformat(self.reviewed_at)
        except ValueError as exc:
            raise ValueError("capacity enrichment review time is invalid") from exc
        return self


@dataclass(frozen=True)
class CatalogBundle:
    root: Path
    manifest: BundleManifest
    bundle_sha256: str
    products: list[dict[str, Any]]
    applicability: list[dict[str, str]]
    prices: list[dict[str, str]]
    base_evidence: list[dict[str, str]]
    object_profiles: dict[str, Any]
    enrichment: list[dict[str, Any]]
    external_evidence: list[dict[str, str]]
    capacity_enrichment: CapacityEnrichmentContract
    capacity_runtime: CapacityRuntimeContract


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogBundleError(f"invalid JSON file: {path.name}") from exc
    if not isinstance(value, dict):
        raise CatalogBundleError(f"JSON root must be an object: {path.name}")
    return value


def _csv(path: Path, expected_headers: tuple[str, ...]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            if tuple(reader.fieldnames or ()) != expected_headers:
                raise CatalogBundleError(f"unexpected CSV columns: {path.name}")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise CatalogBundleError(f"invalid CSV file: {path.name}") from exc
    if any(None in row for row in rows):
        raise CatalogBundleError(f"malformed CSV row: {path.name}")
    return rows


def _require_count(manifest: BundleManifest, key: str, actual: int) -> None:
    expected = manifest.expected_counts.get(key)
    if expected is None or actual != expected:
        raise CatalogBundleError(
            f"count mismatch for {key}: expected {expected}, got {actual}"
        )


def _valid_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise CatalogBundleError(f"invalid UUID in {label}") from exc


def _validate_files(root: Path, manifest: BundleManifest) -> None:
    for entry in manifest.files:
        relative = Path(entry.path)
        if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
            raise CatalogBundleError("bundle file paths must be flat and relative")
        path = root / relative
        if not path.is_file():
            raise CatalogBundleError(f"bundle file is missing: {entry.path}")
        if path.stat().st_size != entry.size_bytes:
            raise CatalogBundleError(f"size mismatch: {entry.path}")
        if _sha256(path) != entry.sha256:
            raise CatalogBundleError(f"checksum mismatch: {entry.path}")


def _validate_base(
    manifest: BundleManifest,
    products: list[dict[str, Any]],
    applicability: list[dict[str, str]],
    prices: list[dict[str, str]],
    evidence: list[dict[str, str]],
) -> None:
    _require_count(manifest, "products", len(products))
    _require_count(manifest, "catalog_source_rows", len(applicability))
    _require_count(manifest, "applicability_rows", len(applicability))
    _require_count(manifest, "price_rows", len(prices))
    _require_count(manifest, "base_evidence_rows", len(evidence))

    product_ids: set[str] = set()
    product_spec_count = 0
    expected_app_ids: set[str] = set()
    expected_price_ids: set[str] = set()
    for product in products:
        organizer_id = str(product.get("organizer_id", ""))
        _valid_uuid(organizer_id, "catalog_products.organizer_id")
        if organizer_id in product_ids:
            raise CatalogBundleError("duplicate product organizer_id")
        product_ids.add(organizer_id)
        if product.get("product_id") != f"org-{organizer_id}":
            raise CatalogBundleError("product_id does not match organizer_id")
        if not str(product.get("name", "")).strip():
            raise CatalogBundleError("product name is empty")
        specs = product.get("specs")
        if not isinstance(specs, dict):
            raise CatalogBundleError("product specs must be an object")
        product_spec_count += len(specs)
        expected_app_ids.update(
            str(value) for value in product.get("applicability_ids", [])
        )
        expected_price_ids.update(
            str(value) for value in product.get("price_offer_ids", [])
        )
    _require_count(manifest, "base_spec_fields", product_spec_count)

    app_ids: set[str] = set()
    price_ids: set[str] = set()
    app_rows: set[int] = set()
    price_rows: set[int] = set()
    app_by_row: dict[int, str] = {}
    for row in applicability:
        row_number = int(row["original_row"])
        app_id = row["applicability_id"]
        if app_id in app_ids or row_number in app_rows:
            raise CatalogBundleError("duplicate applicability identity")
        if app_id != f"app-v4-row-{row_number:04d}":
            raise CatalogBundleError("invalid applicability natural key")
        if row["organizer_id"] not in product_ids:
            raise CatalogBundleError("dangling applicability product reference")
        app_ids.add(app_id)
        app_rows.add(row_number)
        app_by_row[row_number] = row["organizer_id"]
    for row in prices:
        row_number = int(row["original_row"])
        price_id = row["price_offer_id"]
        if price_id in price_ids or row_number in price_rows:
            raise CatalogBundleError("duplicate price identity")
        if price_id != f"price-v4-row-{row_number:04d}":
            raise CatalogBundleError("invalid price natural key")
        if row["organizer_id"] not in product_ids:
            raise CatalogBundleError("dangling price product reference")
        if app_by_row.get(row_number) != row["organizer_id"]:
            raise CatalogBundleError("applicability/price source row mismatch")
        if row["currency"] != "UNKNOWN":
            raise CatalogBundleError("source currency must remain UNKNOWN")
        if row["vat_status"] != "ORGANIZER_ASSUMPTION_INCLUDED":
            raise CatalogBundleError("unexpected source VAT status")
        price_ids.add(price_id)
        price_rows.add(row_number)
    if app_rows != set(range(2, 225)) or price_rows != app_rows:
        raise CatalogBundleError("source rows must cover 2..224 exactly once")
    if expected_app_ids and expected_app_ids != app_ids:
        raise CatalogBundleError("product applicability references differ")
    if expected_price_ids != price_ids:
        raise CatalogBundleError("product price references differ")

    allowed_sources = {artifact.original_name for artifact in manifest.source_artifacts}
    for row in evidence:
        if row["evidence_status"] not in EVIDENCE_STATUSES:
            raise CatalogBundleError("unknown base evidence status")
        if row["source_file"] not in allowed_sources:
            raise CatalogBundleError("base evidence references an unknown source")
        entity_type = row["entity_type"]
        entity_id = row["entity_id"]
        if entity_type == "product" and entity_id not in product_ids:
            raise CatalogBundleError("dangling product evidence")
        if entity_type == "applicability" and entity_id not in app_ids:
            raise CatalogBundleError("dangling applicability evidence")
        if entity_type == "price_offer" and entity_id not in price_ids:
            raise CatalogBundleError("dangling price evidence")
        if entity_type not in {"product", "applicability", "price_offer"}:
            raise CatalogBundleError("unknown base evidence entity type")


def _validate_reference(
    manifest: BundleManifest, object_profiles: dict[str, Any]
) -> None:
    object_types = object_profiles.get("object_types")
    if not isinstance(object_types, list):
        raise CatalogBundleError("object_profiles.object_types must be an array")
    parameter_count = sum(
        len(group.get("parameters", []))
        for object_type in object_types
        for group in object_type.get("groups", [])
    )
    _require_count(manifest, "object_profiles", len(object_types))
    _require_count(manifest, "object_profile_parameters", parameter_count)


def _validate_enrichment(
    manifest: BundleManifest,
    product_ids: set[str],
    enrichment: list[dict[str, Any]],
    evidence: list[dict[str, str]],
) -> None:
    _require_count(manifest, "enrichment_products", len(enrichment))
    _require_count(manifest, "external_evidence_rows", len(evidence))
    overlay_keys: set[tuple[str, str]] = set()
    for product in enrichment:
        organizer_id = str(product.get("organizer_id", ""))
        if organizer_id not in product_ids:
            raise CatalogBundleError("enrichment references an unknown product")
        fields = product.get("fields")
        if not isinstance(fields, dict):
            raise CatalogBundleError("enrichment fields must be an object")
        for field_name, value in fields.items():
            if not isinstance(value, dict):
                raise CatalogBundleError("enrichment field must be an object")
            status = value.get("evidence_status")
            if status not in EVIDENCE_STATUSES:
                raise CatalogBundleError("unknown enrichment evidence status")
            key = (organizer_id, f"specs.{field_name}")
            if key in overlay_keys:
                raise CatalogBundleError("duplicate enrichment field")
            overlay_keys.add(key)
    _require_count(manifest, "overlay_fields", len(overlay_keys))

    evidence_keys: set[tuple[str, str]] = set()
    for row in evidence:
        if row["organizer_id"] not in product_ids:
            raise CatalogBundleError("external evidence references an unknown product")
        if row["evidence_status"] not in EVIDENCE_STATUSES:
            raise CatalogBundleError("unknown external evidence status")
        if not row["source_id"].strip():
            raise CatalogBundleError("external evidence source_id is empty")
        evidence_keys.add((row["organizer_id"], row["field_path"]))
    if not overlay_keys <= evidence_keys:
        raise CatalogBundleError("overlay field has no external evidence")


def _validate_capacity_runtime(
    manifest: BundleManifest,
    products: list[dict[str, Any]],
    applicability: list[dict[str, str]],
    capacity_runtime: CapacityRuntimeContract,
) -> None:
    product_by_id = {str(product["organizer_id"]): product for product in products}
    runtime_ids = {item.model_id for item in capacity_runtime.models}
    if runtime_ids != set(product_by_id):
        raise CatalogBundleError("capacity runtime model coverage differs")
    ready_ids = {item.model_id for item in capacity_runtime.models if item.calculation_ready}
    if any(product_by_id[model_id].get("system_family") != "BRS" for model_id in ready_ids):
        raise CatalogBundleError("capacity runtime pool contains a non-BRS model")
    position_count = sum(row["organizer_id"] in ready_ids for row in applicability)
    if position_count != 24:
        raise CatalogBundleError("capacity runtime pool must cover exactly 24 positions")
    _require_count(manifest, "capacity_runtime_models", len(capacity_runtime.models))
    _require_count(manifest, "capacity_runtime_pool_models", len(ready_ids))
    _require_count(manifest, "capacity_runtime_pool_positions", position_count)


def _validate_capacity_enrichment(
    manifest: BundleManifest,
    product_ids: set[str],
    capacity_enrichment: CapacityEnrichmentContract,
) -> None:
    if any(item.organizer_id not in product_ids for item in capacity_enrichment.facts):
        raise CatalogBundleError("capacity enrichment references an unknown model")
    _require_count(manifest, "capacity_enrichment_facts", len(capacity_enrichment.facts))
    _require_count(
        manifest,
        "capacity_enrichment_matching_facts",
        sum(item.usable_for_matching for item in capacity_enrichment.facts),
    )
    _require_count(
        manifest,
        "capacity_enrichment_evidence_rows",
        sum(len(item.evidence) for item in capacity_enrichment.facts),
    )
    _require_count(
        manifest,
        "capacity_enrichment_models",
        len({item.organizer_id for item in capacity_enrichment.facts}),
    )


def load_catalog_bundle(bundle_path: str | Path) -> CatalogBundle:
    root = Path(bundle_path).resolve()
    manifest_path = root / "manifest.json"
    if not root.is_dir() or not manifest_path.is_file():
        raise CatalogBundleError("bundle directory or manifest.json is missing")
    raw_manifest = _json(manifest_path)
    try:
        manifest = BundleManifest.model_validate(raw_manifest)
    except ValidationError as exc:
        raise CatalogBundleError("manifest contract validation failed") from exc
    _validate_files(root, manifest)

    products_doc = _json(root / "catalog_products.json")
    products = products_doc.get("products")
    if not isinstance(products, list):
        raise CatalogBundleError("catalog_products.products must be an array")
    applicability = _csv(
        root / "catalog_applicability.csv",
        (
            "applicability_id",
            "organizer_id",
            "original_row",
            "industry",
            "scenario",
            "region",
            "case",
            "source_file",
            "source_note",
        ),
    )
    prices = _csv(
        root / "catalog_prices.csv",
        (
            "price_offer_id",
            "organizer_id",
            "original_row",
            "raw_price",
            "normalized_amount",
            "currency",
            "vat_status",
            "included_costs",
            "excluded_costs",
            "price_status",
            "source_file",
            "source_note",
        ),
    )
    base_evidence = _csv(
        root / "catalog_field_evidence.csv",
        (
            "entity_type",
            "entity_id",
            "field_path",
            "normalized_value",
            "source_file",
            "source_sheet_or_page",
            "source_row_or_fragment",
            "evidence_status",
            "confidence",
            "notes",
        ),
    )
    object_profiles = _json(root / "object_profiles.json")
    enrichment_doc = _json(root / "catalog_external_enrichment.json")
    enrichment = enrichment_doc.get("products")
    if not isinstance(enrichment, list):
        raise CatalogBundleError("external enrichment products must be an array")
    external_evidence = _csv(
        root / "catalog_external_evidence.csv",
        (
            "source_id",
            "organizer_id",
            "manufacturer",
            "model",
            "field_path",
            "url",
            "page_title",
            "publisher",
            "source_type",
            "publication_or_update_date",
            "accessed_at",
            "page_section_table",
            "supporting_fragment",
            "raw_value",
            "normalized_value",
            "normalized_unit",
            "evidence_status",
            "confidence",
            "model_match_note",
            "notes",
        ),
    )
    try:
        capacity_enrichment = CapacityEnrichmentContract.model_validate(
            _json(root / "catalog_capacity_enrichment.json")
        )
        capacity_runtime = CapacityRuntimeContract.model_validate(
            _json(root / "catalog_capacity_runtime.json")
        )
    except ValidationError as exc:
        raise CatalogBundleError("capacity runtime contract validation failed") from exc

    _validate_base(manifest, products, applicability, prices, base_evidence)
    _validate_reference(manifest, object_profiles)
    product_ids = {str(product["organizer_id"]) for product in products}
    _validate_enrichment(manifest, product_ids, enrichment, external_evidence)
    _validate_capacity_enrichment(manifest, product_ids, capacity_enrichment)
    _validate_capacity_runtime(
        manifest, products, applicability, capacity_runtime
    )
    return CatalogBundle(
        root=root,
        manifest=manifest,
        bundle_sha256=_sha256(manifest_path),
        products=products,
        applicability=applicability,
        prices=prices,
        base_evidence=base_evidence,
        object_profiles=object_profiles,
        enrichment=enrichment,
        external_evidence=external_evidence,
        capacity_enrichment=capacity_enrichment,
        capacity_runtime=capacity_runtime,
    )
