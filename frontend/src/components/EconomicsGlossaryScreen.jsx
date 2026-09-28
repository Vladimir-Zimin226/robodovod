import { useState } from 'react';
import glossary from '../economicsGlossary.json';
import { searchEconomicsEntries } from '../economicsGlossarySearch';

export default function EconomicsGlossaryScreen({ onOpenCalculation, onOpenDemo, onOpenMethodology }) {
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
    <section className="economics-methodology-invite" aria-label="Полная методология">
      <div><span>ПОЛНАЯ МЕТОДОЛОГИЯ</span><h2>Как из процесса получается проверяемый результат</h2>
        <p>После терминов можно пройти всю цепочку: данные объекта, подбор парка, труд, покупка и аренда, денежные потоки, показатели и границы модели. Отдельно отмечено, какие формулы из исходного документа действуют сейчас, а какие остаются референсными.</p></div>
      <button type="button" onClick={onOpenMethodology}>Читать методологию →</button>
    </section>
    <footer className="economics-glossary-footer">
      <p>Версии правил: C11 {glossary.versions.capacity}; финансы {glossary.versions.finance}; покупка {glossary.versions.purchase}; RaaS {glossary.versions.raas}; регистр {glossary.versions.registry}.</p>
      <p>Примеры служат для объяснения формул. Итог конкретного проекта рассчитывает сервер по его подтверждённым входам.</p>
    </footer>
  </main>;
}
