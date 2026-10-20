# R3 — локальная проверка расчётов, 20.10.2026

Проверен закоммиченный полный bundle `organizer-catalog-v4`: 187 моделей, 223 позиции, 10 файлов. Все SHA-256 и размеры совпадают с `manifest.json`. Это локальная копия данных, а не снимок активированной production PostgreSQL.

| Проверка | Локальный результат |
|---|---|
| Готовность capacity | 6 моделей READY, 15 READY_WITH_ASSUMPTIONS, 19 BLOCKED, 143 UNSUPPORTED, 4 NOT_EQUIPMENT |
| Исполнимость формул | 21 модель / 24 позиции CATALOG_EXECUTABLE; 19 моделей с недостающими безопасными фактами |
| Инженерная готовность | 0 DEPLOYMENT_READY; 40 моделей требуют инженерной проверки |
| Регрессии | 167 passed: каталог, физические ограничения, парк, CAPEX/OPEX, ROI/NPV и согласованность PDF/CSV/XLSX |

Расчётная исполнимость модели не означает готовность установки. Проверки экономики используют контролируемые сценарные данные и не утверждают цены или ROI активной production версии. `TEST_DATABASE_URL` и `DATABASE_URL` отсутствуют; тест импорта/активации полного bundle в PostgreSQL не выполнялся. Прямая команда `build_catalog_calculation_readiness_v2.py --check` не запустилась из-за отсутствующего staging-модуля `scripts.build_catalog_official_source_staging`; профильный тест `test_generated_v2_artifacts_are_schema_valid_and_idempotent` прошёл на зафиксированном отчёте.

Следующая проверка: изолированная одноразовая PostgreSQL, импорт BASE/ENRICHMENT, publish/activate и `test_production_economics_integration.py`; отдельно сверить с фактически опубликованной версией. Секреты и производственные данные в этот отчёт не записывались.
