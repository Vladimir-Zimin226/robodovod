"""Check relative Markdown links in the active documentation tree."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
LINK = re.compile(r"!?\[[^\]]*\]\((<[^>]+>|[^)\s]+)(?:\s+[\"'][^)]*[\"'])?\)")
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def check() -> list[str]:
    problems: list[str] = []
    for source in SOURCES:
        content = source.read_text(encoding="utf-8")
        for match in LINK.finditer(content):
            raw = match.group(1).strip("<>")
            if not raw or raw.startswith("#") or raw.startswith("//") or SCHEME.match(raw):
                continue
            target = unquote(urlsplit(raw).path)
            if not target:
                continue
            candidate = (source.parent / target).resolve()
            if not candidate.exists():
                line = content.count("\n", 0, match.start()) + 1
                problems.append(f"{source.relative_to(ROOT)}:{line}: {raw}")
    return problems


if __name__ == "__main__":
    errors = check()
    for error in errors:
        print(error)
    print(f"checked {len(SOURCES)} Markdown files; broken relative links: {len(errors)}")
    sys.exit(bool(errors))
