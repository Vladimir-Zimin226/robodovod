"""Versioned, explicitly assumed project calculation for warehouse picking.

Picking units never enter the pallet transport engine. A saved result can
compare project cashflows, but it cannot certify a catalog robot or purchase.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_EVEN
from typing import Literal

from pydantic import Field, model_validator

from calculation_contracts import DecimalString, StrictContractModel

ENGINE_VERSION = 'warehouse-picking-project-v1'


def _d(value: str | int) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN), 'f')


def _ceil(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


class PickingRoleInputV1(StrictContractModel):
    role_code: Literal['picker', 'sorter']
    headcount: int = Field(ge=0, le=100000)
    monthly_employer_cost: DecimalString | None = None
    manual_units_per_shift: DecimalString | None = None
    robotizable_fraction: DecimalString
    # Residual shifts describe work outside the counted picking units.
    residual_extra_shifts_per_day: DecimalString = '0'
    robot_covers_role: bool
    source: Literal['USER', 'ASSUMPTION']
    basis: str = Field(min_length=8, max_length=1000)
    confirmed: bool

    @model_validator(mode='after')
    def valid(self):
        if not 0 <= _d(self.robotizable_fraction) <= 1:
            raise ValueError('role robotizable fraction must be within 0..1')
        if _d(self.residual_extra_shifts_per_day) < 0:
            raise ValueError('residual shifts must be non-negative')
        if self.manual_units_per_shift is not None and _d(self.manual_units_per_shift) <= 0:
            raise ValueError('manual productivity must be positive')
        if self.monthly_employer_cost is not None and _d(self.monthly_employer_cost) < 0:
            raise ValueError('monthly employer cost must be non-negative')
        return self


class PickingMoneyInputV1(StrictContractModel):
    purchase_robot_price: DecimalString | None = None
    purchase_implementation: DecimalString | None = None
    purchase_annual_opex_per_robot: DecimalString | None = None
    raas_monthly_per_robot: DecimalString | None = None
    raas_customer_capex: DecimalString | None = None
    raas_customer_annual_opex: DecimalString | None = None
    shared_site_capex: DecimalString | None = None
    shared_site_annual_opex: DecimalString | None = None
    purchase_new_staff_annual_cost: DecimalString | None = None
    raas_new_staff_annual_cost: DecimalString | None = None
    horizon_years: int = Field(default=5, ge=1, le=15)
    discount_rate: DecimalString = '0.15'
    source: Literal['USER', 'ASSUMPTION'] = 'ASSUMPTION'
    basis: str | None = None
    confirmed: bool = False

    @model_validator(mode='after')
    def valid(self):
        if not 0 <= _d(self.discount_rate) <= 1:
            raise ValueError('discount rate must be within 0..1')
        for key in ('purchase_robot_price', 'purchase_implementation',
                    'purchase_annual_opex_per_robot', 'raas_monthly_per_robot',
                    'raas_customer_capex', 'raas_customer_annual_opex',
                    'shared_site_capex', 'shared_site_annual_opex',
                    'purchase_new_staff_annual_cost', 'raas_new_staff_annual_cost'):
            value = getattr(self, key)
            if value is not None and _d(value) < 0:
                raise ValueError(f'{key} must be non-negative')
        if self.confirmed and (not self.basis or len(self.basis.strip()) < 8):
            raise ValueError('confirmed financial terms need a basis')
        return self


class PickingProjectInputV1(StrictContractModel):
    schema_version: Literal['warehouse-picking-project-input-v1'] = 'warehouse-picking-project-input-v1'
    process_id: str = Field(min_length=3, max_length=200)
    unit: Literal['PICK', 'ORDER_LINE']
    unit_basis: str = Field(min_length=8, max_length=1000)
    unit_confirmed: bool
    demand_per_day: DecimalString
    shifts_per_day: int = Field(ge=1, le=3)
    hours_per_shift: DecimalString
    days_per_year: int = Field(ge=1, le=366)
    operation_source: Literal['USER', 'ASSUMPTION']
    operation_basis: str = Field(min_length=8, max_length=1000)
    operation_confirmed: bool
    robot_units_per_hour: DecimalString | None = None
    robot_rate_source: Literal['MEASUREMENT', 'ASSUMPTION'] | None = None
    robot_rate_basis: str | None = None
    robot_rate_confirmed: bool = False
    availability_fraction: DecimalString = '0.85'
    robotizable_fraction: DecimalString
    selected_fleet: int | None = Field(default=None, ge=0)
    roles: list[PickingRoleInputV1] = Field(default_factory=list, max_length=2)
    money: PickingMoneyInputV1 = Field(default_factory=PickingMoneyInputV1)

    @model_validator(mode='after')
    def valid(self):
        if not self.process_id.endswith('.warehouse_picking'):
            raise ValueError('process_id must identify warehouse_picking')
        if _d(self.demand_per_day) <= 0:
            raise ValueError('picking demand must be positive')
        if _d(self.hours_per_shift) <= 0 or _d(self.hours_per_shift) * self.shifts_per_day > 24:
            raise ValueError('picking schedule must fit one day')
        if not 0 < _d(self.availability_fraction) <= 1:
            raise ValueError('availability must be within (0,1]')
        if not 0 <= _d(self.robotizable_fraction) <= 1:
            raise ValueError('robotizable fraction must be within 0..1')
        if self.robot_units_per_hour is not None and _d(self.robot_units_per_hour) <= 0:
            raise ValueError('robot productivity must be positive')
        if len({role.role_code for role in self.roles}) != len(self.roles):
            raise ValueError('picking roles must be unique')
        return self


def _financial(*, fleet: int, baseline_fot: Decimal, scenario_fot: Decimal,
               money: PickingMoneyInputV1, acquisition: str) -> dict:
    if acquisition == 'PURCHASE':
        needed = ('purchase_robot_price', 'purchase_implementation',
                  'purchase_annual_opex_per_robot', 'shared_site_capex',
                  'shared_site_annual_opex', 'purchase_new_staff_annual_cost')
    else:
        needed = ('raas_monthly_per_robot', 'raas_customer_capex',
                  'raas_customer_annual_opex', 'shared_site_capex',
                  'shared_site_annual_opex', 'raas_new_staff_annual_cost')
    missing = [key for key in needed if getattr(money, key) is None]
    if not money.confirmed:
        missing.append('money.confirmed')
    if missing:
        return {'status': 'PARTIAL', 'missing': missing, 'roi_pct': None,
                'npv_rub': None, 'tco_rub': None}
    common_capex = _d(money.shared_site_capex)
    common_opex = _d(money.shared_site_annual_opex)
    if acquisition == 'PURCHASE':
        capex = fleet * _d(money.purchase_robot_price) + _d(money.purchase_implementation) + common_capex
        robot_opex = fleet * _d(money.purchase_annual_opex_per_robot)
        new_staff = _d(money.purchase_new_staff_annual_cost)
    else:
        capex = _d(money.raas_customer_capex) + common_capex
        robot_opex = fleet * _d(money.raas_monthly_per_robot) * 12 + _d(money.raas_customer_annual_opex)
        new_staff = _d(money.raas_new_staff_annual_cost)
    annual_scenario_cost = scenario_fot + robot_opex + new_staff + common_opex
    annual_effect = baseline_fot - annual_scenario_cost
    horizon = money.horizon_years
    rate = _d(money.discount_rate)
    npv = -capex + sum((annual_effect / (1 + rate) ** year for year in range(1, horizon + 1)), Decimal(0))
    roi = None if capex == 0 else (annual_effect * horizon - capex) / capex * 100
    return {'status': 'COMPLETE', 'missing': [], 'capex_rub': _money(capex),
            'baseline_fot_annual_rub': _money(baseline_fot),
            'scenario_fot_annual_rub': _money(scenario_fot),
            'scenario_annual_cost_rub': _money(annual_scenario_cost),
            'annual_effect_rub': _money(annual_effect), 'npv_rub': _money(npv),
            'tco_rub': _money(capex + annual_scenario_cost * horizon),
            'roi_pct': None if roi is None else _money(roi),
            'roi_basis': '(сумма годовых эффектов − CAPEX проекта) / CAPEX проекта × 100',
            'roi_reason': 'Нулевой CAPEX: ROI не определён' if roi is None else None}


def calculate_picking_project(raw: PickingProjectInputV1 | dict) -> dict:
    value = raw if isinstance(raw, PickingProjectInputV1) else PickingProjectInputV1.model_validate(raw)
    demand = _d(value.demand_per_day)
    missing = []
    if not value.unit_confirmed:
        missing.append('unit_confirmed')
    if not value.operation_confirmed:
        missing.append('operation_confirmed')
    if value.robot_units_per_hour is None:
        missing.append('robot_units_per_hour')
    if not value.robot_rate_source or not value.robot_rate_basis or not value.robot_rate_confirmed:
        missing.append('robot_rate_evidence')
    capacity = {'status': 'PARTIAL', 'recommended_fleet': None,
                'selected_fleet': value.selected_fleet, 'covered_units_per_day': None,
                'demand_coverage_fraction': None}
    covered = None
    if not missing:
        per_robot = (_d(value.robot_units_per_hour) * _d(value.hours_per_shift)
                     * value.shifts_per_day * _d(value.availability_fraction))
        eligible = demand * _d(value.robotizable_fraction)
        recommended = _ceil(eligible / per_robot)
        fleet = recommended if value.selected_fleet is None else value.selected_fleet
        covered = min(eligible, Decimal(fleet) * per_robot)
        capacity = {'status': 'CALCULATED', 'recommended_fleet': recommended,
                    'selected_fleet': fleet, 'covered_units_per_day': _money(covered),
                    'demand_coverage_fraction': format(covered / demand, 'f')}
    role_results = []
    baseline_fot = scenario_fot = Decimal(0)
    labour_complete = covered is not None and bool(value.roles)
    if not value.roles:
        missing.append('roles')
    for role in value.roles:
        role_missing = []
        if not role.confirmed:
            role_missing.append('confirmed')
        if role.manual_units_per_shift is None:
            role_missing.append('manual_units_per_shift')
        if role.monthly_employer_cost is None:
            role_missing.append('monthly_employer_cost')
        released = remaining = baseline_shifts = remaining_shifts = None
        if covered is not None and not role_missing:
            manual = _d(role.manual_units_per_shift)
            baseline_shifts = _ceil(demand / manual)
            role_covered = (min(covered, demand * _d(role.robotizable_fraction))
                            if role.robot_covers_role else Decimal(0))
            remaining_shifts = _ceil((demand - role_covered) / manual
                                     + _d(role.residual_extra_shifts_per_day))
            if baseline_shifts > role.headcount:
                role_missing.append('headcount_below_daily_workload')
            elif remaining_shifts > role.headcount:
                role_missing.append('residual_workload_exceeds_staff')
            else:
                released = min(role.headcount, max(0, baseline_shifts - remaining_shifts))
                remaining = role.headcount - released
                annual = _d(role.monthly_employer_cost) * 12
                baseline_fot += annual * role.headcount
                scenario_fot += annual * remaining
        if role_missing or covered is None:
            labour_complete = False
        role_results.append({'role_code': role.role_code,
                             'status': 'PARTIAL' if role_missing or covered is None else 'CALCULATED',
                             'missing': role_missing, 'headcount': role.headcount,
                             'baseline_worker_shifts_per_day': baseline_shifts,
                             'remaining_worker_shifts_per_day': remaining_shifts,
                             'released_people': released, 'remaining_people': remaining,
                             'robot_covers_role': role.robot_covers_role,
                             'source': role.source, 'basis': role.basis})
        missing.extend(f'roles.{role.role_code}.{field}' for field in role_missing)
    if not labour_complete:
        financial = {key: {'status': 'PARTIAL', 'missing': ['labour'],
                           'roi_pct': None, 'npv_rub': None, 'tco_rub': None}
                     for key in ('purchase', 'raas')}
    else:
        financial = {key: _financial(fleet=capacity['selected_fleet'], baseline_fot=baseline_fot,
                                    scenario_fot=scenario_fot, money=value.money,
                                    acquisition=key.upper()) for key in ('purchase', 'raas')}
    missing.extend(f'{key}.{field}' for key, data in financial.items() for field in data['missing'])
    return {'schema_version': 'warehouse-picking-project-result-v1',
            'engine_version': ENGINE_VERSION,
            'status': 'COMPLETE' if not missing else 'PARTIAL',
            'process_id': value.process_id,
            'unit': value.unit, 'unit_basis': value.unit_basis,
            'operation_source': value.operation_source,
            'operation_basis': value.operation_basis,
            'annual_demand_units': _money(demand * value.days_per_year),
            'annual_robot_covered_units': None if covered is None else _money(covered * value.days_per_year),
            'catalog_model_verified': False, 'purchase_recommendation': False,
            'capacity': capacity,
            'labour': {'status': 'CALCULATED' if labour_complete else 'PARTIAL',
                       'roles': role_results,
                       'total_released_people': sum(row['released_people'] or 0 for row in role_results)},
            'financial': financial, 'missing': sorted(set(missing)),
            'limitations': ['Проверочный профиль не является паспортом модели каталога.',
                            'Штатное высвобождение — сценарная оценка без подтверждённого графика.',
                            'Остаточные смены относятся только к работе вне указанного спроса.']}
