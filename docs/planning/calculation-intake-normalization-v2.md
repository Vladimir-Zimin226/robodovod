# Intake и нормализация процессов/ролей v2

Статус: **IMPLEMENTED**, C03 `intake/process-role-normalization-v2`,
policy `hackathon-calculation-policy-v1`, 2026-09-22.

## Результат

`backend/calculation/intake.py` добавляет strict request/response v2 без
подключения к production API. Вход сохраняет object, block, process и
role identity, activation source, raw value/unit, aliases, user confirmation,
LLM text и file hash/sheet/row/cell. Unknown fields запрещены.

K19 закреплён exact projection из 28 process codes: warehouse 6, airport 10,
clinic 12. Scope, role suggestions и allowed quantity kinds заданы из policy
v1; reference v2 не изменил role mapping и allocation fallback. `process_id`,
activation source, raw role allocation и additional-income input сохранены
для последующих V2-gates, но не исполняются.

`backend/calculation/units.py` выполняет только типизированные physical
conversions. Batch/container conversion не угадывается. Pallets, boxes,
cases, carts, deliveries, portions, kg, samples, sets, bins, items, m² и picks
имеют разные typed units. Schedule валидирует
`shifts × hours <= 24`; clamp отсутствует. Active block требует
positive demand и schedule, inactive block сохраняет identity и
`NOT_APPLICABLE` demand без defaults.

Зарплата хранится по роли как monthly gross RUB/person/month.
Для custom intake numerical salary принимается только из USER/FILE;
K05 demo assumption требует explicit confirmation. PRESET/LLM salary
остаётся raw, а normalized salary остаётся `MISSING`. Годовой labour
cost на этом этапе не считается.

## Compatibility, security и replay

`adapt_project_file_v1` адаптирует только уже валидный
`IntakeResult`. Все 42/39/57 raw profile values, profile version, upload hash
и field locations сохраняются. Warehouse receiving+shipping проекция
суммирует два исходных flow как 2000 pallet/day, но сохраняет
оба raw parameter code; clinic food остаётся 1950 portion/day,
а airport baggage — 35000 item/day. Legacy `normalized_input`, old import runs,
storage schema и endpoint не изменялись.

Существующие file-size/type/name, CSV encoding/header/row, XLSX signature,
archive expansion/path traversal и atomic invalid-preview gates сохранены.
Единственное аддитивное уточнение file provenance — XLSX cell address.
Секреты, salaries и raw uploads не логируются; tenant/persistence path
не менялся.

## Артефакты и rollback

- `contracts/calculation-intake-request-v2.schema.json`;
- `contracts/calculation-intake-normalization-v2.schema.json`;
- warehouse/airport/clinic golden fixtures в `contracts/fixtures/`;
- `scripts/build_calculation_intake_contracts.py` с `--check`;
- targeted acceptance в `backend/test_calculation_intake.py`.

Rollback — удалить аддитивные C03 modules/contracts/fixtures/tests и XLSX
cell metadata. Production runtime и DB migration отсутствуют, поэтому
rollback не меняет old runs и v1 import behavior.
