// Conditional scenery. Coordinates are in the same local plan as the safe route.
const item = (type, x, y, width, height, elevation, color, extra = {}) =>
  ({ type, x, y, width, height, elevation, color, ...extra });

export function environmentCandidates(plan) {
  const items = [];
  if (plan.clinic) {
    for (const ward of plan.areas.filter(area => area.id.startsWith('ward-'))) {
      items.push(item('bed', ward.x + 2, ward.y + 1, 3, 1.8, .85, [.68, .82, .85], { patient: Number(ward.id.at(-1)) % 2 === 1 }));
      items.push(item('supply', ward.x + 13, ward.y + 1, 3, 1.8, 1.7, [.65, .77, .78]));
      items.push(item('station', ward.x + 11, ward.y + 5, 1.8, 1.2, .9, [.53, .70, .72]));
    }
    items.push(item('reception', 4, 29, 4, 1.6, 1.15, [.52, .69, .73]));
    items.push(item('person', 10, 31, .8, .8, 1.8, null, { role: 'Сотрудник раздачи' }));
    items.push(item('person', 8, 3, .8, .8, 1.8, null, { role: 'Врач' }));
    items.push(item('person', 36, 21, .8, .8, 1.8, null, { role: 'Медсестра' }));
  } else if (plan.cleaning) {
    for (const hall of plan.areas.slice(0, 3)) {
      items.push(item('checkin', hall.x + 1, 2, 4, 1.5, 1.35, [.43, .63, .67]));
      for (let i = 0; i < 2; i += 1) items.push(item('seat', hall.x + 9 + i * 2.2, 2, 1.3, 1.2, .85, [.31, .50, .57]));
      items.push(item('baggage', hall.x + 13, 3.4, 1.2, .9, .75, [.63, .41, .24]));
      items.push(item('person', hall.x + 7, 4.3, .8, .8, 1.8, null, { role: 'Пассажир' }));
    }
    items.push(item('sign', 19, 1, 5, .18, 2.9, [.28, .68, .76], { overhead: true }));
  } else if (plan.warehouseTransport) {
    for (const rack of plan.furniture.filter(rect => rect.type === 'rack')) {
      items.push(item('rack', rack.x, rack.y, rack.width, rack.height, 3.1, [.40, .52, .54],
        { robotOrdinal: rack.robotOrdinal, compact: true }));
      items.push(item('cargo', rack.x + .55, rack.y + .15, .9, 1, .75, [.68, .47, .25],
        { onRack: true, robotOrdinal: rack.robotOrdinal }));
    }
    items.push(item('station', 59, .5, 2.2, 1.2, 1.15, [.35, .59, .63]));
    items.push(item('person', 61, 3.6, .8, .8, 1.8, null, { role: 'Оператор отгрузки' }));
    for (const home of plan.homes)
      items.push(item('charger', home.x - 1.7, home.y - .5, .55, 1, 1.05, [.19, .52, .45], { compact: true }));
  } else {
    const rack = plan.furniture.find(rect => rect.type === 'rack');
    if (rack) {
      const pitch = Math.max(5, rack.height / 5);
      for (let y = rack.y + 1; y + 3 < rack.y + rack.height && items.filter(row => row.type === 'rack').length < 4; y += pitch) {
        items.push(item('rack', rack.x, y, rack.width, 3, 3.1, [.40, .52, .54]));
        items.push(item('cargo', rack.x + .35, y + .4, 1, 1, .75, [.68, .47, .25], { onRack: true }));
      }
    }
    items.push(item('cargo', 40.5, 6, 1.4, 1.3, .85, [.70, .47, .23]));
    items.push(item('station', 42, .6, 2.2, 1.2, 1.15, [.35, .59, .63]));
    items.push(item('person', 45.5, 1, .8, .8, 1.8, null, { role: 'Оператор' }));
    for (const home of plan.homes.slice(0, Math.min(8, plan.homes.length)))
      items.push(item('charger', home.x - 1.7, home.y - .5, .55, 1, 1.05, [.19, .52, .45]));
  }
  return items;
}
