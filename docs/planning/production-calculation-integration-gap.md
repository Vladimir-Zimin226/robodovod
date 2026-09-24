# Production calculation integration gap — 2026-09-24

Статус: **TECHNICAL GAP CLOSED / C30 TRAFFIC SWITCH HOLD**, повторная проверка
2026-09-24. Владелец выбрал полноценный сервис с работающим расчётом, а не
каталог без расчёта. Реализация не меняет registry v1, catalog membership,
строгий C05 или исторические runs.

## Исполняемый путь сейчас

1. Экран «Процессы и роли v2» нормализует ввод, выбирает одну из трёх
   документированных demo-моделей в активном capacity-каталоге и сохраняет
   immutable C11 run через `/api/v2/capacity-analyses`. После C11 отдельная
   форма требует явные monthly gross, ручную производительность, внедрение,
   сервис, энергию, общеплощадочные затраты и RaaS-условия. Браузер не считает
   экономику и не подставляет неизвестные закупочные условия.
2. `main.app` подключает production executor
   `production-economics-orchestrator-v1` и активную versioned economics route.
   Executor читает только сохранённый owner/project-scoped C11 snapshot и тот
   же опубликованный capacity catalog, исполняет C13–C21 и возвращает strict
   commercial bundle v2 + ScenarioSpec v2. Runtime fixture bundle не
   импортируется.
3. Economics input сохраняется в envelope `economics-run-input-v2` вместе с
   `capacity_run_id`; result/scenario spec/checksums и version mapping
   неизменяемы. Reopen и snapshot-driven ZIP export работают для нового run.
   Explicit rerun создаёт новый run, а CSRF-защищённый v2 replay заново
   исполняет исходные snapshots и требует точного совпадения hashes, revision,
   versions и diagnostics. Source run не переписывается.
4. Строгий production C11 по умолчанию продолжает использовать
   `conservative_constraints`: unknown passport/availability дают
   `NEEDS_VALIDATION`, и обычный `VERIFIED` run остаётся `BLOCKED`.
   Добавленный по просьбе владельца `PRELIMINARY_DEMO` требует явного
   подтверждения, не меняет C05, не проходит известный `FAIL` или неполную
   dependency closure и возвращает только `WITH_ASSUMPTIONS` с warning/trace.
   Это численная предварительная оценка, не deployment eligibility.

Дополнительно исходный backend image не содержал committed snapshots
`data/calculation` и `data/review/process-profile-coverage-v1.json`. Dockerfile
исправлен; локально собранный image успешно загрузил registry, executability,
constraints, process catalog и C11 version bindings.

## Аудит материалов организаторов (2026-09-24)

Проверены локальные `Разобрать/Материалы от организаторов/ТЗ/*.pdf`,
`Датасет/Датасеты_хакатон.xlsx`, `Датасет/Примеры_решений_типы_объектов.docx`,
`Датасет/catalog_export_v4.csv` и текст каталога. Эти файлы остаются локальными,
не добавляются в Git. В Excel лист «Легенда и использование» прямо называет
базовые значения типовым объектом для **демо-расчёта**, а диапазоны min/max —
валидацией формы. Это не обмеры конкретного склада. В ТЗ и дополнениях
допускаются явно описанные допущения для демонстрации предварительной оценки,
но не вымышленная точность или статус готовности к внедрению.

Для складского примера есть 20 000 м² общей и 10 000 м² активной площади,
проходы 3,5/2,8 м, бетонный пол, ровность 3 мм/2 м, 2 смены по 11 ч,
1 000 входящих и 1 000 исходящих паллет в сутки, масса паллеты 800 кг.
Путь 25 м в Excel — **отбор на строку**, не маршрут паллетоперевозчика;
120 м в policy K23 — отдельное раскрываемое сценарное допущение. Ни одно
из этих значений нельзя незаметно принять за подтверждённые параметры
площадки пользователя. В частности, C05 помечает применимое требование с
`ASSUMPTION` как `ASSUMED`/`NEEDS_VALIDATION`, а не `PASS`.

