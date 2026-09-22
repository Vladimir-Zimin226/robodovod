# Role labour baseline v1

Статус: **IMPLEMENTED**, C14 `engine/role-labor-baseline-v1`, 2026-09-23.

## Результат и V2-A

Добавлен pure C14 engine F08–F15 и versioned service boundary. Он принимает
только C03 `NormalizedProcess`/`RolePool` и read-only projection уже готового
C07–C11 capacity result. Capacity не пересчитывается, salary не входит в
capacity input, а исходный capacity digest сохраняется в replay bindings.

V2-A закрыт отдельным overlay
`hackathon-calculation-policy-v1+v2a-c14`: приняты role-level deficit/surplus,
explicit opt-in замены избытка и единый site-level pult/tech ledger. Сохранены
K07 visible `annual_direct` deficit assumption, K09 `ceil` ramp, K17
person-shifts fallback и K19 `airport_catering → trolley_operator`. Изменений
immutable registry v1, C03/C10 mappings и старых runs нет. Полный outcome всех
ZV2-01–07/17 закреплён в `zhenya-reference-v2-delta.md`.

## Контракты и вычисления

`LabourAnalysisRequestV1` связывает tenant/project/revision, role pool,
process-role identity, immutable capacity run/digest, USER/FILE salary source,
manual productivity, allocation, deficit-cost semantics и replacement policy.
Known salary без matching USER/FILE binding отклоняется; ноль требует C03
`ZERO_COST_ROLE`. Missing salary оставляет численность исполнимой, но делает
соответствующие labour/finance строки `INCOMPLETE`.

Engine считает без промежуточного округления:

- F08 manual shift capacity: transport cycle, cleaning `300 × hours × .85`
  ровно с одним useful factor либо explicit USER/FILE rate;
- F09 person-shifts, rotation `max(1, schedule × 1.090) × (1 + loss)` и exact
  `ceil`; schedule/H читается из C03 без clamp;
- F10 gross monthly, annual gross/direct/full/fixed overhead раздельно;
- F11 role-local replacement, deficit growth и surplus без взаимозачёта ролей;
- F12/F13 replacement limit и единый object pult ledger с conservation
  `applied = transferred + released`, `control = transferred + additional`;
- site technicians один раз от sum fleet, а control minimum — от максимума
  одновременных смен, не суммы process shifts;
- F14 forklift withdrawal ограничен base count;
- F15 deficit cost explicit/disabled либо видимый K07 annual-direct assumption.

Shared-role pool распределяется детерминированно: explicit shares имеют
приоритет и сохраняют unallocated remainder; иначе применяются person-shifts,
largest remainder и stable process ID. No-role process возвращает
`NO_FOT_BENEFIT`, а fleet=0 не создаёт control/tech персонал. Annual staffing
использует K09 `ceil(released × ramp)` и хранит remaining по роли.

## Trace, проверки и границы

Результат содержит units, provenance refs, F08–F15 nodes, каждое FLOOR/CEIL,
input/trace/capacity digests, revision и bindings policy/registry/catalog/intake.
Tenant ID остаётся обязательной частью запроса/результата; engine не пишет БД,
не логирует salaries и не меняет owner predicates. Strict request/result JSON
Schemas, warehouse/airport/clinic golden fixtures и negative salary fixture генерируются
`scripts/build_role_labour_contracts.py`; `--check` запрещает drift.

Targeted tests покрывают rotation 27, missing и marked-zero salary, запрет
не-USER/FILE salary, shared roles/reorder, deficit disabled, deficit/surplus,
replacement limit 0/1, surplus opt-in, small pult, cleaning useful factor,
control/tech once, forklift conservation, no-role и fleet=0. C14 не считает
CAPEX/OPEX/NPV/cashflow, не меняет frontend, production HTTP activation,
catalog/pool membership или старые snapshots.

Rollback аддитивен: удалить C14 engine/service boundary, schemas, generator,
fixtures, tests и этот отчёт. C03 и C07–C13 останутся воспроизводимыми.
Следующий этап — C15 `economics/purchase-cost-ledger-v1`.
