"""Build deterministic upload packets for ChatGPT Deep Research."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data" / "import" / "organizer-catalog-v4"
AUDIT = ROOT / "data" / "review" / "catalog-runtime-eligibility-report-v1.json"
CONTRACT = ROOT / "contracts" / "runtime-eligibility-contract-v1.json"
OUTPUT = ROOT / "data" / "research" / "catalog-runtime-eligibility-v1"
FRIENDLY_OUTPUT = ROOT / "Исследования"

BATCH_PLAN = (
    ("deep-mobile-01", "DEEP_RESEARCH", "MOBILE_TRANSPORT", 0, 10),
    ("deep-mobile-02", "DEEP_RESEARCH", "MOBILE_TRANSPORT", 10, 20),
    ("deep-cleaning-01", "DEEP_RESEARCH", "CLEANING", 0, 7),
    ("deep-cleaning-02", "DEEP_RESEARCH", "CLEANING", 7, 13),
    ("deep-other-01", "DEEP_RESEARCH", None, 0, 3),
    ("hybrid-conflicts-01", "HYBRID", None, 0, 5),
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=";"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _render_prompt(template: str, batch_id: str, models: list[dict[str, Any]]) -> str:
    target_count = sum(len(model["research_targets"]) for model in models)
    return (
        template.replace("{{BATCH_ID}}", batch_id)
        .replace("{{MODEL_COUNT}}", str(len(models)))
        .replace("{{TARGET_COUNT}}", str(target_count))
    )


def _parse(value: str) -> Any:
    if not value.strip():
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _known_facts(
    product: dict[str, Any], overlay: dict[str, Any] | None
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for field, value in sorted(product.get("specs", {}).items()):
        facts.append(
            {
                "field_path": f"specs.{field}",
                "layer": "BASE",
                "status": value.get("status"),
                "raw_value": value.get("raw"),
                "normalized_value": value.get("values"),
                "normalized_unit": value.get("unit"),
            }
        )
    for field, value in sorted((overlay or {}).get("fields", {}).items()):
        facts.append(
            {
                "field_path": f"specs.{field}",
                "layer": "EXTERNAL_EVIDENCE_OVERLAY",
                "status": value.get("evidence_status"),
                "raw_value": value.get("raw_value"),
                "normalized_value": value.get("normalized_value"),
                "normalized_unit": value.get("normalized_unit"),
            }
        )
    return facts


def _source_candidates(
    organizer_id: str, external_rows: list[dict[str, str]]
) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for row in external_rows:
        if row["organizer_id"] != organizer_id:
            continue
        url = row["url"].strip()
        if not url:
            continue
        candidates.setdefault(
            row["source_id"],
            {
                "source_id": row["source_id"],
                "url": url,
                "title": row["page_title"],
                "publisher": row["publisher"],
                "source_type": row["source_type"],
                "known_field_paths": [],
            },
        )["known_field_paths"].append(row["field_path"])
    for value in candidates.values():
        value["known_field_paths"] = sorted(set(value["known_field_paths"]))
    return [candidates[key] for key in sorted(candidates)]


def _batch_models() -> dict[str, list[dict[str, Any]]]:
    audit = _json(AUDIT)
    products = _json(BUNDLE / "catalog_products.json")["products"]
    overlays = {
        row["organizer_id"]: row
        for row in _json(BUNDLE / "catalog_external_enrichment.json")["products"]
    }
    external_rows = _csv(BUNDLE / "catalog_external_evidence.csv")
    applicability = _csv(BUNDLE / "catalog_applicability.csv")
    positions: dict[str, list[str]] = defaultdict(list)
    for row in applicability:
        positions[row["organizer_id"]].append(
            f"catalog-v4-row-{int(row['original_row']):04d}"
        )
    products_by_id = {row["organizer_id"]: row for row in products}

    prepared: dict[str, dict[str, Any]] = {}
    for item in audit["models"]:
        if item["status"] not in {"NEEDS_FACTS", "CONFLICT_REVIEW"}:
            continue
        organizer_id = item["model_id"]
        product = products_by_id[organizer_id]
        overlay = overlays.get(organizer_id)
        conflict_fields = sorted(
            {
                conflict["field"]
                for conflict in item["conflicts"]
                if conflict["field"] != "model_identity_or_revision"
            }
        )
        prepared[organizer_id] = {
            "organizer_id": organizer_id,
            "position_ids": sorted(positions[organizer_id]),
            "name": product["name"],
            "manufacturer": product.get("manufacturer"),
            "system_family": product.get("system_family"),
            "type": product.get("type"),
            "subtype": product.get("subtype"),
            "equipment_class": item["equipment_class"],
            "capacity_profile": item["capacity_profile"],
            "current_status": item["status"],
            "required_fields": item["required_fields"],
            "research_targets": sorted(set(item["missing_fields"]) | set(conflict_fields)),
            "conflicts": item["conflicts"],
            "known_facts_do_not_silently_overwrite": _known_facts(product, overlay),
            "known_source_candidates": _source_candidates(organizer_id, external_rows),
        }

    needs = sorted(
        (value for value in prepared.values() if value["current_status"] == "NEEDS_FACTS"),
        key=lambda value: value["organizer_id"],
    )
    conflicts = sorted(
        (value for value in prepared.values() if value["current_status"] == "CONFLICT_REVIEW"),
        key=lambda value: value["organizer_id"],
    )
    mobile = [value for value in needs if value["equipment_class"] == "MOBILE_TRANSPORT"]
    cleaning = [value for value in needs if value["equipment_class"] == "CLEANING"]
    other = [
        value
        for value in needs
        if value["equipment_class"] in {"FIXED_PALLETIZING", "SERVICE_DELIVERY"}
    ]
    pools = {
        ("DEEP_RESEARCH", "MOBILE_TRANSPORT"): mobile,
        ("DEEP_RESEARCH", "CLEANING"): cleaning,
        ("DEEP_RESEARCH", None): other,
        ("HYBRID", None): conflicts,
    }
    batches: dict[str, list[dict[str, Any]]] = {}
    for batch_id, mode, equipment_class, start, end in BATCH_PLAN:
        batches[batch_id] = pools[(mode, equipment_class)][start:end]
    if sum(len(value) for key, value in batches.items() if key.startswith("deep-")) != 36:
        raise ValueError("deep-research batches must cover exactly 36 models")
    if len(batches["hybrid-conflicts-01"]) != 5:
        raise ValueError("hybrid batch must cover exactly 5 models")
    if len({row["organizer_id"] for values in batches.values() for row in values}) != 41:
        raise ValueError("research models must appear exactly once")
    return batches


RETURN_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://robodovod.local/schemas/catalog-official-source-research-return-v1.json",
    "title": "ROBODOVOD official-source research return",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "batch_id", "research_completed_at", "results"],
    "properties": {
        "schema_version": {"const": "catalog-official-source-research-return-v1"},
        "batch_id": {"type": "string", "minLength": 1},
        "research_completed_at": {"type": "string", "format": "date-time"},
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "organizer_id",
                    "identity_status",
                    "matched_manufacturer",
                    "matched_model",
                    "field_results",
                    "unresolved_issues",
                ],
                "properties": {
                    "organizer_id": {"type": "string", "format": "uuid"},
                    "identity_status": {
                        "enum": [
                            "EXACT_MODEL_MATCH",
                            "EXACT_MODEL_MATCH_WITH_CONFLICTS",
                            "AMBIGUOUS_MODEL_MATCH",
                            "MODEL_NOT_FOUND",
                        ]
                    },
                    "matched_manufacturer": {"type": ["string", "null"]},
                    "matched_model": {"type": ["string", "null"]},
                    "field_results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "field_path",
                                "evidence_status",
                                "normalized_value",
                                "normalized_unit",
                                "evidence",
                                "confidence",
                                "notes",
                            ],
                            "properties": {
                                "field_path": {"type": "string", "minLength": 1},
                                "evidence_status": {
                                    "enum": [
                                        "VERIFIED_OFFICIAL",
                                        "VERIFIED_AUTHORIZED_PARTNER",
                                        "CONFLICT",
                                        "AMBIGUOUS_MODEL_MATCH",
                                        "NOT_FOUND",
                                    ]
                                },
                                "normalized_value": {},
                                "normalized_unit": {"type": ["string", "null"]},
                                "evidence": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": [
                                            "raw_value",
                                            "source_url",
                                            "source_title",
                                            "publisher",
                                            "source_type",
                                            "source_locator",
                                            "publication_or_update_date",
                                            "accessed_at"
                                        ],
                                        "properties": {
                                            "raw_value": {"type": "string", "minLength": 1},
                                            "source_url": {"type": "string", "format": "uri"},
                                            "source_title": {"type": "string", "minLength": 1},
                                            "publisher": {"type": "string", "minLength": 1},
                                            "source_type": {
                                                "enum": [
                                                    "OFFICIAL_MODEL_PAGE",
                                                    "OFFICIAL_DATASHEET",
                                                    "OFFICIAL_MANUAL",
                                                    "OFFICIAL_CATALOG",
                                                    "AUTHORIZED_PARTNER_PAGE"
                                                ]
                                            },
                                            "source_locator": {"type": "string", "minLength": 1},
                                            "publication_or_update_date": {
                                                "type": ["string", "null"],
                                                "format": "date"
                                            },
                                            "accessed_at": {"type": "string", "format": "date"}
                                        }
                                    }
                                },
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                "notes": {"type": "string"},
                            },
                        },
                    },
                    "unresolved_issues": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


DEEP_PROMPT = """# ChatGPT Deep Research: catalog evidence batch `{{BATCH_ID}}`

