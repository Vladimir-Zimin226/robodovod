"""Validated official object profiles and calculation-preset projections.

The organizer workbook is represented by the committed, checksummed JSON bundle.
All 138 parameters remain available as metadata.  Only explicit mappings below
are projected into the smaller legacy ``UserInput`` contract; every projected
value carries PRESET, CALCULATED or ASSUMED provenance.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_BUNDLE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "import" / "organizer-catalog-v4"
)
PROFILE_FILE = "object_profiles.json"
EXPECTED_PROFILE_COUNTS = {
    "warehouse": 42,
    "airport": 39,
    "medical_facility": 57,
}
PROFILE_ALIASES = {
    "warehouse": "warehouse",
    "retail": "warehouse",
    "airport": "airport",
    "medical_facility": "medical_facility",
    "clinic": "medical_facility",
}
APPLICATION_OBJECT_TYPES = {
    "warehouse": "retail",
    "airport": "airport",
    "medical_facility": "clinic",
}


class ObjectProfileError(RuntimeError):
    """Raised when the committed official profile cannot be trusted."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProfileParameter(StrictModel):
    parameter_code: str = Field(min_length=1)
    label: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    data_type: Literal["number", "string"]
    default_value: int | float | str
    min_value: int | float | str | None = None
    max_value: int | float | str | None = None
    required: bool | None
    allowed_values: list[int | float | str] | None
    source_note: str | None = None
    source_file: str = Field(min_length=1)
    source_sheet: str = Field(min_length=1)
    source_row: int = Field(ge=1)
    confidence: Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    normalization_notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_value_contract(self) -> ProfileParameter:
        if self.data_type == "number":
            values = (self.default_value, self.min_value, self.max_value)
            if any(
                value is not None
                and (isinstance(value, bool) or not isinstance(value, (int, float)))
                for value in values
            ):
                raise ValueError("number parameter contains a non-numeric value")
            default = float(self.default_value)
            if self.min_value is not None and default < float(self.min_value):
                raise ValueError("default value is below minimum")
            if self.max_value is not None and default > float(self.max_value):
                raise ValueError("default value is above maximum")
            if (
                self.min_value is not None
                and self.max_value is not None
                and float(self.min_value) > float(self.max_value)
            ):
                raise ValueError("minimum is greater than maximum")
        elif not isinstance(self.default_value, str):
            raise ValueError("string parameter contains a non-string default")
        return self


class ProfileGroup(StrictModel):
    group_code: str = Field(min_length=1)
    label: str = Field(min_length=1)
    parameters: list[ProfileParameter] = Field(min_length=1)


class ObjectProfile(StrictModel):
    code: str = Field(min_length=1)
    name_ru: str = Field(min_length=1)
    groups: list[ProfileGroup] = Field(min_length=1)

    def parameters(self) -> tuple[ProfileParameter, ...]:
        return tuple(
            parameter for group in self.groups for parameter in group.parameters
        )

    def parameters_by_code(self) -> dict[str, ProfileParameter]:
        return {parameter.parameter_code: parameter for parameter in self.parameters()}

    @model_validator(mode="after")
    def validate_unique_codes(self) -> ObjectProfile:
        group_codes = [group.group_code for group in self.groups]
        if len(group_codes) != len(set(group_codes)):
            raise ValueError("duplicate group code")
        parameter_codes = [parameter.parameter_code for parameter in self.parameters()]
        if len(parameter_codes) != len(set(parameter_codes)):
            raise ValueError("duplicate parameter code")
        return self


class OfficialProfiles(StrictModel):
    schema_version: Literal["organizer-object-profiles-v1"]
    source_version: str = Field(min_length=1)
    object_types: list[ObjectProfile] = Field(min_length=1)

    def by_code(self) -> dict[str, ObjectProfile]:
        return {profile.code: profile for profile in self.object_types}

    @model_validator(mode="after")
    def validate_catalog_contract(self) -> OfficialProfiles:
        profiles = self.by_code()
        if set(profiles) != set(EXPECTED_PROFILE_COUNTS):
            raise ValueError("official object profile set differs")
        if len(profiles) != len(self.object_types):
            raise ValueError("duplicate object profile code")
        actual_counts = {
            code: len(profile.parameters()) for code, profile in profiles.items()
        }
        if actual_counts != EXPECTED_PROFILE_COUNTS:
            raise ValueError("official object profile parameter counts differ")
        return self


