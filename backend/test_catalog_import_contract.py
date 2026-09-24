from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from catalog_import_contract import CatalogBundleError, load_catalog_bundle

BUNDLE = (
    Path(__file__).resolve().parents[1] / "data" / "import" / "organizer-catalog-v4"
)


def _copy_bundle(tmp_path: Path) -> Path:
    target = tmp_path / "bundle"
    shutil.copytree(BUNDLE, target)
    return target


def _update_file_contract(bundle: Path, file_name: str) -> None:
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = (bundle / file_name).read_bytes()
    for entry in manifest["files"]:
        if entry["path"] == file_name:
            entry["sha256"] = hashlib.sha256(payload).hexdigest()
            entry["size_bytes"] = len(payload)
            break
    for artifact in manifest["source_artifacts"]:
        if artifact["artifact_key"] == f"bundle:{file_name}":
            artifact["sha256"] = hashlib.sha256(payload).hexdigest()
            artifact["size_bytes"] = len(payload)
            break
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_committed_bundle_matches_contract():
    bundle = load_catalog_bundle(BUNDLE)
    assert len(bundle.products) == 187
    assert len(bundle.applicability) == 223
    assert len(bundle.prices) == 223
    assert len(bundle.base_evidence) == 3635
    assert sum(len(product["fields"]) for product in bundle.enrichment) == 140
    assert len(bundle.external_evidence) == 156
    assert len(bundle.capacity_runtime.models) == 187
    assert sum(item.calculation_ready for item in bundle.capacity_runtime.models) == 21


def test_git_bundle_bytes_match_manifest():
    """A Linux checkout must retain the bytes accepted by the import manifest."""

    repository = BUNDLE.parents[2]
    if not (repository / ".git").exists():
        pytest.skip("Git metadata is not packaged in the runtime image")
    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        tracked_path = f"data/import/organizer-catalog-v4/{entry['path']}"
        blob = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={repository.as_posix()}",
                "show",
                f"HEAD:{tracked_path}",
            ],
            cwd=repository,
            check=True,
            capture_output=True,
        ).stdout
        assert len(blob) == entry["size_bytes"], entry["path"]
        assert hashlib.sha256(blob).hexdigest() == entry["sha256"], entry["path"]


def test_checksum_mismatch_is_rejected(tmp_path):
    bundle = _copy_bundle(tmp_path)
    with (bundle / "catalog_prices.csv").open("ab") as handle:
        handle.write(b"tampered")
    with pytest.raises(CatalogBundleError, match="size mismatch"):
        load_catalog_bundle(bundle)


def test_dangling_product_reference_is_rejected(tmp_path):
    bundle = _copy_bundle(tmp_path)
    path = bundle / "catalog_applicability.csv"
    content = path.read_text(encoding="utf-8-sig")
    content = content.replace(
        "5760e938-9a43-45a7-b8e8-f4f2e6383930",
        "00000000-0000-0000-0000-000000000000",
        1,
    )
    path.write_text(content, encoding="utf-8-sig", newline="")
    _update_file_contract(bundle, path.name)
    with pytest.raises(CatalogBundleError, match="dangling applicability"):
        load_catalog_bundle(bundle)


def test_duplicate_natural_key_is_rejected(tmp_path):
    bundle = _copy_bundle(tmp_path)
    path = bundle / "catalog_prices.csv"
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    lines[2] = lines[1].replace("price-v4-row-0002", "price-v4-row-0003", 1)
    path.write_text("".join(lines), encoding="utf-8-sig", newline="")
    _update_file_contract(bundle, path.name)
    with pytest.raises(CatalogBundleError, match="duplicate price identity"):
        load_catalog_bundle(bundle)


def test_unknown_evidence_status_is_rejected(tmp_path):
    bundle = _copy_bundle(tmp_path)
    path = bundle / "catalog_external_evidence.csv"
    content = path.read_text(encoding="utf-8-sig").replace(
        ";NOT_FOUND;", ";UNSAFE_FAKE_STATUS;", 1
    )
    path.write_text(content, encoding="utf-8-sig", newline="")
    _update_file_contract(bundle, path.name)
    with pytest.raises(CatalogBundleError, match="unknown external evidence status"):
        load_catalog_bundle(bundle)


def test_capacity_runtime_cannot_mark_inconsistent_model_ready(tmp_path):
    bundle = _copy_bundle(tmp_path)
    path = bundle / "catalog_capacity_runtime.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    blocked = next(
        item
        for item in payload["models"]
        if item["calculation_readiness_status"] == "NOT_EQUIPMENT"
    )
    blocked["calculation_ready"] = True
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _update_file_contract(bundle, path.name)

    with pytest.raises(CatalogBundleError, match="capacity runtime contract"):
        load_catalog_bundle(bundle)
