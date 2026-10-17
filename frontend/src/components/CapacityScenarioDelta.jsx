import { getCapacityResultsModel, formatServerQuantity } from '../capacityResultsModel';
import { formatFleet } from '../displayNumber';

function distance(request) {
  return Number(request?.process?.route_distance?.normalized_value);
}

export default function CapacityScenarioDelta({ comparison }) {
  const before = getCapacityResultsModel(comparison.before.response);
  const after = getCapacityResultsModel(comparison.after.response);
  const beforeDistance = distance(comparison.before.request);
  const afterDistance = distance(comparison.after.request);
  const sameModel = before.modelId === after.modelId && before.positionId === after.positionId;
  return <section className="capacity-scenario-delta" aria-label="Изменение после нового расчёта">
    <span className="guest-demo-step">ДВЕ СОХРАНЁННЫЕ ВЕРСИИ</span>
    <h2>Что изменилось после нового расчёта</h2>
    <div className="capacity-scenario-delta-grid">
      <div><span>Плечо маршрута</span><strong>{Number.isFinite(beforeDistance) ? beforeDistance : '—'} → {Number.isFinite(afterDistance) ? afterDistance : '—'} м</strong></div>
      <div><span>Рекомендованный парк</span><strong>{formatFleet(before.recommendedFleet)} → {formatFleet(after.recommendedFleet)}</strong></div>
      <div><span>Эффективная мощность</span><strong>{formatServerQuantity(before.effectiveCapacity)} → {formatServerQuantity(after.effectiveCapacity)}</strong></div>
    </div>
    <p>{sameModel ? 'Позиция робота одинакова в обоих расчётах.' : 'Модель робота тоже изменилась.'} Сравните остальные входы и ограничения в сохранённых отчётах, прежде чем приписывать разницу только маршруту. Денежный эффект требует нового экономического расчёта.</p>
  </section>;
}
