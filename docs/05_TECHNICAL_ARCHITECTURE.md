# РОБОДОВОД — Technical Architecture v0.3

Актуализация 16 сентября 2026 года: PostgreSQL является ближайшим обязательным
этапом перед интеграцией официального каталога. Порядок и открытые решения — в
`17_DATA_STORAGE_AND_CATALOG_INTEGRATION.md`.

## 1. Architectural goals

- deterministic numeric core;
- explicit provenance/assumptions;
- low development overhead;
- one deployable application for hackathon;
- stable golden path over breadth;
- easy extension from configured visualization to future simulation/telemetry.

## 2. Stack

### Backend

- Python 3.12;
- FastAPI;
- Pydantic v2;
- SQLAlchemy 2;
- Alembic;
- PostgreSQL 16;
- httpx;
- pytest / pytest-asyncio;
- ruff;
- optional mypy.

### AI

Provider adapter with structured JSON output.

LLM allowed:

- extract;
- classify text into known taxonomy;
- ask next question;
- explain deterministic result;
- draft report prose.

LLM forbidden as final authority for:

- hard pass/fail;
- fleet quantity;
- installed CAPEX/TCO/payback/NPV;
- procurement availability;
- regional multiplier.

### Frontend

- TypeScript;
- React 19;
- Vite;
- TanStack Query;
- Zustand;
- React Router;
- existing styling/Tailwind as practical.

### Visualization

Основной сервис встраивает каталог `robcraft/` как same-origin iframe вместо
прежней React 2D-визуализации в пользовательском пути. RobCraft остаётся
автономным браузерным 3D-движком на native WebGL и ES modules без
runtime-зависимостей.

Viewer contract should support future `source`:

- `configured`;
- `recorded`;
- `live`;
- `simulation`.

Встроенный RobCraft реализует локальный `simulation`. Источники `configured`,
`recorded` и `live` остаются будущими вариантами контракта viewer.

RobCraft изолирован от React через iframe. Основной сервис передаёт
версионированный `ScenarioSpec` по строгому `robcraft-message-v1`; возврат снимка
телеметрии/операционного отчёта остаётся расширением протокола. Числовая экономика
RobCo не зависит от частоты кадров или внутреннего состояния renderer.

### Reports

HTML template → PDF renderer if stable. If PDF rendering threatens demo, HTML/print fallback is acceptable.

### Infra

Docker/Compose + Nginx + one VPS. No microservices.

PostgreSQL доступен как Compose service для воспроизводимого demo/CI и через
`DATABASE_URL` для запуска без Docker. Схема изменяется только миграциями
Alembic; startup не должен молча удалять или пересоздавать данные.

## 3. Logical layers

```text
UI
 ↓
API / application orchestration
 ↓
Domain engines
 ├─ intake normalization
 ├─ readiness
 ├─ architecture selection
 ├─ hard constraints
 ├─ procurement policy
 ├─ capacity
 ├─ economics
 ├─ scenario ranking
 └─ visualization scene builder
 ↓
Evidence/data layer
 ├─ equipment catalog
 ├─ procurement options
 ├─ regional defaults
 ├─ price evidence
 └─ source registry
 ↓
PostgreSQL
```

Текущий implementation note: PostgreSQL storage control-plane и catalog-domain
schema реализованы миграциями `0001` и `0002`, но прототип всё ещё читает
runtime-каталог из `backend/fleet`. Importer и repository boundary пока не
реализованы; публичные calculation/ScenarioSpec contracts и источник данных
под ними не менялись.

### Storage ownership

- PostgreSQL: domain state, версии, evidence metadata, procurement, проекты и
  immutable AnalysisRun.
- P0 local filesystem в named volume: пользовательские загрузки и backup
  artifacts; в БД — checksum, media type, size и storage key. S3-compatible
  adapter отложен и не нужен для защиты.
- `data/staging/`: локальная ignored workspace, не runtime dependency.
- Разрешённый import bundle: вход явного импортёра, не вторая ручная БД.
- Секреты: только server-side environment variables.

## 4. Suggested repo

```text
backend/
  app/
    api/
    domain/
      models/
      readiness/
      architecture_selection/
      constraints/
      procurement/
      capacity/
      economics/
      scenarios/
      regional/
      evidence/
    services/
      intake/
      reports/
      visualization/
    db/
    seeds/
  tests/
    unit/
    golden/
    contracts/
    smoke/
frontend/
  src/
    pages/
    features/
    entities/
    widgets/
    visualization/
robcraft/
  server.mjs
  src/
    core/
    world/
    simulation.js
  tests/
research/
  registry.md
  extracted/
docs/
```

## 5. Core modules

### `projects`
CRUD project, profiles, analysis runs.

### `intake`
LLM extraction → ParameterValue; next-question policy.

### `taxonomy`
Object/process/architecture/equipment enums.

### `regional`
Resolve RU subject into sourced regional context/defaults. Never returns unsourced precise money multiplier.

