import AppIcon from './AppIcon';

const PLANNED_STEPS = [
  { number: '01', title: 'Уточнить задачу', text: 'Помощник поможет описать объект, процесс и ограничения простыми словами.' },
  { number: '02', title: 'Найти решения', text: 'Покажет подходящие позиции библиотеки с источниками и границами применимости.' },
  { number: '03', title: 'Сравнить варианты', text: 'Соберёт сравнение и предложит черновик параметров для вашего подтверждения.' },
];

export default function ProcessScreen({ activeProject, hasResult, onStartCalculation, onOpenCatalog, onReturnToResult }) {
  return <main className="process-screen" aria-labelledby="process-title">
    <section className="process-hero panel">
      <div className="process-hero-copy">
        <p className="eyebrow">РОБОДОВОД / ПРОЦЕСС</p>
        <span className="process-status">Готовим помощника</span>
        <h1 id="process-title">Помощник по выбору решения — готовим</h1>
        <p className="process-lead">Здесь появится диалог, который поможет сформулировать задачу, найти решения в библиотеке и сравнить варианты перед расчётом.</p>
        <p className="process-available">Сейчас можно сразу перейти к работающему расчёту или изучить библиотеку решений.</p>
        {activeProject && <p className="process-project">Выбран проект: <strong>{activeProject.name}</strong></p>}
        <div className="process-actions">
          <button type="button" className="primary-action" onClick={onStartCalculation}>Начать расчёт <AppIcon name="arrow" size={16} /></button>
          <button type="button" className="secondary-action" onClick={onOpenCatalog}>Открыть каталог <AppIcon name="library" size={16} /></button>
        </div>
        {hasResult && <button type="button" className="process-return" onClick={onReturnToResult}>Вернуться к результату расчёта</button>}
      </div>
      <div className="process-hero-mark" aria-hidden="true"><AppIcon name="process" size={82} /></div>
    </section>
    <section className="process-preview" aria-label="Что сможет помощник">
      {PLANNED_STEPS.map((step) => <div className="process-preview-card panel" key={step.number}>
        <span>{step.number}</span><h2>{step.title}</h2><p>{step.text}</p>
      </div>)}
    </section>
  </main>;
}
