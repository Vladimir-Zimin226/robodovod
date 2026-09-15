# RobCo — Full Backlog v0.2

## 1. Priority legend

- **P0** — required for credible hackathon golden path;
- **P1** — strong differentiation/polish if P0 stable;
- **P2** — post-demo or optional;
- **CUT** — explicitly do not build now.

Owners: `V` Владимир, `Z` Женя, `V+Z`, `EXT` reviewer.

## 2. P0 — Product freeze

| ID | Task | Owner | Done when |
|---|---|---|---|
| A01 | Freeze product statement v0.2 | Z | copy appears consistently in UI/pitch |
| A02 | Freeze 3 demo object families | V+Z | warehouse/airport/clinic |
| A03 | Freeze process taxonomy v0.2 | Z | enough for golden path |
| A04 | Freeze automation architecture taxonomy | Z | each demo maps to defined architecture |
| A05 | Freeze explicit CUT list | V+Z | no scope creep |

## 3. P0 — Research/data freeze

| ID | Task | Owner |
|---|---|---|
| B01 | Re-check official LCT updates/Q&A | Z |
| B02 | Curate 8–10 demo equipment/configurations | Z |
| B03 | Verify every demo-visible hard constraint/source | Z+EXT |
| B04 | Verify procurement status/service/price boundary | Z |
| B05 | Prepare minimal regional defaults for demo regions | Z |
| B06 | Mark R9 quantitative Wordstat as not production evidence | Z |

P1: real Wordstat remeasurement.

## 4. P0 — Contracts & persistence

| ID | Task | Owner |
|---|---|---|
| C01 | Implement contracts v0.2 Pydantic | V |
| C02 | DB entities Project/Profile/AnalysisRun | V |
| C03 | EquipmentModel + EvidenceSource/FieldEvidence | V |
| C04 | ProcurementOption + PriceEvidence | V |
| C05 | AutomationArchitecture + SolutionConfiguration | V |
| C06 | RegionalContext | V |
| C07 | Alembic migration + seed command | V |

## 5. P0 — AI intake

| ID | Task | Owner |
|---|---|---|
| D01 | Structured extraction schema | V |
| D02 | Prompt v0.2 | V+Z |
| D03 | Next-question policy | Z |
| D04 | Never ask country | V |
| D05 | Extract region/city when mentioned | V |
| D06 | Ask subject only when material | V+Z |
| D07 | `не знаю` / benchmark flow | V |
| D08 | Provider failure fallback to form/preset | V |

## 6. P0 — Readiness & architecture

| ID | Task | Owner |
|---|---|---|
| E01 | Dimensions/gates final spec | Z |
| E02 | Deterministic readiness engine | V |
| E03 | Architecture decision rules | Z |
| E04 | Architecture selector implementation | V |
| E05 | Preconditions/reason codes | V+Z |

## 7. P0 — Catalog/evidence/procurement

| ID | Task | Owner |
|---|---|---|
| F01 | Technical catalog schema | V |
| F02 | Field evidence/provenance | V |
| F03 | RU seed records | V from Z data |
| F04 | CN→RU seed records | V from Z data |
| F05 | Global technical refs | V |
| F06 | Catalog tiers DISCOVERY/SELECTABLE/DEMO_CURATED | V |
| F07 | Procurement status/confidence | V |
| F08 | Service/spares/supply-risk model | V |
| F09 | Price boundary/status model | V |
| F10 | Evidence conflict flag prevents unsafe auto-match | V |

P1: catalog admin UI.  
CUT: universal auto scraper.

## 8. P0 — Hard constraints

| ID | Task | Owner |
|---|---|---|
| G01 | Rule interface/config | V |
| G02 | Payload/load constraint | V |
| G03 | Geometry/aisle/turning | V |
| G04 | indoor/outdoor/environment | V |
| G05 | runtime/charging | V |
| G06 | integration requirement | V |
| G07 | fixed-cell reach/payload basics | V |
| G08 | PASS/FAIL/UNKNOWN + reasons | V |

## 9. P0 — Regional context RU

| ID | Task | Owner |
|---|---|---|
| RGN01 | RU subject enum/reference | V |
| RGN02 | Region extraction from input | V |
| RGN03 | Minimal region resolver | V |
| RGN04 | Actual environment overrides regional climate hint | V |
| RGN05 | Labor fallback hierarchy | V+Z |
| RGN06 | Logistics/mobilization classes | Z spec / V impl |
| RGN07 | Service coverage adjustment | V |
| RGN08 | Assumption/confidence UI output | V+Z |

P1: broader 89-subject dataset.  
CUT: fake universal regional multiplier.

## 10. P0 — Capacity

| ID | Task | Owner |
|---|---|---|
| I01 | Capacity strategy interface | V |
| I02 | MOBILE_TRANSPORT formula spec | Z |
| I03 | MOBILE_TRANSPORT implementation | V |
| I04 | Golden tests | V |
| I05 | MOBILE_SERVICE minimal | V |

