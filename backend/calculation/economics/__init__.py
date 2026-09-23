"""Versioned C15-C18 economics engines."""

from calculation.economics.allocation import (
    MultiprocessAllocationRequestV1,
    MultiprocessAllocationResultV1,
    calculate_multiprocess_allocation,
)
from calculation.economics.cashflow import (
    FinancialAnalysisRequestV1,
    FinancialResultV1,
    calculate_financial_result,
)
from calculation.economics.raas import (
    RaasAnalysisRequestV1,
    RaasFinancialResultV1,
    calculate_raas_financials,
)

__all__ = [
    "FinancialAnalysisRequestV1",
    "FinancialResultV1",
    "MultiprocessAllocationRequestV1",
    "MultiprocessAllocationResultV1",
    "RaasAnalysisRequestV1",
    "RaasFinancialResultV1",
    "calculate_financial_result",
    "calculate_multiprocess_allocation",
    "calculate_raas_financials",
]
