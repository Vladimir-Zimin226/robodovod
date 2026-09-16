"""Deterministic extraction and serving helpers for official catalog media."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from catalog_models import CatalogMediaAsset, CatalogPositionMedia, CatalogSourceRow
from database import Database, DatabaseSettings
from PIL import Image
from pypdf import PdfReader
from sqlalchemy import select
from storage_models import CatalogVersion, CatalogVersionSource, SourceArtifact

EXPECTED_POSITION_COUNT = 223
OFFICIAL_PDF_NAME = "ФЦ БАС — Каталог внедрения 2008 1247.pdf"
MEDIA_NAMESPACE = uuid.UUID("db0fa585-f13d-4c5a-a21d-9468b834b09b")


class CatalogMediaError(RuntimeError):
    """Raised when media cannot be attached without guessing or partial state."""


@dataclass(frozen=True)
class ExtractedImage:
    data: bytes
    sha256: str
    media_type: str
    extension: str
    width_px: int
    height_px: int
    source_page: int
    source_slot: int


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_metadata(data: bytes) -> tuple[str, str, int, int]:
    with Image.open(BytesIO(data)) as image:
        image.load()
        formats = {
            "PNG": ("image/png", ".png"),
            "JPEG": ("image/jpeg", ".jpg"),
            "WEBP": ("image/webp", ".webp"),
        }
        if image.format not in formats:
            raise CatalogMediaError("catalog image format is unsupported")
        media_type, extension = formats[image.format]
        return media_type, extension, image.width, image.height


def extract_position_images(pdf_path: Path) -> list[ExtractedImage]:
    """Extract product tiles in document order, rejecting ambiguous layouts."""

    reader = PdfReader(str(pdf_path))
    extracted: list[ExtractedImage] = []
    for page_number, page in enumerate(reader.pages, start=1):
        image_files = list(page.images)
        if len(image_files) < 10:
            continue
        card_count, remainder = divmod(len(image_files) - 1, 9)
        if remainder or not 1 <= card_count <= 3:
            raise CatalogMediaError(
                f"PDF page {page_number} has an ambiguous card layout"
            )
        page_images: list[ExtractedImage] = []
        for image_file in image_files[-card_count:]:
            data = image_file.data
            media_type, extension, width, height = _image_metadata(data)
            if width < 100 or height < 100:
                raise CatalogMediaError(
                    f"PDF page {page_number} product image is unexpectedly small"
                )
            page_images.append(
                ExtractedImage(
                    data=data,
                    sha256=hashlib.sha256(data).hexdigest(),
                    media_type=media_type,
                    extension=extension,
                    width_px=width,
                    height_px=height,
                    source_page=page_number,
                    source_slot=len(page_images) + 1,
                )
            )
        extracted.extend(page_images)
    if len(extracted) != EXPECTED_POSITION_COUNT:
        raise CatalogMediaError(
            "official PDF must yield exactly "
            f"{EXPECTED_POSITION_COUNT} position images, got {len(extracted)}"
        )
    return extracted


def _safe_storage_path(storage_root: Path, storage_key: str) -> Path:
    root = storage_root.resolve()
    candidate = (root / storage_key).resolve()
    if candidate == root or root not in candidate.parents:
        raise CatalogMediaError("catalog media storage key escapes storage root")
    return candidate


def _write_asset(storage_root: Path, storage_key: str, item: ExtractedImage) -> None:
    target = _safe_storage_path(storage_root, storage_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if (
            target.stat().st_size != len(item.data)
            or _sha256_file(target) != item.sha256
        ):
            raise CatalogMediaError("existing catalog media asset failed checksum")
        return
    temporary: Path
    with tempfile.NamedTemporaryFile(
        mode="wb", prefix=".media-", dir=target.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(item.data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def import_catalog_media(
    database: Database,
    *,
    catalog_code: str,
    pdf_path: Path,
    storage_root: Path,
) -> dict[str, Any]:
    pdf_path = pdf_path.resolve()
    if not pdf_path.is_file():
        raise CatalogMediaError("official catalog PDF was not found")

    with database.session() as session:
        source = session.execute(
            select(CatalogVersion, SourceArtifact)
            .join(
                CatalogVersionSource,
                CatalogVersionSource.catalog_version_id == CatalogVersion.id,
            )
            .join(
                SourceArtifact,
                SourceArtifact.id == CatalogVersionSource.source_artifact_id,
            )
            .where(
                CatalogVersion.code == catalog_code,
                SourceArtifact.original_name == OFFICIAL_PDF_NAME,
            )
        ).one_or_none()
        if source is None:
            raise CatalogMediaError("catalog PDF provenance record was not found")
        version, artifact = source
        if artifact.sha256 != _sha256_file(pdf_path):
            raise CatalogMediaError("official catalog PDF checksum mismatch")

        source_rows = session.scalars(
            select(CatalogSourceRow)
            .where(CatalogSourceRow.catalog_version_id == version.id)
            .order_by(CatalogSourceRow.source_row_number)
        ).all()
        if len(source_rows) != EXPECTED_POSITION_COUNT:
            raise CatalogMediaError("catalog must contain exactly 223 source rows")

        existing_media = session.execute(
            select(CatalogPositionMedia, CatalogMediaAsset)
            .join(
                CatalogMediaAsset,
                (CatalogMediaAsset.id == CatalogPositionMedia.media_asset_id)
                & (
                    CatalogMediaAsset.catalog_version_id
                    == CatalogPositionMedia.catalog_version_id
                ),
            )
            .where(CatalogPositionMedia.catalog_version_id == version.id)
        ).all()
        existing_links = len(existing_media)
        images = extract_position_images(pdf_path)
        if existing_links:
            if existing_links != EXPECTED_POSITION_COUNT:
                raise CatalogMediaError("catalog has a partial media import")
            existing_by_source = {
                link.catalog_source_row_id: (link, asset)
                for link, asset in existing_media
            }
            for source_row, item in zip(source_rows, images, strict=True):
                link, asset = existing_by_source[source_row.id]
                expected = (
                    item.sha256,
                    item.media_type,
                    len(item.data),
                    item.width_px,
                    item.height_px,
                    item.source_page,
                    item.source_slot,
                )
                actual = (
                    asset.sha256,
                    asset.media_type,
                    asset.byte_size,
                    asset.width_px,
                    asset.height_px,
                    link.source_page,
                    link.source_slot,
                )
                if actual != expected:
                    raise CatalogMediaError("catalog media metadata mismatch")
                _write_asset(storage_root, asset.storage_key, item)
            return {
                "catalog_code": catalog_code,
                "changed": False,
                "positions": EXPECTED_POSITION_COUNT,
                "assets": len({asset.id for _, asset in existing_media}),
            }

        assets: dict[str, CatalogMediaAsset] = {}
        for source_row, item in zip(source_rows, images, strict=True):
            storage_key = f"{catalog_code}/assets/{item.sha256}{item.extension}"
            _write_asset(storage_root, storage_key, item)
            asset = assets.get(item.sha256)
            if asset is None:
                asset = CatalogMediaAsset(
                    id=uuid.uuid5(MEDIA_NAMESPACE, f"{version.id}:asset:{item.sha256}"),
                    catalog_version_id=version.id,
                    source_artifact_id=artifact.id,
                    sha256=item.sha256,
                    media_type=item.media_type,
                    byte_size=len(item.data),
                    width_px=item.width_px,
                    height_px=item.height_px,
                    storage_key=storage_key,
                )
                assets[item.sha256] = asset
                session.add(asset)
            session.add(
                CatalogPositionMedia(
                    id=uuid.uuid5(
                        MEDIA_NAMESPACE, f"{version.id}:position:{source_row.id}"
                    ),
                    catalog_version_id=version.id,
                    catalog_source_row_id=source_row.id,
                    media_asset_id=asset.id,
                    role="PRIMARY",
                    source_page=item.source_page,
                    source_slot=item.source_slot,
                )
            )
        session.commit()
        return {
            "catalog_code": catalog_code,
            "changed": True,
            "positions": len(images),
            "assets": len(assets),
            "source_sha256": artifact.sha256,
        }


def resolve_media_path(
    storage_root: Path, storage_key: str, expected_size: int
) -> Path:
    path = _safe_storage_path(storage_root, storage_key)
    if not path.is_file() or path.stat().st_size != expected_size:
        raise CatalogMediaError("catalog media asset is unavailable")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract official catalog media")
    parser.add_argument("--catalog-code", default="organizer-catalog-v4")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path(os.getenv("OFFICIAL_CATALOG_PDF_PATH", OFFICIAL_PDF_NAME)),
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=Path(os.getenv("CATALOG_MEDIA_ROOT", "../data/catalog-media")),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    database = Database(DatabaseSettings.from_environment())
    try:
        result = import_catalog_media(
            database,
            catalog_code=args.catalog_code,
            pdf_path=args.pdf,
            storage_root=args.storage_root,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except CatalogMediaError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2
    finally:
        database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
