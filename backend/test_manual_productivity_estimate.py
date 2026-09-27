from calculation.labour import manual_productivity_estimate
from calculation_contracts import NormalizedProcess
from test_economics_orchestrator import _capacity_request


def _process(*, demand="220", distance="120", hours="11"):
    raw = _capacity_request().process.model_dump(mode="json")
    for path, value in ((raw["demand"], demand), (raw["route_distance"], distance),
                        (raw["schedule"]["shift_hours"], hours)):
        path["normalized_value"] = path["raw_value"] = value
    return NormalizedProcess.model_validate(raw)


def test_route_estimate_uses_registry_and_changes_with_distance_and_shift():
    first = manual_productivity_estimate(_process())
    assert first["status"] == "ESTIMATE"
    assert first["value"] == "86.4"
    assert first["unit"] == "pallet/shift"
    assert first["inputs"]["manual_speed_m_s"]
    assert first["inputs"]["manual_exchange_s"]
    assert first["inputs"]["units_per_trip"] == "1"
    assert len(first["source_refs"]) == 5
    assert manual_productivity_estimate(_process(demand="2000"))["value"] == first["value"]
    assert manual_productivity_estimate(_process(distance="60"))["value"] != first["value"]
    assert manual_productivity_estimate(_process(hours="8"))["value"] != first["value"]


def test_unsupported_kind_has_no_invented_norm_and_cleaning_has_separate_basis():
    raw = _process().model_dump(mode="json")
    raw.update(quantity_kind="ITEM", scope="REFERENCE_ONLY", process_code="warehouse_inventory", route_distance=None)
    raw["demand"].update(raw_unit="item/day", unit="item/day")
    assert manual_productivity_estimate(NormalizedProcess.model_validate(raw))["status"] == "UNSUPPORTED"
    raw.update(quantity_kind="SQUARE_METER", scope="CLEANING_AREA", process_code="warehouse_cleaning")
    raw["demand"].update(raw_unit="m2/day", unit="m2/day")
    cleaning = manual_productivity_estimate(NormalizedProcess.model_validate(raw))
    assert cleaning["status"] == "ESTIMATE"
    assert "mechanized_rate_m2_h" in cleaning["inputs"]
    assert cleaning["unit"] == "m2/shift"
