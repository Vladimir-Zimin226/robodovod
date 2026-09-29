from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from calculation.registry import (  # noqa: E402
    CalculationParameterRegistryV1,
    RegistryManifestV1,
    registry_semantic_digest,
)

DATA_DIR = ROOT / "data" / "calculation"
REGISTRY_PATH = DATA_DIR / "registry-v1.json"
MANIFEST_PATH = DATA_DIR / "registry-v1.manifest.json"
SCHEMA_PATH = ROOT / "contracts" / "calculation-parameter-registry-v1.schema.json"
MANIFEST_SCHEMA_PATH = (
    ROOT / "contracts" / "calculation-parameter-registry-manifest-v1.schema.json"
)

SOURCE_HASHES = {
    "R00": "bbf66a169149e39235a1cd38c4534fc2461c1accdd3ad1d31fddd02717556cb0",
    "R02": "43addb7aad64dba565a8156b34266ee2492e9e3eebe92455f7986421ec318e01",
    "R03": "60f03e1a76e07db4acc6a44357c56adb2cef280e709eddcd58a5c6a5c5ca0621",
    "R04": "3820498b206b6dbe436c7469009a23fab1f8c81828fb37c9296afdadafad2fb9",
    "R06": "ed650b06ccc846cad4873bb02b027a31210d71ff9a291fc336fa3344a3279b96",
    "POLICY_V1": "212754fe55fca4d5890961b89361ff8b3494650ee5ec9dbcfd22055f98bdd584",
}


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def source(source_id: str, locator: str, status: str = "REFERENCE_CANON") -> dict[str, str]:
    return {"source_id": source_id, "locator": locator, "source_status": status}