### `catalog`
EquipmentModel technical data.

### `evidence`
Source registry + field evidence + conflict flags.

### `procurement`
Supplier/service/procurement options for Russian market.

### `readiness`
Process-level score + gates/preconditions.

### `architecture_selection`
Process → candidate architectures.

### `constraints`
Architecture requirements vs equipment/configuration.

### `capacity`
Strategy interface by calculation profile.

### `economics`
Cash flow independent of robot class where possible.

### `scenarios`
Architecture + procurement alternative + economics.

### `visualization`
Scene JSON generated from scenario/process.

### `reports`
Structured ТЭО model + narrative.

## 6. Analysis orchestration

```text
1 validate input
2 normalize assumptions
3 resolve optional regional context
4 calculate completeness/confidence
5 readiness + blockers
6 propose automation architectures
7 technical hard filtering
8 build solution configurations
9 attach Russian procurement options
10 procurement filtering/scoring
11 capacity calculation
12 economics per configuration/procurement mode
13 scenario diversity/ranking
14 generate visualization scene
15 generate explanation facts
16 persist immutable AnalysisRun
```

## 7. Determinism

Same:

- normalized input;
- catalog version;
- evidence/procurement version;
- regional-default version;
- rules version;
- economics-default version;

must yield same numeric output.

Store in AnalysisRun:

```yaml
rules_version:
catalog_version:
procurement_version:
regional_defaults_version:
economics_defaults_version:
prompt_version:
app_version:
```

## 8. Evidence architecture

Do not duplicate raw source metadata in every table if possible.

`EvidenceSource`:

- id/url/type/title;
- publisher;
- observed_at;
- source_quality.

`FieldEvidence`:

- entity_type/entity_id;
- field_path;
- value snapshot;
- evidence_source_id;
- confidence;
- status `SUPPORTS|CONFLICTS|STALE`.

This allows displaying «почему мы знаем, что payload=1500 kg?».

## 9. Regional design

Regional resolver returns **context, not truth**.

```text
federal_subject
   ↓
known flags / sourced benchmarks
   ↓
user confirms/overrides if material
```

Technical environment is stored separately and can override regional hints.

Example:

- site in Magadan;
- indoor heated warehouse;
- `extreme_cold_context=true`;
- `operating_temperature=+15..+25`;
- indoor AMR is not rejected for outdoor winter temperature.

## 10. Procurement policy implementation

Recommended status enums:

`CONFIRMED_AVAILABLE | LIKELY_AVAILABLE | QUOTE_REQUIRED | SUPPLY_RISK | UNVERIFIED | DISCONTINUED`.

Filter policy:

- technical FAIL → reject;
- critical technical UNKNOWN → needs validation, not recommended automatically;
- procurement UNVERIFIED → technical reference only;
- SUPPLY_RISK → selectable only with explicit warning/policy;
- fresh confirmed RU service path → procurement advantage, not technical advantage.

## 11. Price handling

No single `robot.price`.

Price evidence must preserve boundary/scope. Economics consumes a normalized **scenario cost envelope**, not arbitrary catalog price.

If quote required:

- use user quote if provided;
- otherwise use sourced budgeting allowance only if policy allows;
- otherwise output economic sensitivity / `PRICE_DATA_LOW_CONFIDENCE`.

## 12. Testing

### Unit

- formulas;
- constraint operators;
- status transitions;
- regional fallback hierarchy;
- price-boundary validation.

### Golden

At minimum:

1. Moscow heated warehouse;
2. same process with changed shifts;
3. Magadan warehouse with regional logistics/service assumptions;
4. airport RaaS scenario;
5. negative technical blocker;
6. conflicting evidence record must not auto-match.

### Contract

Frontend fixtures validated against Pydantic/OpenAPI.

### Smoke

Create preset → analyze → what-if → fetch scene → build report.

### Persistence and import

- migrate empty PostgreSQL to head;
- import one bundle twice without duplicates;
- roll back the whole import on an invalid row;
- reject dangling evidence and unknown statuses;
- preserve organizer values when applying enrichment;
- exclude `CONFLICT`, `AMBIGUOUS_MODEL_MATCH` and `NOT_FOUND` from verified
  hard-constraint values;
- compare static and PostgreSQL repositories on golden scenarios;
- reopen AnalysisRun after the active catalog version changes.

## 13. Security MVP

- no secrets in frontend;
- server-side provider keys;
- basic auth/demo token if needed;
- upload size/type limits;
- no arbitrary code execution;
- no PII required for golden path.

## 14. Explicit non-goals

- microservices/Kafka/Celery/K8s;
- vector DB unless genuinely needed;
- ROS;
- real GIS routing;
- weather API dependence;
- live customs/logistics pricing;
- automated legal sanctions classification;
- real ERP integration.

## 15. Technical DoD

Golden warehouse path must survive LLM failure using preset/structured form and still produce identical deterministic calculations.
