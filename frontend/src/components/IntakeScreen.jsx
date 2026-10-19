import { useState } from 'react';
import ProjectFileIntake from './ProjectFileIntake';
import ProcessRoleIntakeV2 from './ProcessRoleIntakeV2';
import WarehouseRoleWorkspace from './WarehouseRoleWorkspace';
import ObjectRoleWorkspace from './ObjectRoleWorkspace';

export default function IntakeScreen({ objectType, journeyMode = 'ADVANCED', initialPrompt = '', importedAssistant, activeProject, initialFacilityContext, initialDraft, initialNormalized, initialCapacityRequest, focusTarget, onDraftChange, user, authChecked,
  projectChoices, projectStatus, onChooseProject, onOpenProjects, onOpenAccount, onOpenObjects,
  onFileApplied, onIntakeV2Normalized, onCapacityResult, onWarehouseRoleSaved }) {
  const [v2FileInput, setV2FileInput] = useState(() => activeProject?.profile?.file_intake_v2?.object_type === objectType
    ? { normalized: activeProject.profile.file_intake_v2, imported: { id: activeProject.profile.project_file_import_id } } : null);
  const [fileNotice, setFileNotice] = useState('');
  const [showLegacyWarehouse, setShowLegacyWarehouse] = useState(false);
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

  if (supported && !showLegacyWarehouse) return <>
    {objectType === 'retail' ? <WarehouseRoleWorkspace activeProject={activeProject} user={user} authChecked={authChecked}
      projectChoices={projectChoices} projectStatus={projectStatus} onChooseProject={onChooseProject}
      onOpenProjects={onOpenProjects} onOpenAccount={onOpenAccount} onSaved={onWarehouseRoleSaved} />
      : <ObjectRoleWorkspace kind={objectType.toUpperCase()} activeProject={activeProject} user={user} authChecked={authChecked}
        projectChoices={projectChoices} projectStatus={projectStatus} onChooseProject={onChooseProject}
        onOpenProjects={onOpenProjects} onOpenAccount={onOpenAccount} onSaved={onWarehouseRoleSaved} />}
    <div className="mx-auto mb-6 max-w-6xl px-4"><button type="button" className="text-sm text-slate-400 underline"
      onClick={() => setShowLegacyWarehouse(true)}>Открыть прежний расчёт по зонам и операциям</button></div>
  </>;

  return <main className="intake-screen simple-intake min-h-full w-full max-w-[1440px] mx-auto p-4 md:p-6 space-y-4" aria-label="Описание работы">
    {supported && <button type="button" className="text-sm text-lime-300 underline" onClick={() => setShowLegacyWarehouse(false)}>Вернуться к расчёту по всем ролям</button>}
    <div className="space-y-3">
      <header>
        <span className="simple-step-eyebrow">ШАГ 2 ИЗ 5 · РАБОТА</span>
        <h1>Какую работу вы хотите автоматизировать?</h1>
        <p className="text-sm text-slate-400">Выберите одну операцию и укажите её объём. Подробности можно раскрыть позже.</p>
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
      </section> : <details className="simple-advanced-panel">
        <summary>У меня есть заполненный файл XLSX/CSV</summary>
        <p className="text-sm">Загрузите шаблон, затем проверьте значения и источники. Числа из внешнего файла не считаются подтверждёнными автоматически.</p>
        <ProjectFileIntake objectType={objectType} project={activeProject}
          scenario={activeProject?.scenarios?.find((item) => item.slot === 'BASE')} onApplied={applyFile} />
        {fileNotice && <p className="text-xs text-amber-300">{fileNotice}</p>}
      </details>}
    </div>
    {supported && <ProcessRoleIntakeV2 key={`${objectType}:${activeProject?.id || 'guest'}:${v2FileInput?.imported?.id || importedAssistant?.id || 'manual'}`}
      objectType={objectType} journeyMode={journeyMode} importedFile={v2FileInput} importedAssistant={importedAssistant?.profile} activeProject={activeProject} initialFacilityContext={initialFacilityContext} initialDraft={initialDraft} initialNormalized={initialNormalized} initialCapacityRequest={initialCapacityRequest} focusTarget={focusTarget} onDraftChange={onDraftChange} user={user}
      authChecked={authChecked} projectChoices={projectChoices} projectStatus={projectStatus}
      onChooseProject={onChooseProject} onOpenProjects={onOpenProjects} onOpenAccount={onOpenAccount}
      onNormalized={onIntakeV2Normalized} onCapacityResult={onCapacityResult} />}
  </main>;
}
