import { useState } from 'react';
import ProjectFileIntake from './ProjectFileIntake';
import ProcessRoleIntakeV2 from './ProcessRoleIntakeV2';

export default function IntakeScreen({ objectType, initialPrompt = '', importedAssistant, activeProject, user, authChecked,
  projectChoices, projectStatus, onChooseProject, onOpenProjects, onOpenAccount, onOpenObjects,
  onFileApplied, onIntakeV2Normalized, onCapacityResult }) {
  const [v2FileInput, setV2FileInput] = useState(null);
  const [fileNotice, setFileNotice] = useState('');
  const supported = ['retail', 'airport', 'clinic'].includes(objectType);

  const applyFile = (normalized, _provenance, imported) => {
    if (normalized?.object_type === 'retail' && normalized?.process_type === 'transport') {
      setV2FileInput({ normalized, imported });
      setFileNotice('Из файла перенесены объём, график, маршрут и численность. Единиц за рейс и месячную зарплату до удержаний подтвердите вручную.');
    } else {
      setFileNotice('Файл сохранён в проекте, но автоматический перенос для этого процесса пока недоступен. Перенесите значения вручную.');
    }
    onFileApplied?.(normalized);
  };

  return <main className="intake-screen flex min-h-full" aria-label="Новый расчёт">
    <div className="flex-1 mx-auto max-w-3xl space-y-4 p-6">
      <header>
        <h1 className="text-xl font-bold">Расчёт сценария роботизации</h1>
        <p className="text-sm text-slate-400">Объект → зона → процесс и роли → расчёт парка → экономика и 2D.</p>
      </header>
      {initialPrompt && <section className="rounded-xl border p-4 text-sm">
        <h2 className="font-semibold">Ваше описание процесса</h2>
        <p className="mt-1 whitespace-pre-wrap">{initialPrompt}</p>
        <p className="mt-2 text-xs text-amber-300">Описание сохранено только на этом экране. Перенесите подтверждённые числа в форму справа.</p>
      </section>}
      {!supported ? <section className="rounded-xl border p-5">
        <h2 className="font-semibold">Для этого объекта расчёт пока не поддержан</h2>
        <p className="mt-2 text-sm">Выберите склад, аэропорт или клинику. Старые сохранённые результаты доступны в проектах для просмотра и экспорта.</p>
        <button type="button" className="primary-action mt-3" onClick={onOpenObjects}>Выбрать поддержанный объект</button>
      </section> : <>
        <ProjectFileIntake objectType={objectType} project={activeProject}
          scenario={activeProject?.scenarios?.find((item) => item.slot === 'BASE')} onApplied={applyFile} />
        {fileNotice && <p className="text-xs text-amber-300">{fileNotice}</p>}
        <section className="rounded-xl border p-5 text-sm">
          <h2 className="font-semibold">Один расчётный маршрут</h2>
          <p className="mt-2">Выберите зону и процесс справа, укажите нагрузку, маршрут, график и роли. Сервер сохранит расчёт потребного парка для выбранного процесса. Затем можно отдельно рассчитать экономику и симуляцию.</p>
          <p className="mt-2 text-amber-300">Если зон или процессов несколько, каждому нужен свой расчёт парка. Общие роботы, роли и затраты нельзя суммировать автоматически; закупочная готовность требует отдельной проверки.</p>
        </section>
      </>}
    </div>
    {supported && <ProcessRoleIntakeV2 key={`${objectType}:${v2FileInput?.imported?.id || importedAssistant?.id || 'manual'}`}
      objectType={objectType} importedFile={v2FileInput} importedAssistant={importedAssistant?.profile} activeProject={activeProject} user={user}
      authChecked={authChecked} projectChoices={projectChoices} projectStatus={projectStatus}
      onChooseProject={onChooseProject} onOpenProjects={onOpenProjects} onOpenAccount={onOpenAccount}
      onNormalized={onIntakeV2Normalized} onCapacityResult={onCapacityResult} />}
  </main>;
}
