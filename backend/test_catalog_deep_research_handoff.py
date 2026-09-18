from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.build_catalog_deep_research_handoff import (
    build,
    build_friendly_workspace,
    check,
    check_friendly_workspace,
)
from scripts.extract_catalog_deep_research_reports import (
    BEGIN_MARKER,
    END_MARKER,
    ReportExtractionError,
    extract_directory,
    extract_json_object,
)
from scripts.validate_catalog_deep_research_returns import (
    ReturnValidationError,
    validate_return,
)
from scripts.review_catalog_deep_research_returns import build_review, render_markdown
from scripts.audit_catalog_deep_research_packets import audit_packets


def test_handoff_has_exact_model_and_batch_coverage(tmp_path: Path):
    output = tmp_path / "handoff"
    build(output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    batches = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((output / "batches").glob("*.json"))
    ]

    assert manifest["deep_research_models"] == 36
    assert manifest["hybrid_models"] == 5
    assert len(batches) == 6
    assert len(list((output / "prompts").glob("*.prompt.md"))) == 6
    prompts = [
        path.read_text(encoding="utf-8")
        for path in (output / "prompts").glob("*.prompt.md")
    ]
    assert all("{{BATCH_ID}}" not in prompt for prompt in prompts)
    assert all("После подтверждения" not in prompt for prompt in prompts)
    assert all("покажи план" not in prompt.lower() for prompt in prompts)
    assert all("CATALOG_RESULT_JSON_BEGIN" in prompt for prompt in prompts)
    assert all("sandbox:/" in prompt for prompt in prompts)
    assert all("Публичный веб-поиск обязателен" in prompt for prompt in prompts)
    assert all("Работай только с прикреплёнными файлами" not in prompt for prompt in prompts)
    assert all("{{MODEL_COUNT}}" not in prompt for prompt in prompts)
    assert all("{{TARGET_COUNT}}" not in prompt for prompt in prompts)
    forbidden_failure_phrases = (
        "до создания обоих файлов",
        "создай скачиваемый файл",
        "После подтверждения проведи исследование",
        "Не открывай внешние URL",
    )
    assert all(
        phrase not in prompt
        for prompt in prompts
        for phrase in forbidden_failure_phrases
    )
    required_statuses = (
        "EXACT_MODEL_MATCH",
        "EXACT_MODEL_MATCH_WITH_CONFLICTS",
        "AMBIGUOUS_MODEL_MATCH",
        "MODEL_NOT_FOUND",
        "VERIFIED_OFFICIAL",
        "VERIFIED_AUTHORIZED_PARTNER",
        "CONFLICT",
        "NOT_FOUND",
    )
    assert all(status in prompt for prompt in prompts for status in required_statuses)
    assert sum(batch["model_count"] for batch in batches) == 41
    assert len(
        {
            model["organizer_id"]
            for batch in batches
            for model in batch["models"]
        }
    ) == 41
    assert all(
        model["research_targets"]
        for batch in batches
        for model in batch["models"]
    )
    assert manifest["prompt_revision"] == "audited-public-web-inline-json-v5"
    for batch in batches:
        prompt = (output / "prompts" / f"{batch['batch_id']}.prompt.md").read_text(
            encoding="utf-8"
        )
        target_count = sum(len(model["research_targets"]) for model in batch["models"])
        assert f"ровно {batch['model_count']} model results" in prompt
        assert f"{target_count} field results" in prompt


def test_each_upload_packet_is_unambiguous_and_self_contained(tmp_path: Path):
    output = tmp_path / "handoff"
    build(output)

    upload_dirs = sorted(path for path in (output / "upload").iterdir() if path.is_dir())
    assert len(upload_dirs) == 6
    for upload in upload_dirs:
        batch_id = upload.name
        assert {path.name for path in upload.iterdir()} == {
            f"01-BATCH-{batch_id}.json",
            "02-RUNTIME-CONTRACT.json",
            "03-RETURN-SCHEMA-REQUIRED.json",
            "COPY-PASTE-PROMPT.md",
            "RECOVERY-CURRENT-CHAT.md",
        }
        prompt = (upload / "COPY-PASTE-PROMPT.md").read_text(encoding="utf-8")
        recovery = (upload / "RECOVERY-CURRENT-CHAT.md").read_text(encoding="utf-8")
        assert f"01-BATCH-{batch_id}.json" in prompt
        assert "03-RETURN-SCHEMA-REQUIRED.json" in prompt
        assert "proposed research plan" in prompt
        assert "но не является итоговым результатом" in prompt
        assert "Продолжи уже начатое исследование" in recovery


