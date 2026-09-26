"""Strict, portable admin-catalog-v1 document and immutable DTO projection.

An inherited physical profile keeps its original evidence and rollout identity.
New/changed physical profiles stay informational until a separate rollout is approved.
No document field can set calculation_ready or override a formula/registry constant.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlsplit

from catalog_repository import (
    CapacityRuntimeDTO,
    CatalogApplicabilityDTO,
    CatalogFactDTO,
    CatalogModelDTO,
    CatalogPositionDTO,
    CatalogSnapshotDTO,
    CatalogVersionDTO,
    ProcurementOptionDTO,
)
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

FORMAT = "admin-catalog-v1"
MAX_BYTES = 4 * 1024 * 1024
SAFE_STATUS = {"VERIFIED_OFFICIAL", "MANUALLY_APPROVED"}
# These are scenario proposals, never vendor facts or locked registry parameters.
DEFAULT_RULES = {
    "exchange_seconds": ("s", Decimal("0.001"), Decimal(86400), False),
    "units_per_trip": ("pallet/trip", Decimal(1), Decimal(100000), True),
    "operating_days": ("day/year", Decimal(1), Decimal(366), True),
}


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def physical_value(value: Any) -> Any:
    """Compare JSON numbers across JavaScript's 600.0 -> 600 roundtrip."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return [type(value).__name__, value]
    if isinstance(value, (int, float, Decimal)):
        return ["number", str(Decimal(str(value)).normalize())]
    if isinstance(value, list):
        return ["array", [physical_value(item) for item in value]]
    return [
        "object",
        [[key, physical_value(item)] for key, item in sorted(value.items())],
    ]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Source(Contract):
    key: str = Field(min_length=1, max_length=180)
    url: str = Field(default="", max_length=2000)
    document: str = Field(default="", max_length=500)
    received_on: str | None
    updated_on: str | None
    comment: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def valid(self):
        received = date.fromisoformat(self.received_on) if self.received_on else None
        updated = date.fromisoformat(self.updated_on) if self.updated_on else None
        if (received is None) != (updated is None) or (received and updated < received):
            raise ValueError("source update precedes receipt")
        if received is None and not self.key.startswith("inherited:"):
            raise ValueError("new source requires receipt/update dates")
        if not self.url.strip() and not self.document.strip():
            raise ValueError("source URL or document reference is required")
        if self.url and (
            urlsplit(self.url).scheme not in {"https", "http"}
            or not urlsplit(self.url).netloc
        ):
            raise ValueError("source URL must be HTTP(S)")
        return self


class Spec(Contract):
    code: str = Field(min_length=1, max_length=180)
    value: JsonValue = None
    datatype: Literal["NUMBER", "TEXT", "BOOLEAN", "JSON"] = "NUMBER"
    unit: str = Field(min_length=1, max_length=80)
    scope: str = Field(default="MODEL", min_length=1, max_length=120)
    status: Literal["UNKNOWN", "CONFLICT", "VERIFIED_OFFICIAL", "MANUALLY_APPROVED"] = (
        "UNKNOWN"
    )
    source: str | None = None
    comment: str = Field(default="", max_length=4000)


class Model(Contract):
    key: str = Field(min_length=1, max_length=180)
    name: str = Field(min_length=1, max_length=300)
    manufacturer: str = Field(default="", max_length=300)
    system_family: str = Field(min_length=1, max_length=180)
    type_code: str = Field(min_length=1, max_length=180)
    purpose: str = Field(default="", max_length=4000)
    country: str = Field(default="", max_length=100)
    availability: str = Field(default="UNKNOWN", max_length=180)
    infrastructure: str = Field(default="", max_length=4000)
    lifespan_years: float | int | None = Field(default=None, gt=0, le=100)
    specs: list[Spec] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def identity_is_nonempty(self):
        if not all(
            value.strip() for value in (self.name, self.system_family, self.type_code)
        ):
            raise ValueError("model name, family and type must be nonempty")
        return self


