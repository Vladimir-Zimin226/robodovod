# C27 — capacity runtime dual-run rollout

Статус: **COMPLETE**, 2026-09-23. Этап реализует отдельный rollout capacity
source, но не активирует его в production и не начинает economics migration C28.

## Результат

- Введены strict contracts `capacity-source-activation-policy-v1`,
  `capacity-catalog-dual-run-report-v1` и `capacity-source-status-v1`.
- Policy закрепляет опубликованный `organizer-catalog-v4`, его content digest,
  capacity runtime version, полный срез 187 моделей / 223 позиции и неизменный
  расчётный pool 21 модель / 24 позиции: 6/6 `CALCULATION_READY`, 15/18
  `CALCULATION_READY_WITH_ASSUMPTIONS`, 0 deployment-ready и 0 BAS.
- `CatalogRuntime.load_capacity()` читает только отдельный activation slot
  `capacity`. Fallback на `discovery`, legacy `runtime` или встроенный Robot
  запрещён; отсутствие и невалидность различаются versioned reason codes.
- C11 `POST /api/v2/capacity-analyses` привязан к этому capacity reader.
  Клиент получает серверный catalog version в trace; frontend не содержит
  новых capacity/economics формул.
- Activation требует approved report с совпадающими policy digest, catalog
  content digest, counts, membership и runtime version. В БД сохраняются
  policy version, report digest и rollback mode/target. Первый rollout
  откатывается деактивацией; последующая смена — восстановлением предыдущей
  опубликованной версии.
- Golden dual-run фиксирует неизменное membership и две разрешённые разницы
  projection/version binding по G48/K29. Любое неизвестное отличие, лишнее
  expected difference, чужая версия контракта или extra field блокирует approval.

## Артефакты

- `backend/catalog_capacity_rollout.py` — policy validation, capacity-only
  projection, deterministic comparison и approval gate.
- `backend/catalog_runtime.py`, `backend/catalog_repository.py` — отдельный
  request-scoped capacity source без fallback.
- `backend/catalog_activation.py` и migration `0009_capacity_catalog_rollout` —
  атомарный approved activation и persisted rollback binding.
- `contracts/capacity-source-activation-policy-v1.json` и JSON schemas —
  версионированная доступность и fail-closed protocol.
- `contracts/fixtures/capacity-catalog-dual-run-report-v1.golden.json` —
  воспроизводимый approved report, генерируемый
  `scripts/build_capacity_rollout_contracts.py`.

## Проверка acceptance gate

- Generator `--check` подтверждает deterministic policy/schema/golden files.
- Backend tests проверяют exact 187/223, 21/24, 6/15 model split, 6/18
  position split, отсутствие BAS, model/position identity, invalid/no-active
  statuses, отсутствие fallback, route binding и sanitized API error.
- Contract tests блокируют unmatched difference, unknown version и extra field.
- Activation integration покрывает approval metadata, idempotency и rollback;
  PostgreSQL-вариант запускается только с `TEST_DATABASE_URL`. В локальной
  среде этапа переменная отсутствовала, поэтому два DB-теста были пропущены и
  никакая база или production activation не изменялись.
- Frontend contract tests подтверждают отображение capacity source и отсутствие
  клиентской арифметики; lint и production build проходят.

## Совместимость и границы

Discovery slot и legacy runtime slot не изменили семантику. Старые runs,
ScenarioSpec v1/v2, immutable registry v1, catalog/pool membership и economics
snapshots не переписываются. Миграция 0009 аддитивна; её применение в текущей
или production БД этим этапом не разрешено. Production C30 не затронут.

Следующий этап: C28 `catalog/economics-runtime-migration` — versioned route
switch для новых economics runs при сохранении legacy replay и rollback.
