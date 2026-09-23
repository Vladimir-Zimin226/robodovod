# C29 — calculation migration acceptance

Статус: **COMPLETE**, 2026-09-23

Ветка: `qa/calculation-migration-acceptance`

Основание: C01–C28, `hackathon-calculation-policy-v1`, R00–R13 и конкурсные
gates docs 12/19. C29 не активирует production runtime и не начинает C30.

## Принятый release scope

`calculation-acceptance-manifest-v1` закрепляет SHA-256 входных и выходных
golden fixtures, три object flows и отображение каждого R00–R13 в исполняемые
тесты. Exact process coverage равна 28 строкам policy K19: warehouse 6,
airport 10, clinic 12. K01–K29 и Q01–Q12 остаются принятым versioned scope;
registry v1, catalog membership 187/223 и capacity pool 21/24 не менялись.

Warehouse release path проверяет intake user/file, constraints, capacity,
purchase и RaaS, full R13-01..49 cashflows, sensitivity, ScenarioSpec,
детерминированную simulation/2D, RobCraft 3D protocol, reopen и snapshot-driven
export. Airport и clinic проходят полный intake/normalization/constraints и
свои принятые capacity/reference-only scopes. Старый economics run открывается
через version mapping и отдельный immutable legacy replay.

## Дефекты, найденные при приёмке

- Capacity activation ошибочно считала BAS во всём discovery catalog. Policy
  теперь проверяет запрещённые family только в selectable calculation pool;
  полный каталог сохраняется.
- Economics v2 сначала сохраняла временные version labels, а затем пыталась
  изменить immutable run. Calculation теперь получает окончательные bindings
  до первого persistence transition; source/historical runs не меняются.
- Description overlay ошибочно требовал byte-identical image containers между
  версиями pypdf/Pillow. Original PDF, transcript/report и все semantic fields
  по-прежнему проверяются строго, а asset SHA связывается с байтами текущего
  проверенного extraction/import. Catalog membership и committed media не
  переписывались.
- Тестовые persistence fixtures были отвязаны от опубликованного runtime,
  lifecycle timestamps и актуального capacity slot. Fixtures теперь создают
  валидный synthetic-only runtime row без production bypass.
- Root pytest collection ограничена authoritative `backend`, поэтому архивные
  копии проекта не создают duplicate-module collisions. Frontend lint исключает
  только generated coverage/pytest cache.

## Acceptance и производительность

Новый executable gate проверяет manifest digests, R00–R13 coverage, exact
6/10/12 scopes, пять одинаковых golden replays, отсутствие внешней сети в
calculation runtime и 50 параллельных economics executions. Профиль policy:
4 vCPU, 8 GiB, CPU-only, offline; economics ≤10 s/request, simulation ≤60 s.
Golden и concurrent результаты byte/JSON-equivalent во всех повторах.

Полный PostgreSQL suite прошёл на disposable Postgres 16: 616 tests. Он
включает migrations до `0010_economics_runtime_migration`, schema metadata,
invalid rollback, historical viewer/replay, copy/delete/export compatibility,
upload/malformed inputs, tenant isolation и CSRF. Backup custom-format был
восстановлен в отдельную временную БД: revision 0010, 31 public tables;
временная БД и dump удалены.

Frontend: 66 tests, lint и production build прошли. Backend offline: 559
passed, 57 DB-only skipped; с PostgreSQL: 616 passed. Единственное предупреждение
— upstream Starlette alias AnyIO, не failure и не изменение product semantics.

## Ограничения и следующий этап

Simulation остаётся conditional model, а не deployment certification. Legacy
implementation не удалена. Production DB, route activation, DNS/TLS и сервер
не изменялись. Одноразовый Compose-стенд удаляется вместе с volumes после
приёмки.

Следующий этап — C30 `ops/production-domain-deployment-v1`, только по отдельной
явной команде владельца. В C29 он не начинался.