class Offer(Contract):
    key: str = Field(min_length=1, max_length=180)
    model_key: str = Field(min_length=1, max_length=180)
    industry: str = Field(default="", max_length=300)
    scenario: str = Field(default="", max_length=4000)
    region: str = Field(default="", max_length=300)
    case_text: str = Field(default="", max_length=4000)
    mode: Literal["PURCHASE", "LEASE", "RENTAL", "RAAS", "MANAGED_SERVICE", "QUOTE"] = (
        "PURCHASE"
    )
    amount: str | None = Field(default=None, max_length=80)
    currency: str | None = None
    vat_status: Literal[
        "UNKNOWN",
        "ORGANIZER_ASSUMPTION_INCLUDED",
        "INCLUDED",
        "EXCLUDED",
        "NOT_APPLICABLE",
    ] = "UNKNOWN"
    vat_rate: str | None = Field(default=None, max_length=30)
    price_unit: Literal["ONE_TIME", "MONTH", "YEAR", "HOUR", "UNKNOWN"] = "UNKNOWN"
    included_costs: list[str] = Field(default_factory=list, max_length=50)
    excluded_costs: list[str] = Field(default_factory=list, max_length=50)
    status: Literal["UNKNOWN", "CONFLICT", "VERIFIED_OFFICIAL", "MANUALLY_APPROVED"] = (
        "UNKNOWN"
    )
    source: str | None = None
    comment: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def valid(self):
        if self.vat_rate is not None and (
            not Decimal(self.vat_rate).is_finite()
            or not 0 <= Decimal(self.vat_rate) <= 1
        ):
            raise ValueError("VAT rate must be between 0 and 1")
        if self.amount is not None and (
            not Decimal(self.amount).is_finite()
            or not 0 <= Decimal(self.amount) < Decimal("1e18")
        ):
            raise ValueError("offer amount must be finite and nonnegative")
        if self.currency is not None and (not re.fullmatch(r"[A-Z]{3}", self.currency)):
            raise ValueError("currency must use a three-letter uppercase code")
        return self


class Norm(Contract):
    key: str
    value: str
    unit: str
    lower: str
    upper: str
    source: str
    comment: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def valid(self):
        if self.key not in DEFAULT_RULES:
            raise ValueError(
                "locked formula/registry parameter is not an allowed scenario default"
            )
        unit, minimum, maximum, integral = DEFAULT_RULES[self.key]
        if not self.comment.strip():
            raise ValueError("default review comment is required")
        value, lower, upper = map(Decimal, (self.value, self.lower, self.upper))
        if not all(item.is_finite() for item in (value, lower, upper)):
            raise ValueError("default must be finite")
        if self.unit != unit or not minimum <= lower <= value <= upper <= maximum:
            raise ValueError("default unit or bounds are invalid")
        if integral and any(
            item != item.to_integral_value() for item in (value, lower, upper)
        ):
            raise ValueError("default must be integral")
        return self


class Dictionary(Contract):
    key: str = Field(min_length=1, max_length=180)
    label: str = Field(min_length=1, max_length=300)
    kind: Literal["type", "availability", "industry", "spec"]
    unit: str | None = None
    source: str


class Document(Contract):
    schema_version: Literal["admin-catalog-v1"] = FORMAT
    base_catalog_code: str = Field(min_length=1, max_length=180)
    base_content_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    models: list[Model] = Field(max_length=3000)
    offers: list[Offer] = Field(max_length=10000)
    sources: list[Source] = Field(max_length=5000)
    defaults: list[Norm] = Field(default_factory=list, max_length=3)
    dictionaries: list[Dictionary] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def references(self):
        for values in (
            self.models,
            self.offers,
            self.sources,
            self.defaults,
            self.dictionaries,
        ):
            if len({item.key for item in values}) != len(values):
                raise ValueError("duplicate stable key")
            if any(item.key != item.key.strip() for item in values):
                raise ValueError("stable keys must be trimmed")
        sources = {source.key for source in self.sources}
        models = {model.key for model in self.models}
        for model in self.models:
            if len({(item.code, item.scope) for item in model.specs}) != len(
                model.specs
            ):
                raise ValueError("duplicate specification code/scope")
            for spec in model.specs:
                if spec.source is not None and spec.source not in sources:
                    raise ValueError("unknown specification source")
                if spec.status in SAFE_STATUS and (
                    spec.value is None or not spec.source or not spec.comment.strip()
                ):
                    raise ValueError(
                        "confirmed specification requires value, source and review comment"
                    )
        for offer in self.offers:
            if offer.model_key not in models or (
                offer.source and offer.source not in sources
            ):
                raise ValueError("unknown offer model/source")
            if offer.status in SAFE_STATUS and (
                offer.amount is None
                or not offer.currency
                or not offer.source
                or not offer.comment.strip()
                or offer.vat_status == "UNKNOWN"
            ):
                raise ValueError(
                    "confirmed offer requires price, currency, VAT, source and review"
                )
        for entry in [*self.defaults, *self.dictionaries]:
            if entry.source not in sources:
                raise ValueError("unknown default/dictionary source")
        return self


