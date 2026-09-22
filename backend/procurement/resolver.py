"""C13 commercial resolver over one immutable catalog snapshot."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from catalog_repository import CatalogPositionDTO, CatalogSnapshotDTO, ProcurementOptionDTO
from procurement.contracts import (
    CommercialMoneyV1,
    CommercialResolutionV1,
    CommercialScopeV1,
    CommercialSourceV1,
    ProcurementAssertionV1,
    ProcurementGroundV1,
    ProcurementReportRequestV1,
    ProcurementReportV1,
)


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _position(request: ProcurementReportRequestV1, snapshot: CatalogSnapshotDTO) -> CatalogPositionDTO:
    if snapshot.version.status != "PUBLISHED":
        raise ValueError("commercial source must be an immutable published snapshot")
    position = next((item for item in snapshot.positions if item.id == request.position_id), None)
    if position is None or position.model.id != request.model_id:
        raise ValueError("model/position is absent from the published commercial snapshot")
    return position


def _catalog_money(position: CatalogPositionDTO, option: ProcurementOptionDTO) -> CommercialMoneyV1 | None:
    if option.amount is None:
        return None
    if option.amount == 0:
        return None
    tax_basis = {
        "ORGANIZER_ASSUMPTION_INCLUDED": "CASH_GROSS_RUB",
        "INCLUDED": "CASH_GROSS_RUB",
        "EXCLUDED": "NET_RUB",
    }.get(option.vat_status, "UNKNOWN")
    return CommercialMoneyV1(
        raw_amount=_decimal(option.amount),
        currency=option.currency or "UNKNOWN",
        tax_basis=tax_basis,
        vat_rate=None if option.vat_rate is None else _decimal(option.vat_rate),
        source=CommercialSourceV1(
            kind="ORGANIZER_DATASET", source_id=option.id or f"catalog-price:{position.id}",
            evidence_ids=[] if option.evidence_id is None else [option.evidence_id],
            observed_on=option.observed_on, valid_until=option.valid_until,
        ),
        scope=CommercialScopeV1(
            model_id=position.model.id, position_id=position.id,
            procurement_option_id=option.id, region=position.applicability.region,
            boundary="BARE_EQUIPMENT",
        ),
    )


def _scope_matches(scope: CommercialScopeV1, request: ProcurementReportRequestV1) -> bool:
    return scope.model_id == request.model_id and scope.position_id == request.position_id


def _resolve_money(
    money: CommercialMoneyV1 | None,
    request: ProcurementReportRequestV1,
    known_evidence: set[str],
    catalog_money: CommercialMoneyV1 | None,
    verified_quotes: dict[str, CommercialMoneyV1],
    blockers: list[str],
    warnings: list[str],
    grounds: list[ProcurementGroundV1],
) -> tuple[CommercialResolutionV1, bool]:
    if money is None:
        blockers.append("COMMERCIAL_PRICE_MISSING")
        return CommercialResolutionV1(
            status="NOT_PROVIDED", raw_money=None, cash_gross_rub=None,
            operation="NONE", provenance_refs=[],
        ), False
    if not _scope_matches(money.scope, request):
        blockers.append("COMMERCIAL_SCOPE_MISMATCH")
        grounds.append(ProcurementGroundV1(
            code="commercial-scope-mismatch", outcome="IGNORED_SCOPE",
            evidence_ids=money.source.evidence_ids,
            message="Commercial money belongs to another model or position",
        ))
        return CommercialResolutionV1(
            status="BLOCKED", raw_money=money, cash_gross_rub=None,
            operation="NONE", provenance_refs=[money.source.source_id],
        ), False
    if money.source.kind == "ORGANIZER_DATASET" and (
        catalog_money is None
        or catalog_money.model_dump(mode="json") != money.model_dump(mode="json")
    ):
        blockers.append("ORGANIZER_PRICE_MISMATCH")
        return CommercialResolutionV1(
            status="BLOCKED", raw_money=money, cash_gross_rub=None,
            operation="NONE", provenance_refs=[money.source.source_id],
        ), False
    if money.source.kind == "VENDOR_QUOTE" and not set(money.source.evidence_ids) <= known_evidence:
        blockers.append("VENDOR_QUOTE_EVIDENCE_MISMATCH")
        return CommercialResolutionV1(
            status="BLOCKED", raw_money=money, cash_gross_rub=None,
            operation="NONE", provenance_refs=[money.source.source_id],
        ), False
    trusted_quote = verified_quotes.get(money.source.source_id)
    if money.source.kind == "VENDOR_QUOTE" and (
        trusted_quote is None
        or trusted_quote.model_dump(mode="json") != money.model_dump(mode="json")
    ):
        blockers.append("UNVERIFIED_VENDOR_QUOTE")
        return CommercialResolutionV1(
            status="BLOCKED", raw_money=money, cash_gross_rub=None,
            operation="NONE", provenance_refs=[money.source.source_id],
        ), False

    currency = money.currency
    provenance = [money.source.source_id]
    if currency == "UNKNOWN":
        assumption = request.currency_assumption
        if assumption is None or assumption.applies_to_source_id != money.source.source_id:
            blockers.append("CURRENCY_REQUIRED")
            return CommercialResolutionV1(
                status="BLOCKED", raw_money=money, cash_gross_rub=None,
                operation="NONE", provenance_refs=provenance,
            ), False
        currency = assumption.currency
        provenance.append(assumption.provenance_id)
        grounds.append(ProcurementGroundV1(
            code="explicit-currency-assumption", outcome="APPLIED", evidence_ids=[],
            message=assumption.rationale,
        ))
    if currency != "RUB":
        blockers.append("UNSUPPORTED_CURRENCY")
        return CommercialResolutionV1(
            status="BLOCKED", raw_money=money, cash_gross_rub=None,
            operation="NONE", provenance_refs=provenance,
        ), False

    amount = Decimal(money.raw_amount)
    if money.tax_basis == "CASH_GROSS_RUB":
        gross = amount
        operation = "IDENTITY"
    elif money.tax_basis == "NET_RUB":
        if money.vat_rate is None:
            blockers.append("EXPLICIT_VAT_RATE_REQUIRED")
            return CommercialResolutionV1(
                status="BLOCKED", raw_money=money, cash_gross_rub=None,
                operation="NONE", provenance_refs=provenance,
            ), False
        gross = amount * (Decimal(1) + Decimal(money.vat_rate))
        operation = "APPLY_EXPLICIT_VAT"
    else:
        blockers.append("TAX_BASIS_REQUIRED")
        return CommercialResolutionV1(
            status="BLOCKED", raw_money=money, cash_gross_rub=None,
            operation="NONE", provenance_refs=provenance,
        ), False

    active_quote = money.source.kind == "VENDOR_QUOTE"
    if active_quote and money.source.valid_until is None:
        warnings.append("QUOTE_VALIDITY_UNKNOWN")
        active_quote = False
    elif active_quote and money.source.valid_until < request.evaluation_date:
        warnings.append("STALE_QUOTE")
        active_quote = False
        grounds.append(ProcurementGroundV1(
            code="stale-vendor-quote", outcome="IGNORED_STALE",
            evidence_ids=money.source.evidence_ids,
            message="Vendor quote expired before the evaluation date",
        ))
    return CommercialResolutionV1(
        status="RESOLVED", raw_money=money, cash_gross_rub=_decimal(gross),
        operation=operation, provenance_refs=provenance,
    ), active_quote


def resolve_procurement_report(
    request: ProcurementReportRequestV1,
    snapshot: CatalogSnapshotDTO,
) -> ProcurementReportV1:
    position = _position(request, snapshot)
    option = position.procurement_option
    known_evidence = {item for item in [option.evidence_id] if item is not None}
    catalog_money = _catalog_money(position, option)
    verified_quotes = {
        item.source.source_id: item
        for item in (CommercialMoneyV1.model_validate(raw) for raw in option.verified_quotes)
    }
    trusted_assertions = {
        item.assertion_id: item
        for item in (ProcurementAssertionV1.model_validate(raw) for raw in option.procurement_assertions)
    }
    blockers: list[str] = []
    warnings: list[str] = []
    grounds: list[ProcurementGroundV1] = []

    applicable_terms = [item for item in request.terms if item.acquisition == request.acquisition]
    if len(applicable_terms) > 1:
        blockers.append("AMBIGUOUS_COMMERCIAL_SOURCE")
        selected_terms = None
        money = None
    elif applicable_terms:
        selected_terms = applicable_terms[0]
        if selected_terms.acquisition == "PURCHASE":
            money = selected_terms.primary_price
        elif selected_terms.tariff_basis.kind in {"FIXED_TOTAL", "PER_ROBOT"}:
            money = selected_terms.tariff_basis.money
        else:
            money = None
    else:
        selected_terms = None
        money = catalog_money if request.acquisition == option.mode else None

    if selected_terms is not None:
        scoped_money = []
        for line in selected_terms.cost_lines:
            if line.basis.kind in {"FIXED_TOTAL", "PER_ROBOT"}:
                scoped_money.append(line.basis.money)
        if selected_terms.acquisition == "RAAS" and selected_terms.buyout is not None:
            scoped_money.append(selected_terms.buyout)
        if any(not _scope_matches(item.scope, request) for item in scoped_money):
            blockers.append("COMMERCIAL_LINE_SCOPE_MISMATCH")

    if option.amount == 0 and selected_terms is None:
        blockers.append("ZERO_SEMANTICS_REQUIRED")
    resolution, active_quote = _resolve_money(
        money, request, known_evidence, catalog_money, verified_quotes,
        blockers, warnings, grounds,
    )

    applied: dict[str, list] = {}
    risk_level = "UNKNOWN"
    risk_order = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    for assertion in request.assertions:
        if not _scope_matches(assertion.scope, request):
            blockers.append("PROCUREMENT_ASSERTION_SCOPE_MISMATCH")
            grounds.append(ProcurementGroundV1(
                code=assertion.reason_code, outcome="IGNORED_SCOPE",
                evidence_ids=assertion.evidence_ids,
                message="Procurement assertion belongs to another model or position",
            ))
            continue
        trusted = trusted_assertions.get(assertion.assertion_id)
        if (
            trusted is None
            or trusted.model_dump(mode="json") != assertion.model_dump(mode="json")
            or not set(assertion.evidence_ids) <= known_evidence
        ):
            blockers.append("UNVERIFIED_PROCUREMENT_ASSERTION")
            continue
        if assertion.valid_until is not None and assertion.valid_until < request.evaluation_date:
            warnings.append("STALE_PROCUREMENT_ASSERTION")
            grounds.append(ProcurementGroundV1(
                code=assertion.reason_code, outcome="IGNORED_STALE",
                evidence_ids=assertion.evidence_ids,
                message="Procurement assertion expired before the evaluation date",
            ))
            continue
        grounds.append(ProcurementGroundV1(
            code=assertion.reason_code, outcome="APPLIED" if assertion.state == "CONFIRMED" else "INFORMATIONAL",
            evidence_ids=assertion.evidence_ids,
            message=f"{assertion.kind} is {assertion.state}",
        ))
        if assertion.state == "CONFIRMED":
            applied.setdefault(assertion.kind, []).append(assertion)
            if assertion.kind == "SUPPLY_RISK" and risk_order[assertion.risk_level] > risk_order[risk_level]:
                risk_level = assertion.risk_level

    if applied.get("DISCONTINUED"):
        procurement_status = "DISCONTINUED"
    elif applied.get("SUPPLY_RISK"):
        procurement_status = "SUPPLY_RISK"
    elif active_quote and resolution.status == "RESOLVED" and applied.get("ORDER_AVAILABLE"):
        procurement_status = "CONFIRMED_AVAILABLE"
    elif applied.get("QUOTE_REQUIRED") or option.price_status == "QUOTE_REQUIRED":
        procurement_status = "QUOTE_REQUIRED"
    elif applied.get("SALES_CHANNEL"):
        procurement_status = "LIKELY_AVAILABLE"
    else:
        procurement_status = "UNVERIFIED"

    responsibilities = [] if selected_terms is None else selected_terms.responsibilities
    if not responsibilities:
        warnings.append("SERVICE_RESPONSIBILITIES_UNKNOWN")
    return ProcurementReportV1(
        model_id=request.model_id, position_id=request.position_id,
        acquisition=request.acquisition, evaluation_date=request.evaluation_date,
        procurement_status=procurement_status,
        procurement_ready=procurement_status == "CONFIRMED_AVAILABLE",
        supply_risk=risk_level, terms=selected_terms, money=resolution,
        responsibilities=responsibilities,
        blockers=sorted(set(blockers)), warnings=sorted(set(warnings)), grounds=grounds,
    )
