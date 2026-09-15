import test from 'node:test';
import assert from 'node:assert/strict';
import { generateWorld } from '../src/world/generator.js';
import { normalizeConfig } from '../src/world/config.js';
import { parseWorldDescription } from '../src/world/prompt-parser.js';
import { createSimulation, getSimulationReport, triggerSimulationEvent, updateSimulation } from '../src/simulation.js';

test('одинаковый seed создаёт одинаковый мир', () => {
  const a = generateWorld({ seed: 'TEST-42', width: 48, depth: 38, rackRows: 5, robotCount: 4, occupancy: 72 });
  const b = generateWorld({ seed: 'TEST-42', width: 48, depth: 38, rackRows: 5, robotCount: 4, occupancy: 72 });
  assert.deepEqual(a.staticObjects, b.staticObjects);
  assert.deepEqual(a.routes, b.routes);
});

test('разные seeds изменяют процедурное наполнение', () => {
  const a = generateWorld({ seed: 'ALPHA' });
  const b = generateWorld({ seed: 'BETA' });
  assert.notDeepEqual(a.staticObjects, b.staticObjects);
});

test('конфигурация ограничивает опасные значения', () => {
  assert.deepEqual(normalizeConfig({ width: 999, depth: 1, rackRows: 20, robotCount: 0, occupancy: 2 }), {
    template: 'warehouse', seed: 'ROBODOVOD-2026', width: 80, depth: 26, rackRows: 8, robotCount: 4, occupancy: 20
  });
});

test('описание склада преобразуется в воспроизводимую спецификацию', () => {
  const description = 'Паллетный склад 60 × 45 метров, 6 рядов стеллажей, парк из 5 роботов, заполнение 80%';
  const first = parseWorldDescription(description);
  const second = parseWorldDescription(description);
  assert.deepEqual(first, second);
  assert.deepEqual(first.config, { template: 'warehouse', seed: first.config.seed, width: 60, depth: 45, rackRows: 6, robotCount: 5, occupancy: 80 });
  assert.match(first.config.seed, /^SPEC-/);
  assert.ok(first.confidence > .5);
});

test('интерпретатор различает аэропорт и больницу', () => {
  const airport = parseWorldDescription('Аэропорт, терминал 70x50 м, 4 выхода на посадку, 7 багажных роботов, загрузка 75%');
  const hospital = parseWorldDescription('Клиника шириной 42 метра и длиной 55 метров, 7 палат, 3 AMR, занятость 68%');
  assert.equal(airport.config.template, 'airport');
  assert.equal(airport.config.rackRows, 4);
  assert.equal(airport.config.robotCount, 7);
  assert.equal(hospital.config.template, 'hospital');
  assert.equal(hospital.config.width, 42);
  assert.equal(hospital.config.depth, 55);
  assert.equal(hospital.config.rackRows, 7);
  assert.equal(hospital.config.robotCount, 3);
});

test('неполное описание сохраняет выбор формы и сообщает о допущениях', () => {
  const result = parseWorldDescription('Объект размером 120 на 10 метров и 15 роботов, заполнение 99%', {
    template: 'airport', seed: 'BASE', width: 48, depth: 38, rackRows: 5, robotCount: 4, occupancy: 72
  });
  assert.equal(result.config.template, 'airport');
  assert.equal(result.config.width, 80);
  assert.equal(result.config.depth, 26);
  assert.equal(result.config.robotCount, 8);
  assert.equal(result.config.occupancy, 95);
  assert.ok(result.assumptions.some(item => item.includes('ограничено')));
});

test('аэропорт и больница создают самостоятельные сцены', () => {
  const airport = generateWorld({ template: 'airport', seed: 'SVO', robotCount: 3 });
  const hospital = generateWorld({ template: 'hospital', seed: 'CLINIC', robotCount: 2 });
  assert.equal(airport.layout.objectName, 'Аэропорт');
  assert.equal(hospital.layout.objectName, 'Больница');
  assert.equal(airport.routes.length, 3);
  assert.equal(hospital.routes.length, 2);
  assert.ok(airport.staticObjects.some(item => item.type === 'checkin'));
  assert.ok(hospital.staticObjects.some(item => item.type === 'bed'));
  assert.ok(airport.labels.some(item => item.text.includes('ВЫХОД')));
  assert.ok(hospital.labels.some(item => item.text.includes('ПАЛАТА')));
  assert.ok(airport.routes.every(route => route.chargeWaypoint === 0));
  assert.ok(hospital.routes.every(route => route.chargeWaypoint === 0));
  assert.ok(airport.staticObjects.some(item => item.type === 'charger'));
  assert.ok(hospital.staticObjects.some(item => item.type === 'charger'));
});