Каталог содержит MULE (`ecd7d582-b342-449a-b43b-66288d159a32`) как
пилотируемую модель с ценой 3 млн ₽; документ с примерами решений описывает
Ronavi H1500, DMR Carrier P и MARK 2 SE как **примеры**, не как паспорта.
[Официальная страница MULE](https://sm-robotics.ru/) подтверждает заявленные
производителем 1500 кг и 1,3 м/с; [официальная страница Ronavi H1500](https://ronavi-robotics.ru/catalogue/h1500)
публикует 1500 кг, 1,5 м/с и минимальную ширину проезда 750 мм. Публичная
страница с ТТХ не равна подписанному техпаспорту выбранной комплектации,
не подтверждает измеренную доступность робота в конкретном режиме и не
удостоверяет параметры пола/маршрута на объекте. Значение 70–85 % загрузки
AMR в легенде Excel — типовой KPI/допущение, а не vendor availability fact
для C05. Не превращать эти источники в `MATCHING_SAFE` для полей
`technical_passport_available` и `availability` без отдельной проверки.
Даже на сайте Ronavi [описание кейса](https://ronavi-robotics.ru/media/kak-rabotaet-robotizirovannaya-zona-na-sklade-vostok-servis)
указывает 1,3 м/с, тогда как карточка модели — 1,5 м/с: для конкретного run
нужно закрепить версию/комплектацию и provenance, а не выбирать удобное число.

Вывод: материалы уже позволяют воспроизводимый **предварительный demo** с
явными допущениями и provenance, но не закрывают C05 до `ELIGIBLE` для
публичного утверждения пригодности конкретной модели к конкретному объекту.
Отдельно остаются технические разрывы UI → C11 → C13–C21, описанные выше.
Три авторские карточки с source/assumption/unknown разделением:
[demo-model-profiles-v1](demo-model-profiles-v1.md). Это не паспорта
изготовителей.

## Повторная production integration acceptance

- Реальный `organizer-catalog-v4` импортирован в disposable PostgreSQL 16,
  опубликован и активирован только в `capacity`/`discovery`; legacy `runtime`
  намеренно не активировался. Авторский MULE profile прошёл HTTP API C11
  (`WITH_ASSUMPTIONS`) → C13–C21 → immutable run → reopen → deterministic
  replay → evidence ZIP. Во всех шести purchase/RaaS сценариях procurement
  остался `UNVERIFIED`, рекомендация к закупке не создана.
- Production projection привязана новым golden digest к economics activation
  report. Full backend/PostgreSQL suite: **625 passed**. Frontend: **73 passed**,
  ESLint и production build зелёные. JSON Schema commercial bundle проходит.
- Tenant isolation, CSRF для create/replay, capacity/result/trace integrity,
  catalog-version binding, rerun parentage и export digest проверены.

## Оставшиеся границы выпуска

- Для конкретного поддержанного процесса и позиции: проверить официальные
  model facts и источник технического паспорта/availability, собрать явные
  требования объекта с provenance, провести C05 до `ELIGIBLE` без test provider.
  Текущий `catalog_capacity_runtime.json` намеренно фиксирует
  `deployment_ready_models=0`; выдавать его за deployment-ready нельзя.
- Для неизвестных фактов продолжать показывать `BLOCKED` либо честный
  `WITH_ASSUMPTIONS` в подтверждённом demo-mode. Не подставлять скрытые значения.
- C05 `ELIGIBLE`/deployment-ready по-прежнему требует внешних паспортов,
  комплектации, availability и фактических условий объекта. Это не блокирует
  разрешённый предварительный demo, но блокирует такое утверждение в UI/API.
- До переноса проверенного commit в `main`, server backup/migration/bootstrap,
  production smoke и TLS проверки C30 traffic switch остаётся на HOLD.
- Fresh catalog по-прежнему нельзя активировать в legacy `runtime`: новые
  поддержанные расчёты идут только через capacity/economics v2, а historical
  viewer/replay остаются snapshot-only. Legacy route не удаляется до отдельной
  совместимой миграции всех неподдержанных custom flows.

Следующее внешнее входное условие для подтверждённого сценария внедрения:
паспорт/комплектация и подтверждённая availability выбранной модели, а также
фактические требования конкретного объекта. Организаторский demo уже доступен
для разработки предварительного режима, но без этих подтверждений C05 не
может честно выдать `ELIGIBLE`; изменение gate на `PASS` по умолчанию запрещено.