def export_document(snapshot: CatalogSnapshotDTO) -> dict:
    sources: dict[str, dict] = {}
    models = []
    for model in snapshot.models:
        specs = []
        for fact in model.facts:
            key = "inherited:" + fact.evidence_id
            sources[key] = {
                "key": key,
                "url": "",
                "document": key,
                "received_on": None,
                "updated_on": None,
                "comment": "Immutable evidence reference; original dates remain in the parent catalog",
            }
            specs.append(
                {
                    "code": fact.code,
                    "value": str(fact.value)
                    if isinstance(fact.value, Decimal)
                    else fact.value,
                    "datatype": "NUMBER"
                    if isinstance(fact.value, (Decimal, int, float))
                    and not isinstance(fact.value, bool)
                    else "BOOLEAN"
                    if isinstance(fact.value, bool)
                    else "JSON"
                    if isinstance(fact.value, (dict, list))
                    else "TEXT",
                    "unit": fact.canonical_unit,
                    "scope": fact.scope_code,
                    "status": "MANUALLY_APPROVED",
                    "source": key,
                    "comment": "Inherited matching-safe evidence: "
                    + fact.resolution_status,
                }
            )
        models.append(
            {
                "key": model.source_record_key,
                "name": model.name,
                "manufacturer": model.manufacturer or "",
                "system_family": model.system_family,
                "type_code": model.type_code,
                "purpose": model.description or "",
                "country": str(model.attributes.get("country", "")),
                "availability": model.maturity_status or "UNKNOWN",
                "infrastructure": "",
                "lifespan_years": None,
                "specs": specs,
            }
        )
    offers = []
    for position in snapshot.positions:
        option, app = position.procurement_option, position.applicability
        offers.append(
            {
                "key": position.source_record_key,
                "model_key": position.model.source_record_key,
                "industry": app.industry or "",
                "scenario": app.scenario or "",
                "region": app.region or "",
                "case_text": app.case_text or "",
                "mode": option.mode,
                "amount": str(option.amount) if option.amount is not None else None,
                "currency": option.currency,
                "vat_status": option.vat_status,
                "vat_rate": str(option.vat_rate)
                if option.vat_rate is not None
                else None,
                "price_unit": "UNKNOWN",
                "included_costs": list(option.included_costs),
                "excluded_costs": list(option.excluded_costs),
                "status": "UNKNOWN",
                "source": None,
                "comment": "",
            }
        )
    return Document.model_validate(
        {
            "schema_version": FORMAT,
            "base_catalog_code": snapshot.version.code,
            "base_content_sha256": snapshot.version.content_sha256,
            "models": models,
            "offers": offers,
            "sources": list(sources.values()),
            "defaults": [],
            "dictionaries": [],
        }
    ).model_dump(mode="json")


