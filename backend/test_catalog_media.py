from __future__ import annotations

from pathlib import Path

import pytest
from catalog_media import (
    EXPECTED_POSITION_COUNT,
    CatalogMediaError,
    extract_position_images,
    resolve_media_path,
)

OFFICIAL_PDF = (
    Path(__file__).resolve().parents[1]
    / "Разобрать"
    / "Материалы от организаторов"
    / "Датасет"
    / "ФЦ БАС — Каталог внедрения 2008 1247.pdf"
)


@pytest.mark.skipif(not OFFICIAL_PDF.is_file(), reason="restricted PDF is local-only")
def test_official_pdf_extracts_one_image_for_each_catalog_position():
    images = extract_position_images(OFFICIAL_PDF)

    assert len(images) == EXPECTED_POSITION_COUNT
    assert (images[0].source_page, images[0].source_slot) == (6, 1)
    assert (images[-1].source_page, images[-1].source_slot) == (91, 3)
    assert all(item.media_type.startswith("image/") for item in images)
    assert all(item.width_px >= 100 and item.height_px >= 100 for item in images)


def test_media_storage_path_cannot_escape_root(tmp_path):
    with pytest.raises(CatalogMediaError, match="escapes"):
        resolve_media_path(tmp_path, "../secret.png", 1)


def test_missing_media_asset_is_rejected(tmp_path):
    with pytest.raises(CatalogMediaError, match="unavailable"):
        resolve_media_path(tmp_path, "catalog/assets/missing.png", 1)