## Результат задачи

Исследуй ровно {{MODEL_COUNT}} model identities из приложенного batch и верни ровно {{TARGET_COUNT}} field results: по одному для каждого `research_target`. Найди только явно опубликованные model-specific значения и доказательства. Не исследуй модели вне batch, цены, экономику, procurement, capacity formulas или runtime activation.

## Входные файлы и доступ к вебу

Файлы `01-BATCH-{{BATCH_ID}}.json`, `02-RUNTIME-CONTRACT.json` и `03-RETURN-SCHEMA-REQUIRED.json` задают scope, контекст и JSON schema. Они не являются источниками новых ТТХ и не ограничивают источники исследования.

Публичный веб-поиск обязателен для каждой модели. Открывай внешние страницы и документы. `known_source_candidates` — только отправные точки: проверь их содержимое и ищи дополнительные официальные источники. Отсутствие первичных документов среди вложений не является основанием для `NOT_FOUND`.

Если интерфейс сначала показывает proposed research plan, это штатный этап до запуска. План должен явно предусматривать публичный веб-поиск по официальным источникам и охватывать {{MODEL_COUNT}} моделей и {{TARGET_COUNT}} targets, но не является итоговым результатом. После запуска доведи исследование до полного отчёта.

## Источники и доказательства

1. Приоритет: точная официальная страница модели, затем официальный datasheet/manual/catalog PDF.
2. Страница авторизованного партнёра допустима только после безуспешного поиска официального источника; evidence должно также доказывать статус партнёра.
3. Маркетплейсы, агрегаторы, SEO-каталоги, форумы, соцсети и неподтверждённые пересказы не являются evidence.
4. Не угадывай URL, модель, ревизию, единицу или значение. Не объединяй разные модели, ревизии и конфигурации.
5. Для каждого verified/conflict/ambiguous field result добавь прямой `source_url`, title, publisher, точный locator/раздел/страницу, `publication_or_update_date` в `YYYY-MM-DD` или `null`, `accessed_at` в `YYYY-MM-DD` и короткий дословный `raw_value` не длиннее 20 слов.
6. Нормализуй только явно опубликованное значение. Не вычисляй производные характеристики и не подставляй типовые значения класса.
7. `known_facts_do_not_silently_overwrite` — контекст для сравнения. Не копируй его как новый факт. Доказанное расхождение возвращай как `CONFLICT` минимум с двумя evidence-записями, показывающими обе стороны.
8. `NOT_FOUND` допустим только после поиска точной модели и конкретного target на официальном сайте и в официальных PDF. Для него `normalized_value=null`, `normalized_unit=null`, `evidence=[]`; в `notes` кратко укажи, что именно было проверено.