test('каждый объект получает подходящий смешанный парк роботов', () => {
  const warehouse = generateWorld({ template: 'warehouse', seed: 'FLEET', robotCount: 6 });
  const airport = generateWorld({ template: 'airport', seed: 'FLEET', robotCount: 4 });
  const hospital = generateWorld({ template: 'hospital', seed: 'FLEET', robotCount: 4 });
  assert.deepEqual(new Set(warehouse.routes.map(route => route.robotType)), new Set(['pallet-amr', 'forklift', 'tow-amr']));
  assert.deepEqual(new Set(airport.routes.map(route => route.robotType)), new Set(['baggage-tug', 'cargo-amr']));
  assert.deepEqual(new Set(hospital.routes.map(route => route.robotType)), new Set(['medical-cart', 'service-robot']));
  assert.ok([...warehouse.routes, ...airport.routes, ...hospital.routes].every(route => route.radius && route.maxLoadKg && route.drive));
});

test('склад создаёт пространственные навигационные подписи', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'LABELS', rackRows: 5 });
  assert.equal(scene.labels.filter(item => item.text.startsWith('РЯД')).length, 5);
  assert.ok(scene.labels.some(item => item.text.includes('ОТГРУЗКА')));
});

test('люди получают локализованные роли для каждого объекта', () => {
  const warehouse = generateWorld({ template: 'warehouse', seed: 'PEOPLE' });
  const airport = generateWorld({ template: 'airport', seed: 'PEOPLE' });
  const hospital = generateWorld({ template: 'hospital', seed: 'PEOPLE' });
  assert.ok(warehouse.people.every(person => person.points.length >= 3 && person.role));
  assert.ok(airport.people.some(person => person.role === 'Пассажир'));
  assert.ok(airport.people.some(person => person.role === 'Сотрудник безопасности'));
  assert.ok(airport.people.some(person => person.role === 'Диспетчер AMR'));
  assert.ok(hospital.people.some(person => person.role === 'Врач'));
  assert.ok(hospital.people.some(person => person.role === 'Пациент'));
  assert.ok([...warehouse.people, ...airport.people, ...hospital.people].every(person => person.skin && person.hair && person.pants && person.height));
});

test('процедурные сцены сохраняют умеренную плотность людей', () => {
  const warehouse = generateWorld({ template: 'warehouse', seed: 'QUIET-FLOOR', rackRows: 8, occupancy: 100 });
  const airport = generateWorld({ template: 'airport', seed: 'QUIET-TERMINAL', occupancy: 100 });
  const hospital = generateWorld({ template: 'hospital', seed: 'QUIET-WARD', occupancy: 100 });
  assert.ok(warehouse.people.length <= 3);
  assert.ok(airport.people.length <= 7);
  assert.ok(hospital.people.length <= 6);
  assert.ok(warehouse.people.length > 0 && airport.people.length > 0 && hospital.people.length > 0);
});

test('люди находятся только в фиксированных безопасных рабочих зонах', () => {
  const warehouse = generateWorld({ template: 'warehouse', seed: 'PEOPLE-ZONES', robotCount: 6, occupancy: 90 });
  assert.equal(warehouse.people.length, 1);
  assert.equal(warehouse.people[0].role, 'Контролёр роботизированной зоны');
  assert.equal(warehouse.people[0].stationary, true);
  assert.ok(warehouse.people[0].points.every(point => point[1] > warehouse.layout.crossAisleZ + 3));

  const airport = generateWorld({ template: 'airport', seed: 'PEOPLE-ZONES', robotCount: 6, occupancy: 90 });
  assert.ok(airport.people.every(person => person.stationary));
  const passengers = airport.people.filter(person => person.role === 'Пассажир');
  const checkins = airport.staticObjects.filter(object => object.type === 'checkin');
  assert.ok(passengers.length > 0);
  assert.ok(passengers.every(person => Math.min(...checkins.map(checkin => Math.hypot(person.points[0][0] - checkin.position[0], person.points[0][1] - checkin.position[2]))) < 2));

  const hospital = generateWorld({ template: 'hospital', seed: 'PEOPLE-ZONES', robotCount: 6, occupancy: 90 });
  assert.ok(hospital.people.every(person => person.stationary));
  assert.ok(hospital.people.every(person => person.points.every(point => Math.abs(point[0]) > 3)));
  const beds = hospital.staticObjects.filter(object => object.type === 'bed');
  const patients = hospital.people.filter(person => person.role === 'Пациент');
  assert.ok(patients.every(person => person.pose === 'lying' && person.allowInsideSolid));
  assert.ok(patients.every(person => beds.some(bed => bed.position[0] === person.points[0][0] && bed.position[2] === person.points[0][1])));
});

