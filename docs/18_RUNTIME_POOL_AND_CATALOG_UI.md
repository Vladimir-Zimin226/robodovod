# Расчётный runtime-пул и его отображение в каталоге

Статус: обязательный контракт следующей малой итерации
`catalog/runtime-pool-materialization-ui-21`.

## Цель

Материализовать доказательно пригодный пул БРС для предварительного расчёта и
сделать его видимым пользователю, не сокращая discovery-каталог.

- Полный каталог сохраняет 187 model identities и 223 позиции.
- В предварительном capacity-расчёте участвует ровно 21 model identity,
  представленная 24 catalog positions.
- Из них 6 моделей / 6 позиций имеют статус `CALCULATION_READY`.
- Ещё 15 моделей / 18 позиций имеют статус
  `CALCULATION_READY_WITH_ASSUMPTIONS`.
- Остальные позиции остаются видимыми, но не становятся расчётными.
- БАС в этот runtime-пул не входят.
- Calculation readiness не означает deployment, procurement или economics
  readiness. Deployment-ready моделей сейчас 0.

Авторитетные входы:

- `contracts/runtime-calculation-readiness-contract-v2.json`;
- `data/review/catalog-calculation-readiness-audit-v2.json`;
- `data/review/catalog-calculation-readiness-summary-v2.md`;
- versioned BASE/ENRICHMENT данные и их provenance.

## Backend и runtime

1. Материализация использует только опубликованные vendor facts и явно
   обозначенные scenario assumptions из contract v2.
2. Нельзя придумывать ТТХ, цены, economics, procurement или deployment facts.
3. Assumption хранится отдельно от vendor fact и сохраняет provenance.
4. Если текущий `Robot` DTO требует недоказанные поля, следует создать
   отдельный capacity-runtime DTO/path, а не ослаблять evidence gate и не
   заполнять поля фиктивными значениями.
5. До активации обязательны schema validation, exact-count checks,
   validate-only/DRAFT import, deterministic ordering, idempotency и
   integration tests.
6. API discovery-позиции должен явно отдавать как минимум:
   `calculation_readiness_status`, `calculation_ready`,
   `calculation_requires_assumptions`, `calculation_profile`,
   `calculation_blockers` и `runtime_catalog_version`.
7. Один model identity может соответствовать нескольким catalog positions;
   API и UI не должны смешивать счётчик 21 модели со счётчиком 24 позиций.

## UI каталога

Каталог показывает все 223 позиции. Расчётная пригодность — отдельное измерение,
а не условие видимости карточки.

- Каждая расчётная позиция получает заметный тег `Участвует в расчёте`.
- Для `CALCULATION_READY_WITH_ASSUMPTIONS` рядом показывается уточнение
  `С допущениями` и доступно объяснение допущений/provenance.
- Добавляется фильтр `Участие в расчёте` со значениями `Все`, `Участвуют`,
  `Требуют данных`.
- Фильтр сочетается с поиском, типом, производителем и сортировкой.
- В интерфейсе явно подписываются оба числа: `21 модель` и `24 позиции`.
- Нерасчётные позиции остаются доступными для discovery, сравнения и просмотра
  evidence, но не могут незаметно попасть в расчёт.
- Ошибка загрузки официального каталога показывается явно; возврата к удалённому
  встроенному fleet нет.

## Acceptance gate

- API и UI показывают ровно 21 расчётную model identity и 24 расчётные позиции.
- Статусы разделены на 6 ready и 15 ready-with-assumptions моделей
  (6 и 18 позиций соответственно).
- Полный каталог по-прежнему содержит 187 identities / 223 positions.
- Фильтр `Участвуют` выдаёт только 24 позиции; `Все` не скрывает остальные.
- БАС не попадают в расчётный пул.
- Ни один расчётный тег не заявляет deployment/procurement/economics readiness.
- Backend unit/integration и frontend component/contract tests проверяют теги,
  фильтры, counts, комбинирование фильтров и негативные случаи.

Следующий этап после прохождения gate — `engine/capacity-formula-trace`.
