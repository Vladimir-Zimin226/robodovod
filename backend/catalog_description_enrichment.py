"""Strict adapters and append-only import for official catalog transcriptions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


EXPECTED_PDF_SHA256 = "9567641d3a3a7bed9d2e470240b17cefacba047257b5f0b4a5311c159c580369"
EXPECTED_PART1_SHA256 = "b0be869c049b95f493035f312ab83b99e4fda4caeec5ba828f0eb9587203bbe6"
EXPECTED_PART2_SHA256 = "044feb0a1d40e750867a70c93b382a52f10c83e8847bcb94f433d885e9c710d2"
PDF_NAME = "ФЦ БАС — Каталог внедрения 2008 1247.pdf"
PART1_NAME = "ФЦ_БАС_Каталог_часть_1_стр_1-46_полная_текстовая_версия.md"
PART2_NAME = "ФЦ_БАС_Каталог_внедрения_часть_2_стр_47-91_полная_текстовая_версия.md"
EXPECTED_COUNTS = {"page-oriented-v1": 110, "field-oriented-v1": 113}
DESCRIPTION_NAMESPACE = uuid.UUID("aa01cd68-d923-51c8-9a12-7fb1386e1f5c")
OVERLAY_NAME = "catalog_description_overlay.json"
REPORT_NAME = "catalog_description_report.json"

_PAGE_RE = re.compile(r"^## Страница (\d+)$")
_PRODUCT_RE = re.compile(r"^### Продукт (\d+)$")
_PROJECT_RE = re.compile(r"^## Проект (\d+)\.\s+(.+)$")
_FIELD_RE = re.compile(r"^- ([^:]+):(?:\s(.*))?$")
_TRL_RE = re.compile(r"^([1-9])/9$")
_MARKET_RE = re.compile(r"^РЫНОЧНЫЙ ПОТЕНЦИАЛ:\s*([1-5])/5(?:\s.*)?$", re.I)


class CatalogDescriptionError(RuntimeError):
    """Raised when a source or normalized overlay violates the contract."""


@dataclass(frozen=True)
class ParsedCard:
    adapter: str
    document_index: int
    source_page: int
    source_slot: int
    section_number: int | None
    project_number: int
    name_raw: str
    type_raw: str | None
    organization_raw: str
    region_raw: str
    scenario_raw: str
    description_raw: str
    trl: int
    lifecycle_stage: str
    market_potential: int
    case_text_raw: str
    service_labels: tuple[str, ...]
    source_url: str | None
    raw_card: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_sources(source_dir: Path) -> dict[str, dict[str, Any]]:
    expected = {
        PDF_NAME: EXPECTED_PDF_SHA256,
        PART1_NAME: EXPECTED_PART1_SHA256,
        PART2_NAME: EXPECTED_PART2_SHA256,
    }
    result: dict[str, dict[str, Any]] = {}
    for name, checksum in expected.items():
        path = source_dir / name
        if not path.is_file():
            raise CatalogDescriptionError(f"required source is missing: {name}")
        actual = _sha256(path)
        if actual != checksum:
            raise CatalogDescriptionError(f"source checksum mismatch: {name}")
        result[name] = {"sha256": actual, "size_bytes": path.stat().st_size}
    return result


def _clean_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip() and line.strip() != "---"]


def _looks_like_type(value: str) -> bool:
    letters = [char for char in value if char.isalpha()]
    return len(letters) >= 2 and all(char == char.upper() for char in letters)


def _single(pattern: re.Pattern[str], lines: Iterable[str], field: str) -> re.Match[str]:
    matches = [match for line in lines if (match := pattern.match(line))]
    if len(matches) != 1:
        raise CatalogDescriptionError(f"card must contain exactly one {field}")
    return matches[0]


def parse_page_oriented(text: str) -> list[ParsedCard]:
    """Parse the line-order format used by pages 1-46."""

    page_matches = list(re.finditer(r"(?m)^## Страница (\d+)\s*$", text))
    cards: list[ParsedCard] = []
    for page_pos, page_match in enumerate(page_matches):
        page = int(page_match.group(1))
        page_end = page_matches[page_pos + 1].start() if page_pos + 1 < len(page_matches) else len(text)
        page_text = text[page_match.end():page_end]
        product_matches = list(re.finditer(r"(?m)^### Продукт (\d+)\s*$", page_text))
        for slot, product_match in enumerate(product_matches, start=1):
            end = product_matches[slot].start() if slot < len(product_matches) else len(page_text)
            body = page_text[product_match.end():end].strip()
            lines = _clean_lines(body)
            if "УГТ" not in lines:
                raise CatalogDescriptionError(f"page {page} slot {slot}: missing УГТ")
            trl_index = lines.index("УГТ")
            prefix, suffix = lines[:trl_index], lines[trl_index + 1:]
            if len(suffix) < 3 or not (trl_match := _TRL_RE.match(suffix[0])):
                raise CatalogDescriptionError(f"page {page} slot {slot}: invalid УГТ")
            market_match = _single(_MARKET_RE, suffix, "market potential")
            market_index = next(i for i, line in enumerate(suffix) if _MARKET_RE.match(line))
            if market_index != 2:
                raise CatalogDescriptionError(f"page {page} slot {slot}: unexpected lifecycle layout")
            org_indexes = [i for i, line in enumerate(prefix) if " · " in line or line.endswith(" ·")]
            if len(org_indexes) != 1 or org_indexes[0] < 1:
                raise CatalogDescriptionError(f"page {page} slot {slot}: invalid organization anchor")
            org_index = org_indexes[0]
            type_indexes = [i for i, line in enumerate(prefix[:org_index]) if _looks_like_type(line)]
            type_index = type_indexes[-1] if type_indexes else None
            organization_start = type_index + 1 if type_index is not None else org_index
            if prefix[org_index].endswith(" ·"):
                if org_index + 1 >= len(prefix):
                    raise CatalogDescriptionError(f"page {page} slot {slot}: missing wrapped region")
                organization = " ".join([*prefix[organization_start:org_index], prefix[org_index][:-2]])
                region = prefix[org_index + 1]
                content_start = org_index + 2
            else:
                organization_tail, region = prefix[org_index].rsplit(" · ", 1)
                organization = " ".join([*prefix[organization_start:org_index], organization_tail])
                content_start = org_index + 1
            type_raw = prefix[type_index] if type_index is not None else None
            name = " ".join(prefix[:type_index]) if type_index is not None else " ".join(prefix[:org_index])
            after_org = [line for line in prefix[content_start:] if line != "↗"]
            if len(after_org) < 2:
                raise CatalogDescriptionError(f"page {page} slot {slot}: missing scenario/description")
            url_lines = [line for line in suffix[3:] if line.startswith("Встроенная ссылка PDF: ")]
            if len(url_lines) > 1:
                raise CatalogDescriptionError(f"page {page} slot {slot}: duplicate URL")
            labels = tuple(line for line in suffix[3:] if not line.startswith("Встроенная ссылка PDF: "))
            cards.append(
                ParsedCard(
                    adapter="page-oriented-v1",
                    document_index=len(cards) + 1,
                    source_page=page,
                    source_slot=slot,
                    section_number=None,
                    project_number=int(product_match.group(1)),
                    name_raw=name,
                    type_raw=type_raw,
                    organization_raw=organization,
                    region_raw=region,
                    scenario_raw=after_org[0],
                    description_raw=" ".join(after_org[1:]),
                    trl=int(trl_match.group(1)),
                    lifecycle_stage=suffix[1],
                    market_potential=int(market_match.group(1)),
                    case_text_raw=" ".join(after_org[1:]),
                    service_labels=labels,
                    source_url=(url_lines[0].removeprefix("Встроенная ссылка PDF: ") if url_lines else None),
                    raw_card=body,
                )
            )
    if len(cards) != EXPECTED_COUNTS["page-oriented-v1"]:
        raise CatalogDescriptionError(f"page-oriented adapter expected 110 cards, got {len(cards)}")
    return cards


def parse_field_oriented(text: str) -> list[ParsedCard]:
    """Parse the explicit labelled-field format used by pages 47-91."""

    section = None
    cards: list[ParsedCard] = []
    page_slots: defaultdict[int, int] = defaultdict(int)
    matches = list(re.finditer(r"(?m)^# Раздел (\d+):.*$|^## Проект (\d+)\.\s+(.+)\s*$", text))
    for index, match in enumerate(matches):
        if match.group(1):
            section = int(match.group(1))
            continue
        if section is None:
            raise CatalogDescriptionError("project appears before a section")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        fields: dict[str, list[str]] = defaultdict(list)
        for line in _clean_lines(body):
            field_match = _FIELD_RE.match(line)
            if not field_match:
                if line.startswith("**") or line.startswith("Титульная страница") or line.startswith("В каталоге указано"):
                    continue
                raise CatalogDescriptionError(f"unexpected field line: {line[:80]}")
            fields[field_match.group(1)].append(field_match.group(2) or "")
        required = {
            "Страница каталога", "Организация", "Регион", "Задача / сценарий",
            "Описание", "УГТ", "Статус", "Рыночный потенциал",
        }
        missing = required - fields.keys()
        unknown = fields.keys() - required - {"Тип", "Метка"}
        if missing or unknown or any(len(values) != 1 for key, values in fields.items() if key != "Метка"):
            raise CatalogDescriptionError(
                f"project {match.group(2)} has invalid fields: missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        page = int(fields["Страница каталога"][0])
        page_slots[page] += 1
        trl_match = _TRL_RE.match(fields["УГТ"][0])
        market_match = re.match(r"^([1-5])/5$", fields["Рыночный потенциал"][0])
        if not trl_match or not market_match:
            raise CatalogDescriptionError(f"page {page}: invalid УГТ/market potential")
        cards.append(
            ParsedCard(
                adapter="field-oriented-v1",
                document_index=len(cards) + 1,
                source_page=page,
                source_slot=page_slots[page],
                section_number=section,
                project_number=int(match.group(2)),
                name_raw=match.group(3).strip(),
                type_raw=(fields.get("Тип") or [None])[0],
                organization_raw=fields["Организация"][0],
                region_raw=fields["Регион"][0],
                scenario_raw=fields["Задача / сценарий"][0],
                description_raw=fields["Описание"][0],
                trl=int(trl_match.group(1)),
                lifecycle_stage=fields["Статус"][0],
                market_potential=int(market_match.group(1)),
                case_text_raw=fields["Описание"][0],
                service_labels=tuple(fields.get("Метка", ())),
                source_url=None,
                raw_card=body,
            )
        )
    if len(cards) != EXPECTED_COUNTS["field-oriented-v1"]:
        raise CatalogDescriptionError(f"field-oriented adapter expected 113 cards, got {len(cards)}")
    return cards


def _anchor(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    value = value.translate(str.maketrans({"«": '"', "»": '"', "“": '"', "”": '"', "–": "-", "—": "-", "×": "x"}))
    return re.sub(r"[^0-9a-zа-я]+", " ", value).strip()


def _anchor_equivalent(left: str | None, right: str | None) -> bool:
    a, b = _anchor(left), _anchor(right)
    if a == b:
        return True
    visual = str.maketrans("амтосехрквн", "amtocexpkbh")
    av, bv = a.translate(visual), b.translate(visual)
    if av == bv:
        return True
    # An ellipsis in the supplied transcription explicitly marks a truncated
    # printed label; it is not silently expanded in the stored raw value.
    return bool(left and "…" in left and bv.startswith(av))


def _text(value: str | None) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "")).strip()


def _align_page_card(card: ParsedCard, product: dict[str, Any], position: dict[str, Any]) -> ParsedCard:
    """Resolve wrapped page-oriented anchors against the already ordered row."""

    lines = _clean_lines(card.raw_card)
    prefix = lines[: lines.index("УГТ")]
    prefix = [line for line in prefix if line != "↗"]
    sep = next(i for i, line in enumerate(prefix) if " · " in line or line.endswith(" ·"))
    name_end = next(
        (i for i in range(1, sep + 1) if _anchor_equivalent(" ".join(prefix[:i]), product["name"])),
        None,
    )
    if name_end is None:
        return card
    organization_start = next(
        (
            i
            for i in range(name_end, sep + 1)
            if _anchor_equivalent(
                " ".join([*prefix[i:sep], prefix[sep].split(" ·", 1)[0]]),
                product.get("manufacturer"),
            )
        ),
        None,
    )
    if organization_start is None:
        return card
    if prefix[sep].endswith(" ·"):
        region = prefix[sep + 1]
        content_start = sep + 2
    else:
        region = prefix[sep].rsplit(" · ", 1)[1]
        content_start = sep + 1
    content = prefix[content_start:]
    scenario_end = next(
        (i for i in range(1, len(content)) if _anchor_equivalent(" ".join(content[:i]), position["scenario"])),
        None,
    )
    if scenario_end is None:
        scenario_end = 1
    return replace(
        card,
        name_raw=" ".join(prefix[:name_end]),
        type_raw=(" ".join(prefix[name_end:organization_start]) or None),
        organization_raw=" ".join([*prefix[organization_start:sep], prefix[sep].split(" ·", 1)[0]]),
        region_raw=region,
        scenario_raw=" ".join(content[:scenario_end]),
        description_raw=" ".join(content[scenario_end:]),
        case_text_raw=" ".join(content[scenario_end:]),
    )


def _load_positions(bundle_dir: Path) -> list[dict[str, Any]]:
    products = json.loads((bundle_dir / "catalog_products.json").read_text(encoding="utf-8"))["products"]
    by_id = {row["organizer_id"]: row for row in products}
    with (bundle_dir / "catalog_applicability.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter=";"))
    rows.sort(key=lambda row: int(row["original_row"]))
    return [{**row, "product": by_id[row["organizer_id"]]} for row in rows]


def build_overlay(source_dir: Path, bundle_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    artifacts = verify_sources(source_dir)
    part1 = parse_page_oriented((source_dir / PART1_NAME).read_text(encoding="utf-8-sig"))
    part2 = parse_field_oriented((source_dir / PART2_NAME).read_text(encoding="utf-8-sig"))
    cards = [*part1, *part2]
    positions = _load_positions(bundle_dir)
    if len(positions) != 223 or len(cards) != 223:
        raise CatalogDescriptionError("overlay requires exactly 223 positions")

    from catalog_media import extract_position_images

    images = extract_position_images(source_dir / PDF_NAME)
    entries: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    missing_type = 0
    missing_type_by_adapter: Counter[str] = Counter()
    url_count = 0
    statuses: Counter[str] = Counter()
    unresolved = 0
    for ordinal, (position, card, image) in enumerate(zip(positions, cards, images, strict=True), start=1):
        product = position["product"]
        if card.adapter == "page-oriented-v1":
            card = _align_page_card(card, product, position)
        name_ok = _anchor_equivalent(card.name_raw, product["name"])
        organization_ok = _anchor_equivalent(card.organization_raw, product.get("manufacturer"))
        if (card.source_page, card.source_slot) != (image.source_page, image.source_slot):
            raise CatalogDescriptionError(
                f"position {ordinal}: transcript/media locator mismatch"
            )
        mapping_status = (
            "VERIFIED"
            if name_ok and organization_ok
            else "VERIFIED_WITH_NAME_CONFLICT"
            if organization_ok
            else "VERIFIED_WITH_ORGANIZATION_CONFLICT"
            if name_ok
            else "UNRESOLVED"
        )
        unresolved += mapping_status == "UNRESOLVED"
        if not name_ok or not organization_ok:
            diagnostics.append({
                "ordinal": ordinal,
                "source_row_number": int(position["original_row"]),
                "source_page": card.source_page,
                "source_slot": card.source_slot,
                "name_ok": name_ok,
                "organization_ok": organization_ok,
                "transcript_name": card.name_raw,
                "catalog_name": product["name"],
                "transcript_organization": card.organization_raw,
                "catalog_organization": product.get("manufacturer"),
            })
        existing = ((product.get("description") or {}).get("normalized") or (product.get("description") or {}).get("raw"))
        if existing:
            description_status = "EXISTING_MATCH" if _anchor(existing) == _anchor(card.description_raw) else "REVIEW_REQUIRED"
        else:
            description_status = "ENRICHED"
        statuses[description_status] += 1
        missing_type += card.type_raw is None
        if card.type_raw is None:
            missing_type_by_adapter[card.adapter] += 1
        url_count += card.source_url is not None
        entries.append({
            "position_ordinal": ordinal,
            "source_record_key": f"catalog-v4-row-{int(position['original_row']):04d}",
            "source_row_number": int(position["original_row"]),
            "adapter": card.adapter,
            "transcript_sha256": artifacts[PART1_NAME if card.adapter == "page-oriented-v1" else PART2_NAME]["sha256"],
            "source_page": card.source_page,
            "source_slot": card.source_slot,
            "media_sha256": image.sha256,
            "project_number": card.project_number,
            "name_raw": card.name_raw,
            "organization_raw": card.organization_raw,
            "region_raw": card.region_raw,
            "type_raw": card.type_raw,
            "scenario_raw": card.scenario_raw,
            "description_raw": card.description_raw,
            "description_normalized": _text(card.description_raw),
            "trl": card.trl,
            "lifecycle_stage": card.lifecycle_stage,
            "market_potential": card.market_potential,
            "case_text_raw": card.case_text_raw,
            "service_labels": list(card.service_labels),
            "source_url": card.source_url,
            "raw_card": card.raw_card,
            "anchor_validation": {
                "name": name_ok,
                "organization": organization_ok,
                "mapping_status": mapping_status,
            },
            "existing_description": existing,
            "description_status": description_status,
            "limitation": "externally prepared transcription; OCR engine/model/version unavailable",
        })
    overlay = {
        "schema_version": "catalog-description-overlay-v1",
        "catalog_code": "organizer-catalog-v4",
        "source_artifacts": artifacts,
        "entries": entries,
    }
    report = {
        "schema_version": "catalog-description-coverage-report-v1",
        "catalog_code": "organizer-catalog-v4",
        "positions_total": 223,
        "mapped": 223 - unresolved,
        "unresolved": unresolved,
        "anchor_conflicts": diagnostics,
        "description_status_counts": dict(sorted(statuses.items())),
        "missing_type_count": missing_type,
        "missing_type_by_adapter": dict(sorted(missing_type_by_adapter.items())),
        "source_url_count": url_count,
        "runtime_facts_created": 0,
        "limitations": ["OCR engine/model/version was not supplied with the externally prepared transcriptions"],
    }
    return overlay, report


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def load_verified_overlay(source_dir: Path, bundle_dir: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Rebuild local inputs and verify the committed semantic overlay."""

    expected_overlay, expected_report = build_overlay(source_dir, bundle_dir)
    overlay_path, report_path = bundle_dir / OVERLAY_NAME, bundle_dir / REPORT_NAME
    if not overlay_path.is_file() or not report_path.is_file():
        raise CatalogDescriptionError("committed description overlay/report is missing")
    overlay_bytes = overlay_path.read_bytes()
    try:
        committed_overlay = json.loads(overlay_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogDescriptionError("committed description overlay is invalid") from exc

    # PDF image containers emitted by pypdf/Pillow are not stable across
    # supported library versions.  The media importer verifies the original
    # PDF digest and the bytes extracted in this process, so compare all
    # durable transcription/provenance fields while binding the import to the
    # locally extracted asset hashes below.
    def without_media_hashes(value: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(value)
        normalized["entries"] = [
            {key: item for key, item in entry.items() if key != "media_sha256"}
            for entry in value.get("entries", [])
        ]
        return normalized

    if without_media_hashes(committed_overlay) != without_media_hashes(expected_overlay):
        raise CatalogDescriptionError("committed description overlay differs from verified local inputs")
    if report_path.read_bytes() != _canonical_bytes(expected_report):
        raise CatalogDescriptionError("committed description report differs from verified local inputs")
    return expected_overlay, expected_report, hashlib.sha256(overlay_bytes).hexdigest()


def import_description_overlay(
    database: Any,
    *,
    source_dir: Path,
    bundle_dir: Path,
    catalog_code: str = "organizer-catalog-v4",
    commit: bool = True,
) -> dict[str, Any]:
    """Validate and optionally insert the complete append-only overlay atomically."""

    from catalog_models import (
        CatalogDescriptionImport,
        CatalogMediaAsset,
        CatalogPositionEnrichment,
        CatalogPositionMedia,
        CatalogSourceRow,
    )
    from sqlalchemy import func, select
    from storage_models import CatalogVersion, CatalogVersionSource, SourceArtifact

    overlay, report, overlay_sha256 = load_verified_overlay(source_dir, bundle_dir)
    if report["unresolved"] or report["positions_total"] != 223:
        raise CatalogDescriptionError("description overlay has unresolved positions")
    with database.session() as session:
        version = session.scalar(
            select(CatalogVersion)
            .where(CatalogVersion.code == catalog_code)
            .with_for_update()
        )
        if version is None:
            raise CatalogDescriptionError("catalog version was not found")
        existing_import = session.scalar(
            select(CatalogDescriptionImport).where(
                CatalogDescriptionImport.catalog_version_id == version.id
            )
        )
        if existing_import is not None:
            count = session.scalar(
                select(func.count()).select_from(CatalogPositionEnrichment).where(
                    CatalogPositionEnrichment.catalog_version_id == version.id
                )
            )
            if existing_import.overlay_sha256 != overlay_sha256 or count != 223:
                raise CatalogDescriptionError("catalog has a conflicting or partial description import")
            return {**report, "changed": False, "overlay_sha256": overlay_sha256}

        source_rows = session.scalars(
            select(CatalogSourceRow)
            .where(CatalogSourceRow.catalog_version_id == version.id)
            .order_by(CatalogSourceRow.source_row_number)
        ).all()
        media_rows = session.execute(
            select(CatalogPositionMedia, CatalogMediaAsset)
            .join(
                CatalogMediaAsset,
                (CatalogMediaAsset.id == CatalogPositionMedia.media_asset_id)
                & (CatalogMediaAsset.catalog_version_id == CatalogPositionMedia.catalog_version_id),
            )
            .where(CatalogPositionMedia.catalog_version_id == version.id)
        ).all()
        media_by_source = {link.catalog_source_row_id: (link, asset) for link, asset in media_rows}
        if len(source_rows) != 223 or len(media_by_source) != 223:
            raise CatalogDescriptionError("description import requires all 223 source rows and media links")
        entries = overlay["entries"]
        for source_row, entry in zip(source_rows, entries, strict=True):
            link, asset = media_by_source[source_row.id]
            actual = (source_row.source_record_key, link.source_page, link.source_slot, asset.sha256)
            expected = (entry["source_record_key"], entry["source_page"], entry["source_slot"], entry["media_sha256"])
            if actual != expected:
                raise CatalogDescriptionError("overlay/source-row/media provenance mismatch")
        if not commit:
            return {**report, "changed": False, "validated_only": True, "overlay_sha256": overlay_sha256}

        transcript_ids: dict[str, uuid.UUID] = {}
        for ordinal, name in enumerate((PART1_NAME, PART2_NAME), start=100):
            metadata = overlay["source_artifacts"][name]
            artifact = session.scalar(select(SourceArtifact).where(SourceArtifact.sha256 == metadata["sha256"]))
            artifact_id = uuid.uuid5(DESCRIPTION_NAMESPACE, metadata["sha256"])
            if artifact is None:
                artifact = SourceArtifact(
                    id=artifact_id,
                    sha256=metadata["sha256"],
                    original_name=name,
                    media_type="text/markdown",
                    byte_size=metadata["size_bytes"],
                    storage_key=None,
                    provenance_status="PENDING",
                    license_status="RESTRICTED",
                    observed_at=datetime(2026, 9, 17, tzinfo=UTC),
                )
                session.add(artifact)
                session.flush()
            elif (artifact.original_name, artifact.media_type, artifact.byte_size) != (name, "text/markdown", metadata["size_bytes"]):
                raise CatalogDescriptionError("transcript artifact metadata conflict")
            transcript_ids[metadata["sha256"]] = artifact.id
            link = session.get(CatalogVersionSource, (version.id, artifact.id))
            if link is None:
                session.add(CatalogVersionSource(catalog_version_id=version.id, source_artifact_id=artifact.id, role="REFERENCE", ordinal=ordinal))

        import_id = uuid.uuid5(DESCRIPTION_NAMESPACE, f"{version.id}:{overlay_sha256}")
        session.add(
            CatalogDescriptionImport(
                id=import_id,
                catalog_version_id=version.id,
                overlay_sha256=overlay_sha256,
                report=report,
            )
        )
        session.flush()
        for source_row, entry in zip(source_rows, entries, strict=True):
            normalized_fields = {
                key: entry[key]
                for key in (
                    "project_number", "name_raw", "organization_raw", "region_raw",
                    "type_raw", "scenario_raw", "trl", "lifecycle_stage",
                    "market_potential", "case_text_raw", "service_labels", "source_url",
                )
            }
            session.add(
                CatalogPositionEnrichment(
                    id=uuid.uuid5(DESCRIPTION_NAMESPACE, f"{version.id}:{source_row.id}"),
                    catalog_version_id=version.id,
                    catalog_source_row_id=source_row.id,
                    transcript_artifact_id=transcript_ids[entry["transcript_sha256"]],
                    description_import_id=import_id,
                    source_page=entry["source_page"],
                    source_slot=entry["source_slot"],
                    adapter=entry["adapter"],
                    transcript_sha256=entry["transcript_sha256"],
                    media_sha256=entry["media_sha256"],
                    raw_card=entry["raw_card"],
                    normalized_fields=normalized_fields,
                    description_raw=entry["description_raw"],
                    description_normalized=entry["description_normalized"],
                    existing_description_snapshot=entry["existing_description"],
                    description_status=entry["description_status"],
                    mapping_status=entry["anchor_validation"]["mapping_status"],
                    limitation=entry["limitation"],
                )
            )
        session.commit()
        return {**report, "changed": True, "overlay_sha256": overlay_sha256}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or verify catalog description overlay")
    parser.add_argument("--source-dir", type=Path, default=Path(os.getenv("OFFICIAL_CATALOG_SOURCE_DIR", "../Разобрать/Материалы от организаторов/Датасет")))
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path(os.getenv("CATALOG_DESCRIPTION_BUNDLE", "../data/import/organizer-catalog-v4")),
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--mode", choices=("BUILD", "VALIDATE_ONLY", "COMMIT"), default="BUILD")
    parser.add_argument("--catalog-code", default="organizer-catalog-v4")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source_dir, bundle_dir = args.source_dir.resolve(), args.bundle.resolve()
    overlay, report = build_overlay(source_dir, bundle_dir)
    if args.write:
        (bundle_dir / OVERLAY_NAME).write_bytes(_canonical_bytes(overlay))
        (bundle_dir / REPORT_NAME).write_bytes(_canonical_bytes(report))
    if args.mode != "BUILD":
        from database import Database, DatabaseSettings

        database = Database(DatabaseSettings.from_environment())
        try:
            report = import_description_overlay(
                database,
                source_dir=source_dir,
                bundle_dir=bundle_dir,
                catalog_code=args.catalog_code,
                commit=args.mode == "COMMIT",
            )
        finally:
            database.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["unresolved"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
