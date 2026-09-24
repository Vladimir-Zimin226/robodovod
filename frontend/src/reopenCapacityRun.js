export async function reopenCapacityRun({ projectId, run, readRun, readCapacity }) {
  const [opened, capacity] = await Promise.all([
    readRun(projectId, run.id),
    readCapacity(run.id, run.revision_id),
  ]);
  if (opened?.run_kind !== 'CAPACITY_ANALYSIS'
      || opened.id !== run.id
      || opened.project_id !== projectId
      || opened.revision_id !== run.revision_id
      || opened.input_snapshot?.project_id !== projectId
      || opened.input_snapshot?.input_revision !== capacity.input_revision
      || capacity.run_id !== run.id) {
    throw new Error('Сохранённый C11 run и исходный snapshot не совпадают. Расчёт не открыт.');
  }
  return { ...opened, result_snapshot: capacity };
}
