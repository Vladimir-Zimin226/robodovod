from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from main import get_preset
from models import UserInput
from object_profiles import (
    EXPECTED_PROFILE_COUNTS,
    ObjectProfileError,
    build_official_preset,
    load_official_profiles,
    official_profile_version,
)
from pydantic import ValidationError

BUNDLE = (
    Path(__file__).resolve().parents[1] / "data" / "import" / "organizer-catalog-v4"
)


def test_official_profiles_preserve_all_metadata_and_exact_counts():
    profiles = load_official_profiles(BUNDLE)

    assert profiles.schema_version == "organizer-object-profiles-v1"
    assert {
        profile.code: len(profile.parameters()) for profile in profiles.object_types
    } == EXPECTED_PROFILE_COUNTS
    assert sum(EXPECTED_PROFILE_COUNTS.values()) == 138
    assert official_profile_version(BUNDLE).startswith(
        "organizer-object-profiles-v1:sha256:"
    )
    for profile in profiles.object_types:
        for parameter in profile.parameters():
            assert parameter.source_file
            assert parameter.source_sheet
            assert parameter.source_row > 0
            assert parameter.unit


@pytest.mark.parametrize(
    ("alias", "profile_code", "count", "object_type"),
    [
        ("retail", "warehouse", 42, "retail"),
        ("airport", "airport", 39, "airport"),
        ("clinic", "medical_facility", 57, "clinic"),
    ],
)
def test_official_presets_are_valid_inputs_with_complete_provenance(
    alias: str, profile_code: str, count: int, object_type: str
):
    result = build_official_preset(alias, BUNDLE)

    assert result["profile_code"] == profile_code
    assert result["parameter_count"] == count
    assert result["normalized_input"]["object_type"] == object_type
    UserInput.model_validate(result["normalized_input"])
    assert set(result["normalized_input"]) == set(result["provenance"])
    assert {item["kind"] for item in result["provenance"].values()} <= {
        "PRESET",
        "CALCULATED",
        "ASSUMED",
    }
    assert result["provenance"]["fte_cost_rub"]["kind"] == "CALCULATED"


def test_legacy_preset_endpoint_is_derived_from_official_profile(monkeypatch):
    monkeypatch.setenv("OFFICIAL_CATALOG_BUNDLE_PATH", str(BUNDLE))

    assert (
        get_preset("retail")
        == build_official_preset("warehouse", BUNDLE)["normalized_input"]
    )


def test_profile_checksum_mismatch_is_rejected(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    shutil.copy2(BUNDLE / "manifest.json", bundle / "manifest.json")
    profile_path = bundle / "object_profiles.json"
    shutil.copy2(BUNDLE / "object_profiles.json", profile_path)
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    payload["object_types"][0]["groups"][0]["parameters"][0]["default_value"] = 1
    profile_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ObjectProfileError, match="checksum or size"):
        load_official_profiles(bundle)


def test_user_input_still_rejects_unrecognized_profile_metadata():
    preset = build_official_preset("retail", BUNDLE)
    with pytest.raises(ValidationError):
        UserInput.model_validate(preset)
