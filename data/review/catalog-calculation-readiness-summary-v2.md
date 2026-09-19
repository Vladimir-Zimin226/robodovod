# Calculation/deployment readiness audit v2

Contract v2 разделяет предварительный capacity-расчёт и инженерную готовность. Scenario
assumptions имеют явную provenance и не становятся vendor facts. Runtime и
active catalog не переключены, capacity formulas не изменены. Для запуска через
текущий backend всё ещё требуется materialization adapter; economics в scope
этого gate не входит.

## Exact coverage

- Models: 187.
- Positions: 223.
- Accepted research cohort: 26 models.
- Local adapter facts: 1.

## Calculation status

| Status | Models | Positions |
|---|---:|---:|
| CALCULATION_READY | 6 | 6 |
| CALCULATION_READY_WITH_ASSUMPTIONS | 15 | 18 |
| CALCULATION_BLOCKED | 19 | 19 |
| UNSUPPORTED_CAPACITY_PROFILE | 143 | 176 |
| NOT_EQUIPMENT | 4 | 4 |

## Deployment status

| Status | Models | Positions |
|---|---:|---:|
| DEPLOYMENT_READY | 0 | 0 |
| DEPLOYMENT_REVIEW_REQUIRED | 40 | 43 |
| UNSUPPORTED_CAPACITY_PROFILE | 143 | 176 |
| NOT_EQUIPMENT | 4 | 4 |

## Расчётный пул accepted research cohort

| Model | Class | Calculation status |
|---|---|---|
| Робот для транспортировки деталей и инструментов | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| Беспилотный тягач (Когнитив Пилот) | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| Робот-штабелёр RoboCV | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| Ronavi SR (грузоподъемность до 50 кг) | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| MARK 2 SE | CLEANING | CALCULATION_READY |
| Ronavi H1500 (грузоподъемность до 1 500 кг) | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| Клинботикс 600 | CLEANING | CALCULATION_READY |
| Ronavi SD (грузоподъемность до 10 кг) | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| Ronavi H2000 (грузоподъемность до 2 000 кг) | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| AMR 1500 (грузоподъемность до 1 500 кг) | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| Робот-тягач RoboCV | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| DMR 600 (грузоподъемность до 600 кг) | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| DMR 1200 (грузоподъемность до 1 200 кг) | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| Ronavi M (грузоподъемность до 1200 кг) | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| АК-SC80 | CLEANING | CALCULATION_READY |
| РУБИ-С-03 | CLEANING | CALCULATION_READY |
| MULE | MOBILE_TRANSPORT | CALCULATION_READY_WITH_ASSUMPTIONS |
| БРО 3.0 | CLEANING | CALCULATION_READY |
| Клинботикс 400 PRO | CLEANING | CALCULATION_READY |

`CALCULATION_READY_WITH_ASSUMPTIONS` означает: model-specific formula facts
доказаны, а операционные cycle inputs должны прийти из сценария; при их
отсутствии применяется зафиксированный fallback. Это не означает готовность к
закупке или внедрению.
