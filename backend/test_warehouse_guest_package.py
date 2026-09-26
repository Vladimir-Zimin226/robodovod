"""The public download and page must remain one self-consistent authored scenario."""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile

from pypdf import PdfReader

from scripts.build_warehouse_guest_package import FRONTEND, PUBLIC, ROOT, build_package, expected_files


def test_generated_guest_package_is_current_and_public_files_match_manifest():
    expected = expected_files()
    for path, data in expected.items():
        assert path.read_bytes() == data, str(path)
    assert subprocess.run([sys.executable, str(ROOT / "scripts/build_warehouse_guest_package.py"), "--check"],
                          cwd=ROOT, check=False, capture_output=True).returncode == 0
    manifest = json.loads((PUBLIC / "manifest.json").read_text(encoding="utf-8"))
    package = json.loads(FRONTEND.read_text(encoding="utf-8"))
    assert manifest["package_version"] == package["schema_version"]
    assert manifest["bindings"] == package["bindings"]
    with zipfile.ZipFile(io.BytesIO((PUBLIC / "evidence.zip").read_bytes())) as archive:
        assert archive.read("manifest.json") == (PUBLIC / "manifest.json").read_bytes()
        assert archive.read("report.pdf") == (PUBLIC / "report.pdf").read_bytes()
        assert archive.read("package.json") == expected[FRONTEND]
        for name, meta in manifest["files"].items():
            data = archive.read(name)
            assert meta == {"sha256": "sha256:" + hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def test_guest_pdf_contains_same_six_values_and_limits_as_page():
    package = build_package()
    pdf = (PUBLIC / "report.pdf").read_bytes()
    text = re.sub(r"\s+", " ", "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages))
    assert package["title"] in text
    assert "2 000 паллет/сутки" in text
    assert "120 м" in text
    assert f"Потребный парк: {package['demo']['capacity']['value']['selected_fleet']} роботов" in text
    for item in package["demo"]["scenarios"]:
        assert item["npv_project"]["value"] in text
    baseline = package["demo"]["scenarios"][0]["annual_ledgers"][0]["primary_cf_base"]
    assert baseline in text
    for item in package["demo"]["sensitivity"]:
        assert item["npv_project"]["delta_value"] in text
    for limit in package["limitations"]:
        assert limit in text
    assert "Комплектовщик: рассчитано" not in text


def test_guest_capture_contains_no_private_project_or_user_snapshot():
    package = build_package()
    request = package["simulation"]["request"]
    assert request["tenant_id"] == "tenant.demo"
    assert request["project_id"] == "00000000-0000-0000-0000-000000000041"
    assert request["scenario_spec"]["analysis"]["capacity_run_id"] == "run.demo.warehouse.c11"
    assert request["process_chain"] is None
    assert package["chain"][0]["status"] == "MODELED"
    assert all(item["status"] == "NOT_MODELED" for item in package["chain"][1:])