def _bundle_path() -> Path:
    configured = os.getenv("OFFICIAL_CATALOG_BUNDLE_PATH")
    return Path(configured) if configured else DEFAULT_BUNDLE_PATH


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=4)
def _load_profiles_cached(bundle_path_text: str) -> tuple[OfficialProfiles, str]:
    bundle_path = Path(bundle_path_text).resolve()
    manifest_path = bundle_path / "manifest.json"
    profile_path = bundle_path / PROFILE_FILE
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        profile_raw = json.loads(profile_path.read_text(encoding="utf-8-sig"))
        profile_size = profile_path.stat().st_size
        profile_sha256 = _sha256(profile_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ObjectProfileError(
            "official object profile bundle is unreadable"
        ) from exc

    file_entries = {
        entry.get("path"): entry
        for entry in manifest.get("files", [])
        if isinstance(entry, dict)
    }
    entry = file_entries.get(PROFILE_FILE)
    if not isinstance(entry, dict):
        raise ObjectProfileError("object profile is absent from bundle manifest")
    if entry.get("phase") != "REFERENCE":
        raise ObjectProfileError("object profile manifest phase differs")
    if entry.get("sha256") != profile_sha256 or entry.get("size_bytes") != profile_size:
        raise ObjectProfileError("object profile checksum or size differs")
    expected_total = manifest.get("expected_counts", {}).get(
        "object_profile_parameters"
    )
    if expected_total != sum(EXPECTED_PROFILE_COUNTS.values()):
        raise ObjectProfileError("manifest object profile count differs")
    try:
        profiles = OfficialProfiles.model_validate(profile_raw)
    except Exception as exc:  # Pydantic details can contain source values.
        raise ObjectProfileError("official object profile contract is invalid") from exc
    return profiles, profile_sha256


def load_official_profiles(bundle_path: str | Path | None = None) -> OfficialProfiles:
    path = Path(bundle_path) if bundle_path is not None else _bundle_path()
    return _load_profiles_cached(str(path.resolve()))[0]


def official_profile_version(bundle_path: str | Path | None = None) -> str:
    path = Path(bundle_path) if bundle_path is not None else _bundle_path()
    profiles, checksum = _load_profiles_cached(str(path.resolve()))
    return f"{profiles.schema_version}:sha256:{checksum}"


def resolve_profile_code(object_type: str) -> str:
    code = PROFILE_ALIASES.get(object_type.strip().lower())
    if code is None:
        raise ObjectProfileError("official object profile was not found")
    return code


def get_official_profile(
    object_type: str, bundle_path: str | Path | None = None
) -> ObjectProfile:
    code = resolve_profile_code(object_type)
    return load_official_profiles(bundle_path).by_code()[code]


def _parameter_provenance(parameter: ProfileParameter) -> dict[str, Any]:
    return {
        "kind": "PRESET",
        "parameter_codes": [parameter.parameter_code],
        "source": {
            "file": parameter.source_file,
            "sheet": parameter.source_sheet,
            "row": parameter.source_row,
            "note": parameter.source_note,
            "confidence": parameter.confidence,
        },
    }


_DIRECT_MAPPINGS: dict[str, dict[str, str]] = {
    "warehouse": {
        "area_m2": "obschaya_ploschad_sklada",
        "avg_distance_m": "srednyaya_dlina_marshruta_otborschika_na_1_stroku",
        "pallets_per_day": "obem_otgruzki_poddony_sutki",
        "shifts_count": "kolichestvo_rabochih_smen_v_sutki",
        "shift_hours": "prodolzhitelnost_smeny",
        "staff_headcount": "iz_nih_otborschiki_komplektovschiki",
        "aisle_width_m": "shirina_rabochih_prohodov_mezhdu_stellazhami",
        "payload_kg": "srednyaya_massa_gruzovoy_edinicy_pallet",
        "operating_days": "rabochih_dney_v_godu",
        "horizon_years": "gorizont_rascheta_okupaemosti",
    },
    "airport": {
        "area_m2": "summarnaya_ploschad_terminala_ov",
        "pallets_per_day": "sutochnoe_kolichestvo_reysov_vnutrennih_gruzovyh_telezhek_vnutri_terminala",
        "staff_headcount": "chislennost_personala_nazemnogo_obsluzhivaniya_ramp",
        "horizon_years": "gorizont_rascheta_okupaemosti",
    },
    "medical_facility": {
        "area_m2": "obschaya_ploschad_zdaniya_y",
        "avg_distance_m": "srednee_rasstoyanie_ot_pischebloka_do_otdeleniya",
        "pallets_per_day": "obschee_kolichestvo_porciy_pitaniya_v_sutki",
        "shifts_count": "kolichestvo_smen_medpersonala_uhod_za_pacientami",
        "staff_headcount": "chislennost_sotrudnikov_pischebloka_razdacha",
        "aisle_width_m": "shirina_koridorov_osnovnyh",
        "payload_kg": "srednyaya_massa_telezhki_s_pitaniem_brutto",
        "horizon_years": "gorizont_rascheta_okupaemosti",
    },
}

_SALARY_MAPPINGS = {
    "warehouse": (
        "srednyaya_z_p_otborschika_gross",
        "koefficient_nachisleniy_na_fot_strahovye_vznosy",
    ),
    "airport": (
        "srednyaya_z_p_sotrudnika_nazemnogo_obsluzhivaniya_gross",
        "koefficient_nachisleniy_na_fot",
    ),
    "medical_facility": (
        "srednyaya_z_p_sotrudnika_pischebloka_gross",
        "koefficient_nachisleniy_na_fot",
    ),
}

_ASSUMED_FIELDS: dict[str, dict[str, Any]] = {
    "warehouse": {
        "mode": "whole",
        "process_type": "transport",
        "cargo_type": "pallets",
    },
    "airport": {
        "mode": "whole",
        "process_type": "transport",
        "cargo_type": "carts",
        "avg_distance_m": 600,
        "shifts_count": 3,
        "shift_hours": 8,
    },
    "medical_facility": {
        "mode": "whole",
        "process_type": "delivery",
        "cargo_type": "deliveries",
        "shift_hours": 8,
    },
}


def build_official_preset(
    object_type: str, bundle_path: str | Path | None = None
) -> dict[str, Any]:
    """Return normalized input plus field-level provenance and full profile identity."""

    profile = get_official_profile(object_type, bundle_path)
    values = {
        parameter.parameter_code: parameter.default_value
        for parameter in profile.parameters()
    }
    result = build_profile_projection(
        profile,
        values,
        value_provenance_kind="PRESET",
        bundle_path=bundle_path,
    )
    result["parameter_count"] = len(profile.parameters())
    return result


def build_profile_projection(
    profile: ObjectProfile,
    values: dict[str, Any],
    *,
    value_provenance_kind: Literal["PRESET", "FILE"],
    file_source: dict[str, Any] | None = None,
    bundle_path: str | Path | None = None,
) -> dict[str, Any]:
    """Project a complete validated profile value set into ``UserInput``.

    Validation of file values belongs to the intake adapter.  This function is
    deliberately shared by presets and file intake so equivalence cannot drift.
    """

    parameters = profile.parameters_by_code()
    missing = sorted(set(parameters) - set(values))
    extra = sorted(set(values) - set(parameters))
    if missing or extra:
        raise ObjectProfileError("profile projection value set differs")
    normalized_input: dict[str, Any] = {
        "object_type": APPLICATION_OBJECT_TYPES[profile.code]
    }
    provenance: dict[str, dict[str, Any]] = {
        "object_type": {
            "kind": "ASSUMED",
            "parameter_codes": [],
            "source": "product-decision:official-profile-alias-v1",
        }
    }
    for field, parameter_code in _DIRECT_MAPPINGS[profile.code].items():
        parameter = parameters[parameter_code]
        normalized_input[field] = values[parameter_code]
        if value_provenance_kind == "PRESET":
            provenance[field] = _parameter_provenance(parameter)
        else:
            provenance[field] = {
                "kind": "FILE",
                "parameter_codes": [parameter_code],
                "source": file_source or {},
            }

    salary_code, multiplier_code = _SALARY_MAPPINGS[profile.code]
    salary = parameters[salary_code]
    multiplier = parameters[multiplier_code]
    normalized_input["fte_cost_rub"] = round(
        float(values[salary_code]) * 12 * float(values[multiplier_code]), 2
    )
    provenance["fte_cost_rub"] = {
        "kind": "CALCULATED",
        "parameter_codes": [salary_code, multiplier_code],
        "expression": "monthly_gross_rub * 12 * payroll_multiplier",
        "source": (
            {
                "file": salary.source_file,
                "sheet": salary.source_sheet,
                "rows": [salary.source_row, multiplier.source_row],
            }
            if value_provenance_kind == "PRESET"
            else (file_source or {})
        ),
    }

    for field, value in _ASSUMED_FIELDS[profile.code].items():
        normalized_input[field] = value
        provenance[field] = {
            "kind": "ASSUMED",
            "parameter_codes": [],
            "source": "product-decision:official-preset-mapping-v1",
        }

    return {
        "profile_code": profile.code,
        "profile_name": profile.name_ru,
        "profile_version": official_profile_version(bundle_path),
        "normalized_input": normalized_input,
        "provenance": provenance,
    }


def profile_api_dict(
    profile: ObjectProfile, bundle_path: str | Path | None = None
) -> dict[str, Any]:
    return {
        **profile.model_dump(mode="json"),
        "parameter_count": len(profile.parameters()),
        "profile_version": official_profile_version(bundle_path),
    }