test('люди ожидают вдали от зарядки, погрузки и выгрузки роботов', () => {
  const distanceToSegment = (point, start, end) => {
    const dx = end[0] - start[0];
    const dz = end[1] - start[1];
    const lengthSquared = dx * dx + dz * dz;
    const amount = lengthSquared ? Math.max(0, Math.min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dz) / lengthSquared)) : 0;
    return Math.hypot(point[0] - (start[0] + dx * amount), point[1] - (start[1] + dz * amount));
  };
  for (const template of ['airport', 'hospital']) {
    const scene = generateWorld({ template, seed: 'CLEAR-ROBOT-ZONES', robotCount: 6, occupancy: 100 });
    const operationalPoints = scene.routes.flatMap(route => [
      route.points[route.chargeWaypoint ?? 0],
      route.points[route.pickupWaypoint ?? 2],
      route.points[route.dropWaypoint ?? 4]
    ]);
    scene.people.forEach(person => {
      assert.ok(person.stopPoints?.length > 0, `${template}: не заданы безопасные точки ожидания`);
      person.stopPoints.forEach(stop => {
        const clearance = Math.min(...operationalPoints.map(point => Math.hypot(stop[0] - point[0], stop[1] - point[1])));
        assert.ok(clearance >= 2, `${template}: человек ожидает слишком близко к рабочей точке робота`);
        const routeClearance = Math.min(...scene.routes.flatMap(route => route.points.slice(0, -1).map((point, index) => distanceToSegment(stop, point, route.points[index + 1]))));
        assert.ok(routeClearance >= 2, `${template}: точка ожидания человека попала в транспортный коридор`);
      });
    });
  }
});

test('пациенты и медицинский персонал остаются внутри палат', () => {
  const scene = generateWorld({ template: 'hospital', seed: 'ROOM-OCCUPANCY', occupancy: 90 });
  const patients = scene.people.filter(person => person.role === 'Пациент');
  const staff = scene.people.filter(person => person.role !== 'Пациент');
  assert.ok(patients.length > 0 && staff.length > 0);
  assert.ok(patients.every(person => person.points.every(point => Math.abs(point[0]) > 2)));
  assert.ok(staff.every(person => person.points.every(point => Math.abs(point[0]) > 1.4)));
});

test('симуляция детерминированно двигает парк и считает рейсы', () => {
  const scene = generateWorld({ seed: 'SIM', robotCount: 3 });
  const simulation = createSimulation(scene);
  const before = simulation.robots.map(robot => [...robot.position]);
  updateSimulation(simulation, 1);
  assert.equal(simulation.robots.length, 3);
  assert.notDeepEqual(simulation.robots.map(robot => robot.position), before);
  for (let i = 0; i < 2400; i += 1) updateSimulation(simulation, .5);
  assert.ok(simulation.trips > 0);
});

test('центральные ворота склада доступны для прохода', () => {
  const scene = generateWorld({ seed: 'OPEN-DOOR', width: 48, depth: 38 });
  const entranceZ = scene.layout.front;
  const blocked = scene.solids.some(solid => {
    const halfX = solid.scale[0] / 2;
    const halfZ = solid.scale[2] / 2;
    return 0.34 > solid.position[0] - halfX && -0.34 < solid.position[0] + halfX &&
      entranceZ + 0.34 > solid.position[2] - halfZ && entranceZ - 0.34 < solid.position[2] + halfZ;
  });
  assert.equal(blocked, false);
});

test('движок сохраняет защитную остановку при неожиданном человеке на пути', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'SAFETY', robotCount: 1 });
  const simulation = createSimulation(scene);
  const person = simulation.people[0];
  const robot = simulation.robots[0];
  const beforePerson = [...person.position];
  person.stationary = false;
  updateSimulation(simulation, .5, scene.solids);
  assert.notDeepEqual(person.position, beforePerson);
  person.speed = 0;
  person.position[0] = robot.position[0] + Math.sin(robot.yaw) * .78;
  person.position[2] = robot.position[2] + Math.cos(robot.yaw) * .78;
  person.pause = 10;
  updateSimulation(simulation, .1, scene.solids);
  assert.equal(robot.blockedByHuman, true);
  assert.equal(robot.currentSpeed, 0);
});

