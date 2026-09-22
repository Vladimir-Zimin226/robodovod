# Frontend process-role intake v2

Статус: **IMPLEMENTED**, C04 `frontend/process-role-intake-v2`,
policy `hackathon-calculation-policy-v1`, 2026-09-22.

## Результат

`frontend/src/processRoleIntakeV2.js` содержит presentation projection
всех 28 K19 process codes с разбиением 6/10/12 по объектам.
Для каждого блока сохраняются `block_id`, `process_id`, activation
source, scope, typed quantity kind/unit и suggested K19 roles. Airport catering
остаётся на `trolley_operator`; ZV2 role/allocation mapping не применён
до V2-A.

`ProcessRoleIntakeV2.jsx` добавлен как отдельная вкладка intake:

- object→blocks→roles с active/inactive статусами;
- empty inactive blocks не получают hidden values;
- demand, schedule, distance и batch отправляются как raw values;
- role headcount и monthly gross salary имеют единицы
  `person` и `RUB/person/month`;
- missing salary объясняет labour/finance incompleteness, но не
  подменяется default;
- no-role block явно маркируется `NO_FOT_BENEFIT`;
- assumption confirmation создаёт override event с новой
  `input_revision`;
- normalization response показывает raw/source/normalized values,
  units, required inputs и server-derived per-block status;
- native checkbox/button/details controls, labels, `aria-expanded` и
  `aria-live` сохраняют keyboard/accessibility path.

## Граница с legacy и API

V2 serializer формирует `calculation-intake-v2` без `normalized_value`,
`fte_cost_rub`, capacity, labour и finance arithmetic. Локальные
`/15.624` и `×15.624` остаются только в legacy `ParamsPanel`/
`ZonalPanel` для старых DTO и не попадают в v2 flow.

Client contract вызывает
`POST /api/v2/calculation-intake/normalize`, проверяет schema version и
отбрасывает response для устаревшей revision. В C04 endpoint покрыт
mock contract; production backend/domain logic не активированы. Текущие
`/api/calculate`, legacy intake, file upload, saved v1 runs и DB schema не
изменялись.

## Проверка и rollback

`frontend/tests/process-role-intake-v2.test.mjs` покрывает exact projection,
каждую suggested role, inactive block, salary, no-role, H>24, assumption
override, stale request, mocked API, accessibility и clinic golden fixture C03.

Rollback — удалить v2 module/component/test и вкладку из `IntakeScreen`.
Ни storage migration, ни изменения old run при rollback не требуются.