## Правила статусов

- `EXACT_MODEL_MATCH`: точная модель/ревизия доказана.
- `EXACT_MODEL_MATCH_WITH_CONFLICTS`: точная identity доказана и есть хотя бы один `CONFLICT`.
- `AMBIGUOUS_MODEL_MATCH`: найдено несколько правдоподобных моделей/ревизий, но применимую нельзя доказать; не выбирай одну из них. Для ambiguous field result значение и unit должны быть `null`, а evidence должно показывать неоднозначность.
- `MODEL_NOT_FOUND`: после веб-поиска точная модель не найдена; target fields возвращаются как `NOT_FOUND`.
- `VERIFIED_OFFICIAL`: значение подтверждено официальным источником.
- `VERIFIED_AUTHORIZED_PARTNER`: официального источника нет, значение подтверждено доказанным авторизованным партнёром.
- `CONFLICT`: применимое единственное значение выбрать нельзя; `normalized_value` и `normalized_unit` должны быть `null`.

## Итоговый Markdown-отчёт

Верни результат непосредственно в теле одного итогового Markdown-отчёта. Не создавай отдельный JSON-файл, не используй `sandbox:/` и не делай полноту результата зависимой от временного файла.

Сначала дай краткую таблицу по {{MODEL_COUNT}} моделям: identity status, counts field statuses, conflicts и кликабельные source links. Затем выведи ровно один полный JSON-объект:

1. отдельная строка `CATALOG_RESULT_JSON_BEGIN`;
2. один fenced-блок, начинающийся строкой ```json;
3. полный JSON строго по `03-RETURN-SCHEMA-REQUIRED.json`;
4. закрывающая строка ```;
5. отдельная строка `CATALOG_RESULT_JSON_END`.

Внутри JSON запрещены Markdown-citations, комментарии, сокращения, `...` и дополнительные schema-поля. `batch_id` должен быть `{{BATCH_ID}}`; `research_completed_at` — валидный RFC 3339 date-time с timezone; каждый `organizer_id` должен присутствовать ровно один раз и без изменения.

## Completion gate

Не завершай итоговый отчёт, пока одновременно не выполнены все условия:

- публичный веб-поиск выполнен для каждой из {{MODEL_COUNT}} моделей;
- JSON синтаксически валиден и содержит ровно {{MODEL_COUNT}} model results и {{TARGET_COUNT}} field results;
- состав `organizer_id` и `field_path` точно совпадает с batch;
- каждый verified/conflict/ambiguous result имеет требуемое evidence, каждый `NOT_FOUND` имеет пустое evidence;
- ни один факт не перенесён из known facts без нового допустимого evidence;
- итоговый JSON полностью находится между двумя маркерами в этом отчёте.
"""


HYBRID_PROMPT = DEEP_PROMPT.replace(
    "Исследуй ровно {{MODEL_COUNT}} model identities из приложенного batch и верни ровно {{TARGET_COUNT}} field results: по одному для каждого `research_target`.",
    "Сначала разреши перечисленные identity/spec conflicts по revision/date/configuration, затем исследуй ровно {{MODEL_COUNT}} model identities и верни ровно {{TARGET_COUNT}} field results: по одному для каждого `research_target`.",
).replace(
    "- публичный веб-поиск выполнен для каждой из {{MODEL_COUNT}} моделей;",
    "- публичный веб-поиск выполнен для каждой из {{MODEL_COUNT}} моделей и обе стороны каждого входного conflict проверены по первичным источникам;",
)


RECOVERY_PROMPT = """Продолжи уже начатое исследование для batch `{{BATCH_ID}}` немедленно в этом же чате по ранее составленному плану.

