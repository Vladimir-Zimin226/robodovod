/** Stable ScenarioSpec v2 identities shared by the 2D plan and RobCraft. */
export function sceneBindingsV2(spec) {
  if (spec?.schema_version !== 'scenario-spec-v2') throw new TypeError('Нужен ScenarioSpec v2');
  for (const key of ['zones', 'tasks', 'routes', 'fleet']) {
    if (!Array.isArray(spec[key])) throw new TypeError(`ScenarioSpec.${key} должен быть массивом`);
  }
  if (!spec.zones.length) throw new TypeError('ScenarioSpec не содержит зон');
  const unique = (items, key) => {
    const ids = new Set();
    for (const item of items) {
      if (typeof item?.[key] !== 'string' || !item[key] || ids.has(item[key])) {
        throw new TypeError(`Повторяющийся или пустой ${key}`);
      }
      ids.add(item[key]);
    }
    return ids;
  };
  const zoneIds = unique(spec.zones, 'zone_id');
  const routeIds = unique(spec.routes, 'route_id');
  unique(spec.tasks, 'task_id');
  unique(spec.fleet, 'fleet_id');
  for (const task of spec.tasks) {
    if (!zoneIds.has(task.zone_id) || (task.route_ref !== null && !routeIds.has(task.route_ref))) {
      throw new TypeError(`Задание ${task.task_id} ссылается на неизвестную зону или маршрут`);
    }
  }
  for (const fleet of spec.fleet) {
    if (!zoneIds.has(fleet.zone_id)) throw new TypeError(`Парк ${fleet.fleet_id} ссылается на неизвестную зону`);
    if (!Number.isInteger(fleet.selected_fleet) || fleet.selected_fleet < 0 || fleet.selected_fleet > 100) {
      throw new TypeError(`Парк ${fleet.fleet_id} содержит недопустимый selected_fleet`);
    }
  }
  return spec.zones.map((zone) => ({
    zoneId: zone.zone_id,
    label: zone.label,
    source: zone,
    tasks: spec.tasks.filter((task) => task.zone_id === zone.zone_id).map((task) => ({
      taskId: task.task_id,
      processId: task.process_id,
      routeId: task.route_ref,
      pickupId: `${task.task_id}.pickup`,
      dropoffId: `${task.task_id}.dropoff`,
      source: task,
    })),
    fleet: spec.fleet.filter((fleet) => fleet.zone_id === zone.zone_id).map((item) => ({
      fleetId: item.fleet_id,
      processId: item.process_id,
      selectedFleet: item.selected_fleet,
      source: item,
    })),
  }));
}
