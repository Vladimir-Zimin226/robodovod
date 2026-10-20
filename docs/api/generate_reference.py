"""Regenerate the API contract from the application's registered FastAPI routers."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from main import app  # noqa: E402


def main() -> None:
    schema = app.openapi()
    output = ROOT / "docs" / "api"
    (output / "openapi.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rows = ["# Зарегистрированные маршруты FastAPI", "", "Сгенерировано из `backend/main.py`; схема: [openapi.json](openapi.json).", "", "| Метод | Путь | Операция |", "| --- | --- | --- |"]
    for path, operations in sorted(schema["paths"].items()):
        for method, operation in operations.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            summary = (operation.get("summary") or operation.get("operationId") or "").replace("|", "\\|")
            rows.append(f"| {method.upper()} | `{path}` | {summary} |")
    (output / "routes.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Generated {len(schema['paths'])} paths")


if __name__ == "__main__":
    main()
