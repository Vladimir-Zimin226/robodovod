import logging
import os
import re
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from auditor import conduct_interview
from catalog_media import CatalogMediaError, resolve_media_path
from catalog_models import CatalogMediaAsset
from catalog_repository import (
    CatalogPositionDTO,
    CatalogSnapshotDTO,
)
from catalog_taxonomy import CATEGORY_LABELS, CATEGORY_ORDER
from catalog_runtime import CatalogRuntime, CatalogRuntimeConfigurationError
from calculation.service import analyze_capacity
from database import get_database
from economics import (
    ASSUMPTIONS,
    DEFAULT_AREA_M2,
    DEFAULT_HORIZON_YEARS,
    SOURCES,
    assess_data_quality,
    calc_combined,
    calc_recommendation,
    calc_zone,
    check_constraints,
    manual_baseline,
    recommendation_sort_key,
    validate_mandatory,
)
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from calculation_contracts import CapacityAnalysisErrorResponse, ContractIssue
from models import CalculationResponse, RejectedRobot, UserInput
from object_profiles import (
    ObjectProfileError,
    build_official_preset,
    get_official_profile,
    load_official_profiles,
    official_profile_version,
    profile_api_dict,
)
from procurement.contracts import ProcurementReportRequestV1, ProcurementReportV1
from procurement.resolver import resolve_procurement_report
from pydantic import BaseModel
from readiness import ReadinessReport, ReadinessRequest, evaluate_readiness
from scenario_spec import build_scenario_spec
from simulation import generate_simulation
from simulation_api import create_simulation_router
from sqlalchemy import select
from storage_models import CatalogVersion

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("robomera.api")


# ═══════════════════════════════════════════════════════════════
# Парк роботов разрешается только из явно активированного runtime-каталога.
# ═══════════════════════════════════════════════════════════════
_CATALOG_RUNTIME = CatalogRuntime()


def _runtime_snapshot() -> CatalogSnapshotDTO:
    try:
        return _CATALOG_RUNTIME.load_runtime()
    except CatalogRuntimeConfigurationError:
        logger.error("Configured runtime catalog is unavailable")
        raise HTTPException(503, "runtime catalog unavailable") from None


def _discovery_snapshot() -> CatalogSnapshotDTO:
    try:
        return _CATALOG_RUNTIME.load_discovery()
    except CatalogRuntimeConfigurationError:
        logger.error("Activated discovery catalog is unavailable")
        raise HTTPException(503, "discovery catalog unavailable") from None


def _robots_by_category(robots: list[dict[str, Any]]):
    return {
        category: {
            "label": CATEGORY_LABELS[category],
            "robots": [robot for robot in robots if robot["category"] == category],
        }
        for category in CATEGORY_ORDER
    }


app = FastAPI(title="РобоМера API", version="3.9.0")


@app.exception_handler(RequestValidationError)
async def versioned_request_validation(request: Request, exc: RequestValidationError):
    if request.url.path == "/api/v2/capacity-analyses":
        body = CapacityAnalysisErrorResponse(
            request_id=f"request.{uuid.uuid4()}", error_code="INVALID_REQUEST",
            issues=[ContractIssue(
                code="c11-invalid-request", reason="INVALID_DOMAIN", severity="BLOCKER",
                field_refs=["request"], decision_refs=["K19"],
                message="capacity analysis request does not match schema v2",
            )],
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))
    return await request_validation_exception_handler(request, exc)
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "APP_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    message: str
    history: list = []
    collected: dict = {}
    meta: dict = {}


# ═══════════════════════════════════════════════════════════════
# Служебные
# ═══════════════════════════════════════════════════════════════
@app.get("/")
def root():
    return {"service": "РобоМера", "version": "3.9.0", "status": "ok"}


@app.get("/ready")
def readiness():
    try:
        get_database().check_connection()
    except Exception as exc:
        # Database exceptions can include connection details. Log only the
        # exception class and expose a stable, non-sensitive response.
        logger.warning(
            "Database readiness check failed (error_type=%s)",
            type(exc).__name__,
        )
        raise HTTPException(status_code=503, detail="database unavailable") from None
    return {"status": "ready", "database": "available"}


