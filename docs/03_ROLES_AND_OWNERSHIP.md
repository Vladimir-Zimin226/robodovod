# RobCo — роли и ownership v0.2

## 1. Владимир — Technical Lead

Основная зона: **как это реализовать надёжно и детерминированно**.

Ownership:

- architecture/repo/contracts;
- backend/FastAPI;
- Pydantic/SQLAlchemy/Alembic;
- AI extraction/provider adapter;
- readiness/constraints/capacity/economics/scenario engines;
- procurement/evidence data model;
- regional context resolver;
- seed/data ingestion;
- testing/golden tests;
- Docker/deploy/observability;
- report generation backend;
- demo reliability.

## 2. Женя — Product Logic & Experience Lead

Основная зона: **что именно считать, почему и как это показать пользователю**.

Ownership:

- process taxonomy;
- architecture taxonomy;
- readiness questions/blockers;
- calculation assumptions/specification;
- procurement comparison logic as product rules;
- regional-impact rules as business specification;
- UX/information architecture;
- interview/wizard structure;
- scenario diversity;
- what-if behavior;
- visualization/storytelling;
- research curation;
- demo narrative.

## 3. Interface между ролями

Женя поставляет rule specification вида:

```yaml
rule_id: ARCH_PALLET_AMR_001
condition:
  load_type: PALLET
  transport_required: true
outcome:
  architecture: PALLET_TRANSPORT_AMR
reason: ...
examples:
  positive: []
  negative: []
```

Владимир:

- превращает rule spec в schema/code;
- добавляет unit/golden tests;
- не зашивает бизнес-логику в prompt LLM;
- возвращает неоднозначности на product decision.

## 4. Joint decisions

Только совместно:

- final scope cuts;
- demo curated catalog;
- threshold readiness;
- formulas/defaults;
- scenario ranking policy;
- procurement language;
- naming/pitch;
- final demo datasets.

## 5. Optional domain reviewer

Инженер по роботизации/автоматизации/логистике нужен как sanity check:

- hard constraints;
- mission cycle;
- charging assumptions;
- pallet/rack geometry;
- fixed-cell cycle logic;
- environmental constraints;
- commissioning realism.

## 6. DRI matrix

| Subsystem | DRI | Reviewer |
|---|---|---|
| Product statement | Женя | Владимир |
| Process taxonomy | Женя | domain reviewer |
| Automation architectures | Женя | Владимир + domain |
| API/domain model | Владимир | Женя |
| AI intake | Владимир | Женя |
| Readiness methodology | Женя | Владимир/domain |
| Hard constraints | Владимир | Женя/domain |
| Capacity formulas | Владимир | Женя/domain |
| Economics formulas | Владимир | Женя |
| Procurement policy | Женя | Владимир |
| Procurement implementation | Владимир | Женя |
| Regional business rules | Женя | Владимир |
| Regional resolver/data | Владимир | Женя |
| UI/UX | Женя | Владимир |
| Visualization product logic | Женя | Владимир |
| RobCraft engine / renderer / simulation | Владимир | Женя |
| ScenarioSpec и интеграция RobCo ↔ RobCraft | Владимир | Женя |
| Demo narrative | Женя | Владимир |
| Demo stability | Владимир | Женя |

## 7. Concrete pool — Владимир

### P0

- domain contracts v0.2;
- initial DB schema;
- deterministic analysis orchestrator;
- AI extraction JSON;
- technical catalog importer;
- procurement/evidence records;
- RU regional resolver;
- hard constraints;
- mobile capacity;
- economics incl. purchase + recurring mode;
- scenario API;
- visualization scene API;
- `scenario-spec-v1` и адаптер автономного RobCraft;
- contract/golden tests интеграции 3D-сцен;
- golden tests;
- deploy/reset/fallback.

### P1

- fixed manipulation engine;
- aerial profile;
- admin catalog tooling;
- evidence inspector;
- PDF export polish.

## 8. Concrete pool — Женя

### P0

- 3 demo process specs;
- architecture decision table;
- critical intake questions;
- readiness rules;
- curated 8–10 demo solutions from RU/CN/global references;
- per-solution reason/caveat copy;
- economics defaults table;
- regional factor policy;
- result screen UX;
- warehouse visualization spec;
- demo script.

### P1

- продуктовая проверка warehouse/airport/clinic сценариев RobCraft;
- naming/SEO remeasurement;
- wider discovery catalog;
- content/landing architecture.

## 9. Daily sync

15 minutes, three questions:

1. Что сегодня стало end-to-end working?
2. Какое product/engineering решение блокирует другого?
3. Что сегодня вырезаем, чтобы сохранить golden path?
