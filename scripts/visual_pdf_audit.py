"""Render three computed local role reports and audit their text pagination.

These reports use repository fixtures and a test catalog, not a published catalog.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from calculation.object_roles import ObjectRoleInput, analyze_object_roles  # noqa: E402
from calculation.role_report import role_report_pdf  # noqa: E402
from test_object_roles import catalog, raw  # noqa: E402


def main() -> None:
    output = ROOT / "docs/visual-polish/pdf"
    output.mkdir(parents=True, exist_ok=True)
    audit = []
    for kind in ("WAREHOUSE", "AIRPORT", "CLINIC"):
        report = analyze_object_roles(ObjectRoleInput.model_validate(raw(kind)), catalog())
        data = role_report_pdf(report)
        target = output / f"{kind.lower()}-local.pdf"
        target.write_bytes(data)
        pages = PdfReader(target).pages
        counts = [len((page.extract_text() or "").strip()) for page in pages]
        assert all(count > 0 for count in counts), (kind, counts)
        text = re.sub(r"\s+", " ", " ".join(page.extract_text() or "" for page in pages))
        view = report["report_view"]
        assert view["executive_conclusion"] in text
        for mode in ("purchase", "raas"):
            assert view["economics"][mode]["npv_rub"] in text
        audit.append({"object": kind, "pages": len(pages), "text_characters_by_page": counts,
                      "catalog": view["catalog_version"], "pdf": str(target.relative_to(ROOT))})
    (output / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
