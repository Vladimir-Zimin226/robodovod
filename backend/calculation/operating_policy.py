"""Explicit, versioned project assumptions; these are not vendor facts."""
from decimal import Decimal, ROUND_CEILING
from typing import Literal
from pydantic import Field, model_validator
from calculation_contracts import DecimalString, StrictContractModel

class StaffingPolicyV2(StrictContractModel):
    schema_version: Literal['staffing-policy-v2'] = 'staffing-policy-v2'
    robots_per_control_post: DecimalString
    robots_per_day_technician: DecimalString
    technician_presence: Literal['DAY_WORKLOAD', 'EACH_SHIFT', 'VENDOR']
    rotation_factor: DecimalString
    source: Literal['USER', 'ASSUMPTION']
    basis: str = Field(min_length=3, max_length=500)
    date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    confirmed: bool

    @model_validator(mode='after')
    def validate_policy(self):
        if not self.confirmed or any(Decimal(v) <= 0 for v in [self.robots_per_control_post, self.robots_per_day_technician]):
            raise ValueError('confirm positive staffing loads')
        if not 1 <= Decimal(self.rotation_factor) <= 10:
            raise ValueError('rotation factor must be 1..10')
        return self

    def requirement(self, fleet: int, shifts: int):
        ceil = lambda n: int(n.to_integral_value(rounding=ROUND_CEILING))
        posts = ceil(Decimal(fleet) / Decimal(self.robots_per_control_post))
        person_shifts = posts * shifts
        tech_posts = ceil(Decimal(fleet) / Decimal(self.robots_per_day_technician))
        tech_shifts = tech_posts * (shifts if self.technician_presence == 'EACH_SHIFT' else 1)
        return {'control_posts': posts, 'control_person_shifts': person_shifts,
                'control_fte': ceil(Decimal(person_shifts) * Decimal(self.rotation_factor)),
                'technician_posts': tech_posts, 'technician_person_shifts': tech_shifts,
                'technician_fte': ceil(Decimal(tech_shifts) * Decimal(self.rotation_factor)),
                'rotation_factor': self.rotation_factor, 'unit': 'person',
                'policy': self.model_dump(mode='json')}

class WorkShareV1(StrictContractModel):
    schema_version: Literal['robotizable-work-share-v1'] = 'robotizable-work-share-v1'
    fraction: DecimalString
    residual_operations: str = Field(min_length=3, max_length=500)
    source: Literal['USER', 'ASSUMPTION']
    basis: str = Field(min_length=3, max_length=500)
    date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    confirmed: bool

    @model_validator(mode='after')
    def validate_share(self):
        if not self.confirmed or not 0 <= Decimal(self.fraction) <= 1:
            raise ValueError('confirm robotizable work fraction 0..1')
        return self
