# F3 — административный каталог и актуализация данных

**Статус: принят локально, критерии F3 проверены. F4 не начат.**
Основание: [план](final-product-remediation-2026-09-26.md),
[исходный аудит](final-tz-compliance-audit-2026-09-26.md), пункт ТЗ 3.3.5.
Предыдущий этап: F2, `2e8f2c3`. Production не обновлялся.

## Результат

ADMIN получил `#admin-catalog`: собственный черновик от published,
create/edit решений и отдельных предложений, ТТХ с units/types и evidence,
страна/доступность/применимость/инфраструктура/срок службы, валюты/НДС/услуги,
источники с URL/document/dates/comment, справочники и разрешённые нормы.
Есть staged before/after diff, validate, отдельные publish/activate,
атомарное переключение выбранных указателей, UI rollback и actor/time/change
audit. Опубликованная версия доступна только для просмотра.

Поддержан JSON `admin-catalog-v1`, 4 МиБ: download → upload → строгая проверка
→ staged draft → ручная правка → validate/publish → явная activation. Повтор
одного файла с тем же кодом возвращает существующую версию; другой документ
с занятым кодом отклоняется. Базовые операции обходятся без shell.

Версии хранятся аддитивно в `admin_catalog_documents`; миграция
`0012_admin_catalog` не обновляет organizer rows, analysis runs или artifacts.
Published documents защищены PostgreSQL trigger, downgrade при опубликованной
административной истории запрещён. Каталог читается через общий repository;
исторические snapshots и физические/evidence IDs исходного пула сохраняются.
Унаследованные изображения доступны через неизменяемые media исходной версии.

## Расчётные границы и нормы

Publication и calculation readiness показаны отдельно. Пустые ТТХ сохраняют
null/unknown и полноту; лишний `calculation_ready` запрещён. Новые модели и
предложения, а также изменённые физические профили остаются информационными
с объяснением evidence/rollout blocker. Подтверждение поля не расширяет
утверждённый расчётный пул.

Совместимый неизменённый утверждённый профиль сохраняет исходные matching-safe
факты и проходит существующие C05/C06 gates. Для derived capacity source
сервер проверяет принятый root rollout, затем точное совпадение исполняемых
membership/facts/units/scopes/profiles/assumptions/runtime version. Расширение
физического пула требует отдельного принятого rollout; редактор не обходит это
ограничение. Accepted formula/registry versions и policy v1 не переписываются.
Legacy runtime переключается только при наличии прежнего evidence-backed
legacy пула, отдельно от capacity; отсутствие такого пула явно показано.

Разрешены только сценарные proposals `exchange_seconds`, `units_per_trip`,
`operating_days` с каноническими units, источником, bounds и comment. Пользователь
применяет предложение в новой версии Brain, отдельно подтверждает и запускает
новый C11. Confirmed user value не заменяется нормой. Ни старые профили, ни
старые расчёты не пересчитываются.

## Критерии готовности

| Критерий F3 | Проверка |
|---|---|
| ADMIN создаёт/правит решение, предложение, источник, цену и default; diff/publication/discovery | Полный manual Chrome journey; две позиции одной модели с 1 млн и 2 млн ₽ видны отдельно |
| USER/guest запрещены, CSRF/owner защищены, concurrent edit без lost update | API tests: 401/403, чужой ADMIN owner, две правки одной редакции → 200/409 |
| Unknown не становится нулём или ready checkbox | Null payload сохранён; extra checkbox отклонён; физическая правка блокирует capacity; восстановленный совместимый профиль проходит gate |
| Import/edit/publish/rollback из UI, published/history неизменны | JSON download/import/repeat/edit, две публикации, activation и возврат указателей через UI; SQL trigger запрещает published document update |
| Старые данные reopen/export прежние; новые используют новую версию | До/после сравнены все rows/checksums; старые PDF/evidence ZIP/XLSX равны; новые C11 и экономические runs связаны с новой версией |
| Admin API sources/defaults и browser 3.3.5 документированы | [Руководство администратора](../ADMIN_CATALOG.md), section API и два acceptance scripts |

## Проверки

