# Runtime eligibility gap audit — organizer catalog v4

Версии: `runtime-eligibility-contract-v1` / `catalog-runtime-eligibility-audit-v1`. Аудит использует только коммитнутые локальные base/overlay/evidence/provenance данные. Порядок детерминирован: модели по `organizer_id`, позиции по `source_row_number`.

## Точное покрытие

- 187 model identities из 187.
- 223 catalog positions из 223; позиции не склеены и наследуют аудит своей model identity.
- Description overlay проверен для всех 223 позиций, но исключён из runtime facts по контракту.
- Runtime source не переключён; capacity formulas, economics и procurement не выполнялись.

| Статус | Модели | Позиции |
|---|---:|---:|
| RUNTIME_READY | 0 | 0 |
| NEEDS_FACTS | 36 | 38 |
| CONFLICT_REVIEW | 5 | 6 |
| UNSUPPORTED_CAPACITY_PROFILE | 142 | 175 |
| NOT_EQUIPMENT | 4 | 4 |

## Классы и capacity profiles

| Класс | Модели |
|---|---:|
| CLEANING | 13 |
| FIXED_PALLETIZING | 2 |
| MOBILE_TRANSPORT | 24 |
| SERVICE_DELIVERY | 1 |
| UNSUPPORTED | 147 |

Контракт фиксирует profiles `TRANSPORT_CYCLE_V1`, `DELIVERY_CYCLE_V1`, `CLEANING_AREA_V1` и `PALLETIZING_THROUGHPUT_V1`. Он определяет только обязательные входы; формул в этой итерации нет.

## Покрытие обязательных полей

| Уровень | Проверок полей | Matching-safe | Local candidate | Conflict | Missing | Safe coverage |
|---|---:|---:|---:|---:|---:|---:|
| Models | 509 | 58 | 0 | 8 | 443 | 11.39% |
| Positions | 548 | 76 | 0 | 8 | 464 | 13.87% |

### Пробелы по обязательным полям

| Поле | Модели | Позиции |
|---|---:|---:|
| capacity.cleaning_rate_m2_h | 13 | 13 |
| capacity.cleaning_width_m | 13 | 13 |
| capacity.elevator_compatibility | 1 | 1 |
| capacity.exchange_time_s | 25 | 28 |
| capacity.units_per_trip | 25 | 28 |
| specs.autonomy | 31 | 32 |
| specs.charging_requirements | 30 | 31 |
| specs.connectivity | 35 | 36 |
| specs.dimensions | 14 | 14 |
| specs.integrations | 34 | 35 |
| specs.max_speed | 29 | 30 |
| specs.min_aisle_width | 37 | 40 |
| specs.navigation | 30 | 31 |
| specs.operating_conditions | 37 | 39 |
| specs.payload | 11 | 11 |
| specs.positioning_accuracy | 2 | 2 |
| specs.service_requirements | 37 | 38 |
| specs.surface_requirements | 37 | 40 |
| specs.throughput | 2 | 2 |

## Следующее обогащение

| Рекомендация | Модели | Позиции |
|---|---:|---:|
| LOCAL_ADAPTER | 0 | 0 |
| DEEP_RESEARCH | 36 | 38 |
| HYBRID | 5 | 6 |
| NO_ACTION | 146 | 179 |

`LOCAL_ADAPTER` означает, что все блокирующие поля уже имеют локальные candidate observations; `DEEP_RESEARCH` — локальных значений для пробелов нет; `HYBRID` — нужны и разбор локального evidence/conflicts, и поиск отсутствующих фактов; `NO_ACTION` — enrichment не снимает текущий тип блокировки или не нужен.

## Конфликты

- `0ece582a-084c-4a8b-99f4-576f0e01b7c8` — SmartCube: fields: specs.max_speed; The current official CR-02 robot page states both 2.1 m/s maximum speed in the operating-principle section and 2.7 m/s linear speed in technical characteristics. Clarify which value is the applicable maximum for matching.
- `2ffc706d-fe43-4c2b-baad-a624a95ad3ce` — Робот-штабелёр RoboCV: fields: specs.aisle_requirements, specs.max_speed; Official HTML and official datasheet disagree on max speed (2.0 vs 1.67 m/s).; Official HTML and official datasheet disagree on minimum full-speed aisle (1900 vs 1800 mm); turning aisle is 2900 mm in both.
- `5760e938-9a43-45a7-b8e8-f4f2e6383930` — Ronavi H1500 (грузоподъемность до 1 500 кг): Current official page states up to 10 h autonomy while the immutable canonical layer contains an older 6 h cross-document value; no canonical field was overwritten. This may indicate a revision/configuration change.
- `89ffd69f-f07b-4bf2-8023-1fd765a2b6ff` — AMR 100 (грузоподъемность до 100 кг): fields: specs.autonomy, specs.charging_requirements, specs.dimensions, specs.integrations, specs.max_speed, specs.operating_conditions, specs.positioning_accuracy; Organizer label identifies AMR 100 with payload up to 100 kg; current official AMR100 page states up to 150 kg. Determine whether this is a newer revision, renamed configuration, or a changed specification before merging any candidate values.
- `b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1` — Робот-тягач RoboCV: fields: specs.max_speed, specs.payload, specs.positioning_accuracy; Official positioning accuracy differs: 50 mm (HTML 5 cm) versus 70 mm (PDF).; Official sources use different load metric/value: HTML 'грузоподъемность до 5000 кг' versus datasheet 'сила тяги 4000 кг'.; Official speed specifications differ: 2.2 m/s HTML versus 7.5 km/h loaded and 12 km/h unloaded in PDF.

## Decision gate

Следующий этап: `catalog/official-source-enrichment`. Он должен брать точный список полей и рекомендации из machine-readable отчёта. После него — `engine/capacity-formula-trace`; до этого runtime остаётся на `backend/fleet`.
