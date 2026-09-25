const stageLabels = {
  TO_PICKUP: 'Едет к подготовленной паллете', LOADING: 'Принимает готовую паллету',
  TO_DROPOFF: 'Везёт груз', UNLOADING: 'Выгрузка',
  RETURN: 'Возврат', WAITING: 'Ожидание',
};
const cargoLabels = {
  AT_PICKUP: 'В точке передачи', ON_ROBOT: 'На роботе',
  AT_DROPOFF: 'В точке выгрузки', DELIVERED: 'Доставлен',
};

function track(robot) {
  const { waiting, pickup, dropoff } = robot.points;
  return `M ${waiting.x} ${waiting.y} L ${pickup.x} ${pickup.y} L ${dropoff.x} ${dropoff.y} L ${waiting.x} ${waiting.y}`;
}

export default function Warehouse2DPlan({ scene, frame, selectedZoneId, stages = null }) {
  const visible = scene.zones.filter((zone) => zone.id === selectedZoneId);
  const zone = visible[0] || scene.zones[0];
  const robots = frame.robots.filter((robot) => robot.zoneId === zone.id);
  const tasks = scene.tasks.filter((task) => task.zoneId === zone.id);
  const taskById = new Map(tasks.map((task) => [task.id, task]));
  return <>
    {stages && <div className="warehouse-process-chain" aria-label="Стадии складского процесса">
      {stages.map((stage) => <div key={stage.stage} className={stage.status === 'MODELED' ? 'is-modeled' : ''}>
        <strong>{({ PICKING: 'Отбор', BUFFER: 'Буфер', FEED_TO_PACK: 'Подача к упаковке', PACKAGING: 'Упаковка' })[stage.stage]}</strong>
        <span>{stage.status === 'MODELED' ? `Очередь до ${stage.maximum_queue_jobs} заданий · занятость ${Math.round(Number(stage.utilization_fraction) * 100)} %` : 'Внешняя граница · нет подтверждённых входов'}</span>
      </div>)}
      <div className="is-modeled"><strong>Передача готовой паллеты → перевозка → выгрузка</strong><span>Показатели паллетной перевозки из сохранённого отчёта</span></div>
    </div>}
    <div className="simulation-canvas-wrap warehouse-canvas-wrap">
      <div className="warehouse-svg-scroll">
      <svg viewBox={`${zone.x - 14} ${zone.y - 14} ${zone.width + 28} ${zone.height + 28}`}
        role="img" aria-label={`Условный план склада: ${zone.label}`}>
        <rect className={`simulation-zone source-${zone.geometrySource.toLowerCase()}`}
          x={zone.x} y={zone.y} width={zone.width} height={zone.height} rx="14" />
        <text className="zone-name" x={zone.x + 18} y={zone.y + 28}>{zone.label}</text>
        <text className="warehouse-geometry-label" x={zone.x + 18} y={zone.y + 47}>Расположение условное</text>
        {zone.racks.map((rack) => <g key={rack.id}>
          <rect className="warehouse-rack" x={rack.x} y={rack.y} width={rack.width} height={rack.height} rx="3" />
          <path className="warehouse-rack-shelf" d={`M ${rack.x} ${rack.y + 16} h ${rack.width} M ${rack.x} ${rack.y + 32} h ${rack.width}`} />
        </g>)}
        <text className="warehouse-aisle-label" x={zone.x + 18} y={zone.y + 127}>СТЕЛЛАЖНЫЕ ПРОХОДЫ</text>
        {robots.map((robot) => <g key={robot.id} data-zone-id={robot.zoneId} data-task-id={robot.taskId || ''}>
          <title>{`Робот ${robot.lane + 1}: ${stageLabels[robot.stage]}; груз: ${cargoLabels[robot.cargoState] || 'нет задания'}`}</title>
          {robot.taskId && <>
            <path className="warehouse-track" d={track(robot)} />
            <circle className="warehouse-pickup" data-point-id={taskById.get(robot.taskId)?.pickupId} cx={robot.points.pickup.x} cy={robot.points.pickup.y} r="5" />
            <circle className="warehouse-dropoff" data-point-id={taskById.get(robot.taskId)?.dropoffId} cx={robot.points.dropoff.x} cy={robot.points.dropoff.y} r="5" />
            {robot.cargoState && <rect className={`warehouse-cargo cargo-${robot.cargoState.toLowerCase()}`}
              x={(robot.cargoState === 'ON_ROBOT' ? robot.x : robot.cargoState === 'AT_PICKUP' ? robot.points.pickup.x : robot.points.dropoff.x) - 6}
              y={(robot.cargoState === 'ON_ROBOT' ? robot.y - 16 : robot.points.pickup.y - 15) - 5}
              width="12" height="10" rx="2" />}
          </>}
          <g transform={`translate(${robot.x} ${robot.y})`}>
            <circle className="simulation-robot" r="9" />
            <text className="warehouse-robot-number" textAnchor="middle" y="3.5">{robot.lane + 1}</text>
          </g>
        </g>)}
        {[zone.waiting, zone.receiving, zone.shipping].map((point) => <g key={point.id}>
          <rect className="warehouse-station" x={point.x - 9} y={point.y - 14} width="18" height="14" rx="2" />
          <text className="warehouse-station-label" x={point.x} y={point.y + 15} textAnchor="middle">{point.label}</text>
        </g>)}
      </svg>
      </div>
      <div className="simulation-legend">
        <span><i className="legend-robot" /> робот</span>
        <span>● передача подготовленной паллеты</span><span>● точка выгрузки</span>
        <span>▰ готовая паллета: в точке передачи → на роботе → у отгрузки</span>
      </div>
      <p className="simulation-schematic-note">Учтена перевозка подготовленных паллет; отбор коробок и упаковка не рассчитаны. Это условный план сверху. План можно прокрутить по горизонтали. Точки и 20-секундный цикл показывают порядок действий, а не реальные координаты, время операций или выполненные задания. Показатели берутся только из отчёта симуляции.</p>
    </div>
    <div className="warehouse-zone-details">
      <strong>{zone.label}</strong><span>Зона: <code>{zone.id}</code></span>
      <span>{zone.geometrySource === 'PROVIDED'
        ? `Есть ссылка на план ${zone.geometryRef}, но координаты в сценарии не сохранены.`
        : 'План здания не загружен; расположение условное.'}</span>
      {tasks.length ? tasks.map((task) => <span key={task.id}>
        Задание <code>{task.id}</code> · маршрут <code>{task.routeId || 'не задан'}</code>
        {task.hasRoute && <> · передача готовой паллеты <code>{task.pickupId}</code> · выгрузка <code>{task.dropoffId}</code></>}
      </span>) : <span>В этой зоне нет сохранённых заданий.</span>}
      {scene.missingTasks.includes(zone.id) && <span>Нет маршрута для показа перевозки: робот остаётся в ожидании.</span>}
      {!robots.length && <span>В этой зоне не выбран парк роботов.</span>}
      <span>Ожидание и зарядка показаны одним условным местом; зарядный цикл не моделируется.</span>
    </div>
    {robots.length > 0 && <div className="warehouse-robot-states" aria-label="Состояния роботов и грузов">
      {robots.map((robot) => <div key={robot.id}>
        <strong>Робот {robot.lane + 1}</strong>
        <span>{stageLabels[robot.stage]}</span>
        <small>Груз: {cargoLabels[robot.cargoState] || 'нет задания'}</small>
      </div>)}
    </div>}
  </>;
}