P1: FIXED_MANIPULATION.  
P2: AERIAL_INSPECTION if not needed for main demo.

## 11. P0 — Economics

| ID | Task | Owner |
|---|---|---|
| J01 | Installed CAPEX structure | V+Z |
| J02 | Annual OPEX | V+Z |
| J03 | Labor benefit hierarchy | V |
| J04 | Logistics + mobilization lines | V |
| J05 | Purchase cash flow | V |
| J06 | One recurring mode (RaaS/managed service) | V |
| J07 | TCO/payback/NPV | V |
| J08 | Conservative/base/upside | V+Z |
| J09 | Price uncertainty propagation | V |
| J10 | No throughput monetization without user value | V |

## 12. P0 — Scenario engine

| ID | Task | Owner |
|---|---|---|
| K01 | Architecture scenario schema | V |
| K02 | Procurement alternatives inside architecture | V |
| K03 | Technical/procurement/economic/confidence separate | V |
| K04 | Diversity/ranking rules | Z |
| K05 | Why-this / caveat output | Z+V |

## 13. P0 — What-if

- shifts;
- volume;
- labor cost;
- robot/system price;
- integration cost;
- utilization;
- optional region comparison for demo.

Owner V implementation / Z UX.

## 14. P0 — Frontend

| ID | Task | Owner |
|---|---|---|
| M01 | New Project / description | Z/V |
| M02 | Extracted facts + assumptions | Z/V |
| M03 | Readiness result | Z/V |
| M04 | Recommended architecture | Z/V |
| M05 | Candidate/procurement comparison | Z/V |
| M06 | Separate Technical / Procurement / Economics | Z/V |
| M07 | Economics cards | Z/V |
| M08 | What-if | Z/V |
| M09 | Risks/preconditions | Z/V |
| M10 | Evidence/source inspector light | Z/V |

## 15. P0 — Visualization

- [DONE] версионированный `ScenarioSpec` между RobCo и RobCraft;
- [DONE/STANDALONE] строгий warehouse transport-адаптер, полный рассчитанный парк и задания из спроса;
- [DONE/STANDALONE] непрерывный событийный режиссёр камеры этапа C;
- [NEXT] same-origin iframe и атомарная загрузка ревизии этапа D;
- [DONE/STANDALONE] процедурные warehouse, airport и hospital layouts;
- [DONE/STANDALONE] маршруты, роботы, люди и грузовые операции;
- [DONE/STANDALONE] first-person/free-camera 3D-анимация;
- before/after;
- basic KPI overlay.

P1: встраивание RobCraft в основной React flow и связь KPI с расчётным ядром.  
CUT: claims инженерного digital twin, ROS/Gazebo/Isaac и калибровка по реальной телеметрии.

## 16. P0 — Report

- structured report DTO;
- HTML template;
- assumptions/confidence;
- procurement section;
- regional context section;
- sources/evidence appendix;
- print/PDF fallback.

## 17. P0 — Demo datasets

1. Warehouse Moscow/standard.
2. Warehouse remote/cold comparison (Magadan optional wow-case).
3. Airport/logistics RaaS.
4. Clinic cleaning/delivery.
5. Negative technical case.

## 18. P0 — Quality & infra

- formula unit tests;
- constraints tests;
- evidence conflict test;
- regional fallback test;
- 5 golden scenarios;
- API smoke;
- UI happy-path E2E;
- seed/reset;
- provider fallback;
- Docker Compose;
- public HTTPS demo;
- logs/health.

## 19. P1

- real Wordstat measurement;
- fixed manipulation depth;
- дальнейшая детализация airport/clinic после интеграции RobCraft;
- richer regional dataset;
- catalog admin;
- richer evidence inspector;
- PDF polish;
- programmatic SEO draft pages;
- current procurement refresh command.

## 20. P2

- subsidy hints;
- broader UAV model;
- more service modes;
- actual supplier quote upload;
- comparative TCO history;
- live regional tariffs.

## 21. CUT

- country selector;
- global market engine;
- ROS/Gazebo/Isaac;
- arbitrary CAD/BIM;
- route optimizer research project;
- live weather dependence;
- 89-subject pseudo-precision;
- sanctions circumvention logic;
- hundreds of models;
- perfect live price scraping;
- real ERP/WMS integration;
- mobile app;
- billing/multitenancy.

## 22. Recommended execution order

1. Contracts/domain freeze.
2. Curated demo data freeze.
3. Warehouse analysis end-to-end without frontend polish.
4. Procurement + regional + economics integrated.
5. Results UI.
6. Visualization.
7. Report.
8. Airport/clinic presets.
9. Stability/fallback.
10. Pitch/polish.

**Rule:** если пункт не улучшает golden path или judging evidence — он не P0.
