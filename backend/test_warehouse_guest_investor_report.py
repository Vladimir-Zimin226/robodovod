"""Presentation must match the verified guest page without mutating its archive."""
from __future__ import annotations

import hashlib
import io
import json

import pytest
from pypdf import PdfReader

from scripts import build_warehouse_guest_investor_report as report


def test_guest_investor_download_is_current_bound_and_visual():
    source_paths = [report.PAGE_PACKAGE, *report.SOURCE.iterdir()]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths if p.is_file()}
    files = report.expected_files()
    assert all(path.read_bytes() == body for path, body in files.items())
    manifest = json.loads(files[report.TARGET / "manifest.json"])
    package, digest = report.load_verified_package()
    assert manifest["source_package_digest"] == digest
    assert manifest["bindings"] == package["bindings"]
    assert manifest["depth"] == "FULL_AUTHORED_EXAMPLE"
    pdf = PdfReader(io.BytesIO(files[report.TARGET / "report.pdf"]))
    texts = [page.extract_text() for page in pdf.pages]
    assert len(texts) >= 8
    assert all("Полный · авторский пример" in text for text in texts)
    assert all(float(page.mediabox.width) > float(page.mediabox.height) for page in pdf.pages)
    assert "2 000 паллет/сутки" in texts[0]
    assert "18 роботов" in texts[0]  # Authored fixture, not the live catalog's 11-robot case.
    assert "это не полный проектный бюджет" in " ".join(texts[0].split())
    assert "Новая версия меняет только представление" in "\n".join(texts)
    assert "Отбор строк и штук" in "\n".join(texts)
    assert "Окупаемость и подробный CAPEX не сохранены" in "\n".join(texts)
    # Charts carry real paths and fills, not headings attached to the old text PDF.
    graph = next(p for p in pdf.pages if "Как меняется годовой денежный эффект" in p.extract_text())
    ops = [op for _, op in graph.get_contents().operations]
    assert ops.count(b"l") > 6 and ops.count(b"re") > 10
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}


def test_guest_investor_rejects_archive_page_mismatch(tmp_path, monkeypatch):
    altered = tmp_path / "page.json"
    altered.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(report, "PAGE_PACKAGE", altered)
    with pytest.raises(ValueError, match="source mismatch"):
        report.expected_files()