Я подтверждаю выполнение всего исследования. Не показывай новый план, не проси нового подтверждения и не останавливайся на промежуточном ответе. Используй только заново приложенные `01-BATCH-{{BATCH_ID}}.json`, `02-RUNTIME-CONTRACT.json` и исправленный `03-RETURN-SCHEMA-REQUIRED.json`; игнорируй прежние вложения с другими именами, включая `runtime-eligibility-contract-v1.schema(1).json`. Проведи поиск по всем моделям и всем `research_targets`, соблюдая исходные правила источников и evidence.

Не создавай отдельный JSON-файл и не давай `sandbox:/` ссылку. Верни весь результат прямо в итоговом Markdown-отчёте. После сводки вставь полный JSON строго по `03-RETURN-SCHEMA-REQUIRED.json` между отдельными видимыми строками `CATALOG_RESULT_JSON_BEGIN` и `CATALOG_RESULT_JSON_END`, внутри одного fenced-блока ```json. Не сокращай JSON, не используй `...` и не пропускай `NOT_FOUND` entries.

Перед завершением проверь exact model count, exact target coverage, отсутствие дополнительных JSON-полей, пустой `evidence` для `NOT_FOUND` и наличие citation URL для каждого verified/conflict result. Если факт не найден, верни `NOT_FOUND` и продолжай остальные targets.
"""


README = """# ChatGPT Deep Research handoff — runtime eligibility v1

Пакет предназначен для ручного запуска в веб-версии ChatGPT. Один batch — один отдельный Deep Research chat.

## Что загружать

Для каждого запуска откройте готовую папку `upload/<batch-id>/` и приложите из неё ровно три файла:

1. `01-BATCH-<batch-id>.json`;
2. `02-RUNTIME-CONTRACT.json`;
3. `03-RETURN-SCHEMA-REQUIRED.json`.

Не загружайте `contracts/runtime-eligibility-contract-v1.schema.json`: это schema runtime-контракта, а не schema результата исследования. Нужный третий файл всегда имеет имя `03-RETURN-SCHEMA-REQUIRED.json` и уже лежит в готовой upload-папке.

Полный 424-KB audit report, исходные restricted PDF/XLSX/DOCX и локальный `.env` загружать не нужно. Batch уже содержит необходимый локальный контекст, stable IDs, known facts, conflicts и ранее известные URL.

## Порядок запуска

1. Откройте новый chat в ChatGPT и выберите **Deep Research** в меню инструментов.
2. Загрузите три JSON-файла из `upload/<batch-id>/`.
3. Откройте `upload/<batch-id>/COPY-PASTE-PROMPT.md` и целиком скопируйте его в chat. Batch ID уже подставлен.
4. В источниках оставьте public web и загруженные файлы; подключать Apps не требуется. Не ограничивайте поиск одним доменом: prompt уже требует приоритет официальных источников.
5. Запустите исследование. Prompt требует выполнить весь batch сразу и запрещает останавливаться ради подтверждения плана. Не объединяйте batch-файлы в один chat.
6. Скачайте итоговый отчёт в Markdown и положите без ручного редактирования в `returns/`. Имя скачанного `.md` не важно: batch определяется из встроенного JSON.
7. После всех запусков извлеките JSON локально или передайте каталог `returns/` обратно Codex с запросом: «Извлеки и провалидируй Deep Research returns, построй evidence review и не импортируй ничего без явного подтверждения».

Веб-интерфейс ChatGPT может независимо от текста prompt показать системный proposed research plan до начала поиска. Это штатный этап интерфейса: проверьте, что в нём 10/10 или указанное для batch число моделей, и нажмите запуск/подтверждение в том же chat. Не создавайте для этого новый Deep Research chat.

Локальная строгая проверка полного комплекта перед передачей:

```powershell
./.venv/Scripts/python.exe scripts/extract_catalog_deep_research_reports.py --reports-dir data/research/catalog-runtime-eligibility-v1/returns --require-complete
```

Extractor требует полный JSON-блок между маркерами `CATALOG_RESULT_JSON_BEGIN/END`, создаёт `<batch-id>.result.json` и сразу выполняет schema/coverage-проверку.

После extraction постройте только staging/review-отчёт (без импорта в catalog/runtime):

```powershell
./.venv/Scripts/python.exe scripts/review_catalog_deep_research_returns.py --returns-dir data/research/catalog-runtime-eligibility-v1/returns --require-complete
```

Проверить целостность всех шести исходных пакетов независимо от результатов:

```powershell
./.venv/Scripts/python.exe scripts/audit_catalog_deep_research_packets.py
```

Если ChatGPT остановился на плане, не создавайте новый chat. Убедитесь, что приложен `03-RETURN-SCHEMA-REQUIRED.json`, затем отправьте в том же chat содержимое `upload/<batch-id>/RECOVERY-CURRENT-CHAT.md`.

## Batch-порядок

1. `deep-mobile-01` — 10 transport моделей.
2. `deep-mobile-02` — 10 transport моделей.
3. `deep-cleaning-01` — 7 cleaning моделей.
4. `deep-cleaning-02` — 6 cleaning моделей.
5. `deep-other-01` — 2 palletizing + 1 delivery модель.
6. `hybrid-conflicts-01` — 5 конфликтных моделей.

Итого: 36 `DEEP_RESEARCH` + 5 `HYBRID` model identities. Позиции не склеиваются: каждый batch содержит связанные `position_ids`.
"""


RETURNS_README = """# Deep Research returns

Сохраните сюда без ручного редактирования Markdown-отчёт каждого из шести исследований. Имя `.md` не важно. Extractor найдёт встроенный блок `CATALOG_RESULT_JSON`, создаст `<batch-id>.result.json` и сразу выполнит строгую schema/coverage-проверку. До evidence review эти данные не являются runtime facts.
"""


FRIENDLY_README_HEADER = """# Исследования — начать здесь

Для каждого исследования используйте отдельный новый чат ChatGPT Deep Research. Не продолжайте старые чаты с ошибочными планами или отчётами: их контекст может повлиять на новый запуск.

Порядок действий для папок `Исследование 1` — `Исследование 6`:

1. Откройте папку исследования и создайте новый ChatGPT Deep Research chat.
2. В настройке источников убедитесь, что включён **Public web**, а не только uploaded files.
3. Приложите к сообщению ровно три JSON-файла с номерами `01`, `02`, `03`.
4. Откройте `00-ПРОМПТ-СКОПИРОВАТЬ-В-ЧАТ.md`, скопируйте весь текст и отправьте его вместе с приложениями.
5. До начала поиска ChatGPT покажет proposed research plan. Не запускайте его, пока план явно не говорит о публичном веб-поиске по официальным источникам и не показывает указанное ниже число моделей/targets.
6. После проверки нажмите запуск/подтверждение в том же чате.
7. После завершения скачайте только итоговый отчёт в формате Markdown и положите его без редактирования в папку `Результаты сюда`. Имя файла менять не нужно.

Не прикладывайте другие schema, старые файлы с `(1)` в имени или материалы из соседнего исследования.

## Соответствие папок

"""


FRIENDLY_RESULTS_README_HEADER = """# Результаты класть сюда

Скачайте сюда без переименования и ручного редактирования по одному итоговому Markdown-отчёту из каждого исследования. Имена файлов могут быть любыми: extractor определяет batch по JSON внутри отчёта.

"""


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "batches").mkdir(exist_ok=True)
    (output / "prompts").mkdir(exist_ok=True)
    (output / "returns").mkdir(exist_ok=True)
    (output / "upload").mkdir(exist_ok=True)
    batches = _batch_models()
    contract = _json(CONTRACT)
    contract_by_class = {
        row["code"]: row for row in contract["equipment_classes"]
    }
    batch_manifest = []
    for batch_id, models in batches.items():
        mode = "HYBRID" if batch_id.startswith("hybrid-") else "DEEP_RESEARCH"
        class_codes = sorted(
            {row["equipment_class"] for row in models if row["equipment_class"]}
        )
        payload = {
            "schema_version": "catalog-official-source-research-batch-v1",
            "batch_id": batch_id,
            "mode": mode,
            "catalog_code": "organizer-catalog-v4",
            "runtime_contract_version": contract["schema_version"],
            "equipment_class_contracts": [contract_by_class[code] for code in class_codes],
            "model_count": len(models),
            "models": models,
            "scope_exclusions": [
                "prices",
                "economics",
                "procurement",
                "capacity formulas",
                "runtime activation",
                "unsupported capacity profiles",
            ],
        }
        path = output / "batches" / f"{batch_id}.json"
        path.write_bytes(_canonical(payload))
        prompt = HYBRID_PROMPT if mode == "HYBRID" else DEEP_PROMPT
        rendered_prompt = _render_prompt(prompt, batch_id, models)
        (output / "prompts" / f"{batch_id}.prompt.md").write_text(
            rendered_prompt,
            encoding="utf-8",
            newline="\n",
        )
        upload = output / "upload" / batch_id
        upload.mkdir(parents=True, exist_ok=True)
        batch_upload = upload / f"01-BATCH-{batch_id}.json"
        shutil.copyfile(path, batch_upload)
        contract_upload = upload / "02-RUNTIME-CONTRACT.json"
        shutil.copyfile(CONTRACT, contract_upload)
        return_schema_upload = upload / "03-RETURN-SCHEMA-REQUIRED.json"
        return_schema_upload.write_bytes(_canonical(RETURN_SCHEMA))
        (upload / "COPY-PASTE-PROMPT.md").write_text(
            rendered_prompt,
            encoding="utf-8",
            newline="\n",
        )
        (upload / "RECOVERY-CURRENT-CHAT.md").write_text(
            RECOVERY_PROMPT.replace("{{BATCH_ID}}", batch_id),
            encoding="utf-8",
            newline="\n",
        )
        batch_manifest.append(
            {
                "batch_id": batch_id,
                "mode": mode,
                "models": len(models),
                "sha256": _sha256(path),
                "path": path.relative_to(output).as_posix(),
                "upload_path": upload.relative_to(output).as_posix(),
                "upload_sha256": {
                    "batch": _sha256(batch_upload),
                    "runtime_contract": _sha256(contract_upload),
                    "return_schema": _sha256(return_schema_upload),
                },
            }
        )
    (output / "catalog-official-source-research-return-v1.schema.json").write_bytes(
        _canonical(RETURN_SCHEMA)
    )
    (output / "PROMPT_DEEP_RESEARCH_RU.md").write_text(DEEP_PROMPT, encoding="utf-8", newline="\n")
    (output / "PROMPT_HYBRID_RU.md").write_text(HYBRID_PROMPT, encoding="utf-8", newline="\n")
    (output / "README.md").write_text(README, encoding="utf-8", newline="\n")
    (output / "returns" / "README.md").write_text(RETURNS_README, encoding="utf-8", newline="\n")
    manifest = {
        "schema_version": "catalog-deep-research-handoff-manifest-v1",
        "prompt_revision": "audited-public-web-inline-json-v5",
        "catalog_code": "organizer-catalog-v4",
        "contract_sha256": _sha256(CONTRACT),
        "audit_sha256": _sha256(AUDIT),
        "deep_research_models": 36,
        "hybrid_models": 5,
        "batches": batch_manifest,
    }
    (output / "manifest.json").write_bytes(_canonical(manifest))


def build_friendly_workspace(output: Path, handoff: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    results = output / "Результаты сюда"
    results.mkdir(exist_ok=True)
    mapping_lines: list[str] = []
    for number, (batch_id, _mode, _class_code, _start, _stop) in enumerate(
        BATCH_PLAN, start=1
    ):
        source = handoff / "upload" / batch_id
        destination = output / f"Исследование {number}"
        destination.mkdir(exist_ok=True)
        for filename in (
            f"01-BATCH-{batch_id}.json",
            "02-RUNTIME-CONTRACT.json",
            "03-RETURN-SCHEMA-REQUIRED.json",
        ):
            shutil.copyfile(source / filename, destination / filename)
        shutil.copyfile(
            source / "COPY-PASTE-PROMPT.md",
            destination / "00-ПРОМПТ-СКОПИРОВАТЬ-В-ЧАТ.md",
        )
        batch = _json(source / f"01-BATCH-{batch_id}.json")
        target_count = sum(len(model["research_targets"]) for model in batch["models"])
        mapping_lines.append(
            f"{number}. `Исследование {number}` → `{batch_id}` — "
            f"{batch['model_count']} моделей, {target_count} target fields."
        )
    (output / "00-НАЧАТЬ-ЗДЕСЬ.md").write_text(
        FRIENDLY_README_HEADER + "\n".join(mapping_lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (results / "00-КЛАСТЬ-РЕЗУЛЬТАТЫ-СЮДА.md").write_text(
        FRIENDLY_RESULTS_README_HEADER
        + "После шести запусков здесь должны лежать шесть скачанных `.md`-отчётов.\n\n"
        + "Затем передайте эту папку Codex или запустите строгую extraction/schema/evidence-проверку.\n\n"
        + "Локальная проверка полного комплекта и построение review-only отчёта:\n\n"
        + "```powershell\n"
        + ".\\.venv\\Scripts\\python.exe scripts\\extract_catalog_deep_research_reports.py "
        + "--reports-dir \"Исследования\\Результаты сюда\" --require-complete\n"
        + ".\\.venv\\Scripts\\python.exe scripts\\review_catalog_deep_research_returns.py "
        + "--returns-dir \"Исследования\\Результаты сюда\" --require-complete\n"
        + "```\n",
        encoding="utf-8",
        newline="\n",
    )


