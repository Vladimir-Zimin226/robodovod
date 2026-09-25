import { useEffect, useState } from 'react';
import { persistenceRequest } from '../persistenceApi';
import { EvidenceExportSession } from '../evidenceExportApi';
import { formatServerMoney } from '../commercialScenariosModel';
import { formatFleet } from '../displayNumber';
import { baseNpv, branchAvailability, comparisonRows, groupProjectRuns, processName, REPORT_BRANCHES, reportType } from '../reportHistoryModel';

const dateLabel = (value) => value ? new Date(value).toLocaleString('ru-RU') : 'Дата не указана';
const percent = (done, total) => total > 0 ? Math.max(0, Math.min(100, Math.round(done / total * 100))) : 0;

export default function ReportsScreen({ user, onOpenAccount, onOpenRun }) {
  const [projects, setProjects] = useState([]);
  const [runsByProject, setRunsByProject] = useState({});
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(Boolean(user));
  const [comparison, setComparison] = useState(null);
  const [busy, setBusy] = useState('');

  useEffect(() => {
    if (!user?.id) { setProjects([]); setRunsByProject({}); setLoading(false); return undefined; }
    const controller = new AbortController();
    setLoading(true);
    setErrors({});
    persistenceRequest('/api/projects', { signal: controller.signal })
      .then(async (payload) => {
        const items = payload.items || [];
        if (controller.signal.aborted) return;
        setProjects(items);
        const results = await Promise.allSettled(items.map((project) => persistenceRequest(
          `/api/projects/${encodeURIComponent(project.id)}/analysis-runs`, { signal: controller.signal },
        )));
        if (controller.signal.aborted) return;
        const next = {}; const failures = {};
        results.forEach((result, index) => {
          const id = items[index].id;
          if (result.status === 'fulfilled') next[id] = result.value.items || [];
          else failures[id] = result.reason.message || 'Не удалось загрузить расчёты';
        });
        setRunsByProject(next);
        setErrors(failures);
      })
      .catch((error) => { if (error.name !== 'AbortError') setErrors({ projects: error.message }); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [user?.id]);

  const open = async (project, run, edit = false) => {
    setBusy(`${run.id}:open`); setErrors((current) => ({ ...current, action: '' }));
    try {
      const opened = await persistenceRequest(`/api/projects/${encodeURIComponent(project.id)}/analysis-runs/${encodeURIComponent(run.id)}`);
      onOpenRun(opened, project, { edit });
    } catch (error) { setErrors((current) => ({ ...current, action: error.message })); }
    finally { setBusy(''); }
  };

  const download = async (project, run, format) => {
    setBusy(`${run.id}:${format}`); setErrors((current) => ({ ...current, action: '' }));
    try {
      const session = new EvidenceExportSession();
      if (format === 'pdf') await session.downloadReport(project.id, run.id);
      else await session.download(project.id, run.id);
    } catch (error) { setErrors((current) => ({ ...current, action: `Экспорт недоступен: ${error.message}` })); }
    finally { setBusy(''); }
  };

  const selectComparison = (projectId, groupId, runId) => {
    setComparison((current) => {
      const selected = current?.projectId === projectId && current?.groupId === groupId ? current.runIds : [];
      return { projectId, groupId, runIds: selected.includes(runId) ? selected.filter((id) => id !== runId) : [...selected.slice(-1), runId] };
    });
  };

  if (!user) return <main className="reports-screen"><header><span className="eyebrow">ОТЧЁТЫ</span><h1>История расчётов</h1><p>Войдите, чтобы увидеть свои проекты и сохранённые версии.</p><button type="button" className="primary-action" onClick={onOpenAccount}>Войти</button></header></main>;
  return <main className="reports-screen" aria-label="Отчёты проектов">
    <header className="reports-heading"><span className="eyebrow">СОХРАНЁННЫЕ РЕЗУЛЬТАТЫ</span><h1>Отчёты проектов</h1>
      <p>Версии сгруппированы по исходному расчёту процесса. Парк и денежные показатели разных операций не складываются.</p>
      <p className="reports-caveat">Полнота показывает только подтверждённые входы и рассчитанные разделы. Она не оценивает пригодность решения или вероятность закупки.</p>
    </header>
    {loading && <p role="status">Загружаем проекты и версии…</p>}
    {errors.projects && <p role="alert" className="reports-error">{errors.projects}</p>}
    {errors.action && <p role="alert" className="reports-error">{errors.action}</p>}
    {!loading && projects.length === 0 && !errors.projects && <p className="reports-empty">Сохранённых проектов пока нет. Создайте проект в «Моих проектах» или начните расчёт.</p>}
    {projects.map((project) => <section className="reports-project" key={project.id} aria-label={`Проект ${project.name}`}>
      <div className="reports-project-heading"><h2>{project.name}</h2><span>{(runsByProject[project.id] || []).length} версий</span></div>
      {errors[project.id] && <p role="alert" className="reports-error">{errors[project.id]}</p>}
      {!loading && !errors[project.id] && (runsByProject[project.id] || []).length === 0 && <p className="reports-empty">В этом проекте пока нет сохранённых расчётов.</p>}
      {groupProjectRuns(runsByProject[project.id] || []).map((group) => {
        const representative = group.runs.find((run) => run.run_kind === 'CAPACITY_ANALYSIS') || group.runs[0];
        const summary = representative.report_summary || {};
        const selected = comparison?.projectId === project.id && comparison?.groupId === group.id ? comparison.runIds : [];
        const compared = selected.map((id) => group.runs.find((run) => run.id === id)).filter(Boolean);
        return <section className="reports-group" key={group.id} aria-label={`Операция ${processName(summary)}`}>
          <div className="reports-group-heading"><div><h3>{processName(summary)}</h3><p>{summary.zone_label ? `Зона: ${summary.zone_label} · ` : ''}Модель: {summary.model_name || 'не указана в каталоге'} · {group.runs.length} версий</p></div><span>СВЯЗАННЫЕ РЕЗУЛЬТАТЫ</span></div>
          <div className="reports-cards">{group.runs.map((run) => <ReportCard key={run.id} run={run} project={project}
            selected={selected.includes(run.id)} busy={busy.startsWith(`${run.id}:`)}
            onCompare={() => selectComparison(project.id, group.id, run.id)}
            onOpen={() => open(project, run)} onEdit={() => open(project, run, true)}
            onPdf={() => download(project, run, 'pdf')} onZip={() => download(project, run, 'zip')} />)}</div>
          {compared.length === 2 && <Comparison left={compared[0]} right={compared[1]} />}
        </section>;
      })}
    </section>)}
  </main>;
}

function ReportCard({ run, selected, busy, onCompare, onOpen, onEdit, onPdf, onZip }) {
  const summary = run.report_summary || {};
  const progress = summary.completeness || {};
  const inputs = progress.inputs;
  const success = run.status === 'SUCCEEDED';
  return <article className="reports-card" aria-label={`${reportType(run)} результат от ${dateLabel(run.created_at)}`}>
    <div className="reports-card-top"><span className={summary.result_type === 'FULL' ? 'reports-type full' : 'reports-type partial'}>{reportType(run)}</span><time dateTime={run.created_at}>{dateLabel(run.created_at)}</time></div>
    <div className="reports-card-facts"><p><strong>Процесс / зона</strong><span>{processName(summary)}{summary.zone_label ? ` · ${summary.zone_label}` : ''}</span></p><p><strong>Модель</strong><span>{summary.model_name || 'Не указана в каталоге'}</span></p><p><strong>Технический парк</strong><span>{summary.fleet == null ? 'Не рассчитан' : formatFleet(summary.fleet)}</span></p></div>
    <div className="reports-branches">{REPORT_BRANCHES.map(([key, label]) => <div key={key} className={['CALCULATED', 'SAVED'].includes(summary.branches?.[key]) ? 'available' : ''}><strong>{label}</strong><span>{branchAvailability(summary, key)}</span></div>)}</div>
    <div className="reports-npv"><p>NPV покупки: <strong>{baseNpv(summary, 'PURCHASE') == null ? 'не рассчитано' : formatServerMoney(baseNpv(summary, 'PURCHASE'))}</strong></p><p>NPV RaaS: <strong>{baseNpv(summary, 'RAAS') == null ? 'не рассчитано' : formatServerMoney(baseNpv(summary, 'RAAS'))}</strong></p><small>Базовые денежные сценарии; ветки показаны отдельно.</small></div>
    <div className="reports-progress" aria-label="Полнота подтверждений и расчётов">
      <Progress label="Рассчитанные разделы" done={progress.branches_calculated || 0} total={progress.branches_total || 5} />
      {inputs && <Progress label="Заполненные подтверждённые входы" done={inputs.confirmed} total={inputs.total} />}
    </div>
    <div className="reports-actions">
      <button type="button" disabled={!success || busy} onClick={onOpen}>Открыть</button>
      <label><input type="checkbox" checked={selected} onChange={onCompare} /> Сравнить</label>
      <button type="button" disabled={!success || busy} onClick={onPdf}>PDF</button>
      <button type="button" disabled={!success || busy} onClick={onZip}>ZIP</button>
      {summary.can_create_version && <button type="button" disabled={busy} onClick={onEdit}>Новая версия</button>}
    </div>
    <details><summary>Технические подробности</summary><p>Run: {run.id} · исходный run: {summary.linked_capacity_run_id || '—'} · родитель: {run.parent_run_id || '—'}</p><p>Каталог: {run.versions?.catalog || '—'} · правила: {run.versions?.rules || '—'}</p><p>Digest результата: {run.checksums?.result || '—'}</p></details>
  </article>;
}

function Progress({ label, done, total }) {
  return <div><div className="reports-progress-label"><span>{label}</span><strong>{done}/{total}</strong></div><div className="reports-progress-track" role="meter" aria-label={label} aria-valuemin="0" aria-valuemax={total} aria-valuenow={done}><span style={{ width: `${percent(done, total)}%` }} /></div></div>;
}

function Comparison({ left, right }) {
  const rows = comparisonRows(left, right);
  return <section className="reports-comparison" aria-label="Сравнение версий"><h4>Сравнение сохранённых версий</h4><p>Показатели приведены рядом, без сложения парков и денежных потоков.</p><div className="reports-table-wrap"><table><thead><tr><th>Показатель</th><th>{dateLabel(left.created_at)}</th><th>{dateLabel(right.created_at)}</th></tr></thead><tbody>{rows.map((row) => <tr key={row.label}><th>{row.label}</th><td>{row.left == null ? '—' : row.unit === '₽' ? formatServerMoney(row.left) : row.unit === 'роботов' ? formatFleet(row.left) : row.left}</td><td>{row.right == null ? '—' : row.unit === '₽' ? formatServerMoney(row.right) : row.unit === 'роботов' ? formatFleet(row.right) : row.right}</td></tr>)}</tbody></table></div></section>;
}
