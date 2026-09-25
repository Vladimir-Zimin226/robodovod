"""Render the current user guide as a standalone, printable HTML document.

The source intentionally uses a small Markdown subset. Run from the repository
root with ``python scripts/render_user_guide.py`` and print the generated HTML
to PDF in a browser when the guide changes.
"""

from __future__ import annotations

import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "USER_GUIDE_CURRENT_2026-09-25.md"
TARGET = ROOT / "docs" / "USER_GUIDE_CURRENT_2026-09-25.html"


def inline(value: str) -> str:
    value = html.escape(value.strip())
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"(?<![\w\"=])(https://[\w.-]+(?:/[\w./-]*)?)", r'<a href="\1">\1</a>', value)
    return value


def render(source: str) -> str:
    lines = source.splitlines()
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            index += 1
            continue
        if line.startswith("> "):
            parts = []
            while index < len(lines) and lines[index].startswith("> "):
                parts.append(lines[index][2:].strip())
                index += 1
            blocks.append(f"<aside>{inline(' '.join(parts))}</aside>")
            continue
        list_match = re.match(r"^(-|\d+\.)\s+", line)
        if list_match:
            ordered = list_match.group(1) != "-"
            items = []
            while index < len(lines):
                item_start = re.match(r"^(-|\d+\.)\s+(.+)$", lines[index])
                if not item_start or (item_start.group(1) != "-") != ordered:
                    break
                parts = [item_start.group(2).strip()]
                index += 1
                while index < len(lines) and lines[index].startswith("  ") and lines[index].strip():
                    parts.append(lines[index].strip())
                    index += 1
                items.append(f"<li>{inline(' '.join(parts))}</li>")
                if index >= len(lines) or not lines[index].strip():
                    break
            tag = "ol" if ordered else "ul"
            blocks.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        parts = [line.strip()]
        index += 1
        while index < len(lines) and lines[index].strip() and not re.match(r"^(#{1,3} |>|- |\d+\. )", lines[index]):
            parts.append(lines[index].strip())
            index += 1
        blocks.append(f"<p>{inline(' '.join(parts))}</p>")
    return "\n".join(blocks)


STYLE = """
@page { size: A4; margin: 16mm 17mm 17mm; }
* { box-sizing: border-box; }
html { color: #18242a; background: #fff; font-family: Arial, 'DejaVu Sans', sans-serif; }
body { max-width: 930px; margin: 0 auto; padding: 28px 34px 42px; font-size: 15px; line-height: 1.58; }
h1, h2, h3 { color: #123c4a; line-height: 1.23; page-break-after: avoid; }
h1 { font-size: 30px; letter-spacing: -.02em; margin: 0 0 18px; padding-bottom: 17px; border-bottom: 4px solid #85bb46; }
h2 { font-size: 22px; margin: 34px 0 12px; padding: 0 0 6px; border-bottom: 1px solid #d6e1e4; }
h3 { font-size: 17px; margin: 23px 0 8px; }
p { margin: 0 0 13px; }
ol, ul { padding-left: 25px; margin: 4px 0 16px; }
li { margin: 0 0 7px; padding-left: 3px; }
li, aside, p { orphans: 3; widows: 3; }
strong { color: #173c45; }
code { background: #e9f0f0; border-radius: 3px; padding: 1px 4px; font-family: Consolas, monospace; font-size: .92em; }
a { color: #09697c; text-decoration-thickness: 1px; }
aside { background: #f2f7e8; border-left: 5px solid #85bb46; padding: 13px 17px; margin: 17px 0 24px; }
@media print {
  body { width: auto; max-width: none; padding: 0; font-size: 10.25pt; line-height: 1.4; }
  h1 { font-size: 22pt; } h2 { font-size: 16pt; margin-top: 21pt; } h3 { font-size: 12.5pt; }
  a { color: #09697c; text-decoration: none; }
  li { break-inside: avoid; }
  aside { break-inside: avoid; }
}
"""


def main() -> None:
    body = render(SOURCE.read_text(encoding="utf-8"))
    page = (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Рободовод — руководство пользователя</title>'
        f"<style>{STYLE}</style></head><body>{body}</body></html>"
    )
    TARGET.write_text(page, encoding="utf-8")
    print(TARGET)


if __name__ == "__main__":
    main()
