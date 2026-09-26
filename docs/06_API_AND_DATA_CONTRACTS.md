# RobCo — API & Data Contracts v0.2

**Актуализация 27.09.2026:** ниже исторический проект API, не действующий
контракт `/api/v1`. Текущий FastAPI контракт доступен через `/openapi.json`
и `/docs`; основные группы `/api/auth`, `/api/projects`, `/api/catalog`,
`/api/admin/catalog`, `/api/brain`, `/api/v2` описаны в
[комплекте финального выпуска](FINAL_DELIVERY_2026-09-27.md).

Base: `/api/v1`  
JSON: `snake_case`  
Units: SI + explicit unit fields  
Money: explicit currency/boundary/status.

## 1. General rules

- country not accepted from user in normal Project API; server uses `RU`;
- unknown != false;
- every derived/benchmark value carries source/confidence;
- breaking changes after v0.2 freeze require new schema version.

## 2. Create project

### POST `/projects`

```json
{
  "name": "Склад Север",
  "preset_id": null,
  "description": "Склад в Магадане, 800 перемещений паллет в сутки..."
}
```

Response includes optional extracted location hints, but no country question.

## 3. AI intake

### POST `/projects/{project_id}/intake/extract`

```json
{
  "message": "Склад в Магадане...",
  "known_profile": {}
}
```

Response:

```json
{
  "extracted": {
    "site_location.federal_subject": {
      "value": "MAGADAN_OBLAST",
      "source": "AI_EXTRACTED",
      "confidence": 0.98
    },
    "process.volume_per_day": {
      "value": 800,
      "unit": "missions/day",
      "source": "AI_EXTRACTED",
      "confidence": 0.99
    }
  },
  "next_question": null,
  "missing_critical": []
}
```

## 4. Update project profile

### PUT `/projects/{project_id}/profile`

Contains:

```json
{
  "object_profile": {},
  "process_profile": {},
  "site_location": {
    "federal_subject": "MAGADAN_OBLAST",
    "city": "Магадан"
  }
}
```

No `country` field required; if sent, only `RU` accepted for v0.2.

## 5. Resolve regional context

### POST `/projects/{project_id}/regional-context/resolve`

Response:

```json
{
  "site_location": {
    "country": "RU",
    "federal_subject": "MAGADAN_OBLAST",
    "city": "Магадан"
  },
  "flags": {
    "far_north": true,
    "arctic_zone": false,
    "remote_location": true,
    "island_logistics": false,
    "extreme_cold_context": true,
    "coastal_corrosion_context": true
  },
  "labor_benchmark": {
    "status": "AVAILABLE|UNKNOWN",
    "value": null,
    "unit": "RUB/month",
    "source_id": null,
    "confidence": 0.0
  },
  "logistics_class": "COMPLEX_REMOTE",
  "mobilization_class": "EXTENDED",
  "warnings": []
}
```

Important: illustrative enums; numeric benchmark remains null until sourced dataset exists.

## 6. Run analysis

### POST `/api/readiness`

Детерминированный предварительный gate до capacity/economics. Request
содержит `input`, необязательный field-level `provenance` и полные
`parameter_values/parameter_provenance` из XLSX/CSV intake. Response
`readiness-report-v1` возвращает:

- `overall_status: READY | NEEDS_VALIDATION | NOT_READY`, score и confidence;
- dimensions, blockers и preconditions;
- architecture candidates до выбора SKU;
- technical candidates с `required`, `available`, `evidence`, `reason_code` и
  `PASS | FAIL | UNKNOWN | ASSUMED` по каждому constraint.

Critical `FAIL` блокирует, critical `UNKNOWN/ASSUMED` даёт
`NEEDS_VALIDATION`. Score не отменяе hard stop. Контракт не сайзит
парк и не считает экономику.

### POST `/projects/{project_id}/analysis`

```json
{
  "mode": "FULL",
  "use_benchmarks": true
}
```

Response `AnalysisRun`:

```json
{
  "id": "run_...",
  "readiness": {},
  "architecture_candidates": [],
  "scenarios": [],
  "assumptions": [],
  "confidence": {},
  "versions": {}
}
```

## 7. Architecture candidate

```json
{
  "architecture_id": "PALLET_TRANSPORT_AMR",
  "fit_score": 88,
  "status": "RECOMMENDED",
  "reason_codes": ["REPETITIVE_INTERNAL_TRANSPORT", "PALLET_LOAD"],
  "preconditions": []
}
```

## 8. Technical candidate

```json
{
  "equipment_model_id": "RU-RONAVI-H1500",
  "technical_fit": 94,
  "hard_constraints": [
    {
      "code": "PAYLOAD",
      "status": "PASS",
      "required": {"value": 650, "unit": "kg"},
      "available": {"value": 1500, "unit": "kg"},
      "evidence_id": "ev_..."
    }
  ],
  "critical_unknowns": []
}
```

## 9. Procurement option

```json
{
  "id": "po_...",
  "equipment_model_id": "RU-RONAVI-H1500",
  "supplier": "...",
  "procurement_status_russia": "CONFIRMED_AVAILABLE",
  "procurement_confidence": 0.96,
  "procurement_modes": ["CAPEX_PURCHASE"],
  "service_coverage": "NATIONWIDE_FLY_IN",
  "spare_parts_status": "CONFIRMED|UNVERIFIED",
  "supply_risk": "MEDIUM",
  "supply_risk_reasons": [],
  "price": {},
  "last_verified_at": "2026-09-10T00:00:00+03:00"
}
```

