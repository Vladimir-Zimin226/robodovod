# РОБОДОВОД — контекст для работы над финальным демо

Срез подготовлен 16.10.2026 после консультации с жюри и обновлён 17.10.2026 по итогам последовательной реализации этапов. Основа: код проекта, документация, исторические кадры от 25–30.09 и новые кадры локальной сборки от 17.10. Production не проверялся. Расчётную спецификацию Евгений готовит отдельно; реального плана склада нет.

## Что читать

1. [01_PROJECT_CONTEXT.md](01_PROJECT_CONTEXT.md) — продукт, текущий путь, код и достоверные границы.
2. [02_VISUAL_AUDIT.md](02_VISUAL_AUDIT.md) — снимки 2D/3D и конкретные проблемы восприятия.
3. [03_WOW_PLAN.md](03_WOW_PLAN.md) — последовательность доработок и критерии готовности.
4. [04_WEB_CHATGPT_BRIEF.md](04_WEB_CHATGPT_BRIEF.md) — готовая постановка для обсуждения дизайна в веб-версии ChatGPT.
5. [05_IMPLEMENTATION_STATUS.md](05_IMPLEMENTATION_STATUS.md) — что уже сделано, что остаётся и как воспроизвести демо.
6. [06_REFERENCE_LAYOUT.md](06_REFERENCE_LAYOUT.md) — источники и границы сгенерированной учебной планировки.

Папку `screenshots/` прикладывать целиком. В веб-чате удобнее загрузить этот комплект архивом и попросить сначала прочитать шесть Markdown-файлов, затем посмотреть изображения. Скриншоты имеют разные даты и наборы данных: не сопоставляйте их числа между собой.

## Скриншоты

| Файл | Что видно | Исходный артефакт |
| --- | --- | --- |
| [warehouse-2d-current.png](screenshots/warehouse-2d-current.png) | Склад, 15 роботов, 2D | `.test-warehouse-activity/browser/warehouse-15-2d-1366.png`, 30.09 |
| [warehouse-3d-current.png](screenshots/warehouse-3d-current.png) | Склад, 15 роботов, 3D-сопровождение | `.test-warehouse-activity/browser/warehouse-15-3d-1366.png`, 30.09 |
| [warehouse-3d-overview.png](screenshots/warehouse-3d-overview.png) | Склад, 3D-общий план | `.test-warehouse-activity/browser/warehouse-15-3d-overview.png`, 30.09 |
| [airport-2d-current.png](screenshots/airport-2d-current.png) | Аэропорт, 2D | `.test-visualization-remediation/final-browser/airport-2d-1366.png`, 29–30.09 |
| [airport-3d-current.png](screenshots/airport-3d-current.png) | Аэропорт, 3D | `.test-visualization-remediation/final-browser/airport-3d-1366.png`, 29–30.09 |
| [clinic-2d-current.png](screenshots/clinic-2d-current.png) | Клиника, 2D | `.test-visualization-remediation/final-browser/clinic-2d-1366.png`, 29–30.09 |
| [clinic-3d-current.png](screenshots/clinic-3d-current.png) | Клиника, 3D | `.test-visualization-remediation/final-browser/clinic-3d-1366.png`, 29–30.09 |
| [warehouse-3d-historical-reference.png](screenshots/warehouse-3d-historical-reference.png) | Старый более насыщенный складской вид, **референс, не текущий режим** | `docs/presentation/assets/warehouse-3d-robots.png`, 25.09 |
| [new-landing.png](screenshots/new-landing.png) | Новая главная с живой схемой и двумя вариантами нагрузки | локальный Chrome, 17.10 |
| [new-demo-choice.png](screenshots/new-demo-choice.png) | Выбор двух просчитанных сценариев и робота перед сценой | локальный Chrome, 17.10 |
| [new-demo-3d.png](screenshots/new-demo-3d.png) | Текущий 3D-кадр после автоперехода камеры | локальный Chrome, 17.10 |
| [new-demo-peak-2d.png](screenshots/new-demo-peak-2d.png) | Текущий 2D-кадр при повышенной нагрузке | локальный Chrome, 17.10 |
| [new-layout-mobile.png](screenshots/new-layout-mobile.png) | Конструктор плана в основном маршруте | локальный Chrome, 17.10 |
| [new-layout-route-mobile.png](screenshots/new-layout-route-mobile.png) | Учебный план, путь и препятствия | локальный Chrome, 17.10 |
| [new-layout-volume-mobile.png](screenshots/new-layout-volume-mobile.png) | Объёмный вид того же плана | локальный Chrome, 17.10 |
| [new-layout-dxf-mobile.png](screenshots/new-layout-dxf-mobile.png) | Контуры импортированного DXF | локальный Chrome, 17.10 |

Все основные кадры сняты локальным Chrome на тестовых или сохранённых сценариях. Это доказательство вида конкретной сборки, а не съёмка реального склада. Исторический кадр нельзя выдавать за актуальную симуляцию или точный план объекта.