@app.post("/api/v2/procurement-reports", response_model=ProcurementReportV1)
def procurement_report(request: ProcurementReportRequestV1) -> ProcurementReportV1:
    """Resolve commercial inputs without calculating economics or changing catalog state."""

    try:
        return resolve_procurement_report(request, _discovery_snapshot())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


# ═══════════════════════════════════════════════════════════════
# Парк роботов
# ═══════════════════════════════════════════════════════════════
@app.get("/api/robots")
def list_robots():
    """Плоский список всего парка."""
    return _runtime_snapshot().runtime_robots()


@app.get("/api/robots/by-category")
def list_robots_by_category():
    """Парк, сгруппированный по категориям с человекочитаемыми заголовками."""
    return _robots_by_category(_runtime_snapshot().runtime_robots())


@app.get("/api/robots/categories")
def list_categories():
    """Список категорий в фиксированном порядке."""
    return [{"key": c, "label": CATEGORY_LABELS[c]} for c in CATEGORY_ORDER]


@app.get("/api/robots/{robot_id}")
def get_robot(robot_id: str):
    """Карточка одного робота по id."""
    robot = {item["id"]: item for item in _runtime_snapshot().runtime_robots()}.get(
        robot_id
    )
    if not robot:
        raise HTTPException(404, f"Робот '{robot_id}' не найден")
    return robot