def build_registry() -> CalculationParameterRegistryV1:
    parameters: list[dict[str, Any]] = []

    def add(
        parameter_id: str,
        semantic_name: str,
        value: str | int | float,
        unit: str,
        quantity_kind: str,
        *,
        scopes: tuple[str, ...] = ("global",),
        scenario: str = "ALL",
        year: int | None = None,
        provenance_kind: str = "ASSUMPTION",
        override_policy: str = "EXPLICIT_USER_OVERRIDE",
        source_refs: tuple[dict[str, str], ...] = (),
        decisions: tuple[str, ...] = ("K01",),
        consumers: tuple[str, ...] = ("C02",),
        minimum: str | None = "0",
        maximum: str | None = None,
        minimum_inclusive: bool = True,
        maximum_inclusive: bool = True,
        allowed_values: list[str] | None = None,
    ) -> None:
        resolved_source_refs = list(source_refs) or [
            source("R02", "§ parameter table")
        ]
        source_binding = [
            {
                "source_id": item["source_id"],
                "source_sha256": SOURCE_HASHES[item["source_id"]],
                "locator": item["locator"],
                "source_status": item["source_status"],
            }
            for item in resolved_source_refs
        ]
        source_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                source_binding,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        parameters.append(
            {
                "parameter_id": parameter_id,
                "semantic_name": semantic_name,
                "value": str(value),
                "unit": unit,
                "quantity_kind": quantity_kind,
                "domain": {
                    "minimum": minimum,
                    "maximum": maximum,
                    "minimum_inclusive": minimum_inclusive,
                    "maximum_inclusive": maximum_inclusive,
                    "allowed_values": allowed_values,
                },
                "applicability": list(scopes),
                "scenario": scenario,
                "year": year,
                "provenance_kind": provenance_kind,
                "override_policy": override_policy,
                "source_refs": resolved_source_refs,
                "source_digest": source_digest,
                "decision_refs": list(decisions),
                "consumers": list(consumers),
                "effective_version": "hackathon-calculation-policy-v1",
                "replaced_by": None,
                "label_key": f"calculation.parameter.{semantic_name}.label",
                "description_key": f"calculation.parameter.{semantic_name}.description",
            }
        )

    # Exact unit definitions: conversions are not empirical assumptions.
    unit_source = (source("R00", "§ Единицы", "UNIT_DEFINITION"),)
    for pid, name, value, unit in (
        ("unit.kg-per-tonne", "kilograms_per_tonne", "1000", "kg/t"),
        ("unit.kmh-per-mps", "kilometres_per_hour_per_metre_per_second", "3.6", "km/h per m/s"),
        ("unit.months-per-year", "months_per_year", "12", "month/year"),
        ("unit.seconds-per-hour", "seconds_per_hour", "3600", "s/h"),
        ("unit.watts-per-kilowatt", "watts_per_kilowatt", "1000", "W/kW"),
    ):
        add(
            pid,
            name,
            value,
            unit,
            "UNIT_DEFINITION",
            provenance_kind="UNIT_DEFINITION",
            override_policy="LOCKED",
            source_refs=unit_source,
            decisions=("K27",),
            consumers=("F01", "F02", "F20"),
        )

    labor_source = (
        source("R02", "§1 Трудовые параметры"),
        source("R06", "§1 Трудовые параметры"),
    )
    labor_values = (
        ("labor.cost.direct-multiplier", "direct_labor_cost_multiplier", "1.302", "1", "F10", "K27"),
        ("labor.cost.full-multiplier", "full_labor_cost_multiplier", "1.55", "1", "F10", "K27"),
        ("labor.cost.fixed-overhead-multiplier", "fixed_overhead_multiplier", "0.248", "1", "F10", "K27"),
        ("labor.staffing.vacation-factor", "vacation_staffing_factor", "1.090", "1", "F09", "K27"),
        ("labor.cleaning.useful-time-share", "cleaning_useful_time_share", "0.85", "1", "F08", "K27"),
        ("labor.forklift-driver-fallback-share", "forklift_driver_fallback_share", "0.30", "1", "F14", "K08"),
        ("labor.forklift.annual-cost", "forklift_annual_cost", "700000", "RUB/equipment/year", "F23", "K08"),
        ("labor.palletizing.cell-efficiency", "palletizing_cell_efficiency", "0.65", "1", "F06", "K27"),
        ("labor.fleet.minimum-area-per-robot", "minimum_area_per_robot", "30", "m2/robot", "F33", "K15"),
        ("labor.severance.months", "severance_months", "2.5", "month", "F24", "K09"),
        ("labor.replacement.default-limit", "replacement_limit", "1.0", "1", "F12", "K06"),
        ("labor.technical.robots-per-fte", "robots_per_technical_fte", "20", "robot/person", "F13", "K06"),
        ("labor.control.minimum-per-shift", "minimum_control_operators_per_shift", "1", "person/shift", "F12", "K06"),
        ("labor.cleaning.mechanized-baseline-rate", "mechanized_cleaning_baseline_rate", "300", "m2/h", "F08", "K27"),
    )
    for pid, name, value, unit, consumer, decision in labor_values:
        add(
            pid,
            name,
            value,
            unit,
                (
                    "MONEY"
                    if "RUB" in unit
                    else "RATE"
                    if "/" in unit
                    else "TIME"
                    if unit == "month"
                    else "FRACTION"
                ),
            source_refs=labor_source,
            decisions=(decision,),
            consumers=(consumer,),
            maximum="1" if unit == "1" and DecimalLike(value) <= 1 else None,
        )

    useful = {6: "0.80", 7: "0.80", 8: "0.80", 9: "0.75", 10: "0.75", 11: "0.72", 12: "0.68"}
    for hours, value in useful.items():
        add(
            f"labor.useful-time.shift-{hours}h",
            "manual_useful_time_share",
            value,
            "1",
            "FRACTION",
            scopes=(f"shift-hours.{hours}",),
            source_refs=labor_source,
            decisions=("K27",),
            consumers=("F08",),
            maximum="1",
        )

    cargo_values = {
        "pallet": ("1.0", "90", "80"),
        "box": ("1.2", "30", "150"),
        "cart": ("0.8", "120", "40"),
        "case": ("1.0", "60", "100"),
        "delivery": ("1.0", "60", "40"),
    }
    for cargo, (speed, exchange, shift_rate) in cargo_values.items():
        common = dict(
            scopes=(f"cargo.{cargo}",),
            source_refs=labor_source,
            decisions=("K27",),
            consumers=("F08",),
        )
        add(f"labor.manual-speed.{cargo}", "manual_loaded_speed", speed, "m/s", "SPEED", **common)
        add(f"labor.manual-exchange.{cargo}", "manual_exchange_total", exchange, "s", "TIME", **common)
        add(f"labor.manual-shift-rate.{cargo}", "manual_fallback_shift_rate", shift_rate, "unit/shift", "RATE", **common)

    for object_kind, loss in {"warehouse": "0.25", "airport": "0.35", "clinic": "0.45"}.items():
        add(
            f"labor.nonproductive-loss.{object_kind}",
            "nonproductive_labor_loss_share",
            loss,
            "1",
            "FRACTION",
            scopes=(f"object.{object_kind}",),
            source_refs=labor_source,
            decisions=("K27",),
            consumers=("F09",),
            maximum="1",
        )

    finance_source = (
        source("R02", "§2 Финансовые параметры"),
        source("R06", "§2 Финансовые параметры"),
        source("POLICY_V1", "§5 Точность, финансы и shared allocation", "ACCEPTED_POLICY"),
    )
    finance = (
        ("finance.electricity-tariff", "electricity_tariff", "8.0", "RUB/kWh", "MONEY", "F20", "K01"),
        ("finance.inflation.labor", "labor_annual_inflation", "0.08", "1/year", "FRACTION", "F23", "K09"),
        ("finance.inflation.electricity", "electricity_annual_inflation", "0.07", "1/year", "FRACTION", "F20", "K09"),
        ("finance.inflation.other-opex", "other_opex_annual_inflation", "0.05", "1/year", "FRACTION", "F19", "K09"),
        ("finance.insurance-share", "annual_insurance_share", "0.01", "1/year", "FRACTION", "F19", "K25"),
        ("finance.raas.monthly-rate", "raas_monthly_robot_price_share", "0.02", "1/month", "FRACTION", "F32", "K21"),
        ("finance.tax.illustrative-rate", "illustrative_profit_tax_rate", "0.25", "1", "FRACTION", "F26", "K12"),
        ("finance.depreciation-years", "depreciation_period", "5", "year", "TIME", "F26", "K11"),
        ("finance.discount.default-rate", "discount_rate", "0.15", "1", "FRACTION", "F28", "K12"),
        ("finance.tax.loss-deduction-cap", "loss_deduction_share_cap", "0.50", "1", "FRACTION", "F26", "K12"),
        ("finance.tax.loss-carry-years", "loss_carry_period", "10", "year", "TIME", "F26", "K12"),
        ("finance.energy.charging-efficiency", "charging_efficiency", "0.85", "1", "FRACTION", "F20", "K01"),
        ("finance.communication.monthly-per-robot", "monthly_communication_per_robot", "500", "RUB/robot/month", "MONEY", "F19", "K25"),
        ("finance.consumables-share", "annual_consumables_share", "0.02", "1/year", "FRACTION", "F19", "K25"),
        ("finance.repair-share", "annual_unplanned_repair_share", "0.01", "1/year", "FRACTION", "F19", "K25"),
    )
    for pid, name, value, unit, kind, consumer, decision in finance:
        add(
            pid,
            name,
            value,
            unit,
            kind,
            source_refs=finance_source,
            decisions=(decision,),
            consumers=(consumer,),
            maximum="1" if unit in {"1", "1/year", "1/month"} else None,
        )

    for asset, life, liquidity in (
        ("amr", "10", "0.6"),
        ("forklift", "10", "0.6"),
        ("shuttle", "10", "0.6"),
        ("fixed-cell", "8", "0.4"),
        ("manipulator", "8", "0.4"),
    ):
        add(
            f"finance.asset-life.{asset}",
            "asset_life",
            life,
            "year",
            "TIME",
            scopes=(f"asset.{asset}",),
            source_refs=finance_source,
            decisions=("K11",),
            consumers=("F22",),
        )
        add(
            f"finance.asset-liquidity.{asset}",
            "asset_liquidity_share",
            liquidity,
            "1",
            "FRACTION",
            scopes=(f"asset.{asset}",),
            source_refs=finance_source,
            decisions=("K11",),
            consumers=("F22",),
            maximum="1",
        )

    scenario_source = (
        source("R02", "§3.2 Сценарий чувствительности"),
        source("R06", "§3 Сценарии"),
        source("POLICY_V1", "K09/K22", "ACCEPTED_POLICY"),
    )
    scenario_values = {
        "PESSIMISTIC": {
            "availability": "0.55", "intraday_peak": "1.25", "peak_reserve": "0.25",
            "capex_multiplier": "1.15", "capex_reserve": "0.15",
            "service_multiplier": "1.20", "supervision_share": "0.35",
            "ramp": ["0.40", "0.70", "0.90", "1.00", "1.00", "1.00"],
        },
        "BASE": {
            "availability": "0.70", "intraday_peak": "1.25", "peak_reserve": "0.20",
            "capex_multiplier": "1.00", "capex_reserve": "0.10",
            "service_multiplier": "1.00", "supervision_share": "0.25",
            "ramp": ["0.50", "0.85", "1.00", "1.00", "1.00", "1.00"],
        },
        "OPTIMISTIC": {
            "availability": "0.80", "intraday_peak": "1.25", "peak_reserve": "0.15",
            "capex_multiplier": "0.95", "capex_reserve": "0.05",
            "service_multiplier": "0.90", "supervision_share": "0.15",
            "ramp": ["0.70", "0.95", "1.00", "1.00", "1.00", "1.00"],
        },
    }
    consumers = {
        "availability": "F04", "intraday_peak": "F04", "peak_reserve": "F04",
        "capex_multiplier": "F16", "capex_reserve": "F17",
        "service_multiplier": "F19", "supervision_share": "F12",
    }
    decisions = {
        "availability": "K22", "intraday_peak": "K22", "peak_reserve": "K22",
        "capex_multiplier": "K09", "capex_reserve": "K25",
        "service_multiplier": "K09", "supervision_share": "K06",
    }
    for scenario, values in scenario_values.items():
        slug = scenario.lower()
        for name, value in values.items():
            if name == "ramp":
                for year, ramp in enumerate(value, start=1):
                    year_scope = year if year <= 5 else None
                    pid_suffix = f"year-{year}" if year <= 5 else "year-6-plus"
                    add(
                        f"scenario.{slug}.ramp.{pid_suffix}",
                        "annual_ramp_share",
                        ramp,
                        "1",
                        "FRACTION",
                        scopes=("scenario.ramp", "year.6-plus" if year == 6 else f"year.{year}"),
                        scenario=scenario,
                        year=year_scope,
                        source_refs=scenario_source,
                        decisions=("K09",),
                        consumers=("F19", "F21", "F23", "F24", "F32"),
                        maximum="1",
                    )
            else:
                add(
                    f"scenario.{slug}.{name.replace('_', '-')}",
                    name,
                    value,
                    "1",
                    "FRACTION",
                    scopes=("scenario.uncertainty",),
                    scenario=scenario,
                    source_refs=scenario_source,
                    decisions=(decisions[name],),
                    consumers=(consumers[name],),
                    maximum="2" if "multiplier" in name or name == "intraday_peak" else "1",
                )

    defaults_source = (source("R02", "§5–6 Значения по умолчанию"),)
    defaults = (
        ("default.days-per-year", "operating_days_per_year", "365", "day/year", "TIME", ("global",), "F01", "K26"),
        ("default.aisle-width", "aisle_width", "2.5", "m", "DISTANCE", ("object.warehouse",), "C03", "K26"),
        ("default.warehouse.ceiling-height", "ceiling_height", "10", "m", "DISTANCE", ("object.warehouse",), "C03", "K26"),
        ("default.floors", "floor_count", "1", "floor", "COUNT", ("global",), "C03", "K26"),
        ("default.cleaning-frequency", "cleaning_frequency", "1", "1/day", "RATE", ("process.cleaning",), "F05", "K26"),
        ("default.receiving.boxes-per-pallet", "boxes_per_pallet", "33", "box/pallet", "RATE", ("process.warehouse-receiving",), "C03", "K26"),
        ("default.palletizing.boxes-per-pallet", "boxes_per_pallet", "20", "box/pallet", "RATE", ("process.warehouse-palletizing",), "F06", "K26"),
        ("default.other.area", "object_area", "6000", "m2", "AREA", ("object.other",), "C03", "K26"),
        ("default.other.available-power", "available_power", "100", "kW", "POWER", ("object.other",), "C03", "K26"),
        ("default.horizon.maximum", "maximum_horizon", "15", "year", "TIME", ("global",), "C03", "K26"),
        ("demo.warehouse.route-distance", "one_way_route_distance", "120", "m", "DISTANCE", ("demo.warehouse",), "F02", "K23"),
    )
    for pid, name, value, unit, kind, scopes, consumer, decision in defaults:
        add(
            pid, name, value, unit, kind, scopes=scopes, source_refs=defaults_source,
            decisions=(decision,), consumers=(consumer,)
        )

    object_defaults = {
        "warehouse": ("2", "11", "5", "20000", "10000", "500"),
        "airport": ("3", "8", "7", "85000", None, "300"),
        "clinic": ("3", "8", "7", "45000", None, "80"),
    }
    fields = (
        ("shifts", "shifts_per_day", "shift/day", "COUNT"),
        ("shift-hours", "shift_hours", "h/shift", "TIME"),
        ("horizon", "horizon_years", "year", "TIME"),
        ("total-area", "object_area", "m2", "AREA"),
        ("active-area", "active_area", "m2", "AREA"),
        ("available-power", "available_power", "kW", "POWER"),
    )
    for object_kind, values in object_defaults.items():
        for (suffix, name, unit, kind), value in zip(fields, values):
            if value is None:
                continue
            add(
                f"default.{object_kind}.{suffix}", name, value, unit, kind,
                scopes=(f"object.{object_kind}",), source_refs=defaults_source,
                decisions=("K26",), consumers=("C03",)
            )

    score_source = (
        source("R02", "§7 Пороги ранжирования"),
        source("R03", "§4 Ranking and normalization"),
        source("R06", "§4 Пороги ранжирования"),
        source("POLICY_V1", "K14/K16", "ACCEPTED_POLICY"),
    )
    for component, weight in {
        "availability": "0.30", "integrations": "0.25", "aisle_margin": "0.20",
        "trl": "0.15", "payload_margin": "0.10",
    }.items():
        add(
            f"score.applicability.weight.{component}", "applicability_component_weight",
            weight, "1", "FRACTION", scopes=(f"score.component.{component}",),
            provenance_kind="POLICY", override_policy="LOCKED", source_refs=score_source,
            decisions=("K14",), consumers=("F33",), maximum="1"
        )
    for component, weight in {
        "applicability": "0.50", "economics": "0.35", "data": "0.15"
    }.items():
        add(
            f"score.final.weight.{component}", "final_score_component_weight",
            weight, "1", "FRACTION", scopes=(f"score.final-component.{component}",),
            provenance_kind="POLICY", override_policy="LOCKED", source_refs=score_source,
            decisions=("K14",), consumers=("F33",), maximum="1"
        )
    score_thresholds = {
        "availability-hard-fail": "0.40", "availability-optimum-start": "0.70",
        "availability-optimum-end": "0.85", "availability-upper-reserve": "0.92",
        "aisle-risk": "0.15", "aisle-comfort": "0.40", "aisle-full": "0.60",
        "payload-good": "0.15", "payload-full": "0.50", "payload-upper": "1.00",
        "equal-economics-score": "50", "amr-volume-threshold": "5000",
        "amr-volume-penalty": "-5",
    }
    for name, value in score_thresholds.items():
        is_score = "score" in name or "penalty" in name
        is_aisle = name.startswith("aisle-")
        is_volume = name == "amr-volume-threshold"
        unit = (
            "score"
            if is_score
            else "m"
            if is_aisle
            else "pallet/day"
            if is_volume
            else "1"
        )
        kind = (
            "SCORE"
            if is_score
            else "DISTANCE"
            if is_aisle
            else "RATE"
            if is_volume
            else "FRACTION"
        )
        add(
            f"score.threshold.{name}", name.replace("-", "_"), value,
            unit, kind,
            provenance_kind="POLICY", override_policy="LOCKED", source_refs=score_source,
            decisions=("K14",), consumers=("F33",), minimum=None if value.startswith("-") else "0",
            maximum="100" if is_score else None,
        )

    curve_knots = {
        "availability": (("0.40", "0.0"), ("0.55", "0.5"), ("0.70", "0.8"), ("0.85", "1.0"), ("0.92", "0.9"), ("1.00", "0.5")),
        "aisle-margin": (("0", "0.0"), ("0.15", "0.3"), ("0.40", "0.7"), ("0.60", "1.0")),
        "trl": (("1", "0.0"), ("6", "0.0"), ("7", "0.3"), ("8", "0.7"), ("9", "1.0")),
        "payload-margin": (("0", "0.0"), ("0.15", "0.5"), ("0.50", "1.0"), ("1.00", "0.5")),
    }
    for curve, knots in curve_knots.items():
        for index, (input_value, output_value) in enumerate(knots, start=1):
            scope = f"score.curve.{curve}.knot-{index}"
            input_unit = (
                "m" if curve == "aisle-margin" else "level" if curve == "trl" else "1"
            )
            input_kind = (
                "DISTANCE"
                if curve == "aisle-margin"
                else "COUNT"
                if curve == "trl"
                else "FRACTION"
            )
            add(
                f"score.curve.{curve}.knot-{index}.input", "score_curve_input",
                input_value, input_unit, input_kind, scopes=(scope,), provenance_kind="POLICY",
                override_policy="LOCKED", source_refs=score_source, decisions=("K14",),
                consumers=("F33",),
                maximum="9" if curve == "trl" else None if curve == "aisle-margin" else "1",
            )
            add(
                f"score.curve.{curve}.knot-{index}.output", "score_curve_output",
                output_value, "1", "FRACTION", scopes=(scope,), provenance_kind="POLICY",
                override_policy="LOCKED", source_refs=score_source, decisions=("K14",),
                consumers=("F33",), maximum="1"
            )
    add(
        "score.integrations.no-requirements", "integrations_score_without_requirements",
        "1.0", "1", "FRACTION", scopes=("score.component.integrations",),
        provenance_kind="POLICY", override_policy="LOCKED", source_refs=score_source,
        decisions=("K14",), consumers=("F33",), maximum="1"
    )

    completeness_source = (
        source("R02", "§9 Оценка полноты ввода"),
        source("POLICY_V1", "K16", "ACCEPTED_POLICY"),
    )
    completeness_weights = {
        "headcount": 20, "salary": 19, "demand": 14, "distance": 10,
        "aisle": 10, "shifts": 8, "area": 5, "cargo-weight": 5,
        "discount": 5, "shift-hours": 4,
    }
    for field, weight in completeness_weights.items():
        add(
            f"completeness.intake.weight.{field}", "intake_completeness_weight",
            weight, "point", "SCORE", scopes=(f"input-field.{field}",),
            provenance_kind="POLICY", override_policy="LOCKED",
            source_refs=completeness_source, decisions=("K16",), consumers=("F35",),
            maximum="100",
        )
    for name, value in (
        ("basic-upper-exclusive", "40"), ("working-upper-exclusive", "70"),
        ("full-total", "100"), ("card-critical-count", "12"),
        ("card-important-count", "17"), ("card-useful-count", "7"),
        ("card-critical-weight", "3"), ("card-important-weight", "2"),
        ("card-useful-weight", "1"), ("card-full-weight", "77"),
        ("status-verified", "1.0"), ("status-unverified", "0.5"),
        ("status-missing", "0.0"),
    ):
        add(
            f"completeness.{name}", name.replace("-", "_"), value,
            "point", "SCORE", provenance_kind="POLICY", override_policy="LOCKED",
            source_refs=completeness_source, decisions=("K16",), consumers=("F35",),
            maximum="100",
        )

    visualization_source = (
        source("R02", "§8 Прочие параметры"),
        source("R06", "§5 Соотношение сторон и размеры визуализации"),
    )
    for object_kind, aspect in {"warehouse": "0.60", "airport": "0.35", "clinic": "0.75"}.items():
        add(
            f"visualization.aspect.{object_kind}", "visualization_aspect_ratio", aspect,
            "1", "FRACTION", scopes=(f"object.{object_kind}",), source_refs=visualization_source,
            decisions=("K18",), consumers=("F34",), maximum="1"
        )
    corridor_bands = (
        ("band-1", "2000", "2"),
        ("band-2", "10000", "3"),
        ("band-3", "40000", "4"),
    )
    for band, max_area, count in corridor_bands:
        add(
            f"visualization.corridor.{band}", "visualization_corridor_band_max_area",
            max_area, "m2", "AREA", scopes=(f"visualization.{band}",),
            source_refs=visualization_source, decisions=("K18",), consumers=("F34",)
        )
        add(
            f"visualization.corridor.{band}.count", "visualization_corridor_count",
            count, "corridor", "COUNT", scopes=(f"visualization.{band}",),
            source_refs=visualization_source, decisions=("K18",), consumers=("F34",)
        )
    add(
        "visualization.corridor.band-4.count", "visualization_corridor_count",
        "5", "corridor", "COUNT", scopes=("visualization.area-above-40000",),
        source_refs=visualization_source, decisions=("K18",), consumers=("F34",)
    )

    parameters.sort(key=lambda item: item["parameter_id"])
    parameter_ids = {item["parameter_id"] for item in parameters}

    def matching(*prefixes: str) -> list[str]:
        return sorted(pid for pid in parameter_ids if pid.startswith(prefixes))

    coverage = [
        coverage_item("r02.1.labor-values", "R02", "§1 table: numeric labour parameters", "REGISTRY_VALUES", matching("labor."), ("K01", "K05", "K27"), "Atomic labour assumptions and policies are materialized."),
        coverage_item("r02.1.derived-labor", "R02", "§1 formulas: deficit, coverage, equipment savings", "DERIVED_FORMULA", [], ("K04", "K06", "K07", "K08"), "Formula definitions belong to C07/C14, not the value registry."),
        coverage_item("r02.1.salary", "R02", "§1 salary rows", "USER_INPUT_REQUIRED", [], ("K05",), "Role, technical and control salaries have no registry default."),
        coverage_item("r02.2.finance-values", "R02", "§2 financial parameter table", "REGISTRY_VALUES", matching("finance."), ("K01", "K09", "K11", "K12", "K21", "K25"), "Atomic financial assumptions and illustrative policy values are materialized."),
        coverage_item("r02.2.finance-formulas", "R02", "§2 residual/TCO/tax/ROI formulas", "DERIVED_FORMULA", [], ("K10", "K11", "K12", "K13", "K21"), "Algorithms are versioned by formula contracts and are not constants."),
        coverage_item("r02.3.scenarios", "R02", "§3.2 uncertainty table", "REGISTRY_VALUES", matching("scenario."), ("K09", "K22"), "All three scenarios and annual ramp values are atomic entries."),
        coverage_item("r02.3.raas-zeroing", "R02", "§3.1/3.3 acquisition and RaaS zeroing", "POLICY_RULE", [], ("K21",), "Responsibility/zeroing is a policy table, not a numeric fallback."),
        coverage_item("r02.4.technology", "R02", "§4 technology parameters", "REGISTRY_VALUES", matching("finance.energy."), ("K01", "K02", "K03", "K22"), "Charging efficiency is materialized; capacity algorithms remain formulas."),
        coverage_item("r02.4.vendor-values", "R02", "§4 robot power and box batch", "VENDOR_INPUT_REQUIRED", [], ("K03", "K29"), "Robot power/payload/item mass must be evidence-safe or explicit scenario input."),
        coverage_item("r02.5-6.defaults", "R02", "§5–6 defaults", "REGISTRY_VALUES", matching("default.", "demo."), ("K23", "K26"), "Optional/preset defaults are explicit scoped assumptions."),
        coverage_item("r02.7.ranking", "R02", "§7 ranking thresholds", "REGISTRY_VALUES", matching("score."), ("K14",), "Accepted scoring weights and endpoints replace superseded penalties."),
        coverage_item("r02.7.data-weight-75", "R02", "§7 historical card denominator 75", "SUPERSEDED", [], ("K16", "K28"), "K16 accepts 17 important fields and denominator 77."),
        coverage_item("r02.8.misc", "R02", "§8 supported miscellaneous values", "REGISTRY_VALUES", matching("visualization.", "default.other.", "default.horizon."), ("K18", "K26"), "Safe object and visualization assumptions are scoped."),
        coverage_item("r02.8.unsafe-vendor-defaults", "R02", "§8 10 picks/min and 800 m2/h", "FORBIDDEN_UNSAFE_DEFAULT", [], ("K29",), "These values never populate vendor facts or calculation profiles."),
        coverage_item("r02.9.completeness", "R02", "§9 intake completeness", "REGISTRY_VALUES", matching("completeness."), ("K16",), "Weights sum to 100; card-data denominator is separately 77."),
        coverage_item("r06.1.labor", "R06", "§1 labour assumptions", "REGISTRY_VALUES", matching("labor."), ("K05", "K06", "K07", "K08", "K27"), "R06 rationale is bound to the same atomic labour entries."),
        coverage_item("r06.1.salary", "R06", "§1 salary only user input", "USER_INPUT_REQUIRED", [], ("K05",), "Removed 80000 salary default is not materialized."),
        coverage_item("r06.1.robot-exchange", "R06", "§1 robot exchange time", "VENDOR_INPUT_REQUIRED", [], ("K02",), "Safe split/total exchange facts are resolved per model/run."),
        coverage_item("r06.2.finance", "R06", "§2 finance assumptions", "REGISTRY_VALUES", matching("finance."), ("K09", "K11", "K12", "K21", "K25"), "R06 financial assumptions share IDs with R02."),
        coverage_item("r06.2.flow-rules", "R06", "§2 full-flow, ROI, depreciation rules", "POLICY_RULE", [], ("K11", "K12", "K13"), "Ledger behavior is formula/policy, not a scalar constant."),
        coverage_item("r06.3.scenarios", "R06", "§3 scenario assumptions", "REGISTRY_VALUES", matching("scenario."), ("K09", "K22"), "Every uncertainty axis and ramp year is materialized."),
        coverage_item("r06.3.raas", "R06", "§3 RaaS responsibility assumptions", "POLICY_RULE", [], ("K21",), "RaaS line ownership is preserved for C17."),
        coverage_item("r06.4.ranking", "R06", "§4 ranking parameters", "REGISTRY_VALUES", matching("score."), ("K14",), "Accepted ranking parameters are materialized."),
        coverage_item("r06.5.unsafe-picks", "R06", "§5 default picks/min", "FORBIDDEN_UNSAFE_DEFAULT", [], ("K29",), "10 picks/min is excluded from vendor calculation facts."),
        coverage_item("r06.5.completeness-visual", "R06", "§5 completeness and visualization", "REGISTRY_VALUES", matching("completeness.", "visualization."), ("K16", "K18"), "Accepted weights and synthetic visualization values are materialized."),
        coverage_item("r06.5.vendor-trl-noise", "R06", "§5 TRL and noise", "VENDOR_INPUT_REQUIRED", [], ("K15", "K29"), "TRL/noise require scoped evidence; no default is created."),
        coverage_item("r06.6.priorities", "R06", "§6 field priorities", "POLICY_RULE", [], ("K26",), "Mandatory/default behavior is a normalization policy."),
    ]
    coverage.sort(key=lambda item: item["coverage_id"])

    supersessions = [
        supersession("supersession.r04.d9.peak", "R04 D9", "single hard-coded peak multiplier 1.5", matching("scenario.")[:0] + ["scenario.base.intraday-peak", "scenario.base.peak-reserve"], "Peak is intraday factor multiplied by one plus scenario reserve.", ("K22", "K28")),
        supersession("supersession.r04.51.applicability", "R04 replacement 51", "binary applicability and duplicate penalties", matching("score.applicability.", "score.threshold."), "Use accepted scoped applicability components and K14 curves.", ("K14", "K28")),
        supersession("supersession.r04.58.raas", "R04 replacement 58", "ambiguous RaaS payment inside OPEX subtotal", ["finance.raas.monthly-rate"], "Payment is one separate operating line and enters cash flow/TCO once.", ("K21", "K28")),
        supersession("supersession.r04.64.opex-base", "R04 replacement 64", "percentage OPEX based on total CAPEX", ["finance.insurance-share", "finance.consumables-share", "finance.repair-share"], "Percentage OPEX uses equipment CAPEX only.", ("K25", "K28")),
        supersession("supersession.r04.66.penalties", "R04 replacement 66", "duplicated checks and score penalties", matching("score."), "Hard checks and score components are separate; only accepted residual penalty remains.", ("K14", "K28")),
    ]
    supersessions.sort(key=lambda item: item["supersession_id"])

    provisional = {
        "schema_version": "calculation-parameter-registry-v1",
        "registry_version": "hackathon-calculation-parameter-registry-v1",
        "policy_version": "hackathon-calculation-policy-v1",
        "registry_digest": "sha256:" + "0" * 64,
        "semantic_order": "parameter_id",
        "parameters": parameters,
        "coverage": coverage,
        "supersessions": supersessions,
    }
    parsed = CalculationParameterRegistryV1.model_validate(provisional)
    payload = parsed.model_dump(mode="json")
    payload["registry_digest"] = registry_semantic_digest(parsed)
    return CalculationParameterRegistryV1.model_validate(payload)