## 10. PriceEvidence

```json
{
  "status": "PUBLIC_RANGE",
  "currency": "RUB",
  "min": 2160000,
  "max": 2700000,
  "boundary": "BARE_ROBOT",
  "tax_status": "NOT_STATED",
  "incoterm": null,
  "includes": [],
  "excludes": ["integration", "infrastructure"],
  "source_id": "src_...",
  "observed_at": "2026-09-10",
  "confidence": 0.9
}
```

## 11. Capacity DTO

```json
{
  "profile": "MOBILE_TRANSPORT",
  "required_units": 7,
  "recommended_units": 8,
  "reserve_units": 1,
  "mission_cycle_s": {
    "low": 240,
    "base": 285,
    "high": 340
  },
  "assumptions": [],
  "formula_trace": []
}
```

## 12. Economics DTO

```json
{
  "procurement_mode": "CAPEX_PURCHASE",
  "installed_capex": {"low": 0, "base": 0, "high": 0, "currency": "RUB"},
  "annual_opex": {},
  "annual_cash_benefit": {},
  "tco_5y": {},
  "npv_5y": {},
  "simple_payback_years": {},
  "regional_adjustments": [
    {
      "type": "MOBILIZATION",
      "source": "PLANNING_ALLOWANCE",
      "confidence": 0.45
    }
  ]
}
```

## 13. Scenario DTO

```json
{
  "id": "scenario_base_ru_01",
  "architecture_id": "PALLET_TRANSPORT_AMR",
  "solution_configuration": {},
  "procurement_option": {},
  "technical_fit": 94,
  "procurement_fit_ru": 88,
  "economic_fit": 73,
  "evidence_confidence": 0.84,
  "capacity": {},
  "economics": {},
  "risks": [],
  "why": []
}
```

## 14. What-if

### POST `/projects/{project_id}/analysis/{run_id}/what-if`

```json
{
  "changes": {
    "process.shifts_per_day": 3,
    "economics.labor_cost_monthly": 140000
  }
}
```

Can optionally change `site_location.federal_subject` for demo comparison, but normal UX treats location as object attribute, not a toy slider.

## 15. Visualization

Standalone RobCraft по-прежнему принимает локальную конфигурацию `{ template, seed, width, depth, rackRows, robotCount, occupancy }`. Этап A зафиксировал публичный `ScenarioSpec v1`, который формируется `POST /api/calculate`; этап B подключил его к складскому движку через строгий `generateWorldFromScenarioSpec`. Каноническая схема: `contracts/scenario-spec-v1.schema.json`; пример: `contracts/fixtures/scenario-spec-v1.golden.json`. Текущий адаптер поддерживает одну рекомендованную warehouse transport-зону, одну запись парка и один task profile. Основной сервис не импортирует внутренние структуры renderer или simulation напрямую.

Успешный расчёт возвращает `schema_version=calculation-response-v1`,
`revision_id` и `scenario_spec` с тем же `revision_id`. Неизвестные поля входа и
неизвестная major-версия ScenarioSpec отклоняются. Старые поля расчётного ответа
остались additive-совместимыми; клиентам следует перейти от позиции `[0]` к
флагу `is_best` и обрабатывать `economic_status`/статусы зон.

### GET `/visualization-scenes/{scene_id}`

```json
{
  "source": "configured",
  "schema_version": "scenario-spec-v1",
  "template": "warehouse|airport|hospital",
  "seed": "WAREHOUSE-42",
  "units": "m",
  "coordinate_system": "px|m",
  "bounds": {},
  "zones": [],
  "obstacles": [],
  "routes": [],
  "stations": [],
  "agents": [],
  "overlays": [],
  "timeline": []
}
```

Для `source = simulation` дополнительно предусматриваются `tasks`, `robot_profiles`, `people_flows`, `telemetry` и `report`. Публичной границей входа является `scenario-spec-v1`; текущие структуры `scene`, `route`, `robot` и `person` внутри `robcraft/src/` остаются внутренними и могут меняться.

## 16. Evidence endpoint

### GET `/evidence/{evidence_id}`

Returns source metadata and field/value snapshot.

## 17. Catalog endpoints

- `GET /catalog/equipment`;
- `GET /catalog/equipment/{id}`;
- `GET /catalog/equipment/{id}/procurement-options`;
- `GET /catalog/architectures`.

Admin/write endpoints are P1.

## 18. Report

### POST `/projects/{project_id}/reports`

Input: `run_id`, format.

Output:

- structured report model;
- HTML/PDF location;
- sources/evidence appendix.

## 19. Errors

- `VALIDATION_ERROR`;
- `INSUFFICIENT_DATA`;
- `NO_FEASIBLE_ARCHITECTURE`;
- `NO_ELIGIBLE_EQUIPMENT`;
- `NO_PROCUREMENT_OPTION_RU`;
- `CATALOG_DATA_MISSING`;
- `EVIDENCE_CONFLICT`;
- `PRICE_DATA_LOW_CONFIDENCE`;
- `REGIONAL_DATA_LOW_CONFIDENCE`;
- `CALCULATION_ERROR`.

## 20. Freeze policy

After `contracts-v0.2`:

- additive fields allowed;
- enum extension only when frontend tolerates unknown values;
- breaking renames/types → v0.3.
