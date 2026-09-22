"""Strict C13 contracts; no financial formulas live in this module."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from calculation_contracts import DecimalString, StableId, StrictContractModel


class CommercialScopeV1(StrictContractModel):
    model_id: Annotated[str, Field(min_length=1)]
    position_id: Annotated[str, Field(min_length=1)]
    procurement_option_id: Annotated[str, Field(min_length=1)] | None = None
    region: Annotated[str, Field(min_length=1)] | None = None
    boundary: Literal[
        "BARE_EQUIPMENT", "CONFIGURED_EQUIPMENT", "TURNKEY_SOLUTION",
        "SERVICE_TARIFF", "SCENARIO_BUDGET",
    ]


class CommercialSourceV1(StrictContractModel):
    kind: Literal["USER", "FILE", "ORGANIZER_DATASET", "VENDOR_QUOTE", "ASSUMPTION"]
    source_id: StableId
    evidence_ids: list[StableId] = Field(default_factory=list)
    observed_on: date | None = None
    valid_until: date | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "CommercialSourceV1":
        if self.kind == "VENDOR_QUOTE" and not self.evidence_ids:
            raise ValueError("vendor quote requires evidence_ids")
        if self.valid_until is not None and self.observed_on is not None and self.valid_until < self.observed_on:
            raise ValueError("commercial source validity ends before observation")
        return self


class CommercialMoneyV1(StrictContractModel):
    schema_version: Literal["commercial-money-v1"] = "commercial-money-v1"
    raw_amount: DecimalString
    currency: Literal["RUB", "USD", "EUR", "UNKNOWN"]
    tax_basis: Literal["CASH_GROSS_RUB", "NET_RUB", "UNKNOWN"]
    vat_rate: DecimalString | None = None
    source: CommercialSourceV1
    scope: CommercialScopeV1
    zero_semantics: Literal["EXCLUDED_BY_SCENARIO", "ZERO_PRICE_CONFIRMED"] | None = None

    @model_validator(mode="after")
    def validate_money(self) -> "CommercialMoneyV1":
        amount = Decimal(self.raw_amount)
        if amount < 0:
            raise ValueError("commercial amount cannot be negative")
        if amount == 0 and self.zero_semantics is None:
            raise ValueError("zero commercial amount requires explicit semantics")
        if amount != 0 and self.zero_semantics is not None:
            raise ValueError("zero semantics are only valid for amount 0")
        if self.vat_rate is not None:
            rate = Decimal(self.vat_rate)
            if rate < 0 or rate > 1:
                raise ValueError("VAT rate must be within 0..1")
        return self


class FixedTotalBasisV1(StrictContractModel):
    kind: Literal["FIXED_TOTAL"] = "FIXED_TOTAL"
    money: CommercialMoneyV1


class PerRobotBasisV1(StrictContractModel):
    kind: Literal["PER_ROBOT"] = "PER_ROBOT"
    money: CommercialMoneyV1


class PercentBaseBasisV1(StrictContractModel):
    kind: Literal["PERCENT_BASE"] = "PERCENT_BASE"
    rate: DecimalString
    base_line_id: StableId

    @model_validator(mode="after")
    def validate_rate(self) -> "PercentBaseBasisV1":
        if Decimal(self.rate) < 0 or Decimal(self.rate) > 1:
            raise ValueError("percent-base rate must be within 0..1")
        return self


CostBasisV1 = Annotated[
    FixedTotalBasisV1 | PerRobotBasisV1 | PercentBaseBasisV1,
    Field(discriminator="kind"),
]


class CommercialCostLineV1(StrictContractModel):
    line_id: StableId
    category: Literal[
        "ROBOT", "CHARGER", "INTEGRATION", "INFRASTRUCTURE", "DELIVERY",
        "COMMISSIONING", "TRAINING", "SERVICE", "SOFTWARE", "SPARES",
        "RECURRING_SUPPLIES", "OTHER",
    ]
    timing: Literal["CAPITAL_ONCE", "ANNUAL", "MONTHLY"]
    basis: CostBasisV1
    included_in: list[StableId] = Field(default_factory=list)
    excluded_by_scenario: bool = False


class ServiceResponsibilityV1(StrictContractModel):
    area: Literal[
        "HARDWARE", "BATTERY", "CHARGING", "MAINTENANCE", "SPARES",
        "SOFTWARE", "CONNECTIVITY", "INTEGRATION", "INFRASTRUCTURE", "INSURANCE",
    ]
    responsible_party: Literal["CUSTOMER", "VENDOR", "INTEGRATOR", "SHARED", "UNKNOWN"]
    evidence_ids: list[StableId] = Field(default_factory=list)


class PurchaseTermsV1(StrictContractModel):
    schema_version: Literal["purchase-terms-v1"] = "purchase-terms-v1"
    acquisition: Literal["PURCHASE"] = "PURCHASE"
    primary_price: CommercialMoneyV1
    cost_lines: list[CommercialCostLineV1] = Field(default_factory=list)
    responsibilities: list[ServiceResponsibilityV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lines(self) -> "PurchaseTermsV1":
        _validate_cost_lines(self.cost_lines)
        return self


class RaasTermsV1(StrictContractModel):
    schema_version: Literal["raas-terms-v1"] = "raas-terms-v1"
    acquisition: Literal["RAAS"] = "RAAS"
    tariff_basis: CostBasisV1
    billing_basis: Literal["PER_ROBOT_MONTH", "PER_SITE_MONTH"]
    contract_months: Annotated[int, Field(gt=0)]
    renewal: Literal["SAME_TERMS_TO_HORIZON", "MANUAL_REVIEW"]
    deployment_mode: Literal["ALL_FLEET", "PHASED"]
    buyout: CommercialMoneyV1 | None = None
    cost_lines: list[CommercialCostLineV1] = Field(default_factory=list)
    responsibilities: list[ServiceResponsibilityV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lines(self) -> "RaasTermsV1":
        _validate_cost_lines(self.cost_lines)
        return self


def _validate_cost_lines(lines: list[CommercialCostLineV1]) -> None:
    ids = [item.line_id for item in lines]
    if len(ids) != len(set(ids)):
        raise ValueError("commercial line_id must be unique")
    new_service = [item for item in lines if item.category == "SERVICE"]
    if len(new_service) > 1:
        raise ValueError("new commercial input cannot provide multiple service bases")


AcquisitionTermsV1 = Annotated[PurchaseTermsV1 | RaasTermsV1, Field(discriminator="acquisition")]

CommercialIssueCode = Literal[
    "COMMERCIAL_PRICE_MISSING", "COMMERCIAL_SCOPE_MISMATCH",
    "VENDOR_QUOTE_EVIDENCE_MISMATCH", "CURRENCY_REQUIRED",
    "UNVERIFIED_VENDOR_QUOTE", "ORGANIZER_PRICE_MISMATCH",
    "COMMERCIAL_LINE_SCOPE_MISMATCH",
    "UNSUPPORTED_CURRENCY", "EXPLICIT_VAT_RATE_REQUIRED", "TAX_BASIS_REQUIRED",
    "AMBIGUOUS_COMMERCIAL_SOURCE", "ZERO_SEMANTICS_REQUIRED",
    "PROCUREMENT_ASSERTION_SCOPE_MISMATCH", "UNVERIFIED_PROCUREMENT_ASSERTION",
    "QUOTE_VALIDITY_UNKNOWN", "STALE_QUOTE", "STALE_PROCUREMENT_ASSERTION",
    "SERVICE_RESPONSIBILITIES_UNKNOWN",
]


class CurrencyAssumptionV1(StrictContractModel):
    currency: Literal["RUB"] = "RUB"
    provenance_id: StableId
    rationale: Annotated[str, Field(min_length=1)]
    applies_to_source_id: StableId
    confirmation_state: Literal["POLICY_ACCEPTED", "USER_CONFIRMED"]


class ProcurementAssertionV1(StrictContractModel):
    assertion_id: StableId
    kind: Literal["DISCONTINUED", "SUPPLY_RISK", "ORDER_AVAILABLE", "QUOTE_REQUIRED", "SALES_CHANNEL"]
    state: Literal["CONFIRMED", "NEGATED", "UNKNOWN"]
    scope: CommercialScopeV1
    evidence_ids: list[StableId] = Field(min_length=1)
    valid_until: date | None = None
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"] | None = None
    reason_code: StableId

    @model_validator(mode="after")
    def validate_risk(self) -> "ProcurementAssertionV1":
        if (self.kind == "SUPPLY_RISK") != (self.risk_level is not None):
            raise ValueError("risk_level is required only for SUPPLY_RISK")
        return self


class ProcurementReportRequestV1(StrictContractModel):
    schema_version: Literal["procurement-report-request-v1"] = "procurement-report-request-v1"
    model_id: Annotated[str, Field(min_length=1)]
    position_id: Annotated[str, Field(min_length=1)]
    acquisition: Literal["PURCHASE", "RAAS"]
    evaluation_date: date
    terms: list[AcquisitionTermsV1] = Field(default_factory=list)
    currency_assumption: CurrencyAssumptionV1 | None = None
    assertions: list[ProcurementAssertionV1] = Field(default_factory=list)


class CommercialResolutionV1(StrictContractModel):
    status: Literal["RESOLVED", "BLOCKED", "NOT_PROVIDED"]
    raw_money: CommercialMoneyV1 | None
    cash_gross_rub: DecimalString | None
    operation: Literal["IDENTITY", "APPLY_EXPLICIT_VAT", "NONE"]
    provenance_refs: list[StableId] = Field(default_factory=list)


class ProcurementGroundV1(StrictContractModel):
    code: StableId
    outcome: Literal["APPLIED", "IGNORED_STALE", "IGNORED_SCOPE", "INFORMATIONAL"]
    evidence_ids: list[StableId] = Field(default_factory=list)
    message: Annotated[str, Field(min_length=1)]


class ProcurementReportV1(StrictContractModel):
    schema_version: Literal["procurement-report-v1"] = "procurement-report-v1"
    model_id: Annotated[str, Field(min_length=1)]
    position_id: Annotated[str, Field(min_length=1)]
    acquisition: Literal["PURCHASE", "RAAS"]
    evaluation_date: date
    procurement_status: Literal[
        "DISCONTINUED", "SUPPLY_RISK", "CONFIRMED_AVAILABLE", "QUOTE_REQUIRED",
        "LIKELY_AVAILABLE", "UNVERIFIED",
    ]
    procurement_ready: bool
    supply_risk: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
    terms: AcquisitionTermsV1 | None = None
    money: CommercialResolutionV1
    responsibilities: list[ServiceResponsibilityV1] = Field(default_factory=list)
    blockers: list[CommercialIssueCode] = Field(default_factory=list)
    warnings: list[CommercialIssueCode] = Field(default_factory=list)
    grounds: list[ProcurementGroundV1] = Field(default_factory=list)
    commercial_policy_version: Literal["hackathon-commercial-policy-v1"] = "hackathon-commercial-policy-v1"

    @model_validator(mode="after")
    def validate_readiness(self) -> "ProcurementReportV1":
        if self.procurement_ready != (self.procurement_status == "CONFIRMED_AVAILABLE"):
            raise ValueError("only CONFIRMED_AVAILABLE is procurement-ready")
        return self