def check(output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="robodovod-deep-research-") as temporary:
        candidate = Path(temporary) / output.name
        build(candidate)
        expected = {
            path.relative_to(candidate).as_posix(): path.read_bytes()
            for path in candidate.rglob("*")
            if path.is_file()
        }
        actual = {
            path.relative_to(output).as_posix(): path.read_bytes()
            for path in output.rglob("*")
            if path.is_file()
        }
        if expected != actual:
            missing = sorted(expected.keys() - actual.keys())
            extra = sorted(actual.keys() - expected.keys())
            changed = sorted(
                key
                for key in expected.keys() & actual.keys()
                if expected[key] != actual[key]
            )
            raise SystemExit(
                f"handoff differs: missing={missing}, extra={extra}, changed={changed}"
            )


def check_friendly_workspace(output: Path, handoff: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="robodovod-friendly-research-") as temporary:
        candidate = Path(temporary) / output.name
        build_friendly_workspace(candidate, handoff)
        expected = {
            path.relative_to(candidate).as_posix(): path.read_bytes()
            for path in candidate.rglob("*")
            if path.is_file()
        }
        actual = {
            path.relative_to(output).as_posix(): path.read_bytes()
            for path in output.rglob("*")
            if path.is_file()
            and (
                path.parent.name != "Результаты сюда"
                or path.name == "00-КЛАСТЬ-РЕЗУЛЬТАТЫ-СЮДА.md"
            )
        }
        if expected != actual:
            missing = sorted(expected.keys() - actual.keys())
            extra = sorted(actual.keys() - expected.keys())
            changed = sorted(
                key
                for key in expected.keys() & actual.keys()
                if expected[key] != actual[key]
            )
            raise SystemExit(
                f"friendly workspace differs: missing={missing}, extra={extra}, changed={changed}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--friendly-output", type=Path, default=FRIENDLY_OUTPUT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    friendly_output = args.friendly_output.resolve()
    if args.write:
        build(output)
        build_friendly_workspace(friendly_output, output)
    else:
        check(output)
        check_friendly_workspace(friendly_output, output)


if __name__ == "__main__":
    main()
