"""Investment report contract shared by preview and guest PDF."""

from copy import deepcopy
from io import BytesIO
import re
import base64

import pytest
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader

from calculation.object_roles import ObjectRoleInput, analyze_object_roles
from calculation.role_report import role_report_pdf
from calculation.warehouse_roles import WarehouseRoleInput, analyze_warehouse_roles
from object_roles_api import create_object_roles_router
from test_object_roles import catalog as object_catalog, raw
from test_warehouse_roles import catalog as warehouse_catalog, sample
from warehouse_roles_api import create_warehouse_roles_router


def pdf_text(data):
    return re.sub(r"\s+", " ", " ".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages))


@pytest.mark.parametrize("kind", ["WAREHOUSE", "AIRPORT", "CLINIC"])
def test_object_report_view_pdf_has_same_numbers_a4_tables_charts_and_sources(kind):
    value = raw(kind)
    report = analyze_object_roles(ObjectRoleInput.model_validate(value), object_catalog())
    view = report["report_view"]
    pdf = PdfReader(BytesIO(role_report_pdf(report)))
    extracted = pdf_text(role_report_pdf(report))
    assert all(float(page.mediabox.width) == 595 and float(page.mediabox.height) == 842 for page in pdf.pages)
    for page in pdf.pages:
        stream = page.get_contents().get_data().decode("ascii")
        for x, y in re.findall(r"(-?\d+\.\d+) (-?\d+\.\d+) Td", stream):
            assert 0 <= float(x) <= 595 and 0 <= float(y) <= 842
        for x, y, width, height in re.findall(
                r"(-?\d+\.\d+) (-?\d+\.\d+) (-?\d+\.\d+) (-?\d+\.\d+) re f", stream):
            assert 0 <= float(x) and 0 <= float(y)
            assert float(x) + float(width) <= 595 and float(y) + float(height) <= 842
    assert view["executive_conclusion"] in extracted
    assert view["catalog_version"] in extracted
    assert "Работа" in extracted and "Доля ФОТ" in extracted
    assert "Год 10" in extracted and "Waterfall" in extracted
    assert "Демонстрационная геометрия" in extracted
    for mode in ("purchase", "raas"):
        money = view["economics"][mode]
        assert money["npv_rub"] in extracted
        assert money["capex_rub"] in extracted
        assert money["horizons"][0]["npv_rub"] in extracted
        assert money["horizons"][1]["npv_rub"] in extracted
    assert len(view["works"]) == sum(len(role["works"]) for role in report["roles"])
    assert len(view["sources"]) == len(view["works"])
    assert "ИСТОЧНИКИ · ПРОДОЛЖЕНИЕ" in pdf.pages[-1].extract_text()


def test_missing_price_stays_unknown_in_warehouse_report_and_pdf():
    value = sample()
    value["roles"] = [role for role in value["roles"] if role["role_code"] == "picker"]
    value["selected_positions"] = {"picker": "picking"}
    value["overrides"] = [{"role_code": "picker", "position_id": "picking", "omit_purchase_price": True}]
    report = analyze_warehouse_roles(WarehouseRoleInput.model_validate(value), warehouse_catalog())
    view = report["report_view"]
    assert view["economics"]["purchase"]["npv_rub"] is None
    assert view["economics"]["purchase"]["cashflows"] == []
    text = pdf_text(role_report_pdf(report))
    assert "нужны цена или тариф" in text
    assert "Нужны данные" in text
    assert view["economics"]["raas"]["npv_rub"] is None


@pytest.mark.parametrize("kind", ["WAREHOUSE", "AIRPORT", "CLINIC"])
def test_guest_pdf_recalculates_same_report_view_as_preview(kind):
    app = FastAPI()
    app.include_router(create_object_roles_router(object_catalog))
    client = TestClient(app)
    value = raw(kind)
    original = deepcopy(value)
    preview = client.post(f"/api/v2/object-roles/{kind}/preview", json=value)
    assert preview.status_code == 200
    view = preview.json()["report_view"]
    response = client.post(f"/api/v2/object-roles/{kind}/report.pdf", json={
        "expected_catalog_version": preview.json()["catalog_version"], "input": value})
    assert response.status_code == 200
    text = pdf_text(response.content)
    assert view["executive_conclusion"] in text
    assert view["economics"]["purchase"]["npv_rub"] in text
    assert value == original


def test_warehouse_guest_pdf_matches_preview_report_view():
    app = FastAPI()
    app.include_router(create_warehouse_roles_router(warehouse_catalog))
    client = TestClient(app)
    value = sample()
    preview = client.post("/api/v2/warehouse-roles/preview", json=value)
    assert preview.status_code == 200
    view = preview.json()["report_view"]
    response = client.post("/api/v2/warehouse-roles/report.pdf", json={
        "expected_catalog_version": preview.json()["catalog_version"], "input": value})
    assert response.status_code == 200
    text = pdf_text(response.content)
    assert view["executive_conclusion"] in text
    assert view["economics"]["purchase"]["npv_rub"] in text


def test_guest_pdf_includes_recomputed_what_if_without_changing_base():
    app = FastAPI()
    app.include_router(create_object_roles_router(object_catalog))
    client = TestClient(app)
    value = raw("AIRPORT")
    value["roles"] = value["roles"][:1]
    value["roles"][0]["works"] = value["roles"][0]["works"][:1]
    branch = deepcopy(value)
    branch["roles"][0]["works"][0]["daily_volume"] = str(
        float(branch["roles"][0]["works"][0]["daily_volume"]) * 1.4)
    original = deepcopy(value)
    base_view = client.post("/api/v2/object-roles/AIRPORT/preview", json=value).json()["report_view"]
    branch_view = client.post("/api/v2/object-roles/AIRPORT/preview", json=branch).json()["report_view"]
    response = client.post("/api/v2/object-roles/AIRPORT/report.pdf", json={
        "expected_catalog_version": "test-v2", "input": value, "what_if_input": branch})
    assert response.status_code == 200
    extracted = pdf_text(response.content)
    assert "Временная ветка" in extracted
    assert base_view["economics"]["purchase"]["npv_rub"] in extracted
    assert branch_view["economics"]["purchase"]["npv_rub"] in extracted
    assert value == original


def test_guest_pdf_embeds_current_scene_snapshots_as_a4_pages_and_rejects_bad_png():
    app = FastAPI()
    app.include_router(create_object_roles_router(object_catalog))
    client = TestClient(app)
    value = raw("AIRPORT")
    image = BytesIO()
    Image.new("RGB", (1000, 550), "#7099aa").save(image, format="PNG")
    png = "data:image/png;base64," + base64.b64encode(image.getvalue()).decode("ascii")
    request = {"expected_catalog_version": "test-v2", "input": value,
               "scene_snapshots": {"two_d_png": png, "three_d_png": png}}
    response = client.post("/api/v2/object-roles/AIRPORT/report.pdf", json=request)
    assert response.status_code == 200
    pages = PdfReader(BytesIO(response.content)).pages
    assert len(pages) > 3
    assert all(float(page.mediabox.width) == 595 and float(page.mediabox.height) == 842 for page in pages)
    assert "/XObject" in pages[-1]["/Resources"]
    assert "/XObject" in pages[-2]["/Resources"]
    request["scene_snapshots"]["three_d_png"] = "data:image/png;base64,bad"
    invalid = client.post("/api/v2/object-roles/AIRPORT/report.pdf", json=request)
    assert invalid.status_code == 422
