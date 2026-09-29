# Проверка исправления продуктовой цепочки, 29.09.2026

Область проверки: локальная рабочая копия и одноразовая PostgreSQL 17 на
`127.0.0.1:55439`; production, push, production-формы и SSH не использовались.
Диагностический `backup` читался только для проверки и воспроизведения.
Посторонние изменения, существовавшие до работы, не вошли в коммиты.

## Воспроизведение и результат по этапам

| Этап | До изменения | После изменения |
| --- | --- | --- |
| P0, экспорт | Реальный warehouse PDF v2 с реальным manifest отвергался клиентом при корректном source binding; сохранений было 0. | Клиент принимает versioned v1/v2/v3, проверяет исходный run, ETag, digest и устаревший источник. Реальный HTTP backend→Node: 23 passed. |
| P1, деньги | Нулевая цена робота приводила к ошибке старой процентной чувствительности. | Новый результат с нулевой базой имеет отдельную схему v4 и явный статус недоступности старой чувствительности. Сами шесть финансовых вариантов и NPV сохраняются. Старая методика и старые снимки не пересчитаны. |
| P2–P3, форма | Коды и числовое округление мешали прочесть сравнение; длинные формы труда и допущений сливались. | Человеческие подписи, точные значения, группы условий и адаптивная форма проверены 30 DOM/геометрическими проверками и клиентскими тестами. |
| P4, модели | В списке кандидатов не было привязанных миниатюр выбранных позиций. | HTTP-тест проверяет URL и размер media по `position_id`, а также fallback при его отсутствии; старые scores и binding остаются прежними. |
| P5, 2D/3D | У склада 11 роботов физический повторитель допускал максимум 2; условный 2D показывал другое движение. У аэропорта было 37 выборок пересечения за первый модельный час, минимум ≈0,097 м. | Новая версия использует общее расписание и часы, отдельные безопасные стоянки, ресурсные ожидания, swept-проверки и честное отличие визуальной очереди от сохранённого KPI. |
| P6, PDF | Исторический экспорт нельзя было менять без отдельной версии представления. | Старый генератор v2 и гостевые байты сохранены; активное представление v3 даёт понятную сверку денег, персонала и источников. |

Воспроизведение P0/P5: `backup/product-chain-audit-2026-09-29/audit_client_and_playback.mjs`.
Подробные локальные результаты находятся в игнорируемом каталоге
`.test-product-chain-implementation/session/`.

## Проверки

| Проверка | Результат / доказательство |
| --- | --- |
| Денежная матрица, одноразовая PostgreSQL | 3/3 профиля (склад, аэропорт, клиника), 13 вариантов на каждый: цена, ноль цены/сервиса/ставки, фиксированные и процентные затраты, горизонт, отсутствующая оплата, advanced/basic/partial, отрицательный NPV. Preview = saved = reopened по значениям; PDF/XLSX/CSV; независимая сумма дисконтированных потоков; исходные snapshots и checksums неизменны. `money-matrix-final.log`. |
| Backend по затронутым веткам | 93 passed, 11 предупреждений окружения. `backend-final.log`. Отдельно PDF и гостевой отчёт: 20 passed. |
| Frontend и RobCraft | 287 passed, 0 skipped. `node-final.log`; swept-пути 17/17 после явной проверки людей. `safe-playback-final.log`. |
| Browser UI | 30 проверок DOM, кодов, связей и геометрии на 1366/390 px. `ui-acceptance.log`. Собранная страница безопасного playback: склад, аэропорт, клиника, ×1/×2/×4, pause/stop/restart/seek, скрытая вкладка, 3D source binding. `playback-browser/evidence.json`. |
| FPS, SwiftShader | Chrome/ANGLE SwiftShader Device Subzero. На 1366 px: 2D callback 133,7 FPS; 3D callback 85,2 FPS при целевой отрисовке сцены 30 FPS. На 390 px: 3D callback 121,8 FPS. Максимальный интервал кадра 90,3/14 мс, высота панели 350/300 px постоянна, горизонтальное переполнение 0. Это замер программного GPU, не характеристика устройств пользователей. |
| PDF | 20 исторических + 39 синтетических денежных + 1 длинный видимый текст = 60 PDF, 623 страницы. Все страницы отрисованы и просмотрены на контактных листах, текст выделяется/ищется, DejaVu встроен и имеет ToUnicode, bounding boxes внутри страницы, технических кодов в тексте нет. `pdf-review/evidence.json`, `contact-01.jpg`…`contact-52.jpg`. |
| История | 31/31 членов `backup/manifest.json` совпали по SHA-256. Старый гостевой `report.pdf` и manifest совпали побайтно (`build_warehouse_guest_investor_report.py --check`). Старый генератор v2 оставлен отдельным файлом, snapshots не меняются при генерации. |
| Статика и сборка | `eslint src tests` и `vite build` прошли; `git diff --check` проверяется перед завершением. |

Локальные команды повторения из корня проекта, PowerShell:

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://chain_test@127.0.0.1:55439/chain_acceptance'
python -m pytest backend/test_product_chain_money_postgres.py -q
Remove-Item Env:TEST_DATABASE_URL
python -m pytest backend/test_investor_report.py backend/test_evidence_export.py backend/test_evidence_export_v2.py backend/test_evidence_export_v3.py backend/test_economics_preview.py backend/test_evgeny_project.py backend/test_warehouse_guest_investor_report.py backend/test_final_economics.py backend/test_backend_evidence_client.py backend/test_candidate_comparison_api.py -q
$tests = @(Get-ChildItem frontend/tests -Filter '*.test.mjs' | ForEach-Object FullName) + @(Get-ChildItem robcraft/tests -Filter '*.test.mjs' | ForEach-Object FullName)
node --preserve-symlinks --preserve-symlinks-main --test $tests
python scripts/browser_safe_playback.py
python scripts/review_pdf_product_chain.py
python scripts/build_warehouse_guest_investor_report.py --check
cd frontend
node node_modules/eslint/bin/eslint.js src tests
node node_modules/vite/bin/vite.js build
```

Тест PostgreSQL требует одноразовую локальную БД с активированным реальным
каталогом; его нельзя считать пройденным, если pytest помечает его skipped.
Проверки браузера используют локальные фикстуры и Chrome, PDF-обзор сохраняет
изображения только в игнорируемом тестовом каталоге.

## Оставшиеся ограничения

- Геометрия 2D/3D условная и не подтверждает безопасность реального объекта.
  Измерения фактического GPU пользователя и production-пути не проводились.
- При нулевой базе старая процентная чувствительность не определена; это явно
  показано в результате v4. Шесть вариантов и расчётные потоки доступны.
- Полный `eslint .` в этой рабочей копии не смог прочитать посторонний
  untracked Chrome-профиль `frontend/.tmp-p5/`; проверка `src tests` прошла.
- Существующий drift схемы `financial-analysis-request-v1.schema.json` вне
  данной цепочки не менялся. Vite сообщает о крупном chunk после сборки.
- Docker Engine здесь отсутствует. Сборка контейнеров, состояние схемы и
  smoke на production требуют отдельной проверки оператором перед выпуском.
