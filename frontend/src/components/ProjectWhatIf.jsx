import { useState } from 'react';
import ProjectScenarioDialog from './ProjectScenarioDialog';

export default function ProjectWhatIf({ project, run, onComplete, onCreateVersion, onPhysical }) {
  const [open, setOpen] = useState(false);
  if (!run || !project?.id) return null;
  if (run.input_snapshot?.economics?.schema_version !== 'economics-explicit-inputs-v6') return <section className="commercial-details">
    <p>Эта версия сохранена со старым набором входов. Для пересчёта нужно заполнить недостающие значения.</p>
    {onCreateVersion && <button onClick={onCreateVersion}>Создать новую версию для пересчёта</button>}
  </section>;
  return <section className="commercial-details"><button className="primary-action" onClick={() => setOpen(true)}>Сценарии и пересчёт</button>
    {open && <ProjectScenarioDialog key={`${project.id}:${run.id}:${run.checksums?.result || run.result_sha256}`} project={project}
      run={{ ...run, result_sha256: run.checksums?.result || run.result_sha256 }} onComplete={onComplete}
      onPhysical={onPhysical} onClose={() => setOpen(false)} />}
  </section>;
}