def DecimalLike(value: str) -> float:
    return float(value)


def coverage_item(
    coverage_id: str,
    source_id: str,
    locator: str,
    disposition: str,
    parameter_ids: list[str],
    decisions: tuple[str, ...],
    rationale: str,
) -> dict[str, Any]:
    return {
        "coverage_id": coverage_id,
        "source_id": source_id,
        "locator": locator,
        "disposition": disposition,
        "parameter_ids": parameter_ids,
        "decision_refs": list(decisions),
        "rationale": rationale,
    }


def supersession(
    supersession_id: str,
    source_ref: str,
    old_semantics: str,
    replacement_parameter_ids: list[str],
    replacement_rule: str,
    decisions: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "supersession_id": supersession_id,
        "source_ref": source_ref,
        "old_semantics": old_semantics,
        "replacement_parameter_ids": replacement_parameter_ids,
        "replacement_rule": replacement_rule,
        "decision_refs": list(decisions),
    }


def expected_files() -> tuple[tuple[Path, bytes], ...]:
    registry = build_registry()
    registry_bytes = pretty_bytes(registry.model_dump(mode="json"))
    schema_bytes = pretty_bytes(CalculationParameterRegistryV1.model_json_schema())
    manifest_schema_bytes = pretty_bytes(RegistryManifestV1.model_json_schema())
    scenario_count = sum(item.scenario != "ALL" for item in registry.parameters)
    manifest = RegistryManifestV1.model_validate(
        {
            "schema_version": "calculation-parameter-registry-manifest-v1",
            "registry_version": registry.registry_version,
            "registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
            "registry_semantic_digest": registry.registry_digest,
            "schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
            "sources": [
                {
                    "source_id": source_id,
                    "path": path,
                    "sha256": SOURCE_HASHES[source_id],
                    "role": role,
                    "runtime_dependency": False,
                }
                for source_id, path, role in (
                    ("R00", "Разобрать/Версии проекта от Жени/reference/00_METHODOLOGY.md", "REFERENCE"),
                    ("R02", "Разобрать/Версии проекта от Жени/reference/02_CONSTANTS.md", "REFERENCE"),
                    ("R03", "Разобрать/Версии проекта от Жени/reference/03_FORMULAS.md", "REFERENCE"),
                    ("R04", "Разобрать/Версии проекта от Жени/reference/04_DECISIONS.md", "REFERENCE"),
                    ("R06", "Разобрать/Версии проекта от Жени/reference/06_EXPERT.md", "REFERENCE"),
                    ("POLICY_V1", "data/calculation/sources/POLICY_V1.md", "ACCEPTED_POLICY"),
                )
            ],
            "parameter_count": len(registry.parameters),
            "coverage_count": len(registry.coverage),
            "supersession_count": len(registry.supersessions),
            "scenario_parameter_count": scenario_count,
            "required_decisions": [
                "K01", "K05", "K06", "K07", "K08", "K09", "K11", "K12",
                "K14", "K16", "K18", "K21", "K22", "K23", "K25", "K26",
                "K27", "K28", "K29",
            ],
        }
    )
    return (
        (REGISTRY_PATH, registry_bytes),
        (SCHEMA_PATH, schema_bytes),
        (MANIFEST_PATH, pretty_bytes(manifest.model_dump(mode="json"))),
        (MANIFEST_SCHEMA_PATH, manifest_schema_bytes),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = expected_files()
    if args.check:
        stale = [
            str(path.relative_to(ROOT))
            for path, content in expected
            if not path.is_file() or path.read_bytes() != content
        ]
        if stale:
            raise SystemExit("generated calculation registry differs: " + ", ".join(stale))
        return 0
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in expected:
        path.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