test('выгруженный груз остаётся в зоне назначения', () => {
  const scene = generateWorld({ template: 'airport', seed: 'CARGO', robotCount: 1 });
  const simulation = createSimulation(scene);
  simulation.people = [];
  for (let i = 0; i < 4000 && simulation.deliveredCargo.length === 0; i += 1) {
    updateSimulation(simulation, .1, scene.solids);
  }
  assert.ok(simulation.deliveredCargo.length > 0);
  assert.equal(simulation.deliveredCargo[0].kind, 'baggage');
});

test('роботы выдерживают безопасную дистанцию друг от друга', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'TRAFFIC', robotCount: 2 });
  const simulation = createSimulation(scene);
  simulation.people = [];
  const leader = simulation.robots[0];
  const follower = simulation.robots[1];
  follower.yaw = leader.yaw;
  follower.position[0] = leader.position[0] - Math.sin(follower.yaw) * .8;
  follower.position[2] = leader.position[2] - Math.cos(follower.yaw) * .8;
  updateSimulation(simulation, .05, scene.solids);
  assert.equal(follower.blockedByRobot, true);
  assert.equal(follower.currentSpeed, 0);
});

test('робот расходует энергию, заряжается и возвращается к работе', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'POWER', robotCount: 1 });
  const simulation = createSimulation(scene);
  simulation.people = [];
  const robot = simulation.robots[0];
  const initialBattery = robot.battery;
  for (let i = 0; i < 30; i += 1) updateSimulation(simulation, .1, scene.solids);
  assert.ok(robot.battery < initialBattery);

  robot.battery = 29;
  robot.needsCharge = true;
  for (let i = 0; i < 6000 && robot.mode !== 'charging'; i += 1) updateSimulation(simulation, .1, scene.solids);
  assert.equal(robot.mode, 'charging');
  assert.equal(robot.carrying, false);
  const chargingBattery = robot.battery;
  updateSimulation(simulation, .2, scene.solids);
  assert.ok(robot.battery > chargingBattery);
  for (let i = 0; i < 100 && robot.mode === 'charging'; i += 1) updateSimulation(simulation, .1, scene.solids);
  assert.equal(robot.mode, 'working');
  assert.equal(robot.needsCharge, false);
  assert.equal(robot.battery, 100);
});

test('диспетчер выдаёт ожидающему роботу следующее задание', () => {
  const scene = generateWorld({ template: 'hospital', seed: 'DISPATCH', robotCount: 1 });
  const simulation = createSimulation(scene);
  const robot = simulation.robots[0];
  const queuedTask = simulation.taskQueue[0];
  robot.activeTask = null;
  robot.mode = 'idle';
  updateSimulation(simulation, .1, scene.solids);
  assert.equal(robot.mode, 'working');
  assert.equal(robot.activeTask.id, queuedTask.id);
  assert.equal(robot.activeTask.status, 'active');
  assert.equal(simulation.taskQueue.length, 0);
});

test('выгрузка завершает назначенное задание и пополняет историю', () => {
  const scene = generateWorld({ template: 'airport', seed: 'TASK-FLOW', robotCount: 1 });
  const simulation = createSimulation(scene);
  simulation.people = [];
  const taskId = simulation.robots[0].activeTask.id;
  for (let i = 0; i < 5000 && simulation.completedTasks.length === 0; i += 1) updateSimulation(simulation, .1, scene.solids);
  assert.equal(simulation.completedTasks[0].id, taskId);
  assert.equal(simulation.completedTasks[0].status, 'completed');
  assert.ok(simulation.completedTasks[0].completedAt >= simulation.completedTasks[0].startedAt);
  assert.equal(simulation.trips, 1);
});

test('груз проходит видимые стадии захвата, перевозки и выгрузки', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'CARGO-STAGES', robotCount: 2 });
  const simulation = createSimulation(scene);
  simulation.people = [];
  const robot = simulation.robots.find(item => item.robotType === 'forklift');
  assert.ok(robot);
  simulation.robots = [robot];

  for (let i = 0; i < 5000 && robot.operationType !== 'pickup'; i += 1) updateSimulation(simulation, .1, scene.solids);
  assert.equal(robot.operationType, 'pickup');
  assert.equal(robot.cargoStage, 'carried');
  assert.equal(robot.carrying, true);
  const stoppedAtPickup = robot.distance;
  updateSimulation(simulation, .2, scene.solids);
  assert.ok(robot.operationProgress > 0);
  assert.equal(robot.distance, stoppedAtPickup);

  for (let i = 0; i < 5000 && robot.operationType !== 'drop'; i += 1) updateSimulation(simulation, .1, scene.solids);
  assert.equal(robot.operationType, 'drop');
  assert.equal(robot.cargoStage, 'delivered');
  assert.equal(robot.carrying, false);
  assert.ok(simulation.deliveredCargo.length > 0);
});

