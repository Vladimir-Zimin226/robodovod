# Реестр расчётных параметров v1

Статус: **IMPLEMENTED**, C02, 2026-09-22.

## Результат

`hackathon-calculation-parameter-registry-v1` материализует принятые константы
и policy-параметры до реализации формул. Снимок содержит 228 атомарных
параметров, 27 записей покрытия источников, 5 правил supersession и 39
scenario-параметров. Реестр и JSON Schema генерируются детерминированно;
manifest закрепляет их hashes и hashes источников.

Каждая запись содержит стабильный ID и semantic name, decimal value, единицу,
quantity kind, domain, applicability, scenario/year, override policy,
provenance kind, source refs и source digest, решения Kxx, потребителей,
effective version и localization keys. `extra` fields запрещены. Параметры
сортируются по ID, а совпадения semantic/applicability/scenario/year и orphan
references отклоняются.

## Артефакты и использование

- `data/calculation/registry-v1.json` — immutable snapshot;
- `data/calculation/registry-v1.manifest.json` — file/semantic/schema/source
  digests и контрольные counts;
- `contracts/calculation-parameter-registry-v1.schema.json` и manifest schema —
  сериализованные strict contracts;
- `backend/calculation/registry.py` — cached loader и проверка snapshot,
  manifest, schema, source bindings и counts;
- `scripts/build_calculation_registry.py` — единственная точка регенерации;
  `--check` проверяет exact committed output.

Reference-файлы нужны только для сборки и проверки provenance. Runtime loader
читает committed JSON и manifest и не зависит от ignored каталога reference.
Production API, legacy DTO, формулы, frontend и каталог не подключены к
реестру на этом этапе.

## Зафиксированные решения и границы

Реестр включает R02/R06 assumptions, согласованные R03/R04 replacements и
policy K01/K05–K09/K11–K12/K14/K16/K18/K21–K23/K25–K29. Coverage ledger явно
отделяет значения реестра от формул, пользовательских входов, vendor inputs,
policy rules, superseded значений и запрещённых unsafe defaults.

Зарплата не имеет default и остаётся пользовательским monthly gross input.
Значения 10 picks/min и 800 m²/h не стали vendor facts. Принятый знаменатель
полной карточки — 77. Для каждого из трёх сценариев сохранены availability,
peak/reserve, CAPEX, service, supervision и ramp по годам 1–5 с явным правилом
для year 6+.

## Проверка и rollback

Targeted acceptance покрывает exact generation, schema/domain failures,
duplicate/orphan protection, source hashes, tamper detection, idempotent load,
scenario completeness, supersessions, отсутствие salary/vendor defaults и
знаменатель 77. Rollback — удалить аддитивные C02-артефакты; runtime поведение
при этом не меняется, поскольку consumers будут подключаться в последующих
этапах.

Следующий этап — C03 `intake/process-role-normalization-v2`: он использует
контракты C01 и этот реестр как versioned source нормализационных правил, но не
должен вычислять capacity или finance.