def test_friendly_workspace_has_six_numbered_research_folders(tmp_path: Path):
    handoff = tmp_path / "handoff"
    friendly = tmp_path / "Исследования"
    build(handoff)
    build_friendly_workspace(friendly, handoff)

    expected_folders = {f"Исследование {number}" for number in range(1, 7)} | {
        "Результаты сюда"
    }
    assert {path.name for path in friendly.iterdir() if path.is_dir()} == expected_folders
    for number, folder in enumerate(
        sorted(
            (path for path in friendly.iterdir() if path.name.startswith("Исследование ")),
            key=lambda path: int(path.name.rsplit(" ", 1)[1]),
        ),
        start=1,
    ):
        files = {path.name for path in folder.iterdir() if path.is_file()}
        assert len(files) == 4
        assert "00-ПРОМПТ-СКОПИРОВАТЬ-В-ЧАТ.md" in files
        assert len([name for name in files if name.endswith(".json")]) == 3
        prompt = (folder / "00-ПРОМПТ-СКОПИРОВАТЬ-В-ЧАТ.md").read_text(
            encoding="utf-8"
        )
        assert "Публичный веб-поиск обязателен" in prompt
        assert "После подтверждения" not in prompt
    user_result = friendly / "Результаты сюда" / "deep-mobile-01.result.json"
    user_result.write_text("user data must survive regeneration", encoding="utf-8")
    build_friendly_workspace(friendly, handoff)
    assert user_result.read_text(encoding="utf-8") == "user data must survive regeneration"
    check_friendly_workspace(friendly, handoff)


def test_handoff_is_idempotent_and_preserves_positions(tmp_path: Path):
    output = tmp_path / "handoff"
    build(output)
    first = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    }
    build(output)
    second = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    }

    assert first == second
    check(output)
    assert sum(
        len(model["position_ids"])
        for path in (output / "batches").glob("*.json")
        for model in json.loads(path.read_text(encoding="utf-8"))["models"]
    ) == 44


def test_return_schema_requires_evidence_and_identity_fields(tmp_path: Path):
    output = tmp_path / "handoff"
    build(output)
    schema = json.loads(
        (output / "catalog-official-source-research-return-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    result_schema = schema["properties"]["results"]["items"]
    field_schema = result_schema["properties"]["field_results"]["items"]

    assert result_schema["additionalProperties"] is False
    assert field_schema["additionalProperties"] is False
    assert {"evidence", "evidence_status", "normalized_value"} <= set(
        field_schema["required"]
    )
    evidence_schema = field_schema["properties"]["evidence"]["items"]
    assert {"source_url", "source_locator", "raw_value", "accessed_at"} <= set(
        evidence_schema["required"]
    )


def test_return_validator_enforces_exact_target_coverage(tmp_path: Path):
    output = tmp_path / "handoff"
    build(output)
    batch_path = output / "batches" / "deep-other-01.json"
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    result = {
        "schema_version": "catalog-official-source-research-return-v1",
        "batch_id": batch["batch_id"],
        "research_completed_at": "2026-09-18T12:00:00+00:00",
        "results": [
            {
                "organizer_id": model["organizer_id"],
                "identity_status": "MODEL_NOT_FOUND",
                "matched_manufacturer": None,
                "matched_model": None,
                "field_results": [
                    {
                        "field_path": field,
                        "evidence_status": "NOT_FOUND",
                        "normalized_value": None,
                        "normalized_unit": None,
                        "evidence": [],
                        "confidence": 0.9,
                        "notes": "No exact official model source found.",
                    }
                    for field in model["research_targets"]
                ],
                "unresolved_issues": [],
            }
            for model in batch["models"]
        ],
    }
    result_path = output / "returns" / "deep-other-01.result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")

    summary = validate_return(batch_path, result_path)
    assert summary["models"] == 3
    assert summary["target_fields"] == 28
    result["results"][0]["identity_status"] = "AMBIGUOUS_MODEL_MATCH"
    result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(
        ReturnValidationError, match="ambiguous identity requires ambiguous field evidence"
    ):
        validate_return(batch_path, result_path)
    result["results"][0]["identity_status"] = "MODEL_NOT_FOUND"
    result["results"][0]["field_results"].pop()
    result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ReturnValidationError, match="target field coverage mismatch"):
        validate_return(batch_path, result_path)


def test_markdown_report_is_extracted_and_validated(tmp_path: Path):
    handoff = tmp_path / "handoff"
    reports = tmp_path / "reports"
    build(handoff)
    reports.mkdir()
    batch = json.loads(
        (handoff / "batches" / "deep-other-01.json").read_text(encoding="utf-8")
    )
    result = {
        "schema_version": "catalog-official-source-research-return-v1",
        "batch_id": batch["batch_id"],
        "research_completed_at": "2026-09-18T12:00:00+00:00",
        "results": [
            {
                "organizer_id": model["organizer_id"],
                "identity_status": "MODEL_NOT_FOUND",
                "matched_manufacturer": None,
                "matched_model": None,
                "field_results": [
                    {
                        "field_path": field,
                        "evidence_status": "NOT_FOUND",
                        "normalized_value": None,
                        "normalized_unit": None,
                        "evidence": [],
                        "confidence": 0.9,
                        "notes": "No exact official model source found.",
                    }
                    for field in model["research_targets"]
                ],
                "unresolved_issues": [],
            }
            for model in batch["models"]
        ],
    }
    report = reports / "deep-research-report arbitrary name.md"
    report.write_text(
        "# Human summary\n\n"
        + BEGIN_MARKER
        + "\n```json\n"
        + json.dumps(result, ensure_ascii=False, indent=2)
        + "\n```\n"
        + END_MARKER
        + "\n",
        encoding="utf-8",
    )

    summaries = extract_directory(handoff, reports, reports, require_complete=False)
    assert summaries[0]["batch_id"] == "deep-other-01"
    assert summaries[0]["models"] == 3
    assert summaries[0]["target_fields"] == 28
    assert (reports / "deep-other-01.result.json").is_file()


