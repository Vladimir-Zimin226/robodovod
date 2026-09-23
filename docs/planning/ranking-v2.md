# Ranking v2

Статус: **IMPLEMENTED**, C19 `engine/ranking-v2`, 2026-09-23.

## Результат

Добавлен pure ranking engine после C05/C06 eligibility и C18 economics. Strict
request связывает tenant/project/revision/process, frozen C18 cohort и каждый
кандидат с semantic digests constraint report, executability report и
multiprocess allocation. Вход сортируется по stable candidate ID; результат,
tie-break и replay digest не зависят от порядка кандидатов.

Eligibility применяется до score. Hard-fail и blocked executability исключают
кандидата и не публикуют score. Кандидат с неполной экономикой сохраняет только
technical score и не участвует в financial recommendation. Technical и
financial recommendation разделены; отрицательные NPV никогда не становятся
положительной финансовой рекомендацией.

## Формулы и trace

Applicability использует явные piecewise-кривые K14 для availability, aisle
margin, TRL и payload margin; integrations входят отдельным компонентом.
`N_A` исключается с reweight, `UNKNOWN` даёт ноль. Data completeness использует
immutable R08/K16 набор 36 полей с весами 3/2/1, знаменателем 77 для полного
набора и коэффициентом 1/0.5/0 для verified/unverified/missing. Unverified
поле повышает только completeness и не становится matching-safe fact.

Economy нормализуется по NPV внутри frozen process cohort после C18:
`100 × (NPV - min) / (max - min)`, а при равных NPV всем присваивается 50.
Полный score равен `0.50 × applicability + 0.35 × economy + 0.15 × data +
penalty`, с reweight для `N_A` и clamp 0..100. Сохранён единственный принятый
штраф −5 для AMR при pallet flow свыше 5000/day; fleet-density остаётся warning
без score penalty. Legacy floor 45 отсутствует.

Каждый результат содержит component values, knots, nominal/effective weights,
numerator/denominator, provenance refs, F33/F35 trace nodes и version bindings.
Replay фиксирует canonical input, C05/C06/C18 digests и trace content digest.

## V2-D

Overlay `hackathon-calculation-policy-v1+v2d-c19` разрешает противоречие
`reference v2` следующим образом:

- литеральные счётчики 23 и 31 не являются исполнимым gate;
- canonical set — точная упорядоченная совокупность stable check IDs активной
  versioned `calculation-constraint-rules-v2` (29 правил на момент C19);
- integrations — advisory applicability component и не hard fail;
- изменение состава checks требует новой версии rules/policy и новых fixtures,
  а не молчаливой подмены старого cohort.

## Контракты, проверки и границы

Сгенерированы strict schemas `ranking-request-v2`/`ranking-result-v2`, golden
fixture с тремя кандидатами и negative fixture для unsafe evidence, broken
digest и fake NPV при incomplete finance. Unit/golden tests покрывают границы
кривых, equal NPV = 50, all-negative cohort, hard fail, incomplete finance,
R08 denominator 77, all-`N_A`, advisory integrations, единственный penalty,
deterministic reorder/ties, exact rule set, schemas и service boundary.
Targeted regressions C05, C06 и C18 сохранены.

C19 не меняет frontend, DB/API persistence, capacity snapshots,
catalog/pool membership, immutable registry v1, старые runs или production
runtime. Rollback аддитивен: удалить ranking module, service boundary, schemas,
fixtures, generator, tests и этот отчёт. Следующий этап — C20
`economics/sensitivity-v1`.
