"""F4 filter/context contracts, including hard failures and unknown evidence."""

import copy

import pytest
from catalog_selection import annotate, filter_items


def position(**changes):
    item = {
        "position_id": "p.test",
        "model_id": "m.test",
        "name": "Test",
        "manufacturer": "Maker",
        "type_code": "AMR",
        "system_family": "BRS",
        "maturity_status": "OPERATION",
        "calculation_ready": True,
        "calculation_profile": "TRANSPORT_CYCLE_V1",
        "use_cases": ["Внутрискладская логистика"],
        "industries": ["Торговля"],
        "applicability": [],
        "source_row_number": 1,
        "selectable": False,
        "facts": [
            {
                "code": "payload",
                "value": 1,
                "unit": "t",
                "status": "CORROBORATED",
                "evidence_id": "e.payload",
            },
            {
                "code": "min_aisle_width",
                "value": 900,
                "unit": "mm",
                "status": "CORROBORATED",
                "evidence_id": "e.aisle",
            },
        ],
        "purchase": {
            "amount": 1000000,
            "currency": "RUB",
            "price_status": "NORMALIZED",
        },
    }
    item.update(changes)
    return item


@pytest.mark.parametrize(
    "kwargs",
    [
        {"q": "missing"},
        {"system_family": "BAS"},
        {"type_code": "DRONE"},
        {"manufacturer": "Other"},
        {"maturity": "RND"},
        {"quality": "unknown"},
        {"calculation_participation": "requires_data"},
        {"selectable": True},
        {"price_min": 1000001},
        {"price_max": 999999},
        {"payload_min": 1001},
        {"payload_max": 999},
        {"aisle_max": 0.8},
        {"object_kind": "airport"},
        {"object_kind": "clinic"},
        {"object_kind": "warehouse", "process_code": "warehouse_cleaning"},
    ],
)
def test_known_excluded_filter_values(kwargs):
    assert not filter_items([position()], **kwargs)


def test_combined_filters_units_query_sort_and_reset():
    items = [position(name="Z", source_row_number=2), position(name="A")]
    result = filter_items(
        items,
        q=" maker ",
        object_kind="warehouse",
        process_code="warehouse_receiving_shipping",
        maturity="OPERATION",
        quality="verified",
        price_min=999999,
        payload_min=1000,
        aisle_max=0.9,
    )
    assert [p["name"] for p in result] == ["A", "Z"]
    assert result[0]["normalized_specs"]["payload"]["value"] == "1000"
    assert len(filter_items(items)) == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"payload_min": 0},
        {"aisle_max": 0},
        {"price_min": 0},
        {"object_kind": "warehouse"},
    ],
)
def test_unknown_never_zero_and_can_be_included(kwargs):
    item = position(facts=[], purchase=None, use_cases=[], industries=["Торговля"])
    assert not filter_items([item], **kwargs)
    assert (
        filter_items([item], include_unknown=True, **kwargs)[0]["selection"]["status"]
        == "REQUIRES_CHECK"
    )


@pytest.mark.parametrize(
    "context,check",
    [({"max_payload_kg": "1001"}, "payload"), ({"min_aisle_width_m": "0.8"}, "aisle")],
)
def test_hard_fail_never_pass_or_calculation_compatible(context, check):
    item = position()
    previous = copy.deepcopy(item)
    result = annotate(item, "warehouse", "warehouse_receiving_shipping", context)
    assert result["selection"]["status"] == "EXCLUDED"
    assert not result["selection"]["calculation_compatible"]
    assert (
        next(c for c in result["selection"]["checks"] if c["check_id"] == check)[
            "status"
        ]
        == "FAIL"
    )
    assert item == previous


def test_conflicting_unverified_nonfinite_and_unknown_units_are_not_safe():
    for change in (
        {"value": "NaN"},
        {"unit": "lb"},
        {"status": "UNKNOWN"},
        {"evidence_id": None},
    ):
        item = position()
        item["facts"][0].update(change)
        result = annotate(
            item,
            "warehouse",
            "warehouse_receiving_shipping",
            {"max_payload_kg": "2000"},
        )
        assert (
            next(
                c for c in result["selection"]["checks"] if c["check_id"] == "payload"
            )["status"]
            == "UNKNOWN"
        )
    item = position()
    item["facts"].append({**item["facts"][0], "value": 2})
    assert annotate(item)["normalized_specs"]["payload"]["value"] is None


def test_industry_is_hint_not_confirmed_applicability():
    item = annotate(
        position(use_cases=[], industries=["Здравоохранение"]), "clinic", "clinic_food"
    )
    assert item["taxonomy"]["objects"] == []
    assert item["selection"]["status"] == "REQUIRES_CHECK"
    assert (
        next(c for c in item["selection"]["checks"] if c["check_id"] == "object-kind")[
            "status"
        ]
        == "UNKNOWN"
    )


def test_missing_manufacturer_type_maturity_and_availability_are_explicit():
    item = position(
        manufacturer=None,
        type_code=None,
        maturity_status=None,
        admin_metadata={"availability": "UNKNOWN"},
    )
    for key in ("manufacturer", "type_code", "maturity"):
        assert filter_items([item], **{key: "__unknown"})
        assert not filter_items([position()], **{key: "__unknown"})
    assert filter_items([item], availability="unknown")
    assert not filter_items([item], availability="OPERATION")


def test_confirmed_safety_incompatibility_is_excluded():
    item = position(
        calculation_profile="CLEANING_AREA_V1",
        use_cases=["Уборка склада"],
        facts=[
            {
                "code": "sterilization_supported",
                "value": False,
                "unit": "1",
                "status": "VERIFIED_OFFICIAL",
                "evidence_id": "e.cleaning",
            }
        ],
    )
    result = annotate(
        item, "warehouse", "warehouse_cleaning", {"sanitization_required": True}
    )
    assert result["selection"]["status"] == "EXCLUDED"
    assert (
        next(
            c for c in result["selection"]["checks"] if c["check_id"] == "sanitization"
        )["status"]
        == "FAIL"
    )
