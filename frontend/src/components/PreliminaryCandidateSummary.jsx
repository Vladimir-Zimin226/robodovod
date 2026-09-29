const CHECK_LABELS = {
  'object-kind': 'Тип объекта', 'process-scope': 'Операция', cargo: 'Тип груза',
  payload: 'Грузоподъёмность', aisle: 'Ширина прохода', 'lift-height': 'Высота подъёма',
  'ceiling-clearance': 'Высота помещения', 'route-floors': 'Маршрут между этажами',
  temperature: 'Температура', noise: 'Уровень шума', airside: 'Допуск на аэродром',
  apron: 'Работа на перроне', 'restricted-zone': 'Доступ в ограниченную зону',
  sanitization: 'Санитарная обработка', 'class-b-containment': 'Изоляция класса Б',
  'cleanable-surface': 'Очищаемая поверхность', 'material-disinfection': 'Дезинфекция материалов',
  'access-protocols': 'Протоколы доступа', 'passport-availability': 'Технический паспорт',
  'floor-flatness': 'Ровность пола', 'floor-covering': 'Покрытие пола', slope: 'Уклон',
  outdoor: 'Работа вне помещения', availability: 'Эксплуатационная доступность',
  integrations: 'Интеграции', 'life-warning': 'Срок службы', 'budget-warning': 'Бюджет',
  'charging-warning': 'Мощность зарядки', 'density-warning': 'Плотность парка',
};
const REASON_LABELS = {
  'candidate-fact-missing': 'нет подтверждённой характеристики',
  'requirement-exceeded': 'характеристики недостаточно',
  'object-kind-unsupported': 'тип объекта не поддерживается',
  'process-scope-unsupported': 'операция не поддерживается',
  'technical-passport-unknown': 'не подтверждён',
  'technical-passport-unavailable': 'отсутствует',
  'availability-fact-unknown': 'не подтверждена',
  'availability-below-minimum': 'ниже требуемой',
  'limit-exceeded': 'превышен допустимый предел',
  'capability-not-supported': 'не поддерживается',
  'floor-covering-fact-unknown': 'нет подтверждённых данных',
  'temperature-range-unknown': 'нет подтверждённого диапазона',
  'scoped-noise-facts-unknown': 'нет подтверждённых данных для места и времени',
  'access-protocols-unknown': 'нет подтверждённых данных',
  'integration-facts-unknown': 'нет подтверждённых данных',
  'integrations-need-review': 'нужна проверка совместимости',
  'cargo-compatibility-unknown': 'совместимость груза не подтверждена',
  'cargo-unsupported': 'тип груза не поддерживается',
  'ceiling-clearance-insufficient': 'высоты помещения недостаточно',
  'ceiling-height-unknown': 'высота помещения не подтверждена',
  'floor-covering-unsupported': 'покрытие не поддерживается',
  'lift-integration-unknown': 'работа с лифтом не подтверждена',
  'lift-route-unsupported': 'маршрут с лифтом не поддерживается',
  'scoped-noise-exceeded': 'превышен допустимый уровень шума',
  'temperature-range-exceeded': 'температура вне рабочего диапазона',
  'access-protocols-unsupported': 'протокол доступа не поддерживается',
  'life-fact-unknown': 'срок службы не подтверждён',
  'life-shorter-than-horizon': 'срок службы короче горизонта расчёта',
  'density-below-review-threshold': 'плотность парка требует проверки',
  'requirement-source-assumed': 'требование основано на допущении',
};

const scoreText = value => value == null ? '—' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value));

function statusText(row) {
  if (row.status === 'EXCLUDED') return 'Исключена';
  if (row.status === 'INFORMATION_ONLY') return 'Только сведения';
  if (row.constraints?.eligibility === 'ELIGIBLE') return 'Проверки пройдены';
  return 'Нужна проверка';
}

function checkText(check) {
  const label = CHECK_LABELS[check.rule_id || check.check_id] || 'Другая проверка';
  const reason = REASON_LABELS[check.reason_code] || 'нужно уточнить основание';
  return `${label}: ${reason}`;
}

function unresolvedText(row) {
  const checks = (row.constraints?.checks || []).filter(check => ['FAIL', 'UNKNOWN'].includes(check.status));
  if (!checks.length) return row.status === 'EXCLUDED' ? 'Основание исключения не указано' : 'Дополнительных проверок не перечислено';
  return checks.map(checkText).join('; ');
}

