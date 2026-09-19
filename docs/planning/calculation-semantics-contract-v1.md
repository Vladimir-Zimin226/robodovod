# Calculation semantics contract v1

Статус: **IMPLEMENTED**, этап C01 `contracts/calculation-semantics-v1`,
policy `hackathon-calculation-policy-v1`, дата 2026-09-20.

Этот документ описывает аддитивный контрактный слой до исполнения формул.
Production API, legacy DTO, каталог, runtime slots и численные алгоритмы C07+
не переключаются.

## Артефакты

- `backend/calculation_contracts.py` — строгие Pydantic DTO и каноническая
  сериализация; DTO реэкспортированы из `backend/models.py` без включения в
  действующие endpoint-модели.
- `contracts/normalized-process-v1.schema.json` и
  `contracts/role-pool-v1.schema.json` — object/process/role identities,
  единицы, quantity kinds, schedule, discriminated exchange и отсутствие
  salary fallback.
- `contracts/calculation-partial-result-v1.schema.json` — независимые статусы
  capacity/finance и nullable incomplete/blocked layers.
- `contracts/calculation-trace-v1.schema.json` — envelope, version bindings,
  provenance, DAG, conversions, assumptions, constraints, rounding, issues и
  replay bindings.
- `contracts/calculation-semantics-manifest-v1.json` — precision policy,
  source-to-parameter map F01–F07, compatibility records и draft полей C02.
- `contracts/capacity-analysis-*-v*.schema.json` — зафиксированный для C11
  `POST /api/v2/capacity-analyses`, request без обязательной экономики,
  success envelope и machine-readable error/partial envelope; endpoint пока
  не зарегистрирован.
- `contracts/calculation-parameter-registry-v1.proposed.schema.json` — только
  proposed registry shape; значения и полный source coverage реализует C02.
- `contracts/fixtures/calculation-*.json` — synthetic specification fixtures,
  не карточки vendor и не production catalog rows.

Все генерируемые schema/fixtures воспроизводятся
`scripts/build_calculation_contracts.py`; `--check` запрещает незаметный drift.

## Семантика границы

Числа передаются как canonical decimal strings. Dimension `QuantityKind`
проверяет физическую размерность единицы, а отдельный process quantity kind
различает pallet/box/case/cart/delivery/portion/kg/sample/set/bin/item/m²/pick;
typed demand unit обязан соответствовать обоим. Semantic name обязан своей
canonical normalized unit. Unknown
quantity не содержит числового значения: у неё обязательны status,
expected unit и typed missing reason. `0`, `MISSING` и `NOT_APPLICABLE` не
взаимозаменяемы.

`NormalizedProcess` использует ровно один exchange path: `TOTAL` либо полный
`SPLIT(load, unload)`. Новый total 45 остаётся 45; split 45+45 нормализуется в
90; legacy 45→90 разрешён только provenance-gated adapter. Активный процесс
требует положительный typed demand; inactive block не получает скрытых
defaults. 28 process codes и union ролей K19 замкнуты enum-контрактами; identity
роли — `(object_scope, role_code)`, а custom label не создаёт новый role code.

Capacity и finance не зависят друг от друга по nullability. `BLOCKED` capacity
имеет `value=null` и machine-readable blockers. `INCOMPLETE` finance не
уничтожает готовый capacity. Fleet 0 для активного demand имеет capacity 0,
coverage 0, utilization null и overload; inactive block — NOT_APPLICABLE.

## Trace, replay и версии

Порядок formula nodes топологический и проверяется; stable IDs, formula/source
versions, source digests и supporting nodes обязательны. Vendor fact допустим
в исполняемом trace только с matching-safe evidence status; CONFLICT,
AMBIGUOUS_MODEL_MATCH, NOT_FOUND и UNKNOWN могут появляться только как причина
отказа, не как числовой input.

Канонизация использует UTF-8, Unicode NFC, сортировку object keys и
фиксированный порядок contract arrays. Decimal strings не округляются.
`trace_content_digest` покрывает semantic trace вместе с run identity, но
исключает само поле digest и `runtime_metadata`; build/runtime IDs поэтому не
ломают replay. `canonical_input_digest` привязан к immutable normalized input.
Неизвестные major/policy versions отвергаются, автоматического downgrade нет.
Обновление registry/catalog создаёт новый run; старый snapshot не меняется.

Основание этих технических уточнений: ТЗ требует версии и воспроизводимость,
R00 требует immutable replay, policy §5 задаёт precision, policy §7 требует
fail-closed исход при неоднозначности. Проверяемые примеры находятся в
`backend/test_calculation_contracts.py`.

## Security и presentation

Trace не меняет tenant model. Будущие persistence/API этапы обязаны применять
существующие owner/tenant predicates к snapshot, trace и export. Raw uploads,
зарплаты, email, имена и tokens не входят в общие application logs. Contract
issue содержит stable reason code и field/node refs; localized `message` —
presentation, а не единственный источник смысла.

## Совместимость и следующий этап

`CalculationResponse` и `ScenarioSpec v1` не изменены. C01 добавляет новые DTO,
но не вызывает adapter и не меняет `/api/calculate`. Будущий C11 endpoint
зафиксирован как `POST /api/v2/capacity-analyses`; C01 его не активирует.
Единственный legacy
adapter, предусмотренный контрактом, — provenance-gated exchange migration;
его реализация относится к C03/C07.

C02 получает manifest source map, proposed registry schema, точные unit/kind
enums, `VersionBindings.registry_version/digest` и правила immutable ordering.
C02 должен наполнить registry всеми R02/R06 parameters, source digests,
decision refs и supersession links; C01 не содержит registry values.