@app.post("/api/readiness", response_model=ReadinessReport)
def process_readiness(request: ReadinessRequest) -> ReadinessReport:
    """Evaluate process readiness before capacity and economics.

    The catalog is resolved from the same immutable activated runtime snapshot
    as calculation; this endpoint does not activate discovery records.
    """

    snapshot = _runtime_snapshot()
    return evaluate_readiness(
        request.input,
        snapshot.runtime_robots(),
        provenance=request.provenance,
        parameter_values=request.parameter_values,
        parameter_provenance=request.parameter_provenance,
        catalog_version=snapshot.version.code,
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _public_type_code(value: str) -> str | None:
    """Hide internal sentinels used for a required storage column."""

    return None if value in {"None", "UNSPECIFIED"} else value


def _discovery_position(
    position: CatalogPositionDTO, catalog_code: str
) -> dict[str, Any]:
    model = position.model
    purchase = position.procurement_option
    applicability = position.applicability
    media = position.media
    enrichment = position.enrichment
    capacity = model.capacity_runtime
    description = (
        enrichment.description_normalized
        if enrichment is not None and enrichment.description_status == "ENRICHED"
        else model.description
    )
    return {
        "id": position.id,
        "position_id": position.id,
        "model_id": model.id,
        "source_record_key": position.source_record_key,
        "source_row_number": position.source_row_number,
        "organizer_id": model.organizer_id,
        "manufacturer": model.manufacturer,
        "name": model.name,
        "system_family": model.system_family,
        "type_code": _public_type_code(model.type_code),
        "subtype_code": model.subtype_code,
        "maturity_status": model.maturity_status,
        "trl": model.trl,
        "description": description,
        "industries": [applicability.industry] if applicability.industry else [],
        "use_cases": [applicability.scenario] if applicability.scenario else [],
        "regions": [applicability.region] if applicability.region else [],
        "facts": [
            {
                "code": fact.code,
                "value": _json_value(fact.value),
                "unit": fact.canonical_unit,
                "status": fact.resolution_status,
                "evidence_id": fact.evidence_id,
            }
            for fact in model.facts
        ],
        "applicability": [
            {
                "id": applicability.id,
                "industry": applicability.industry,
                "scenario": applicability.scenario,
                "region": applicability.region,
                "case": applicability.case_text,
            }
        ],
        "purchase": (
            {
                "id": purchase.id,
                "raw_price": purchase.raw_price,
                "amount": float(purchase.amount),
                "currency": purchase.currency,
                "price_status": purchase.price_status,
                "vat_status": purchase.vat_status,
                "evidence_id": purchase.evidence_id,
            }
            if purchase.amount is not None
            else None
        ),
        "media": (
            {
                "id": media.id,
                "url": f"/api/catalog/media/{catalog_code}/{media.sha256}",
                "sha256": media.sha256,
                "media_type": media.media_type,
                "width_px": media.width_px,
                "height_px": media.height_px,
                "source_page": media.source_page,
                "source_slot": media.source_slot,
            }
            if media is not None
            else None
        ),
        "enrichment": (
            {
                "description_status": enrichment.description_status,
                "mapping_status": enrichment.mapping_status,
                "transcript_description": enrichment.description_normalized,
                "existing_description": enrichment.existing_description,
                "fields": _json_value(enrichment.fields),
                "provenance": {
                    "adapter": enrichment.adapter,
                    "transcript_sha256": enrichment.transcript_sha256,
                    "source_page": enrichment.source_page,
                    "source_slot": enrichment.source_slot,
                    "media_sha256": enrichment.media_sha256,
                    "limitation": enrichment.limitation,
                },
            }
            if enrichment is not None
            else None
        ),
        "selectable": position.runtime_robot is not None,
        "runtime_blockers": list(position.runtime_blockers),
        "calculation_readiness_status": capacity.calculation_readiness_status,
        "calculation_ready": capacity.calculation_ready,
        "calculation_requires_assumptions": capacity.calculation_requires_assumptions,
        "calculation_profile": capacity.calculation_profile,
        "calculation_blockers": list(capacity.calculation_blockers),
        "runtime_catalog_version": capacity.runtime_catalog_version,
        "calculation_vendor_facts": [
            {
                "field": next(
                    (
                        field
                        for field in capacity.calculation_model_fields
                        if field.split(".", 1)[-1] == fact.code
                    ),
                    fact.code,
                ),
                "code": fact.code,
                "value": _json_value(fact.value),
                "unit": fact.canonical_unit,
                "status": fact.resolution_status,
                "evidence_id": fact.evidence_id,
            }
            for fact in capacity.vendor_facts
        ],
        "calculation_assumptions": [
            _json_value(item) for item in capacity.scenario_assumptions
        ],
        "calculation_provenance": _json_value(capacity.provenance),
        "deployment_readiness_status": capacity.deployment_readiness_status,
    }


@app.get("/api/catalog/status")
def catalog_status():
    try:
        discovery = _CATALOG_RUNTIME.load_discovery()
    except CatalogRuntimeConfigurationError:
        logger.warning("Discovery catalog status is unavailable")
        raise HTTPException(503, "discovery catalog unavailable") from None
    try:
        runtime = _CATALOG_RUNTIME.load_runtime()
        runtime_status = {
            "source": "activated",
            "catalog_code": runtime.version.code,
            "catalog_status": runtime.version.status,
            "selectable_count": len(runtime.runtime_robots()),
        }
    except CatalogRuntimeConfigurationError:
        runtime_status = {
            "source": "unavailable",
            "catalog_code": None,
            "catalog_status": None,
            "selectable_count": 0,
        }
    return {
        "runtime": runtime_status,
        "discovery": {
            "source": "activated",
            "catalog_code": discovery.version.code,
            "catalog_status": discovery.version.status,
            "model_count": len(discovery.models),
            "position_count": len(discovery.positions),
            "selectable_count": len(discovery.runtime_robots()),
            "calculation_ready_model_count": len(
                discovery.calculation_ready_models()
            ),
            "calculation_ready_position_count": len(
                discovery.calculation_ready_positions()
            ),
        },
    }


@app.get("/api/catalog/models")
def discover_catalog_models(
    q: str | None = Query(None, max_length=200),
    system_family: str | None = Query(None, max_length=100),
    type_code: str | None = Query(None, max_length=200),
    manufacturer: str | None = Query(None, max_length=200),
    selectable: bool | None = None,
    calculation_participation: str = Query(
        "all", pattern="^(all|participating|requires_data)$"
    ),
    sort: str = Query("name", pattern="^(name|manufacturer|type)$"),
):
    """Search/filter the activated discovery catalog without making it selectable."""

    snapshot = _discovery_snapshot()
    positions = list(snapshot.positions)
    if q and q.strip():
        needle = q.casefold().strip()

        def matches(position: CatalogPositionDTO) -> bool:
            model = position.model
            applicability = position.applicability
            enrichment = position.enrichment
            values = (
                model.name,
                model.manufacturer or "",
                model.type_code,
                model.subtype_code or "",
                (
                    enrichment.description_normalized
                    if enrichment is not None
                    and enrichment.description_status == "ENRICHED"
                    else model.description or ""
                ),
                applicability.industry or "",
                applicability.scenario or "",
                applicability.region or "",
                applicability.case_text or "",
            )
            return any(needle in value.casefold() for value in values)

        positions = [position for position in positions if matches(position)]
    if system_family:
        positions = [
            position
            for position in positions
            if position.model.system_family == system_family
        ]
    if type_code:
        positions = [
            position for position in positions if position.model.type_code == type_code
        ]
    if manufacturer:
        positions = [
            position
            for position in positions
            if position.model.manufacturer == manufacturer
        ]
    if selectable is not None:
        positions = [
            position
            for position in positions
            if (position.runtime_robot is not None) == selectable
        ]
    if calculation_participation == "participating":
        positions = [
            position
            for position in positions
            if position.model.capacity_runtime.calculation_ready
        ]
    elif calculation_participation == "requires_data":
        positions = [
            position
            for position in positions
            if not position.model.capacity_runtime.calculation_ready
        ]
    sort_keys = {
        "name": lambda position: (
            position.model.name.casefold(),
            position.source_row_number,
        ),
        "manufacturer": lambda position: (
            (position.model.manufacturer or "").casefold(),
            position.model.name.casefold(),
            position.source_row_number,
        ),
        "type": lambda position: (
            position.model.type_code.casefold(),
            position.model.name.casefold(),
            position.source_row_number,
        ),
    }
    positions.sort(key=sort_keys[sort])
    all_positions = snapshot.positions
    return {
        "catalog": {
            "id": snapshot.version.id,
            "code": snapshot.version.code,
            "status": snapshot.version.status,
            "source": "activated",
        },
        "total": len(positions),
        "model_count": len(snapshot.models),
        "position_count": len(all_positions),
        "selectable_count": sum(
            position.runtime_robot is not None for position in all_positions
        ),
        "calculation_ready_model_count": len(snapshot.calculation_ready_models()),
        "calculation_ready_position_count": len(
            snapshot.calculation_ready_positions()
        ),
        "calculation_readiness_counts": {
            status: {
                "models": sum(
                    model.capacity_runtime.calculation_readiness_status == status
                    for model in snapshot.models
                ),
                "positions": sum(
                    position.model.capacity_runtime.calculation_readiness_status
                    == status
                    for position in all_positions
                ),
            }
            for status in (
                "CALCULATION_READY",
                "CALCULATION_READY_WITH_ASSUMPTIONS",
                "CALCULATION_BLOCKED",
                "UNSUPPORTED_CAPACITY_PROFILE",
                "NOT_EQUIPMENT",
            )
        },
        "hierarchy": [
            {
                "system_family": family,
                "types": [
                    {
                        "type_code": item_type,
                        "count": sum(
                            position.model.system_family == family
                            and position.model.type_code == item_type
                            for position in all_positions
                        ),
                    }
                    for item_type in sorted(
                        {
                            _public_type_code(position.model.type_code)
                            for position in all_positions
                            if position.model.system_family == family
                            and _public_type_code(position.model.type_code) is not None
                        }
                    )
                ],
            }
            for family in sorted(
                {position.model.system_family for position in all_positions}
            )
        ],
        "manufacturers": sorted(
            {
                position.model.manufacturer
                for position in all_positions
                if position.model.manufacturer
            }
        ),
        "items": [
            _discovery_position(position, snapshot.version.code)
            for position in positions
        ],
    }


@app.get("/api/catalog/positions/{position_id}")
def get_catalog_position(position_id: str):
    """Return one position with gated description enrichment and provenance."""

    snapshot = _discovery_snapshot()
    position = next((item for item in snapshot.positions if item.id == position_id), None)
    if position is None:
        raise HTTPException(404, "catalog position not found")
    return _discovery_position(position, snapshot.version.code)


@app.get("/api/catalog/media/{catalog_code}/{sha256}")
def catalog_media(catalog_code: str, sha256: str):
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise HTTPException(404, "catalog media not found")
    with get_database().session() as session:
        asset = session.scalar(
            select(CatalogMediaAsset)
            .join(
                CatalogVersion,
                CatalogVersion.id == CatalogMediaAsset.catalog_version_id,
            )
            .where(
                CatalogVersion.code == catalog_code,
                CatalogVersion.status == "PUBLISHED",
                CatalogMediaAsset.sha256 == sha256,
            )
        )
        if asset is None:
            raise HTTPException(404, "catalog media not found")
        try:
            path = resolve_media_path(
                Path(os.getenv("CATALOG_MEDIA_ROOT", "data/catalog-media")),
                asset.storage_key,
                asset.byte_size,
            )
        except CatalogMediaError:
            raise HTTPException(404, "catalog media not found") from None
        return FileResponse(
            path,
            media_type=asset.media_type,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "ETag": f'"{asset.sha256}"',
            },
        )


