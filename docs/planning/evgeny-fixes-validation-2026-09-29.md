# Протокол проверки замечаний Жени

Дата: 29.09.2026. Работы локальные; push, production-деплой и отправка форм
не выполнялись. [Аудит и критерии приёмки](evgeny-fixes-audit-2026-09-29.md).

## Локальные коммиты

| Коммит | Содержание |
|---|---|
| `126feb5` | Аудит обоих файлов замечаний, классификация, план, SHA-256 первоисточников |
| `4ec6706` | Отдельный C16 v3, service selection, C17 contract binding, новый golden и тесты |
| `3a115a4` | Сохранение трёх NPV, PDF v2, совместимость исторического гостевого PDF, пример отчёта |

## Воспроизведение и результат

| Проверка | До исправления | После исправления |
|---|---|---|
| Доход 1 млн RUB/год | C16 v2: постоянный доход; тест v3 не проходит, версии v3 нет | C16 v3: 1 000 000; 1 050 000; 1 102 500; 1 157 625; 1 215 506.25 RUB. Строки затрат содержат эти доходы с минусом |
| Новая comparison projection | Тест на `npv_base` падает с `KeyError` | Все шесть сценариев содержат `npv_base`, `npv_scenario`, `npv_project` из C18, без нового вычисления NPV в отчёте |
| Подпись PDF | Тест на `NPV проекта (инкремент)` падает | Для старого снимка явная подпись инкремента; при полных согласованных метриках три отдельные строки |
| Исторический гостевой PDF | При общем обновлении VERSION тест сравнения байтов падает | Гостевой генератор закреплён за v1; существующие PDF/manifest/ZIP не перегенерированы и совпадают по байтам |

Для одинакового входа с включённым доходом переход v2 → v3 даёт:

- прирост эффекта за пять лет **525 631.25 RUB**;
- прирост NPV проекта **302 469.90 RUB** при ставке 15%; проверено отдельной
  суммой дисконтированных годовых разностей, допуск округления ≤0.01 RUB;
- неизменный TCO покупки;
- совпадение окупаемости с её расчётом из differential CF;
- в C17 ежегодная разность EBITDA с доходом/без дохода равна соответствующей
  индексированной сумме. Платёж RaaS и ответственность сторон не меняются.

Проверены также текущая граница налога и сохранность primary metrics: при
положительном EBIT иллюстративный налог ненулевой и уменьшает supplement CF,
но не переписывает NPV/ROI/payback/TCO принятого pretax профиля.

Проверочный PDF из локальных offline-fixtures:
[NPV reconciliation v2](assets/evgeny-fixes-2026-09-29/npv-reconciliation-v2.pdf)
(449 326 байт, 12 страниц, Creator `investor-presentation-v2`).
[Полные сохранённые NPV шести сценариев](assets/evgeny-fixes-2026-09-29/npv-values.json)
содержат source refs и digest результата. Это тестовый пример, не данные
пользовательского объекта и не подтверждённое коммерческое предложение.

## Команды проверки из Windows cmd

```bat
cd /d "C:\Users\Владимир Королев\PycharmProjects\Конкурсы\robodovod"
.venv\Scripts\python.exe -m pytest backend/test_financial_cashflows.py backend/test_raas_cashflows.py backend/test_multiprocess_allocation.py backend/test_role_labour.py backend/test_investor_report.py backend/test_warehouse_guest_investor_report.py backend/test_sensitivity_v1.py backend/test_final_economics.py backend/test_economics_orchestrator.py backend/test_economics_glossary.py backend/test_calculation_migration_acceptance.py -q --tb=short --basetemp .test-evgeny-fixes-final-rerun
.venv\Scripts\python.exe scripts/build_financial_v3_fixture.py --check
.venv\Scripts\python.exe scripts/build_economics_glossary.py --check
.venv\Scripts\python.exe scripts/build_warehouse_guest_investor_report.py --check
```

Результат: **118 passed**, 34.92 s; все три `--check` завершились с кодом 0.
JUnit сохранён локально в
`backup/evgeny-fixes-2026-09-29/pytest-final.xml`. Проверены старые golden v1/v2,
registry, role-pool conservation, округление общих затрат, перестановка
процессов, missing-input outcomes, six scenarios, sensitivity, частичный и
исторический экспорт. `git diff --check` без ошибок.

Первый запуск без `--basetemp` столкнулся с ACL чужого каталога
`C:\Temp\pytest-of-Владимир Королев`; каталог внутри workspace устранил
проблему. Предупреждение Starlette/AnyIO относится к устаревшему alias в
установленной зависимости и не является ошибкой расчёта.

## Сохранность и ограничения

- Пять исходных файлов кода/документов, изменённых или добавленных до работы,
  совпадают с резервной копией по SHA-256: `economics_orchestrator.py`,
  planning README, USER_GUIDE HTML и два посторонних planning-документа.
  Они не вошли ни в один коммит этой задачи.
- Архив `backup/evgeny-fixes-2026-09-29/preexisting-worktree.zip` содержит
  **2 112** доступных исходных файлов. Архив проверен повторным чтением и
  SHA-256; manifest лежит рядом в `sha256.json`.
- **4 753** файла временных браузерных профилей недоступны для чтения даже
  после разрешённого запуска с расширенным доступом. Их список — локальный
  `unavailable.json`; они оставлены на месте без изменений. Полную копию этих
  файлов сделать в текущем окружении не удалось.
- Существующие application datasets, registry v1, golden v1/v2 и гостевой
  пакет сохранены. Новый доходный профиль выбирается через service явно;
  UI/runtime остаётся на v2 и явно исключает дополнительный доход.
- Общий `scripts/build_financial_contracts.py --check` сообщает **прежний
  drift только `financial-analysis-request-v1.schema.json`**: вложенная
  схема operating staff отстаёт от существующих optional staffing полей.
  Эта модель входа в задаче не менялась. Генератор сначала затронул этот
  посторонний drift; рабочий файл был возвращён к HEAD и не включён в коммиты.
  Затронутые v3 result и C17 request проверены JSON Schema и Pydantic.

## Открытые решения

Нужны отдельные методические версии для after-tax primary и налогового
default (Fix 1/2/A), вывода ричтраков (Fix 5), распределения объектного ФОТ
по процессам (Fix 6), ручной/механизированной уборки (Fix 9). Основания,
конфликты первоисточников и проверяемые условия для этих версий перечислены
в аудите. Fix 7 уже корректен; проверка C17 с новым C16 подтверждает это.

## Push после самостоятельной проверки

```bat
cd /d "C:\Users\Владимир Королев\PycharmProjects\Конкурсы\robodovod"
git status --short
git log --oneline origin/main..HEAD
git push origin main
```

Посторонние незакоммиченные файлы не отправляются командой push.
