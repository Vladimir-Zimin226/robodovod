"""Read-only checks for the official catalog media import (local or production)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from catalog_media import extract_position_images
from database import get_database
from main import app


def verify(
    storage_root: Path,
    *,
    pdf: Path | None = None,
) -> dict:
    with get_database().session() as session:
        rows = session.execute(
            text(
                """
                SELECT r.id::text, r.source_row_number, p.source_page,
                       p.source_slot, a.sha256, a.storage_key, a.media_type,
                       a.byte_size
                FROM catalog_source_rows r
                JOIN catalog_position_media p ON p.catalog_source_row_id = r.id
                JOIN catalog_media_assets a ON a.id = p.media_asset_id
                JOIN catalog_versions v ON v.id = r.catalog_version_id
                WHERE v.code = 'organizer-catalog-v4'
                ORDER BY r.source_row_number
                """
            )
        ).all()
    assert len(rows) == 223, f"expected 223 media links, got {len(rows)}"
    assert len({row[0] for row in rows}) == 223
    assert len({(row[2], row[3]) for row in rows}) == 223
    assert len({row[4] for row in rows}) == 189
    if pdf is not None:
        images = extract_position_images(pdf)
        for row, image in zip(rows, images, strict=True):
            assert (row[2], row[3], row[4]) == (
                image.source_page,
                image.source_slot,
                image.sha256,
            ), row[1]
    for row in rows:
        path = (storage_root / row[5]).resolve()
        assert storage_root.resolve() in path.parents
        assert path.is_file() and path.stat().st_size == row[7], row[1]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row[4], row[1]

    with TestClient(app) as client:
        response = client.get("/api/catalog/models")
        assert response.status_code == 200, response.status_code
        items = response.json()["items"]
        assert len(items) == 223
        assert {item["position_id"] for item in items} == {row[0] for row in rows}
        assert all(item["media"] and item["media"]["url"] for item in items)
        by_id = {item["position_id"]: item for item in items}
        for row in rows:
            media = by_id[row[0]]["media"]
            assert media["url"] == f"/api/catalog/media/organizer-catalog-v4/{row[4]}"
            assert (media["source_page"], media["source_slot"]) == row[2:4]
            assert media["media_type"] == row[6]

        samples = {}
        for item in items:
            samples.setdefault(item["system_family"], item)
        for family, item in samples.items():
            detail = client.get(f"/api/catalog/positions/{item['position_id']}")
            assert detail.status_code == 200
            assert detail.json()["media"] == item["media"]
            image = client.get(item["media"]["url"])
            assert image.status_code == 200, family
            assert image.headers["content-type"] == item["media"]["media_type"]
            assert hashlib.sha256(image.content).hexdigest() == item["media"]["sha256"]

        missing_sha = "0" * 64
        assert client.get(f"/api/catalog/media/organizer-catalog-v4/{missing_sha}").status_code == 404
        assert client.get(f"/api/catalog/media/other-catalog/{rows[0][4]}").status_code == 404
        assert client.get("/api/catalog/media/organizer-catalog-v4/invalid").status_code == 404
    return {"positions": len(rows), "assets": len({row[4] for row in rows}), "families": sorted(samples)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage-root", type=Path, default=Path(os.getenv("CATALOG_MEDIA_ROOT", "data/catalog-media")))
    parser.add_argument("--pdf", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.storage_root, pdf=args.pdf), ensure_ascii=False, sort_keys=True))
