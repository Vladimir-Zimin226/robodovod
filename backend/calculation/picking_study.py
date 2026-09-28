"""Isolated synthetic warehouse picking study; never converts pallet transport."""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Literal
from pydantic import Field, model_validator
from calculation_contracts import DecimalString, StrictContractModel


class PickingStudyV1(StrictContractModel):
    schema_version: Literal['warehouse-picking-study-v1'] = 'warehouse-picking-study-v1'
    unit: Literal['PICK', 'ORDER_LINE']
    demand_per_day: DecimalString
    hours_per_shift: DecimalString
    shifts_per_day: int = Field(ge=1, le=3)
    robot_picks_per_hour: DecimalString | None = None
    robot_rate_source: Literal['MEASUREMENT', 'SYNTHETIC_TEST'] | None = None
    manual_picks_per_shift: DecimalString | None = None
    manual_rate_source: Literal['MEASUREMENT', 'SYNTHETIC_TEST'] | None = None
    robotizable_fraction: DecimalString | None = None
    residual_operations: str | None = None
    selected_fleet: int | None = Field(default=None, ge=0)
    existing_pickers: int | None = Field(default=None, ge=0)
    annual_gross_per_picker: DecimalString | None = None
    robot_price_gross: DecimalString | None = None
    annual_robot_opex_gross: DecimalString | None = None
    horizon_years: int = Field(default=5, ge=1, le=15)
    discount_rate: DecimalString = '0.15'
    confirmation: bool = False

    @model_validator(mode='after')
    def validate_units(self):
        if Decimal(self.demand_per_day) < 0 or Decimal(self.hours_per_shift) <= 0 or Decimal(self.hours_per_shift)*self.shifts_per_day > 24:
            raise ValueError('invalid picking demand or window')
        if not 0 <= Decimal(self.discount_rate) <= 1:
            raise ValueError('invalid discount rate')
        for rate, source in [(self.robot_picks_per_hour,self.robot_rate_source),(self.manual_picks_per_shift,self.manual_rate_source)]:
            if (rate is None) != (source is None) or rate is not None and Decimal(rate) <= 0:
                raise ValueError('picking rate requires a positive value and source')
        if self.robotizable_fraction is not None and not 0 <= Decimal(self.robotizable_fraction) <= 1:
            raise ValueError('robotizable fraction must be within 0..1')
        return self


def calculate_picking_study(value: PickingStudyV1) -> dict:
    """Preview arithmetic only; synthetic rate cannot certify a catalog robot."""
    missing = [name for name in ['robot_picks_per_hour','manual_picks_per_shift','robotizable_fraction',
                                  'residual_operations','existing_pickers'] if getattr(value,name) is None]
    if not value.confirmation:
        missing.append('confirmation')
    result = {'schema_version':'warehouse-picking-study-result-v1','unit':value.unit,
              'status':'PARTIAL' if missing else 'SYNTHETIC_STUDY',
              'missing':missing, 'catalog_model_verified':False,
              'limitations':['Паллетная перевозка не является отбором SKU.',
                             'Синтетическая производительность не подтверждает реальную модель.'],
              'recommended_fleet':None,'selected_fleet':value.selected_fleet,
              'coverage':None,'released_people':None,'project_npv':None}
    if missing:
        return result
    ceil=lambda n:int(n.to_integral_value(rounding=ROUND_CEILING))
    floor=lambda n:int(n.to_integral_value(rounding=ROUND_FLOOR))
    demand=Decimal(value.demand_per_day)
    robot_daily=Decimal(value.robot_picks_per_hour)*Decimal(value.hours_per_shift)*value.shifts_per_day
    recommended=ceil(demand/robot_daily)
    fleet=recommended if value.selected_fleet is None else value.selected_fleet
    coverage=Decimal(1) if demand==0 else min(Decimal(1),Decimal(fleet)*robot_daily/demand)
    released=min(value.existing_pickers, floor(Decimal(value.existing_pickers)*Decimal(value.robotizable_fraction)*coverage))
    result.update(recommended_fleet=recommended,selected_fleet=fleet,coverage=format(coverage,'f'),
                  released_people=released,remaining_people=value.existing_pickers-released,
                  manual_rate_source=value.manual_rate_source,robot_rate_source=value.robot_rate_source)
    if any(getattr(value,name) is None for name in ['annual_gross_per_picker','robot_price_gross','annual_robot_opex_gross']):
        result['status']='PARTIAL'
        result['missing']=[name for name in ['annual_gross_per_picker','robot_price_gross','annual_robot_opex_gross'] if getattr(value,name) is None]
        return result
    investment=Decimal(fleet)*Decimal(value.robot_price_gross)
    annual=Decimal(released)*Decimal(value.annual_gross_per_picker)-Decimal(fleet)*Decimal(value.annual_robot_opex_gross)
    discount=Decimal(value.discount_rate)
    npv=-investment+sum((annual/(1+discount)**year for year in range(1,value.horizon_years+1)),Decimal(0))
    result['project_npv']=format(npv.quantize(Decimal('0.01')),'f')
    result['annual_effect_gross']=format(annual,'f')
    return result