test('робот объезжает человека, когда сбоку есть безопасное пространство', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'DETOUR', robotCount: 1 });
  const simulation = createSimulation(scene);
  const robot = simulation.robots[0];
  const person = simulation.people[0];
  simulation.people = [person];
  person.speed = 0;
  person.pause = 10;
  person.position[0] = robot.position[0] + Math.sin(robot.yaw) * 1.8;
  person.position[2] = robot.position[2] + Math.cos(robot.yaw) * 1.8;
  updateSimulation(simulation, .1, []);
  assert.equal(robot.avoidingHuman, true);
  assert.equal(robot.blockedByHuman, false);
  assert.ok(Math.abs(robot.avoidanceOffset) > 0);
  assert.equal(simulation.detours, 1);
});

test('защитные остановки учитывают потерянное время', () => {
  const scene = generateWorld({ template: 'hospital', seed: 'STOP-METRIC', robotCount: 1 });
  const simulation = createSimulation(scene);
  const robot = simulation.robots[0];
  const person = simulation.people[0];
  simulation.people = [person];
  person.speed = 0;
  person.pause = 10;
  person.position[0] = robot.position[0] + Math.sin(robot.yaw) * .7;
  person.position[2] = robot.position[2] + Math.cos(robot.yaw) * .7;
  updateSimulation(simulation, .2, []);
  assert.equal(robot.blockedByHuman, true);
  assert.equal(robot.currentSpeed, 0);
  assert.equal(simulation.safetyStops, 1);
  assert.ok(simulation.totalWaitingTime > 0);
});

test('диспетчер резервирует конфликтную зону только одному роботу', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'RESERVATION', robotCount: 2 });
  const simulation = createSimulation(scene);
  simulation.people = [];
  const [emptyRobot, loadedRobot] = simulation.robots;
  loadedRobot.route = emptyRobot.route;
  loadedRobot.distance = emptyRobot.distance;
  loadedRobot.position = [...emptyRobot.position];
  emptyRobot.carrying = false;
  loadedRobot.carrying = true;
  updateSimulation(simulation, .1, []);
  assert.equal(emptyRobot.reservationBlocked, true);
  assert.equal(loadedRobot.reservationBlocked, false);
  assert.ok(emptyRobot.reservedPosition);
  assert.ok(loadedRobot.reservedPosition);
  assert.equal(simulation.activeReservations, 1);
  assert.equal(simulation.trafficConflicts, 1);
  assert.ok(simulation.totalReservationWait > 0);
});

test('пик спроса добавляет воспроизводимую волну заданий', () => {
  const scene = generateWorld({ template: 'airport', seed: 'DEMAND-WAVE', robotCount: 3 });
  const simulation = createSimulation(scene);
  const before = simulation.taskQueue.length;
  assert.equal(triggerSimulationEvent(simulation, 'demand-wave'), true);
  assert.equal(simulation.taskQueue.length, before + 6);
  assert.equal(simulation.demandWaves, 1);
  assert.equal(simulation.events.at(-1).type, 'demand');
});

test('временный отказ сохраняет задание и заканчивается восстановлением', () => {
  const scene = generateWorld({ template: 'hospital', seed: 'ROBOT-FAULT', robotCount: 2 });
  const simulation = createSimulation(scene);
  const taskIds = new Set(simulation.robots.map(robot => robot.activeTask.id));
  assert.equal(triggerSimulationEvent(simulation, 'robot-fault'), true);
  const failed = simulation.robots.find(robot => robot.mode === 'fault');
  assert.ok(failed);
  assert.ok(taskIds.has(failed.activeTask.id));
  const stoppedPosition = [...failed.position];
  updateSimulation(simulation, 1, scene.solids);
  assert.deepEqual(failed.position, stoppedPosition);
  assert.ok(failed.downtime > 0);
  for (let i = 0; i < 20 && failed.mode === 'fault'; i += 1) updateSimulation(simulation, 1, scene.solids);
  assert.equal(failed.mode, 'working');
  assert.equal(simulation.faults, 1);
  assert.equal(simulation.faultsResolved, 1);
  assert.equal(simulation.events.at(-1).type, 'recovery');
  assert.ok(taskIds.has(failed.activeTask.id));
});