def validate_document(payload: dict, baseline: CatalogSnapshotDTO) -> Document:
    if (
        len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode())
        > MAX_BYTES
    ):
        raise ValueError("catalog document exceeds 4 MiB")
    document = Document.model_validate(payload)
    if (
        document.base_catalog_code != baseline.version.code
        or document.base_content_sha256 != baseline.version.content_sha256
    ):
        raise ValueError("parent catalog checksum/code mismatch")
    units = {
        (fact.code, fact.canonical_unit)
        for model in baseline.models
        for fact in model.facts
    }
    inherited_sources = {
        "inherited:" + fact.evidence_id
        for model in baseline.models
        for fact in model.facts
    }
    if any(
        source.key.startswith("inherited:") and source.key not in inherited_sources
        for source in document.sources
    ):
        raise ValueError("inherited source identity is not present in the root catalog")
    for entry in document.dictionaries:
        if entry.kind == "spec":
            if not entry.unit or (
                any(code == entry.key for code, _ in units)
                and (entry.key, entry.unit) not in units
            ):
                raise ValueError("specification dictionary requires the canonical unit")
            units.add((entry.key, entry.unit))
    for model in document.models:
        for spec in model.specs:
            if (spec.code, spec.unit) not in units:
                raise ValueError(
                    "unknown specification code or incompatible canonical unit"
                )
            if spec.value is not None and spec.datatype == "NUMBER":
                if isinstance(spec.value, (bool, dict, list)):
                    raise ValueError("numeric specification requires a finite number")
                number = Decimal(str(spec.value))
                if not number.is_finite() or number < 0:
                    raise ValueError(
                        "numeric specification must be finite and nonnegative"
                    )
            if (
                spec.value is not None
                and spec.datatype == "BOOLEAN"
                and not isinstance(spec.value, bool)
            ):
                raise ValueError("boolean specification requires true/false")
            if (
                spec.value is not None
                and spec.datatype == "TEXT"
                and not isinstance(spec.value, str)
            ):
                raise ValueError("text specification requires text")
    # Parent identities are retained; removal would silently invalidate an approved pool.
    if not {model.source_record_key for model in baseline.models} <= {
        model.key for model in document.models
    }:
        raise ValueError(
            "parent models cannot be removed; create a new information-only model"
        )
    if not {position.source_record_key for position in baseline.positions} <= {
        offer.key for offer in document.offers
    }:
        raise ValueError("parent offers cannot be removed")
    return document


def diff(old: dict, new: dict) -> list[dict]:
    changes = []
    for section in ("models", "offers", "sources", "defaults", "dictionaries"):
        left, right = (
            {item["key"]: item for item in document[section]} for document in (old, new)
        )
        for key in sorted(set(left) | set(right)):
            if left.get(key) != right.get(key):
                changes.append(
                    {
                        "section": section,
                        "key": key,
                        "before": left.get(key),
                        "after": right.get(key),
                    }
                )
    return changes


