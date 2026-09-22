"""Small deterministic trace helpers shared by pure capacity engines."""

from __future__ import annotations

from calculation_contracts import (
    CalculationTrace,
    FormulaNode,
    QuantityKind,
    ResultQuantity,
    Unit,
    calculation_trace_digest,
    semantic_digest,
)

from .quantities import canonical


def result_quantity(value, unit: Unit, kind: QuantityKind) -> ResultQuantity:
    return ResultQuantity(value=canonical(value), unit=unit, quantity_kind=kind)


def formula_node(
    formula_id: str,
    dependencies: list[str],
    inputs: list[str],
    *,
    applicability_domain: str,
) -> FormulaNode:
    source = {"formula_id": formula_id, "version": "hackathon-calculation-policy-v1"}
    return FormulaNode(
        node_id=f"node.{formula_id.lower()}",
        formula_id=formula_id,
        formula_version="calculation-formulas-v1",
        source_refs=["R03", "POLICY_V1"],
        source_digest=semantic_digest(source),
        template_id=f"template.{formula_id.lower()}",
        applicability_domain=applicability_domain,
        dependency_node_ids=dependencies,
        input_refs=inputs,
    )


def finalize_trace(trace: CalculationTrace) -> CalculationTrace:
    payload = trace.model_copy(deep=True)
    payload.replay.trace_content_digest = calculation_trace_digest(payload)
    return payload
