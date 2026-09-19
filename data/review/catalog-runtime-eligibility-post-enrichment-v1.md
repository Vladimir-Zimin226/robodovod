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
| NEEDS_FACTS | 37 | 39 |
| CONFLICT_REVIEW | 3 | 4 |
| UNSUPPORTED_CAPACITY_PROFILE | 143 | 176 |
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
| Models | 509 | 184 | 2 | 6 | 317 | 36.15% |
| Positions | 548 | 210 | 3 | 6 | 329 | 38.32% |

### Пробелы по обязательным полям

| Поле | Модели | Позиции |
|---|---:|---:|
| capacity.cleaning_rate_m2_h | 7 | 7 |
| capacity.cleaning_width_m | 9 | 9 |
| capacity.elevator_compatibility | 1 | 1 |
| capacity.exchange_time_s | 25 | 28 |
| capacity.units_per_trip | 25 | 28 |
| specs.autonomy | 19 | 19 |
| specs.charging_requirements | 18 | 18 |
| specs.connectivity | 25 | 26 |
| specs.dimensions | 8 | 8 |
| specs.integrations | 22 | 22 |
| specs.max_speed | 17 | 17 |
| specs.min_aisle_width | 29 | 31 |
| specs.navigation | 16 | 16 |
| specs.operating_conditions | 25 | 26 |
| specs.payload | 8 | 8 |
| specs.positioning_accuracy | 2 | 2 |
| specs.service_requirements | 31 | 31 |
| specs.surface_requirements | 30 | 33 |
| specs.throughput | 2 | 2 |

## Следующее обогащение

| Рекомендация | Модели | Позиции |
|---|---:|---:|
| LOCAL_ADAPTER | 0 | 0 |
| DEEP_RESEARCH | 36 | 38 |
| HYBRID | 4 | 5 |
| NO_ACTION | 147 | 180 |

`LOCAL_ADAPTER` означает, что все блокирующие поля уже имеют локальные candidate observations; `DEEP_RESEARCH` — локальных значений для пробелов нет; `HYBRID` — нужны и разбор локального evidence/conflicts, и поиск отсутствующих фактов; `NO_ACTION` — enrichment не снимает текущий тип блокировки или не нужен.

## Конфликты

- `5760e938-9a43-45a7-b8e8-f4f2e6383930` — Ronavi H1500 (грузоподъемность до 1 500 кг): Organizer revision remains unconfirmed after review; current official revision facts are not matching-safe.
- `89ffd69f-f07b-4bf2-8023-1fd765a2b6ff` — AMR 100 (грузоподъемность до 100 кг): fields: specs.autonomy, specs.charging_requirements, specs.dimensions, specs.integrations, specs.max_speed, specs.operating_conditions, specs.positioning_accuracy; Current official AMR100 150 kg revision is not proven applicable to organizer AMR 100 100 kg identity.
- `f31223c1-44c8-4410-8381-6356e2158b61` — Клинботикс 400 PRO: fields: specs.dimensions

## Decision gate

Это post-enrichment projection поверх versioned staging overlay. База данных и runtime не изменены. Следующий шаг — адаптировать 129 matching-safe facts в новый immutable ENRICHMENT bundle/version, выполнить validate-only import и повторить audit по фактически импортированному DRAFT. До этого capacity formulas и runtime activation запрещены.
