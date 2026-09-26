import { useState } from 'react';
import ProjectFileIntake from './ProjectFileIntake';
import ProcessRoleIntakeV2 from './ProcessRoleIntakeV2';

export default function IntakeScreen({ objectType, initialPrompt = '', importedAssistant, activeProject, initialFacilityContext, user, authChecked,
  projectChoices, projectStatus, onChooseProject, onOpenProjects, onOpenAccount, onOpenObjects,
  onFileApplied, onIntakeV2Normalized, onCapacityResult }) {
  const [v2FileInput, setV2FileInput] = useState(() => activeProject?.profile?.file_intake_v2?.object_type === objectType
    ? { normalized: activeProject.profile.file_intake_v2, imported: { id: activeProject.profile.project_file_import_id } } : null);
  const [fileNotice, setFileNotice] = useState('');
  const supported = ['retail', 'airport', 'clinic'].includes(objectType);

  const applyFile = (normalized, _provenance, imported) => {
    if (normalized?.schema_version === 'project-workbook-v1' || (normalized?.object_type === 'retail' && normalized?.process_type === 'transport')) {
      setV2FileInput({ normalized, imported });
      setFileNotice(normalized.schema_version === 'project-workbook-v1' ? 'Перенесены зоны, процессы, batch, gross зарплаты и предложения экономики. Проверьте и отдельно подтвердите входы.'
        : 'Из файла перенесены объём, график, маршрут и численность. Единиц за рейс и месячную зарплату до удержаний подтвердите вручную.');
    } else {
      setFileNotice('Файл сохранён в проекте, но автоматический перенос для этого процесса пока недоступен. Перенесите значения вручную.');
    }
    onFileApplied?.(normalized, imported);
  };

  return <main className="intake-screen min-h-full w-full max-w-[1440px] mx-auto p-4 md:p-6 space-y-4" aria-label="Новый расчёт">
    <div className="space-y-3">
      <header>
        <h1 className="text-xl font-bold">Расчёт сценария роботизации</h1>
        <p className="text-sm text-slate-400">Объект → зоны → процессы и роли → расчёт парка → экономика.</p>
      </header>
      {initialPrompt && <section className="rounded-xl border p-4 text-sm">
        <h2 className="font-semibold">Ваше описание процесса</h2>
        <p className="mt-1 whitespace-pre-wrap">{initialPrompt}</p>
        <p className="mt-2 text-xs text-amber-300">Описание сохранено только на этом экране. Перенесите подтверждённые числа в форму ниже.</p>
      </section>}
      {!supported ? <section className="rounded-xl border p-5">
        <h2 className="font-semibold">Для этого объекта расчёт пока не поддержан</h2>
        <p className="mt-2 text-sm">Выберите склад, аэропорт или клинику. Старые сохранённые результаты доступны в проектах для просмотра и экспорта.</p>
        <button type="button" className="primary-action mt-3" onClick={onOpenObjects}>Выбрать поддержанный объект</button>
      </section> : <>
        <p className="text-sm">Скачайте шаблон XLSX/CSV и заполните его сами или передайте шаблон вместе с внешним промптом в LLM. Затем загрузите файл, проверьте предложения и подтвердите входы. Числа из LLM не считаются проверенными автоматически.</p>
        <ProjectFileIntake objectType={objectType} project={activeProject}
          scenario={activeProject?.scenarios?.find((item) => item.slot === 'BASE')} onApplied={applyFile} />
        {fileNotice && <p className="text-xs text-amber-300">{fileNotice}</p>}
      </>}
    </div>
    {supported && <ProcessRoleIntakeV2 key={`${objectType}:${activeProject?.id || 'guest'}:${v2FileInput?.imported?.id || importedAssistant?.id || 'manual'}`}
      objectType={objectType} importedFile={v2FileInput} importedAssistant={importedAssistant?.profile} activeProject={activeProject} initialFacilityContext={initialFacilityContext} user={user}
      authChecked={authChecked} projectChoices={projectChoices} projectStatus={projectStatus}
      onChooseProject={onChooseProject} onOpenProjects={onOpenProjects} onOpenAccount={onOpenAccount}
      onNormalized={onIntakeV2Normalized} onCapacityResult={onCapacityResult} />}
  </main>;
}
