from __future__ import annotations

from diagnostic_export import (
    TABLE_NAMES,
    _safe_value,
    record_http_event,
    request_events_snapshot,
)
from storage_models import Base


def test_export_allowlist_covers_mapped_tables_except_sessions():
    assert set(TABLE_NAMES) == set(Base.metadata.tables) - {"user_sessions"}


def test_nested_credential_keys_are_redacted_but_calculation_data_remain():
    value = {
        "password": "hidden",
        "commercial": {"monthly_gross_salary": "120000", "api_key": "hidden"},
        "roles": [{"csrf_token": "hidden", "headcount": 12}],
    }
    assert _safe_value(value) == {
        "password": "<redacted>",
        "commercial": {"monthly_gross_salary": "120000", "api_key": "<redacted>"},
        "roles": [{"csrf_token": "<redacted>", "headcount": 12}],
    }


def test_request_log_keeps_only_safe_metadata_and_error_class():
    record_http_event("POST", "/api/v2/calculation-intake/normalize", 404, 17)
    record_http_event("GET", "/ready", 200, 1)
    record_http_event("POST", "/api/v2/projects", 500, 21, "ValueError")
    record_http_event("POST", "/api/admin/diagnostics/export", 200, 3)
    events = request_events_snapshot()[-2:]
    assert len(events) == 2
    assert events[0]["status_code"] == 404
    assert events[0]["path"] == "/api/v2/calculation-intake/normalize"
    assert events[1]["error_type"] == "ValueError"
    assert all("body" not in item and "headers" not in item for item in events)
