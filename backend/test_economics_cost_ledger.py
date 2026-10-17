"""New financial runs keep commercial unknowns distinct from confirmed zero."""

from copy import deepcopy
import json

from economics_cost_ledger import parse_implementation_lines
from economics_partial import INPUT_VERSION_V7, execute_partial_economics_v2
from test_economics_partial import _context
from test_evgeny_project import project_input


def _line(status, amount=None, source_ref=None, explanation=None):
    return {"status": status, "amount": amount, "source_ref": source_ref,
            "explanation": explanation}


def _raw():
    raw = project_input()
    raw["schema_version"] = INPUT_VERSION_V7
    raw["implementation_cost_total_gross"] = "0"
    raw["implementation_lines"] = {
        "DELIVERY": _line("USER_ESTIMATE", "150000", "Смета 17.10.2026"),
        "COMMISSIONING": _line("EXPLICIT_ZERO", "0", explanation="Выполнит свой персонал"),
        "INTEGRATION": _line("POLICY_ASSUMPTION", "220000", "Допущение проекта", "Согласовать с ИТ"),
    }
    return raw


def test_missing_commissioning_blocks_purchase_npv_without_erasing_known_subtotal():
    snapshot, context = _context()
    raw = _raw()
    raw["implementation_lines"]["COMMISSIONING"] = _line("UNKNOWN")
    before = deepcopy(raw)
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    json.dumps(result, sort_keys=True)
    assert raw == before
    assert result["implementation_coverage"]["known_subtotal_gross_rub"] == "370000.00"
    assert result["implementation_coverage"]["status"] == "PARTIAL"
    assert "implementation_lines.commissioning" in result["branches"]["purchase"]["required_fields"]
    assert result["branches"]["purchase"]["status"] == "NOT_CALCULATED"
    assert not any(item["acquisition"] == "PURCHASE" for item in result["scenarios"])


def test_explicit_zero_and_itemized_costs_reach_full_result():
    snapshot, context = _context()
    result = execute_partial_economics_v2(_raw(), snapshot, context).result_snapshot
    json.dumps(result, sort_keys=True)
    assert result["implementation_coverage"]["status"] == "COMPLETE"
    assert result["implementation_coverage"]["known_subtotal_gross_rub"] == "370000.00"
    assert len(result["scenarios"]) == 6
    purchase = next(item for item in result["scenarios"] if item["acquisition"] == "PURCHASE")
    assert purchase["report_facts"]["project_npv"]["value"] is not None
    old = project_input()
    old["implementation_cost_total_gross"] = "370000"
    old_result = execute_partial_economics_v2(old, snapshot, context).result_snapshot
    old_purchase = next(item for item in old_result["scenarios"] if item["acquisition"] == "PURCHASE")
    assert purchase["report_facts"]["project_npv"]["value"] == old_purchase["report_facts"]["project_npv"]["value"]


def test_invalid_amount_never_becomes_confirmed_zero():
    lines = _raw()["implementation_lines"]
    lines["DELIVERY"] = _line("USER_ESTIMATE", "not-money", "Смета")
    parsed, missing, issues = parse_implementation_lines(lines, None)
    assert parsed["DELIVERY"]["status"] == "UNKNOWN"
    assert "implementation_lines.delivery" in missing
    assert issues[0]["code"] == "COST_LINE_INVALID"


def test_missing_other_implementation_work_is_not_silently_zero():
    snapshot, context = _context()
    raw = _raw()
    raw["implementation_cost_total_gross"] = None
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    assert result["branches"]["purchase"]["status"] == "NOT_CALCULATED"
    assert "implementation_cost_total_gross" in result["branches"]["purchase"]["required_fields"]
    assert result["implementation_coverage"]["status"] == "PARTIAL"


def test_unknown_percentage_basis_keeps_implementation_coverage_partial():
    snapshot, context = _context()
    raw = _raw()
    raw["implementation_mode"] = "PERCENT"
    raw["implementation_percent"] = "5"
    raw["organizer_price_currency_rub_confirmed"] = False
    result = execute_partial_economics_v2(raw, snapshot, context).result_snapshot
    assert result["implementation_coverage"]["status"] == "PARTIAL"
    assert result["branches"]["purchase"]["status"] == "NOT_CALCULATED"


def test_included_cost_requires_positive_named_aggregate():
    lines = _raw()["implementation_lines"]
    lines["DELIVERY"] = {"status": "INCLUDED", "amount": None,
                         "included_in": "implementation_cost_total_gross",
                         "explanation": "Входит в общий договор"}
    parsed, missing, _ = parse_implementation_lines(lines, "0")
    assert parsed["DELIVERY"]["status"] == "UNKNOWN"
    assert "implementation_lines.delivery" in missing
    parsed, missing, _ = parse_implementation_lines(lines, "500000")
    assert parsed["DELIVERY"]["status"] == "INCLUDED"
    assert "implementation_lines.delivery" not in missing