def test_markdown_report_requires_exact_machine_markers(tmp_path: Path):
    report = tmp_path / "broken.md"
    report.write_text("```json\n{}\n```\n", encoding="utf-8")
    with pytest.raises(ReportExtractionError, match="exactly one JSON marker pair"):
        extract_json_object(report)


def _not_found_return(batch: dict) -> dict:
    return {
        "schema_version": "catalog-official-source-research-return-v1",
        "batch_id": batch["batch_id"],
        "research_completed_at": "2026-09-18T12:00:00+00:00",
        "results": [
            {
                "organizer_id": model["organizer_id"],
                "identity_status": "MODEL_NOT_FOUND",
                "matched_manufacturer": None,
                "matched_model": None,
                "field_results": [
                    {
                        "field_path": field,
                        "evidence_status": "NOT_FOUND",
                        "normalized_value": None,
                        "normalized_unit": None,
                        "evidence": [],
                        "confidence": 0.5,
                        "notes": "Official manufacturer sources were checked; exact model fact was not found.",
                    }
                    for field in model["research_targets"]
                ],
                "unresolved_issues": [],
            }
            for model in batch["models"]
        ],
    }


def test_validator_rejects_private_citations_and_duplicate_evidence(tmp_path: Path):
    handoff = tmp_path / "handoff"
    build(handoff)
    batch_path = handoff / "batches" / "deep-other-01.json"
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    result = _not_found_return(batch)
    result_path = handoff / "returns" / "deep-other-01.result.json"
    result["results"][0]["field_results"][0]["notes"] = "bad \ue200cite marker"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ReturnValidationError, match="forbidden inline"):
        validate_return(batch_path, result_path)

    field = result["results"][0]["field_results"][0]
    result["results"][0]["identity_status"] = "EXACT_MODEL_MATCH"
    result["results"][0]["matched_manufacturer"] = "Example"
    result["results"][0]["matched_model"] = "Model"
    field.update(
        {
            "evidence_status": "VERIFIED_OFFICIAL",
            "normalized_value": "x",
            "notes": "Verified by the exact official model page.",
            "evidence": [
                {
                    "raw_value": "x",
                    "source_url": "https://example.com/model",
                    "source_title": "Model",
                    "publisher": "Example",
                    "source_type": "OFFICIAL_MODEL_PAGE",
                    "source_locator": "Specifications",
                    "publication_or_update_date": None,
                    "accessed_at": "2026-09-18",
                }
            ] * 2,
        }
    )
    result_path.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ReturnValidationError, match="duplicate evidence"):
        validate_return(batch_path, result_path)


def test_review_is_deterministic_and_never_authorizes_import(tmp_path: Path):
    handoff = tmp_path / "handoff"
    returns = tmp_path / "returns"
    build(handoff)
    returns.mkdir()
    batch = json.loads(
        (handoff / "batches" / "deep-other-01.json").read_text(encoding="utf-8")
    )
    (returns / "deep-other-01.result.json").write_text(
        json.dumps(_not_found_return(batch), ensure_ascii=False), encoding="utf-8"
    )
    first = build_review(handoff, returns, require_complete=False)
    second = build_review(handoff, returns, require_complete=False)
    assert first == second
    assert first["review_policy"] == {
        "mode": "REVIEW_ONLY",
        "writes_runtime_or_catalog": False,
        "automatic_acceptance": False,
        "known_facts_are_context_only": True,
    }
    assert first["coverage"]["models"] == 3
    assert first["coverage"]["target_fields"] == 28
    assert first["review_decision_counts"] == {"REMAINS_MISSING": 28}
    assert "не изменяет base, overlay, backend, fleet или runtime" in render_markdown(first)


def test_packet_cross_audit_covers_all_six_batches(tmp_path: Path):
    handoff = tmp_path / "handoff"
    build(handoff)
    report = audit_packets(
        handoff,
        Path("data/review/catalog-runtime-eligibility-report-v1.json"),
    )
    assert report["status"] == "PASS"
    assert report["source_eligibility_scope"] == {"models": 187, "positions": 223}
    assert report["research_scope"] == {
        "batches": 6,
        "models": 41,
        "positions": 44,
        "target_fields": 456,
    }
    assert report["invariants"]["runtime_switch_allowed"] is False
    assert report["invariants"]["capacity_formulas_in_scope"] is False
