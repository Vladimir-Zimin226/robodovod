import { useState } from 'react';
import glossary from '../economicsGlossary.json';
import { searchEconomicsEntries } from '../economicsGlossarySearch';

export default function EconomicsGlossaryScreen({ onOpenCalculation, onOpenDemo }) {
  const [query, setQuery] = useState('');
  const entries = searchEconomicsEntries(glossary.entries, query);
  return <main className="economics-glossary" aria-label="Экономика: справочник формул">
    <header className="economics-glossary-header">
      <p className="economics-glossary-eyebrow">СПРАВОЧНИК РАСЧЁТА</p>
      <h1>Экономика роботизации</h1>
      <p>Формулы, входы и примеры из действующего расчётного ядра. Найдите термин, откройте карточку и перейдите к нужным полям.</p>
      <div className="economics-glossary-actions">
        <button type="button" onClick={onOpenCalculation}>Открыть расчёт</button>
        <button type="button" onClick={onOpenDemo}>Посмотреть складской пример</button>
      </div>
    </header>
    <details className="economics-glossary-card economics-methodology" aria-label="Методология оценки роботизации">
      <summary><span><strong>Как мы оцениваем роботизацию</strong><small>Раскрыть методологию: от операции до денежного результата</small></span><b>Методология</b></summary>
      <div className="economics-glossary-body">
        <p>Сначала описываем конкретную операцию: объём за сутки, маршрут, груз, график, ограничения объекта и занятые роли. Для склада, аэропорта и клиники единицы потока различаются. Если для операции нет проверенной расчётной формулы или данных, денежный вывод остаётся частичным.</p>
        <ol>
          <li><strong>Применимость и парк.</strong> Проверяем допустимость робота для операции, затем считаем цикл, полезное время, зарядку, резерв и число машин под заданный поток. Результат зависит от сохранённых входов, а не от названия объекта.</li>
          <li><strong>Труд до и после.</strong> Исходная роль и зарплата вводятся отдельно. Экономия ограничена долей работы, которую реально забирают роботы; остаточные ручные операции и новые функции диспетчера/техника остаются в сценарии. Перевод сотрудника не приравнивается к увольнению.</li>
          <li><strong>Два способа финансирования.</strong> Для покупки учитываются оборудование, внедрение, площадка и ежегодная эксплуатация. Для RaaS — условия услуги, срок и ответственность сторон. Проценты от цены и фиксированные суммы выбираются явно; неизвестная цена не подменяется нулём.</li>
          <li><strong>Сравнение с текущим процессом.</strong> Сервер строит денежные потоки базы и сценария по годам; эффект проекта — разность их NPV при выбранных ставке и горизонте. Положительный NPV означает положительный эффект только в границах введённых допущений, а не гарантию окупаемости.</li>
          <li><strong>Проверяемость.</strong> В сохранённом результате видны источники, версии правил и невыполненные условия. PDF фиксирует именно этот расчёт; изменение вводных создаёт новую версию, старые результаты не пересчитываются.</li>
        </ol>
        <p><strong>Граница модели:</strong> основной денежный маршрут сейчас рассчитывается до налога на прибыль; универсальную ставку НДС к пользовательским gross ценам мы не применяем. Каталожные и типовые значения требуют проверки у поставщика и на объекте. 2D/3D показывает модельный сценарий, не заменяет натурный замер или испытание.</p>
      </div>
    </details>
    <section className="economics-glossary-search" aria-label="Поиск по справочнику">
      <label htmlFor="economics-term-search">Поиск по названию, синониму или обозначению</label>
      <input id="economics-term-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)}
        placeholder="Например: окупаемость, NPV, цена владения" autoComplete="off" />
      <span aria-live="polite">Найдено: {entries.length}</span>
    </section>
    <div className="economics-glossary-list">
      {entries.length === 0 && <p className="economics-glossary-empty">Такого термина нет. Попробуйте синоним или обозначение.</p>}
      {entries.map((entry) => <details className="economics-glossary-card" key={entry.id} open={query.trim() ? true : undefined}>
        <summary><span><strong>{entry.title}</strong><small>{entry.synonyms.join(' · ')}</small></span><b>{entry.notation}</b></summary>
        <div className="economics-glossary-body">
          <div className="economics-glossary-formula"><span>Формула</span><p>{entry.formula}</p><small>Единицы: {entry.units}</small></div>
          <div className="economics-glossary-columns">
            <section><h2>Что заполнить</h2><ul>{entry.inputs.map((input) => <li key={input.field}>
              <strong>{input.label}</strong><span>{input.source}</span><code>{input.field}</code>
            </li>)}</ul></section>
            <section><h2>Пример</h2><p>{entry.example}</p><small>{entry.example_source}</small></section>
          </div>
          <div className="economics-glossary-meta">
            <p><strong>Когда применяется:</strong> {entry.applicability}</p>
            <p><strong>Источник данных:</strong> {entry.source}</p>
            <p><strong>Где в расчёте:</strong> {entry.section}</p>
            <p><strong>Правила:</strong> {entry.formula_ids.join(', ')}</p>
          </div>
          <button type="button" className="economics-glossary-link" onClick={onOpenCalculation}>Перейти к полям расчёта →</button>
        </div>
      </details>)}
    </div>
    <footer className="economics-glossary-footer">
      <p>Версии правил: C11 {glossary.versions.capacity}; финансы {glossary.versions.finance}; покупка {glossary.versions.purchase}; RaaS {glossary.versions.raas}; регистр {glossary.versions.registry}.</p>
      <p>Примеры служат для объяснения формул. Итог конкретного проекта рассчитывает сервер по его подтверждённым входам.</p>
    </footer>
  </main>;
}