# ═══════════════════════════════════════════════════════════════
# Пресеты и источники
# ═══════════════════════════════════════════════════════════════
@app.get("/api/presets/{object_type}")
def get_preset(object_type: str):
    try:
        return build_official_preset(object_type)["normalized_input"]
    except ObjectProfileError:
        raise HTTPException(404, "Пресет не найден") from None


@app.get("/api/object-profiles")
def list_object_profiles():
    try:
        profiles = load_official_profiles()
        return {
            "schema_version": profiles.schema_version,
            "source_version": profiles.source_version,
            "items": [
                {
                    "code": profile.code,
                    "name": profile.name_ru,
                    "parameter_count": len(profile.parameters()),
                }
                for profile in profiles.object_types
            ],
        }
    except ObjectProfileError:
        raise HTTPException(503, "official object profiles unavailable") from None


@app.get("/api/object-profiles/{object_type}/preset")
def get_structured_preset(object_type: str):
    try:
        return build_official_preset(object_type)
    except ObjectProfileError:
        raise HTTPException(404, "Пресет не найден") from None


@app.get("/api/object-profiles/{object_type}")
def get_object_profile(object_type: str):
    try:
        return profile_api_dict(get_official_profile(object_type))
    except ObjectProfileError:
        raise HTTPException(404, "Профиль не найден") from None


