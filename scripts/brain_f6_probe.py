"""Reproducible, credential-free Brain request measurements for F6."""

from __future__ import annotations

import json
import json as json_module
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import brain_api as brain

GOLDEN = [
    "На складе перевозим 220 паллет в сутки на 120 м.",
    "В аэропорту убираем 10000 м² за сутки.",
    "В клинике перевозим 35 тележек за смену.",
]


def main() -> None:
    captures = []

    def post(_url, *, json: dict, headers: dict, timeout: tuple) -> SimpleNamespace:
        assert headers["Authorization"] == "Api-Key probe-key"
        assert timeout == (5, 50)
        captures.append(json)
        answer = {"message": "Уточните следующий параметр.", "field_updates": [],
                  "process_updates": [], "next_action": "ask", "question": None}
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {
            "choices": [{"finish_reason": "stop", "message": {"content": json_module.dumps(answer)}}],
            "usage": {"prompt_tokens": 760, "completion_tokens": 45},
        })

    rows = []
    with patch.dict("os.environ", {"YC_API_KEY": "probe-key", "YC_FOLDER_ID": "probe-folder"}), patch.object(brain.requests, "post", post):
        for message in GOLDEN:
            started = time.perf_counter()
            answer, usage = brain._call_model(message, {})
            body = captures[-1]
            legacy = json.loads(json.dumps(body))
            legacy["messages"][1]["content"] = json.dumps({"profile": {"fields": {
                "operations_per_day": {"value": "220", "unit": "pallet/day", "provenance": "user", "confirmed_by_user": "False", "raw_text": "220 паллет в сутки"},
                "avg_distance_m": {"value": "120", "unit": "m", "provenance": "user", "confirmed_by_user": "False", "raw_text": "120 м"},
            }, "active_processes": ["warehouse_receiving_shipping"]}, "message": message}, ensure_ascii=False)
            current_bytes = len(json.dumps(body, ensure_ascii=False).encode())
            legacy_bytes = len(json.dumps(legacy, ensure_ascii=False).encode())
            rows.append({"dialogue": message, "status": "MODEL", "finish_reason": usage["finish_reason"],
                         "request_bytes": current_bytes, "legacy_context_request_bytes": legacy_bytes,
                         "context_reduction_bytes": legacy_bytes - current_bytes,
                         "provider_stub_ms": usage["provider_ms"], "validation_ms": usage["validation_ms"],
                         "application_total_ms": round((time.perf_counter() - started) * 1000, 2),
                         "input_tokens_mocked": usage["input"], "output_tokens_mocked": usage["output"],
                         "valid_json": bool(answer.message)})
    input_tokens = sum(row["input_tokens_mocked"] for row in rows)
    output_tokens = sum(row["output_tokens_mocked"] for row in rows)
    report = {"mode": "SYNTHETIC_MOCKED_PROVIDER", "actual_external_calls": 0,
              "research_call_budget": 10, "model": brain.MODEL,
              "generation": {"temperature": 0.1, "max_tokens": brain.MODEL_OUTPUT_TOKENS,
                             "response_format": "json_schema", "stream": False},
              "rows": rows, "mocked_usage_total": {"input": input_tokens, "output": output_tokens},
              "estimated_rub_at_documented_rates_if_usage_were_real": round(input_tokens * 0.3 / 1000 + output_tokens * 0.5 / 1000, 4),
              "estimated_rub_for_ten_calls_at_mocked_average_usage": round((input_tokens * 0.3 / 1000 + output_tokens * 0.5 / 1000) / 3 * 10, 4),
              "external_sla_measured": False}
    output = ROOT / "docs" / "planning" / "assets" / "f6" / "probe.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