- Backend/PostgreSQL: **102 passed, 0 skipped** — persistence/Brain/workbook,
  repository/runtime/rollout/C06/C11, exports и 18 F3 lifecycle/security tests.
  Включены concurrency, late-slot conflict rollback, revalidation after edit,
  immutable trigger, invalid units/references/fields/currency/bounds/import,
  duplicate offers и JavaScript numeric JSON roundtrip.
- Frontend: **133 passed**; ESLint и production build прошли. Прежнее
  предупреждение о размере основного chunk >500 кБ сохраняется; оптимизация
  производительности относится к F8.
- Chrome **1366×768 и 390×844**: ручной create/edit/source/default/dictionary,
  diff/validate/publish, discovery+capacity activation, JSON download/upload,
  idempotent repeat, новая ручная проверка ТТХ, публикация и UI rollback.
  Норма **40 s** применена как unconfirmed assumption, отдельно подтверждена,
  вошла в новый C11. JS ошибок и horizontal overflow нет.
- **220 паллет/сутки, 120 м** и типовой склад **2000 паллет/сутки**: новые C11
  и экономические runs используют `f3-browser-d205a4e084ed`. При одинаковых
  подтверждённых физических входах значения capacity совпадают со старыми.
- На активном F3 каталоге повторён physical gate: отдельные новые изменения
  спроса/плеча/парка, overload/queue, точная связь ScenarioSpec → C23 → 2D/3D,
  selector/controls/Back/reload, автономный SVG, owner isolation, export
  manifest/member SHA. **Все previously existing rows остались прежними.**
- Ruff новых Python-файлов и `git diff --check` прошли.

Проверки выполнялись только на localhost PostgreSQL 17: `f1_tests` и
`stage11_f1_browser`, порт 5541; backend/Vite — 8000/5173. YC отключён.
Полная production-приёмка всего ТЗ остаётся F8.

## История и свидетельства

Финальный F3 UI проход сохранил все **105** прежних synthetic runs, **28**
simulation artifacts, **16** прежних catalog versions (из них **15 published**)
и **15** документов. Сравнивались полные JSON строк, включая snapshots,
trace/version bindings и checksums. Старые PDF и evidence ZIP совпали по SHA;
сохранённый XLSX проекта сохранил SHA
`5af828f646769da25060a93e4dbdcd3865ad694f9dbdb74cd3c847a94cef5b36`.
Это существующий input workbook; новый финансовый XLSX остаётся задачей F5.
Дополнительный physical gate сохранил **110** существовавших runs и **28**
artifacts, добавляя только новые synthetic runs/artifacts.

Все **30** файлов существующего `backup/` совпали с manifest от
26.09.2026 01:51:11 UTC по SHA/row counts. Его **20** production runs и
**4** artifacts не импортировались в disposable БД и не изменялись.
Исходный аудит, organizer data и accepted registry/formula contracts не правились.

Свидетельства: [browser JSON](assets/f3/evidence/browser.json),
[manual draft](assets/f3/evidence/manual-draft-desktop.png),
[published/rollback](assets/f3/evidence/published-rollback-desktop.png),
[mobile](assets/f3/evidence/published-mobile.png),
[подтверждённая норма и C11](assets/f3/evidence/confirmed-norm-calculation.png),
[physical checks](assets/f3/evidence/physical-check.txt),
[physical history](assets/f3/evidence/physical-history-check.json),
[desktop 2D](assets/f3/evidence/physical-desktop.png),
[mobile 2D](assets/f3/evidence/physical-mobile.png),
[manifest check](assets/f3/evidence/backup-check.json).

Для повторения нужны локальные services, disposable `stage11_f1_browser`,
seed организатора и synthetic warehouse runs из stage31/F1/F2. Файловый root
должен указывать на существующее disposable хранилище F2 для reopen XLSX.
Скрипты отклоняют нелокальный адрес / неподходящее имя БД. Windows CMD:

```cmd
set F3_DATABASE_URL=postgresql://f1@127.0.0.1:5541/stage11_f1_browser
python scripts\browser_f3_acceptance.py
set F1_DATABASE_URL=postgresql://f1@127.0.0.1:5541/stage11_f1_browser
python scripts\browser_f3_physical_acceptance.py
```

Production deploy не выполнялся; серверный бекап не требовался. Для будущего
обновления потребуется обычный Alembic upgrade до `0012_admin_catalog`.
**Следующий этап F4 — только после новой команды пользователя.**
