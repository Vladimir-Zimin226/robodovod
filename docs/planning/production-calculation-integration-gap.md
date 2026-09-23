# Production calculation integration gap — 2026-09-24

Статус: **BLOCKED FOR FULL PUBLIC RELEASE**. Владелец выбрал полноценный сервис
с работающим расчётом после исправлений, а не каталог без расчёта. Эта проверка
не изменяет принятые формулы, registry v1, catalog membership или исторические
runs.

## Исполняемый путь сейчас

1. Основной экран `frontend/src/App.jsx:recalc` вызывает legacy
   `POST /api/calculate`; `saveAnalysis` выбирает legacy `/analysis-runs` для
   результата этого пути. Пустой fresh DB не имеет `runtime` slot, а
   `organizer-catalog-v4` не содержит `runtime_robots`. Активация этого каталога
   в `runtime` правильно отвергается.
2. Экран «Процессы и роли v2» делает только
   `POST /api/v2/calculation-intake/normalize`. Он не выбирает capacity position
   и не создаёт capacity/economics run.
3. Persistence v2 API требует `resolve_economics_version` и
   `calculate_economics_v2`; `main.app` их не передаёт. Тест API подставляет
   fixture executor, который возвращает готовый commercial bundle; такого
   production orchestrator в репозитории нет.
4. Даже прямой вызов production C11 с готовым capacity-кандидатом использует
   `conservative_constraints`. Он знает только object/process scope и даёт
   `NEEDS_VALIDATION`, в частности для обязательных проверок technical passport
   и availability. `analyze_capacity` в этом состоянии возвращает `BLOCKED`.
   Положительный C11 golden явно подменяет provider на тестовый `ELIGIBLE`.
   Это допустимый unit test формул, но не доказательство исполнимости на VDS.

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

## Что требуется для полноценного выпуска

- Для конкретного поддержанного процесса и позиции: проверить официальные
  model facts и источник технического паспорта/availability, собрать явные
  требования объекта с provenance, провести C05 до `ELIGIBLE` без test provider.
  Текущий `catalog_capacity_runtime.json` намеренно фиксирует
  `deployment_ready_models=0`; выдавать его за deployment-ready нельзя.
- Подключить UI к нормализованным процессам, отдельному capacity slot и
  server-owned C11 endpoint. Для неизвестных фактов показывать `BLOCKED` или
  `PARTIAL` с причиной, не подставлять скрытые значения.
- Реализовать production orchestrator C13–C21 поверх неизменных validated
  snapshots и явных user inputs. Создавать commercial bundle и ScenarioSpec v2
  на сервере, затем подключить versioned economics route. Fixture bundle не
  может быть runtime executor.
- Пройти новый сквозной тест браузер → API → official catalog → C05/C11 →
  C13–C21 → immutable run → reopen/export, включая tenant/CSRF, goldens,
  deterministic replay и повторный C29 gate. Только после этого C30 может
  продолжить migration/bootstrap/traffic switch.

Следующее внешнее входное условие для подтверждённого сценария внедрения:
паспорт/комплектация и подтверждённая availability выбранной модели, а также
фактические требования конкретного объекта. Организаторский demo уже доступен
для разработки предварительного режима, но без этих подтверждений C05 не
может честно выдать `ELIGIBLE`; изменение gate на `PASS` по умолчанию запрещено.
