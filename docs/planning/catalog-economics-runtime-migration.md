# C28 — economics runtime migration

Статус: **COMPLETE**, 2026-09-23

Ветка: `catalog/economics-runtime-migration`

Основание: C13–C21, C26–C27, policy v1, persistence contract docs 17.

## Результат

C28 добавляет control plane для перехода economics runtime, не меняя формулы и
не активируя production. `economics-runtime-migration-policy-v1` фиксирует:

- новые активированные runs и explicit reruns направляются в
  `economics-runtime-v2`, отсутствие корректной activation конфигурации
  закрывается ошибкой, а не fallback;
- historical view и отдельный legacy replay читают только immutable saved
  snapshot с проверкой SHA-256;
- rerun всегда создаёт новый run и не изменяет source run;
- `fte_cost_rub` без доказанного старого basis получает
  `UNKNOWN_LEGACY_BASIS`; migration никогда не выводит из него monthly gross;
- rollback изменяет только активную route configuration и сохраняет историю.

Legacy `backend/economics.py` оставлен на месте. Registry v1, catalog
membership, C27 capacity slot/rollout и production runtime не менялись.

## Контракты и dual-run

Добавлены strict policy/report schemas и approved golden report, связанный
byte-digest с legacy warehouse fixture и C21 commercial scenarios golden.
Каждая разница классифицирована:

| Группа | Gxx | Почему числовой delta отсутствует |
|---|---|---|
| Labour basis | G06, G07, G39, G52 | legacy FTE cost не доказывает gross/payroll basis |
| Capacity/constraints | G12, G34, G48 | изменились формулы, trace и входной contract |
| Commercial lifecycle | G21–G32, G36, G47 | изменились scenarios, money semantics, allocation, ranking и provenance |

Непривязанная разница блокирует approval. Для несопоставимых basis поле
`numeric_delta` обязано быть `null`; это исключает ложную точность.

## Persistence и rollback

Migration `0010_economics_runtime_migration` аддитивно создаёт:

- `analysis_run_economics_versions` — immutable one-to-one mapping run →
  execution route/viewer/replay/rerun/FTE basis;
- `economics_route_activations` — append-only activation history с policy и
  report digest, actor и rollback version.

Backfill читает существующие `FULL_ANALYSIS` и добавляет mapping. Ни один столбец
`analysis_runs` не обновляется. Downgrade запрещён при v2 run mapping или rollout
history. Применение migration само по себе не создаёт active route. Сервис
activation требует approved report; rollback закрывает текущую запись и
добавляет новую route запись, не переписывая расчётные данные.

## API, frontend и совместимость

- Старые create/rerun endpoints сохранены для production compatibility и
  помечены FastAPI/HTTP deprecation metadata; C28 их не переключает скрыто.
- Новый CSRF-protected `POST /api/v2/projects/{project_id}/economics-runs`
  принимает только server-orchestrated v2 input, отвергает `fte_cost_rub` на
  любой глубине и исполняется лишь при approved active route. `source_run_id`
  задаёт explicit rerun и сохраняется как parent, не меняя source snapshot.
- Owner-scoped `legacy-replay` возвращает проверенный saved result; cross-tenant
  запрос выглядит как 404. Это read-only GET, mutations сохраняют CSRF gate.
- Run response содержит `economics_runtime` mapping и migration notice.
- Frontend fail-closed проверяет соответствие run economics version/viewer:
  legacy открывается прежним viewer, v2 — C21 viewer. Browser не считает деньги.
- Copy/delete продолжают работать на уровне project lifecycle; mapping удаляется
  только каскадно вместе с run. C26 export читает те же immutable snapshots и
  сохраняет исходную economics version.

## Проверки

Выполнены targeted contract/runtime, evidence export, persistence collection,
frontend model и syntax checks. PostgreSQL integration cases включают upgrade
head/metadata, immutable replay, tenant isolation, activation/rollback и
отсутствие run rewrite; без `TEST_DATABASE_URL` они корректно skip и не служат
основанием для production activation. Docker, full suites и production DB не
запускались.

## Rollback и ограничения

До C29 production activation запрещена. Откат C28 означает route rollback через
сохранённую activation запись; исторические runs и их mappings остаются. DDL
downgrade допустим только до появления rollout history/v2 mappings. Backup /
restore и production rehearsal относятся к C29/C30 gates; C28 предоставляет
проверяемые механизмы, но не заявляет deployment readiness.

Следующий этап — C29 `qa/calculation-migration-acceptance`; в C28 он не начат.