def project_document(
    document: Document, baseline: CatalogSnapshotDTO, version: CatalogVersionDTO
) -> CatalogSnapshotDTO:
    inherited = baseline.by_source_key()
    original = export_document(baseline)
    original_models = {model["key"]: model for model in original["models"]}
    original_offers = {offer["key"]: offer for offer in original["offers"]}
    old_positions = {
        position.source_record_key: position for position in baseline.positions
    }
    models = {}
    blocked = CapacityRuntimeDTO(
        "CALCULATION_BLOCKED",
        False,
        False,
        None,
        ("ADMIN_PHYSICAL_PROFILE_REQUIRES_EVIDENCE_AND_ROLLOUT_APPROVAL",),
        None,
    )
    for model in document.models:
        parent = inherited.get(model.key)
        # Metadata edits never grant a physical/evidence identity. Exact inherited
        # specs keep original evidence IDs; a claimed confirmation is insufficient.
        physical = lambda specs: sorted(
            (
                spec["code"],
                spec["scope"],
                str(Decimal(str(spec["value"])).normalize())
                if spec["datatype"] == "NUMBER" and spec["value"] is not None
                else digest(physical_value(spec["value"])),
                spec["datatype"],
                spec["unit"],
                spec["source"] or "",
                spec["status"] in SAFE_STATUS,
            )
            for spec in specs
        )
        same = (
            parent is not None
            and all(
                model.model_dump()[key] == original_models[model.key][key]
                for key in ("system_family", "type_code")
            )
            and physical([spec.model_dump() for spec in model.specs])
            == physical(original_models[model.key]["specs"])
        )
        facts = (
            parent.facts
            if same
            else tuple(
                CatalogFactDTO(
                    spec.code,
                    spec.scope,
                    spec.value,
                    spec.unit,
                    spec.status,
                    f"admin:{version.id}:{model.key}:{spec.code}:{spec.source}",
                )
                for spec in model.specs
                if spec.value is not None and spec.status in SAFE_STATUS
            )
        )
        attributes = copy.deepcopy(parent.attributes) if parent else {}
        attributes["admin_physical_inherited"] = same
        attributes["admin_metadata"] = {
            "country": model.country,
            "availability": model.availability,
            "infrastructure": model.infrastructure,
            "lifespan_years": model.lifespan_years,
            "specifications": [spec.model_dump() for spec in model.specs],
        }
        item = CatalogModelDTO(
            id=parent.id
            if parent
            else str(uuid.uuid5(uuid.UUID(version.id), "model:" + model.key)),
            source_namespace=parent.source_namespace if parent else "admin-v1",
            source_record_key=model.key,
            organizer_id=parent.organizer_id if same else None,
            manufacturer=model.manufacturer or None,
            name=model.name,
            system_family=model.system_family,
            type_code=model.type_code,
            subtype_code=parent.subtype_code if parent else None,
            maturity_status=model.availability,
            trl=parent.trl if parent else None,
            description=model.purpose,
            attributes=attributes,
            facts=facts,
            applicability=(),
            procurement_options=(),
            runtime_robot=None,
            runtime_blockers=() if same else blocked.calculation_blockers,
            capacity_runtime=parent.capacity_runtime if same else blocked,
        )
        # Runtime legacy pricing is rebuilt per offer below; inherited robots remain
        # eligible only when the physical projection and offer are both unchanged.
        models[model.key] = item
    positions = []
    for n, offer in enumerate(document.offers, 1):
        parent = old_positions.get(offer.key)
        model = models[offer.model_key]
        unchanged = (
            parent is not None and offer.model_dump() == original_offers[offer.key]
        )
        option = (
            parent.procurement_option
            if unchanged
            else ProcurementOptionDTO(
                mode=offer.mode,
                amount=Decimal(offer.amount) if offer.amount is not None else None,
                currency=offer.currency,
                price_status="NORMALIZED" if offer.amount is not None else "UNKNOWN",
                vat_status=offer.vat_status,
                vat_rate=Decimal(offer.vat_rate)
                if offer.vat_rate is not None
                else None,
                included_costs=tuple(offer.included_costs),
                excluded_costs=tuple(offer.excluded_costs),
                evidence_id=f"admin:{version.id}:{offer.source}"
                if offer.source
                else None,
                id=str(uuid.uuid5(uuid.UUID(version.id), "offer:" + offer.key)),
                evidence_status=offer.status,
            )
        )
        app = CatalogApplicabilityDTO(
            offer.industry or None,
            offer.scenario or None,
            offer.region or None,
            offer.case_text or None,
        )
        # Only approved existing positions retain calculation membership. New offers
        # stay informational even when attached to an approved model.
        physical_same = (
            parent is not None
            and parent.model.source_record_key == offer.model_key
            and model.attributes["admin_physical_inherited"]
        )
        position_model = (
            model if physical_same else replace(model, capacity_runtime=blocked)
        )
        robot = (
            copy.deepcopy(parent.runtime_robot) if unchanged and physical_same else None
        )
        if robot:
            robot["name"] = model.name
        positions.append(
            CatalogPositionDTO(
                id=parent.id
                if parent
                else str(uuid.uuid5(uuid.UUID(version.id), "position:" + offer.key)),
                source_record_key=offer.key,
                source_row_number=n,
                model=position_model,
                applicability=app,
                procurement_option=option,
                media=parent.media if parent else None,
                runtime_robot=robot,
                runtime_blockers=()
                if robot
                else ("ADMIN_OFFER_REQUIRES_RUNTIME_PRICE_REVIEW",),
                enrichment=None,
                source_name=offer.source or (parent.source_name if parent else None),
                source_observed_on=next(
                    (
                        date.fromisoformat(source.received_on)
                        if source.received_on
                        else None
                        for source in document.sources
                        if source.key == offer.source
                    ),
                    None,
                ),
            )
        )
    for key, model in models.items():
        associated = [
            position
            for position in positions
            if position.model.source_record_key == key
        ]
        models[key] = replace(
            model,
            procurement_options=tuple(p.procurement_option for p in associated),
            applicability=tuple(p.applicability for p in associated),
        )
    return CatalogSnapshotDTO(
        version,
        tuple(models.values()),
        tuple(positions),
        admin_defaults=tuple(item.model_dump() for item in document.defaults),
        rollout_reference=baseline,
    )