export default function PreliminaryCandidateSummary({ comparison, diagnostics, rankedCandidates, candidatePositions, selectedPositionId, onSelect }) {
  const first = rankedCandidates[0];
  const tied = first ? rankedCandidates.filter(row => Number(row.technical_score) === Number(first.technical_score)).length : 0;
  const selectableIds = new Set(candidatePositions.map(row => row.position_id));
  return <div className="preliminary-comparison" aria-label="Техническое сопоставление моделей">
    <header className="preliminary-comparison-heading">
      <div><span className="preliminary-eyebrow">ПОДБОР ПО ТЕХНИЧЕСКИМ ДАННЫМ</span><h4>Сопоставление моделей</h4></div>
      <span className="preliminary-review-badge">Пригодность требует проверки</span>
    </header>
    {!comparison ? <p role="status" className="preliminary-muted">Укажите физические входы, подтвердите допущения и выберите проект. Затем сравним расчётные позиции на одинаковых входах.</p> : <>
      <p className="preliminary-muted">Позиции проходят несколько этапов отбора. Наличие формулы расчёта не подтверждает пригодность модели на объекте.</p>
      <dl className="preliminary-funnel">
        <div><dt>Активный каталог</dt><dd>{diagnostics.active ?? '—'}</dd></div>
        <div><dt>Для объекта и операции</dt><dd>{diagnostics.process}</dd></div>
        <div><dt>С физическим профилем</dt><dd>{diagnostics.profile ?? '—'}</dd></div>
        <div className="preliminary-funnel-emphasis"><dt>Расчётно совместимы</dt><dd>{diagnostics.ready}</dd></div>
      </dl>
      <p className="preliminary-count-note">При первичном отборе {diagnostics.check} позиций требуют проверки сведений, {diagnostics.excluded} исключены. Последний счётчик показывает наличие расчётной формулы, а не подтверждённую пригодность.</p>
      {first ? <>
        <div className="preliminary-first">
          <div><span className="preliminary-eyebrow">ПЕРВЫЙ В ТЕХНИЧЕСКОЙ СОРТИРОВКЕ</span><h5>{first.name}</h5>
            <p>{first.readiness === 'VERIFIED' ? 'Технические проверки пройдены.' : 'Пригодность на объекте ещё не подтверждена.'}</p></div>
          <div className="preliminary-score"><strong>{scoreText(first.technical_score)}</strong><span>технический балл</span></div>
        </div>
        {tied > 1 && <p className="preliminary-tie">Одинаковый балл у {tied} позиций. Порядок внутри этой группы не означает преимущество первой модели.</p>}
        <div className="preliminary-table-wrap preliminary-top-wrap"><table className="preliminary-table">
          <caption>Первые варианты технического сопоставления</caption>
          <thead><tr><th scope="col">Модель</th><th scope="col">Балл</th><th scope="col">Статус</th><th scope="col">Выбор</th></tr></thead>
          <tbody>{rankedCandidates.slice(0, 5).map(row => <tr key={row.position_id}>
            <th scope="row">{row.name}</th><td>{scoreText(row.technical_score)}</td><td>{statusText(row)}</td>
            <td>{selectableIds.has(row.position_id)
              ? <button type="button" disabled={selectedPositionId === row.position_id} onClick={() => onSelect(row.position_id)}>{selectedPositionId === row.position_id ? 'Выбрана' : 'Выбрать'}</button>
              : <span className="preliminary-unselectable">Нет расчётного профиля</span>}</td>
          </tr>)}</tbody>
        </table></div>
      </> : <p className="preliminary-empty">Допустимого технического варианта пока нет. Проверьте ограничения объекта и сведения каталога.</p>}
      <details className="preliminary-all"><summary>Все позиции и причины проверки · {comparison.candidates.length}</summary>
        <div className="preliminary-table-wrap"><table className="preliminary-table">
          <thead><tr><th scope="col">Модель</th><th scope="col">Результат</th><th scope="col">Что нужно проверить</th></tr></thead>
          <tbody>{comparison.candidates.map(row => <tr key={row.position_id}>
            <th scope="row">{row.name}</th><td>{statusText(row)}</td><td>{unresolvedText(row)}</td>
          </tr>)}</tbody>
        </table></div>
      </details>
      <p className="preliminary-disclaimer">Технический балл — только предварительное сравнение. Денежное сопоставление требует подтверждённых цен и одинаковых финансовых входов; эта таблица не является рекомендацией к закупке.</p>
    </>}
  </div>;
}
