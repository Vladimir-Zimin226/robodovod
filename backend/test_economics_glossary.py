"""Keep the public formula examples bound to current server calculations."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_economics_glossary import TARGET, build  # noqa: E402


def test_glossary_replays_current_engines_and_golden_examples():
    published = json.loads(TARGET.read_text(encoding="utf-8"))
    current = build()
    assert published == current
    assert len(current["entries"]) == 13
    assert {"transport-capacity-engine-v1", "full-cashflows-reconciliation-v2"} <= set(current["versions"].values())
    for entry in current["entries"]:
        assert all(entry[key] for key in ("formula", "units", "inputs", "example", "source", "section"))