@app.get("/api/sources")
def sources():
    robots = _runtime_snapshot().runtime_robots()
    prices = [
        {
            "group": "Цены решений",
            "parameter": r["name"],
            "value": r.get("price", {}).get("note", ""),
            "type": r.get("price", {}).get("basis", ""),
        }
        for r in robots
    ]
    return {"usd_rub_rate": 90.0, "sources": SOURCES + prices}


# ═══════════════════════════════════════════════════════════════
# Интервью
# ═══════════════════════════════════════════════════════════════
@app.post("/api/audit")
def audit(req: AuditRequest):
    return conduct_interview(req.message, req.history, req.collected, req.meta)


# ═══════════════════════════════════════════════════════════════
# Расчёт — whole + zonal
# ═══════════════════════════════════════════════════════════════
@app.post("/api/calculate")
def calculate(inp: UserInput) -> CalculationResponse:
    return calculate_with_catalog(inp, _runtime_snapshot())


def calculate_with_catalog(
    inp: UserInput, catalog: CatalogSnapshotDTO
) -> CalculationResponse:
    robots = catalog.runtime_robots()
    robot_by_id = {robot["id"]: robot for robot in robots}
    err = validate_mandatory(inp)
    if err:
        raise HTTPException(400, err)

    assumptions = dict(ASSUMPTIONS)
    assumptions["horizon_years"] = inp.horizon_years or DEFAULT_HORIZON_YEARS

    # ─── Zonal-режим ───
    if inp.mode == "zonal":
        try:
            zone_results = [calc_zone(inp, z, robots) for z in inp.zones]
            combined = calc_combined(zone_results, inp, robots)
        except Exception as e:
            logger.exception("Zonal calculation failed")
            raise HTTPException(500, f"Ошибка расчёта по зонам: {e}")

        revision_id, scenario_spec, response_warnings = build_scenario_spec(
            inp,
            [],
            zone_results,
            combined,
            robot_by_id,
        )
        return CalculationResponse(
            revision_id=revision_id,
            mode="zonal",
            zones=zone_results,
            combined=combined,
            data_quality=assess_data_quality(inp),
            assumptions=assumptions,
            warnings=response_warnings,
            scenario_spec=scenario_spec,
        )

    # ─── Whole-режим ───
    recommendations, rejected = [], []
    for robot in robots:
        reason = check_constraints(inp, robot)
        selected = robot["id"] in (inp.selected_robot_ids or [])
        if reason and not selected:
            rejected.append(
                RejectedRobot(
                    robot_id=robot["id"], robot_name=robot["name"], reason=reason
                )
            )
            continue
        rec = calc_recommendation(inp, robot, is_zone=False)
        if selected:
            rec.forced = True
            if reason:
                rec.technical_status = "FORCED_UNSUPPORTED"
                rec.warnings.insert(
                    0, f"⚠ Выбор клиента — не проходит фильтр: {reason}"
                )
        recommendations.append(rec)

    if not recommendations:
        raise HTTPException(
            400, "Ни одно решение не проходит: " + "; ".join(r.reason for r in rejected)
        )

    # Экономически неприемлемый вариант остаётся доступен для сравнения, но не
    # получает семантику "лучшего" и не становится основой сцены.
    recommendations.sort(key=recommendation_sort_key)
    best = next(
        (
            rec
            for rec in recommendations
            if rec.technical_status == "ELIGIBLE"
            and rec.economic_status != "NOT_ACCEPTABLE"
        ),
        None,
    )
    if best:
        best.is_best = True
    response_warnings = []
    if best is None:
        response_warnings.append(
            "Допустимое оборудование найдено, но экономика всех вариантов неприемлема; "
            "лучшая рекомендация не назначена"
        )

    # Симуляция только для процессов, где она осмысленна
    sim = None
    if best and inp.process_type == "palletizing":
        from models import SimulationData, SimulationUnit

        sim = SimulationData(
            width_m=22.0,
            height_m=14.0,
            robots_count=best.quantity,
            corridors_x=[8.0, 12.0, 16.0],
            main_aisle_y=2.0,
            units=[
                SimulationUnit(id=0, speed=0.5, route=[[2, 2], [9, 2], [16, 2], [9, 2]])
            ],
        )
    elif best and inp.process_type == "transport":
        sim_inp = inp.model_copy(update={"area_m2": inp.area_m2 or DEFAULT_AREA_M2})
        sim = generate_simulation(sim_inp, robot_by_id[best.robot_id], best.quantity)

    revision_id, scenario_spec, contract_warnings = build_scenario_spec(
        inp,
        recommendations,
        [],
        None,
        robot_by_id,
    )
    return CalculationResponse(
        revision_id=revision_id,
        mode="whole",
        recommendations=recommendations,
        rejected=rejected,
        simulation=sim,
        manual_baseline=manual_baseline(inp),
        data_quality=assess_data_quality(inp),
        assumptions=assumptions,
        warnings=response_warnings + contract_warnings,
        scenario_spec=scenario_spec,
    )


# Persistence resolves the snapshot before creating the run and reuses that
# exact immutable value for calculation and version references.
from persistence_api import create_persistence_router  # noqa: E402

app.include_router(
    create_persistence_router(
        calculate,
        resolve_catalog=_runtime_snapshot,
        calculate_for_catalog=calculate_with_catalog,
        readiness_for_catalog=lambda inp, catalog, **context: evaluate_readiness(
            inp,
            catalog.runtime_robots(),
            catalog_version=catalog.version.code,
            **context,
        ),
        resolve_object_profile_version=official_profile_version,
        resolve_capacity_catalog=_discovery_snapshot,
        analyze_capacity_for_catalog=analyze_capacity,
    )
)
app.include_router(create_simulation_router())