test('операционный отчёт собирает воспроизводимые KPI парка', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'REPORT', robotCount: 3 });
  const simulation = createSimulation(scene);
  simulation.people = [];
  triggerSimulationEvent(simulation, 'robot-fault');
  for (let i = 0; i < 1800; i += 1) updateSimulation(simulation, .1, scene.solids);
  const report = getSimulationReport(simulation);
  assert.deepEqual(getSimulationReport(simulation), report);
  assert.equal(report.fleetSize, 3);
  assert.equal(report.tasks.completed, simulation.trips);
  assert.ok(report.tasks.throughputPerHour > 0);
  assert.ok(report.fleet.utilizationPercent >= 0 && report.fleet.utilizationPercent <= 100);
  assert.ok(report.fleet.availabilityPercent >= 0 && report.fleet.availabilityPercent <= 100);
  assert.ok(report.fleet.downtimeSeconds > 0);
  assert.ok(report.energy.consumedUnits > 0);
  assert.equal(report.robots.length, 3);
  assert.doesNotThrow(() => JSON.stringify(report));
});

test('физический корпус AMR не проходит через статическое препятствие', () => {
  const scene = generateWorld({ template: 'warehouse', seed: 'SOLID-BODY', robotCount: 1 });
  const simulation = createSimulation(scene);
  simulation.people = [];
  const robot = simulation.robots[0];
  robot.pause = 0;
  const beforeDistance = robot.distance;
  const obstacle = {
    position: [robot.position[0] + Math.sin(robot.yaw) * .9, .5, robot.position[2] + Math.cos(robot.yaw) * .9],
    scale: [.24, 1, .24]
  };
  updateSimulation(simulation, .5, [obstacle]);
  assert.equal(robot.distance, beforeDistance);
  assert.equal(robot.blockedBySolid, true);
  assert.equal(robot.currentSpeed, 0);
});

test('люди соблюдают персональное пространство и не входят в корпус AMR', () => {
  const scene = generateWorld({ template: 'airport', seed: 'PEDESTRIAN-BODY', robotCount: 1 });
  const simulation = createSimulation(scene);
  const [first, second] = simulation.people;
  simulation.people = [first, second];
  first.stationary = false;
  second.stationary = false;
  first.pause = 0;
  second.pause = 10;
  second.position = [...first.position];
  second.position[2] += .4;
  updateSimulation(simulation, .2, []);
  assert.equal(first.blockedByPerson, true);
  assert.equal(first.currentSpeed, 0);
  first.position[0] = simulation.robots[0].position[0];
  first.position[2] = simulation.robots[0].position[2] - 1.0;
  first.distance = second.distance;
  updateSimulation(simulation, .2, []);
  assert.equal(first.blockedByRobot, true);
});

test('длительный прогон трёх сцен не допускает пересечения физических корпусов', () => {
  const circleHitsSolid = (position, solid, radius) => {
    const halfX = solid.scale[0] / 2;
    const halfZ = solid.scale[2] / 2;
    return position[0] + radius > solid.position[0] - halfX && position[0] - radius < solid.position[0] + halfX &&
      position[2] + radius > solid.position[2] - halfZ && position[2] - radius < solid.position[2] + halfZ;
  };
  for (const template of ['warehouse', 'airport', 'hospital']) {
    const scene = generateWorld({ template, seed: 'BODY-AUDIT', robotCount: 8 });
    const simulation = createSimulation(scene);
    for (let step = 0; step < 1200; step += 1) {
      updateSimulation(simulation, .05, scene.solids);
      simulation.robots.forEach((robot, index) => {
        assert.equal(scene.solids.some(solid => circleHitsSolid(robot.position, solid, robot.radius - .01)), false, `${template}: AMR вошёл в препятствие`);
        simulation.robots.slice(index + 1).forEach(other => {
          assert.ok(Math.hypot(robot.position[0] - other.position[0], robot.position[2] - other.position[2]) >= robot.radius + other.radius - .001, `${template}: корпуса AMR пересеклись`);
        });
        simulation.people.forEach(person => {
          assert.ok(Math.hypot(robot.position[0] - person.position[0], robot.position[2] - person.position[2]) >= robot.radius + .269, `${template}: AMR пересёк человека`);
        });
      });
    }
  }
});
