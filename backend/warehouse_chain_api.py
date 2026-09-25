"""Versioned warehouse operation map. This module never calls a calculation formula."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from auth import AuthContext, require_auth_context, require_csrf
from calculation_contracts import semantic_digest
from catalog_repository import CatalogSnapshotDTO
from database import database_session
from fastapi import APIRouter, Depends, HTTPException
from persistence_models import Project
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

SCHEMA = "warehouse-chain-v1"
KEY = "warehouse_chain_v1"
MAX_VERSIONS = 100
AUTH = Depends(require_auth_context)
CSRF = Depends(require_csrf)
DB = Depends(database_session)

OPERATIONS = {
    "receiving_putaway": ("pallet/day", "forklift_driver", "Приёмка и размещение готовых паллет"),
    "picking_lines": ("line/day", "picker", "Отбор строк заказа"),
    "picking_items": ("item/day", "picker", "Отбор штук"),
    "tote_handoff": ("tote/day", "sorter", "Передача тары"),
    "packaging": ("box/day", "packaging_line_operator", "Упаковка на линии"),
    "palletizing": ("pallet/day", "packer", "Паллетизация"),
    "shipping": ("pallet/day", "forklift_driver", "Отгрузка готовых паллет"),
}
PICKING_PHYSICS = {"picks_per_hour", "max_item_mass_kg", "max_width_mm", "max_height_mm",
                   "gripper", "reach_mm", "cycle_seconds", "availability", "rack_compatibility", "tote_feed"}


class WarehouseFlow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    value: str | None = Field(default=None, max_length=16)
    unit: str
    shifts_per_day: str | None = Field(default=None, max_length=8)
    hours_per_shift: str | None = Field(default=None, max_length=8)
    days_per_year: str | None = Field(default=None, max_length=8)
    source: Literal["UNKNOWN", "USER", "FILE", "EXPERT_ASSUMPTION"] = "UNKNOWN"
    source_ref: str | None = Field(default=None, max_length=200)
    confirmed: bool = False
    zone: str = Field(default="Основная зона", max_length=100)
    role_code: str
    resource_ids: list[str] = Field(default_factory=list, max_length=20)
    solution: Literal["MANUAL", "UNASSESSED", "CATALOG"] = "MANUAL"
    position_id: str | None = Field(default=None, max_length=100)
    physical_profile: dict[str, str] = Field(default_factory=dict)
    physical_profile_source: Literal["UNKNOWN", "USER", "FILE", "VENDOR"] = "UNKNOWN"
    physical_profile_ref: str | None = Field(default=None, max_length=200)
    physical_profile_confirmed: bool = False


class SharedResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_id: str = Field(min_length=1, max_length=80)
    kind: Literal["STAFF", "EQUIPMENT", "CONVEYOR", "AREA", "EXPENSE"]
    role_code: str | None = Field(default=None, max_length=80)
    amount: str | None = Field(default=None, max_length=16)
    unit: str | None = Field(default=None, max_length=40)
    monthly_gross_salary_rub: str | None = Field(default=None, max_length=16)
    source: Literal["UNKNOWN", "USER", "FILE", "EXPERT_ASSUMPTION"] = "UNKNOWN"
    source_ref: str | None = Field(default=None, max_length=200)
    confirmed: bool = False


class FlowConversion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_code: str
    to_code: str
    factor: str = Field(max_length=16)
    source: Literal["USER", "FILE", "EXPERT_ASSUMPTION"]
    source_ref: str | None = Field(default=None, max_length=200)
    confirmed: bool = False


class SaveChain(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    flows: list[WarehouseFlow] = Field(min_length=7, max_length=7)
    resources: list[SharedResource] = Field(default_factory=list, max_length=80)
    conversions: list[FlowConversion] = Field(default_factory=list, max_length=25)


class WarehouseChainSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["warehouse-chain-v1"]
    project_id: uuid.UUID
    version: int = Field(ge=0)
    parent_version: int | None = Field(default=None, ge=0)
    created_at: datetime | None = None
    flows: list[WarehouseFlow] = Field(min_length=7, max_length=7)
    resources: list[SharedResource] = Field(max_length=80)
    conversions: list[FlowConversion] = Field(max_length=25)


def _positive(value: str | None, label: str, *, allow_zero: bool = False) -> None:
    if value is None:
        return
    if not re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d+)?", value):
        raise HTTPException(422, f"{label}: invalid decimal")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise HTTPException(422, f"{label}: invalid decimal") from exc
    if number < 0 or (not allow_zero and number == 0):
        raise HTTPException(422, f"{label}: expected positive value")


def validate_chain(payload: SaveChain) -> None:
    by_code = {item.code: item for item in payload.flows}
    if set(by_code) != set(OPERATIONS):
        raise HTTPException(422, "warehouse operations must be unique and complete")
    resource_ids = [item.resource_id for item in payload.resources]
    if len(set(resource_ids)) != len(resource_ids):
        raise HTTPException(422, "shared resources must have unique ids")
    for flow in payload.flows:
        expected_unit, expected_role, _ = OPERATIONS[flow.code]
        if flow.unit != expected_unit or flow.role_code != expected_role:
            raise HTTPException(422, f"{flow.code}: flow unit or role is incompatible")
        if not flow.zone.strip() or (flow.value is not None and flow.source == "UNKNOWN"):
            raise HTTPException(422, f"{flow.code}: value needs a zone and source")
        if flow.confirmed and flow.value is None:
            raise HTTPException(422, f"{flow.code}: cannot confirm unknown flow")
        if flow.confirmed and flow.source in {"FILE", "EXPERT_ASSUMPTION"} and not flow.source_ref:
            raise HTTPException(422, f"{flow.code}: source reference required")
        _positive(flow.value, f"{flow.code}.value")
        for key in ("shifts_per_day", "hours_per_shift", "days_per_year"):
            _positive(getattr(flow, key), f"{flow.code}.{key}")
        if flow.solution == "CATALOG" and not flow.position_id:
            raise HTTPException(422, f"{flow.code}: catalog position required")
        if flow.solution != "CATALOG" and flow.position_id:
            raise HTTPException(422, f"{flow.code}: position requires catalog solution")
        if any(ref not in resource_ids for ref in flow.resource_ids) or len(set(flow.resource_ids)) != len(flow.resource_ids):
            raise HTTPException(422, f"{flow.code}: unknown or duplicate shared resource")
        if flow.physical_profile and flow.code not in {"picking_lines", "picking_items"}:
            raise HTTPException(422, "picking physical profile belongs to picking only")
        if set(flow.physical_profile) - PICKING_PHYSICS:
            raise HTTPException(422, "unknown picking physical field")
        if any(not value.strip() or len(value) > 100 for value in flow.physical_profile.values()):
            raise HTTPException(422, "invalid picking physical field")
        for key in ("picks_per_hour", "max_item_mass_kg", "max_width_mm", "max_height_mm", "reach_mm", "cycle_seconds", "availability"):
            if key in flow.physical_profile:
                _positive(flow.physical_profile[key], f"{flow.code}.{key}")
        if "availability" in flow.physical_profile and Decimal(flow.physical_profile["availability"]) > 1:
            raise HTTPException(422, "picking availability must be a fraction from 0 to 1")
        if flow.physical_profile_confirmed and (set(flow.physical_profile) != PICKING_PHYSICS or flow.physical_profile_source == "UNKNOWN"):
            raise HTTPException(422, "complete sourced picking physical profile required")
        if flow.physical_profile_confirmed and flow.physical_profile_source in {"FILE", "VENDOR"} and not flow.physical_profile_ref:
            raise HTTPException(422, "picking physical source reference required")
    for item in payload.resources:
        _positive(item.amount, f"{item.resource_id}.amount", allow_zero=True)
        _positive(item.monthly_gross_salary_rub, f"{item.resource_id}.salary", allow_zero=True)
        if item.kind == "STAFF" and not item.role_code:
            raise HTTPException(422, f"{item.resource_id}: role required")
        if item.confirmed and (item.amount is None or item.source == "UNKNOWN"):
            raise HTTPException(422, f"{item.resource_id}: cannot confirm unknown resource")
        if item.confirmed and item.source in {"FILE", "EXPERT_ASSUMPTION"} and not item.source_ref:
            raise HTTPException(422, f"{item.resource_id}: source reference required")
    conversion_pairs: set[tuple[str, str]] = set()
    for link in payload.conversions:
        if link.from_code not in OPERATIONS or link.to_code not in OPERATIONS or link.from_code == link.to_code:
            raise HTTPException(422, "conversion must link distinct warehouse operations")
        pair = (link.from_code, link.to_code)
        if pair in conversion_pairs:
            raise HTTPException(422, "duplicate warehouse unit conversion")
        conversion_pairs.add(pair)
        _positive(link.factor, "conversion.factor")
        if link.confirmed and not link.source_ref:
            raise HTTPException(422, "confirmed conversion needs a source reference")


def default_chain(project_id: uuid.UUID) -> dict[str, Any]:
    resources = []
    for role in dict.fromkeys(item[1] for item in OPERATIONS.values()):
        resources.append(SharedResource(resource_id=f"staff.{role}", kind="STAFF", role_code=role).model_dump())
    flows = [WarehouseFlow(code=code, unit=unit, role_code=role, resource_ids=[f"staff.{role}"]).model_dump()
             for code, (unit, role, _) in OPERATIONS.items()]
    return {"schema_version": SCHEMA, "project_id": str(project_id), "version": 0, "parent_version": None,
            "created_at": None, "flows": flows, "resources": resources, "conversions": []}


def confirmed_conversion(chain: dict[str, Any], from_code: str, to_code: str) -> Decimal | None:
    """No conversion exists by default, including between lines and pallets."""
    for item in chain["conversions"]:
        if item["from_code"] == from_code and item["to_code"] == to_code and item["confirmed"]:
            return Decimal(item["factor"])
    return None


def resource_ledger(chain: dict[str, Any]) -> dict[str, Any]:
    """Count project resources once; unknown salaries never become savings."""
    rows = []
    total_fot = Decimal(0)
    complete = True
    for resource in chain["resources"]:
        linked = [flow["code"] for flow in chain["flows"] if resource["resource_id"] in flow["resource_ids"]]
        annual_fot = None
        if resource["kind"] == "STAFF":
            if resource["confirmed"] and resource["amount"] is not None and resource["monthly_gross_salary_rub"] is not None:
                annual_fot = Decimal(resource["amount"]) * Decimal(resource["monthly_gross_salary_rub"]) * 12
                total_fot += annual_fot
            elif linked:
                complete = False
        rows.append({"resource_id": resource["resource_id"], "kind": resource["kind"],
                     "role_code": resource["role_code"], "linked_operations": linked,
                     "amount": resource["amount"] if resource["confirmed"] else None,
                     "unit": resource["unit"],
                     "annual_gross_fot_rub": str(annual_fot) if annual_fot is not None else None,
                     "status": "KNOWN" if annual_fot is not None else "UNKNOWN" if resource["kind"] == "STAFF" else
                     "KNOWN" if resource["confirmed"] else "UNKNOWN"})
    return {"rows": rows, "total_annual_gross_fot_rub": str(total_fot) if complete else None,
            "total_status": "KNOWN" if complete else "UNKNOWN",
            "notice": "Это текущий ФОТ по уникальным ролям, не экономия от роботизации."}


def _candidate(code: str, position: Any) -> bool:
    model = position.model
    text = " ".join((model.name, model.type_code, model.description or "",
                     *(item.scenario or "" for item in model.applicability))).casefold()
    if code in {"receiving_putaway", "shipping"}:
        return model.capacity_runtime.calculation_profile == "TRANSPORT_CYCLE_V1"
    if code in {"picking_lines", "picking_items"}:
        return bool(re.search(r"pick|отбор|комплект|as.?rs|g2p|voice|light|роборук|манипулятор", text))
    if code == "palletizing":
        return model.capacity_runtime.calculation_profile in {"PALLETIZING_THROUGHPUT_V1", "PALLETIZING_CELL_V1"} or bool(re.search(r"паллетиз|palletiz", text))
    if code == "tote_handoff":
        return bool(re.search(r"конвейер|conveyor|тара|tote", text))
    if code == "packaging":
        return bool(re.search(r"упаков|packag", text))
    return False


def _picking_kind(position: Any) -> str:
    model = position.model
    text = " ".join((model.name, model.type_code, model.description or "",
                     *(item.scenario or "" for item in model.applicability))).casefold()
    if re.search(r"as.?rs|g2p|goods.?to.?person|товар.к.человек|шаттл|shuttle", text):
        return "ASRS_G2P"
    if re.search(r"pick.by.voice|pick.by.light|voice|light|голосов|светов", text):
        return "PICK_ASSIST"
    if re.search(r"роборук|манипулятор|robotic.arm|robot.arm|robotic.picking", text):
        return "ROBOT_ARM"
    return "OTHER_PICKING"


def capability_matrix(snapshot: CatalogSnapshotDTO | None, chain: dict[str, Any]) -> dict[str, Any]:
    positions = snapshot.positions if snapshot else ()
    rows = []
    for flow in chain["flows"]:
        code = flow["code"]
        matched = list({item.id: item for item in positions if _candidate(code, item)}.values())
        ready = [item for item in matched if item.model.capacity_runtime.calculation_ready
                 and item.model.maturity_status != "RND"]
        supported_formula = code in {"receiving_putaway", "shipping", "palletizing"}
        if snapshot is None:
            status = "CATALOG_UNAVAILABLE"
        elif ready and supported_formula:
            status = "CALCULABLE"
        elif matched and all(item.model.maturity_status == "RND" for item in matched):
            status = "RESEARCH"
        elif matched:
            status = "COMPARE_ONLY"
        else:
            status = "INSUFFICIENT_DATA"
        reason = ("Активный каталог недоступен; возможность участка нельзя определить."
                  if status == "CATALOG_UNAVAILABLE" else
                  "Есть активная расчётная позиция; парк определяется отдельным расчётом с проверкой входов и пригодности."
                  if status == "CALCULABLE" else
                  "Исследовательская разработка: нет подтверждённого расчёта парка."
                  if status == "RESEARCH" else
                  "Можно сравнить характеристики; формула и физическая пригодность не подтверждены."
                  if status == "COMPARE_ONLY" else
                  "Нет подходящей позиции активного каталога и подтверждённой формулы для этой операции.")
        if code in {"picking_lines", "picking_items"}:
            reason += " AS-RS/G2P и Pick by Voice/Light не считаются автономным захватом; для роборуки нужен отдельный подтверждённый физический профиль."
        rows.append({"code": code, "label": OPERATIONS[code][2], "unit": flow["unit"], "role_code": flow["role_code"],
                     "status": status, "reason": reason, "candidate_count": len(matched),
                     "calculation_ready_count": len(ready) if supported_formula else 0,
                     "solution_families": ({kind: sum(_picking_kind(item) == kind for item in matched)
                                            for kind in ("ROBOT_ARM", "ASRS_G2P", "PICK_ASSIST", "OTHER_PICKING")}
                                           if code in {"picking_lines", "picking_items"} else {}),
                     "candidates": [{"position_id": item.id, "name": item.model.name,
                                     "maturity_status": item.model.maturity_status,
                                     "calculation_ready": item.model.capacity_runtime.calculation_ready,
                                     "calculation_profile": item.model.capacity_runtime.calculation_profile}
                                    for item in matched],
                     "flow_confirmed": flow["confirmed"]})
    return {"catalog_version": snapshot.version.code if snapshot else None, "rows": rows}


def create_warehouse_chain_router(discovery_loader: Callable[[], CatalogSnapshotDTO]) -> APIRouter:
    router = APIRouter(prefix="/api/warehouse-chain")

    def owned(db: Session, project_id: uuid.UUID, context: AuthContext, lock: bool = False) -> Project:
        query = select(Project).where(Project.id == project_id, Project.owner_id == context.user.id, Project.status == "ACTIVE")
        project = db.scalar(query.with_for_update() if lock else query)
        if project is None:
            raise HTTPException(404, "project not found")
        return project

    def result(project: Project) -> dict[str, Any]:
        state = (project.profile or {}).get(KEY) or {"version": 0, "versions": []}
        chain = deepcopy(state["versions"][-1]) if state["versions"] else default_chain(project.id)
        try:
            catalog = discovery_loader()
        except HTTPException:
            catalog = None
        return {"chain": chain, "chain_digest": semantic_digest(chain),
                "versions": [item["version"] for item in state["versions"]],
                "capabilities": capability_matrix(catalog, chain), "resources": resource_ledger(chain)}

    @router.get("/projects/{project_id}")
    def read(project_id: uuid.UUID, context: AuthContext = AUTH, db: Session = DB):
        return result(owned(db, project_id, context))

    @router.post("/projects/{project_id}/versions")
    def save(project_id: uuid.UUID, payload: SaveChain, context: AuthContext = CSRF, db: Session = DB):
        project = owned(db, project_id, context, lock=True)
        state = deepcopy((project.profile or {}).get(KEY)) or {"version": 0, "versions": []}
        if state["version"] != payload.expected_version:
            raise HTTPException(409, "warehouse chain version changed; reload before saving")
        if len(state["versions"]) >= MAX_VERSIONS:
            raise HTTPException(429, "warehouse chain version limit reached")
        validate_chain(payload)
        selected = [flow for flow in payload.flows if flow.solution == "CATALOG"]
        if selected:
            catalog = discovery_loader()
            positions = {item.id: item for item in catalog.positions}
            for flow in selected:
                position = positions.get(flow.position_id)
                if position is None or not _candidate(flow.code, position):
                    raise HTTPException(422, f"{flow.code}: position is not suitable for this operation in the active catalog")
        chain = WarehouseChainSnapshot(
            schema_version=SCHEMA, project_id=project_id,
            version=state["version"] + 1, parent_version=state["version"] or None,
            created_at=datetime.now(timezone.utc), flows=payload.flows,
            resources=payload.resources, conversions=payload.conversions,
        ).model_dump(mode="json")
        state["version"] = chain["version"]
        state["versions"].append(chain)
        project.profile = {**(project.profile or {}), KEY: state}
        db.commit()
        return result(project)

    return router
