# Frontend РОБОДОВОД

React 19 + Vite интерфейс демо «РОБОДОВОД».

Главный результатный экран реализован как visualization-first dashboard. Он
использует данные `calculation-response-v1` через чистый presentation-adapter,
не пересчитывает экономику. Технически допустимый, но экономически отвергнутый
парк показывается только как явно маркированная визуализация без `is_best`.
Whole- и zonal-режимы
показывают RobCraft через прежний same-origin iframe, а переключатель текущего
состояния использует реальные baseline-данные без вымышленной 3D-сцены.

Адаптивные точки: полный sidebar от 1200 px, drawer ниже 1200 px, одноколоночная
компоновка ниже 900 px. Основные controls имеют keyboard focus и текстовые
обозначения состояний.

```powershell
npm.cmd install
npm.cmd run dev
```

При локальной разработке Vite проксирует `/api` на `http://localhost:8000`. Другой адрес можно задать в `frontend/.env.local`:

```dotenv
VITE_API_URL=http://localhost:8000
```

Vite также публикует соседний автономный движок RobCraft по same-origin пути
`/robcraft/`. Production build копирует его runtime-assets в
`frontend/dist/robcraft`; отдельный сервер или контейнер для 3D не нужен.

Основные команды: `npm.cmd test`, `npm.cmd run lint`, `npm.cmd run build`,
`npm.cmd run preview`.
