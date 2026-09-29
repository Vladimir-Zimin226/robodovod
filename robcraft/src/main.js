import { Renderer } from './core/renderer.js';
import { Player } from './player.js';
import { CameraDirector } from './camera-director.js';
import { generateWorld, generateWorldsFromScenarioSpec } from './world/generator.js';
import { configFromUrl, configToQuery, normalizeConfig } from './world/config.js';
import { parseWorldDescription } from './world/prompt-parser.js';
import { buildRendererReport, createSimulation, getSimulationReport, triggerSimulationEvent, updateSimulation } from './simulation.js';
import { AudioEngine } from './audio.js';
import { BUILD_CATALOG, pickEntity, rayGroundPoint, SceneEditorModel } from './editor/editor.js';
import { canPlaceSolid, circleIntersectsSolid } from './editor/collisions.js';
import { assertScenePatchCompatible, compatibleRobotTypes, createScenePatch, exportSceneDocument, importSceneDocument, rebindScenePatch, scenarioVisualFingerprint, scenePatchHasChanges, scenePatchSummary } from './editor/scene-patch.js';
import { childMessage, installParentBridge } from './integration/message-protocol.js';
import { applyFacilityPlayback, updateFacilityCamera } from './integration/facility-renderer.js';

const canvas = document.querySelector('#world');
const launcher = document.querySelector('#launcher');
const hud = document.querySelector('#hud');
const form = document.querySelector('#world-form');
const targetCard = document.querySelector('#target-card');
const prompt = document.querySelector('#prompt');
const pauseNote = document.querySelector('#pause-note');
const cameraMode = document.querySelector('#camera-mode');
const directorCaption = document.querySelector('#director-caption');
const manualToggle = document.querySelector('#manual-toggle');
const worldLabels = document.querySelector('#world-labels');
const analyticsPanel = document.querySelector('#analytics-panel');
const reportPanel = document.querySelector('#report-panel');
const errorBox = document.querySelector('#error');
const descriptionField = document.querySelector('#world-description');
const parseResult = document.querySelector('#parse-result');
const editorPanel = document.querySelector('#editor-panel');
const editorSelection = document.querySelector('#editor-selection');
const editorMessage = document.querySelector('#editor-message');
const gridEnabled = document.querySelector('#grid-enabled');
const gridStep = document.querySelector('#grid-step');
const fields = Object.fromEntries(['template', 'seed', 'width', 'depth', 'rackRows', 'robotCount', 'occupancy'].map(id => [id, document.querySelector(`#${id}`)]));
const embeddedMode = new URLSearchParams(location.search).get('embedded') === '1' && window.parent !== window;

let renderer;
let player;
let cameraDirector;
let scene;
let simulation;
let active = false;
let inspectedEntity = null;
let lastFrame = performance.now();
let hudTimer = 0;
let analyticsEnabled = false;
let reportEnabled = false;
let labelElements = [];
let inspectionEntities = [];
let lastEventId = 0;
let eventToastUntil = 0;
let descriptionSpec = null;
let baseScene;
let sceneEditor;
let editorMode = false;
let editorTool = 'select';
let buildKind = null;
let editorHovered = null;
let editorPreview = null;
let editorPreviousFlight = false;
let editorAxis = 'xz';
let cameraState = 'AUTOPILOT';
let editorPreviousCameraState = 'AUTOPILOT';
let visualFingerprint = null;
let embeddedBridge = null;
let zoneSessions = [];
let scenarioZoneEntries = [];
let activeZoneIndex = 0;
let zoneRotationElapsed = 0;
let pinnedZoneId = null;
let authoritativeSimulationReport = null;
let embeddedPlayback = null;
const audioEngine = new AudioEngine();

function cameraSnapshot(reason = 'STATE_CHANGED') {
  return {
    mode: cameraState,
    reason,
    pointerLocked: document.pointerLockElement === canvas
  };
}

function updateCameraUi() {
  const manual = cameraState === 'MANUAL_FIRST_PERSON';
  document.body.classList.toggle('manual-active', manual);
  manualToggle.textContent = 'Осмотреть вручную';
  directorCaption.classList.toggle('hidden', manual || !cameraDirector?.caption);
  if (manual) {
    cameraMode.textContent = player.flying ? '◆ РЕЖИМ: СВОБОДНЫЙ ПОЛЁТ' : '● РЕЖИМ: ПЕШКОМ';
    cameraMode.classList.toggle('flying', player.flying);
  } else {
    cameraMode.textContent = '◉ РЕЖИМ: АВТОПОКАЗ';
    cameraMode.classList.add('flying');
  }
}

function announceCameraMode(reason) {
  const state = cameraSnapshot(reason);
  embeddedBridge?.cameraModeChanged(state.mode, state.reason, state.pointerLocked);
  return state;
}

function manualControlAllowed() {
  return scene?.scenarioSpec?.presentation?.manual_control_available !== false;
}

function requestManualPointerLock() {
  if (typeof canvas.requestPointerLock !== 'function') return Promise.reject(new Error('Pointer Lock API недоступен'));
  return new Promise((resolve, reject) => {
    let settled = false;
    const cleanup = () => {
      document.removeEventListener('pointerlockchange', changed);
      document.removeEventListener('pointerlockerror', failed);
      clearTimeout(timeout);
    };
    const finish = (callback, value) => {
      if (settled) return;
      settled = true;
      cleanup();
      callback(value);
    };
    const changed = () => {
      if (document.pointerLockElement === canvas) finish(resolve);
    };
    const failed = () => finish(reject, new Error('Браузер отклонил захват указателя'));
    const timeout = setTimeout(() => {
      if (document.pointerLockElement === canvas) finish(resolve);
      else finish(reject, new Error('Захват указателя не подтверждён'));
    }, 1500);
    document.addEventListener('pointerlockchange', changed);
    document.addEventListener('pointerlockerror', failed);
    try {
      const result = canvas.requestPointerLock();
      result?.catch(failed);
    } catch (error) {
      finish(reject, error);
    }
  });
}

function prepareEmbeddedScenario(spec, simulationReport = null) {
  const generated = generateWorldsFromScenarioSpec(spec, { facilityPlans: Boolean(simulationReport), safePlayback: Boolean(simulationReport) });
  if (!generated.zones.some(zone => zone.supported)) {
    throw new TypeError(`Нет поддерживаемых 3D-зон: ${generated.zones.map(zone => `${zone.zone.name} — ${zone.reason}`).join('; ')}`);
  }
  return {
    generated,
    fingerprint: scenarioVisualFingerprint(spec),
    authoritativeReport: simulationReport
  };
}

function createZoneSession(entry, fingerprint) {
  const base = entry.scene;
  const editor = new SceneEditorModel(base, createScenePatch(base.config, {
    revisionId: base.scenarioSpec.revision_id, visualFingerprint: fingerprint, zoneId: base.scenario.zoneId
  }));
  const zoneSimulation = createSimulation(editor.scene);
  zoneSimulation.baseRevisionId = base.scenarioSpec.revision_id;
  zoneSimulation.sceneModified = false;
  return { zoneId: base.scenario.zoneId, baseScene: base, sceneEditor: editor, simulation: zoneSimulation };
}

function activateZone(index, reason = 'ZONE_SELECTED', resetCamera = true) {
  const session = zoneSessions[index];
  if (!session) return false;
  activeZoneIndex = index;
  if (reason === 'PARENT_SELECTED' || reason === 'USER_SELECTED') pinnedZoneId = session.zoneId;
  baseScene = session.baseScene; sceneEditor = session.sceneEditor;
  scene = sceneEditor.scene; simulation = session.simulation;
  zoneRotationElapsed = 0; inspectedEntity = null;
  if (resetCamera) {
    document.exitPointerLock?.();
    player.reset(scene.spawn); player.enabled = false; player.editorEnabled = false;
    cameraState = 'AUTOPILOT'; editorMode = false;
    cameraDirector.reset(scene, simulation, scene.spawn);
  }
  document.body.classList.remove('editor-active');
  document.querySelector('#zone-select').disabled = false;
  buildWorldLabels(); updateScenePatchUi(); updateCameraUi();
  const objectLabel = {warehouse: 'СКЛАД', airport: 'АЭРОПОРТ', hospital: 'КЛИНИКА'};
  const processLabel = {transport: 'Перевозка', delivery: 'Доставка', cleaning: 'Уборка', palletizing: 'Паллетизация'};
  document.querySelector('#hud-seed').textContent = scene.facilityPlan ? (objectLabel[scene.config.template] || 'ОБЪЕКТ') : scene.config.seed;
  document.querySelector('#hud-trips').previousElementSibling.textContent = scene.facilityPlan ? 'ЗАДАНИЙ' : 'РЕЙСЫ';
  document.querySelector('#hud-cargo').parentElement.classList.toggle('hidden', Boolean(scene.facilityPlan));
  document.querySelector('#hud-robots').textContent = simulation.robots.length;
  document.querySelector('#hud-mode').textContent = `${processLabel[scene.scenario.processType] || 'Процесс'} · ${scene.scenario.zoneName}`;
  document.querySelector('#zone-select').value = session.zoneId;
  document.querySelector('#zone-note').textContent = `Концептуальная сцена · ${scene.scenario.zoneName} · ${processLabel[scene.scenario.processType] || 'Процесс'}`;
  if (reason !== 'INITIAL') { announceScenePatch(); announceEditorState(); }
  return true;
}

function renderZoneSelector(entries) {
  const select = document.querySelector('#zone-select');
  select.replaceChildren(...entries.map(entry => {
    const option = document.createElement('option'); option.value = entry.zone.id;
    option.disabled = !entry.supported;
    option.textContent = entry.supported ? `${entry.zone.name} · ${entry.zone.process_type}` : `${entry.zone.name} · недоступно (${entry.reason})`;
    return option;
  }));
  document.querySelector('#zone-control').classList.toggle('hidden', entries.length < 2);
}

function applyEmbeddedScenario(candidate) {
  const metadataOnly = scene && simulation && visualFingerprint === candidate.fingerprint;
  const previousCameraState = cameraState;
  const wasEditing = editorMode;
  const previousZoneId = scene?.scenario?.zoneId;
  if (metadataOnly) {
    zoneSessions = zoneSessions.map(session => {
      const next = candidate.generated.zones.find(entry => entry.supported && entry.zone.id === session.zoneId);
      if (!next) return null;
      const patch = rebindScenePatch(session.sceneEditor.history.present, {
        revisionId: candidate.generated.revisionId, visualFingerprint: candidate.fingerprint, zoneId: session.zoneId
      });
      const nextBase = { ...session.baseScene, scenarioSpec: candidate.generated.spec, scenario: next.scene.scenario };
      const editor = new SceneEditorModel(nextBase, patch);
      session.simulation.revisionId = candidate.generated.revisionId;
      session.simulation.baseRevisionId = candidate.generated.revisionId;
      return { ...session, baseScene: nextBase, sceneEditor: editor };
    }).filter(Boolean);
  } else {
    zoneSessions = candidate.generated.zones.filter(entry => entry.supported).map(entry => createZoneSession(entry, candidate.fingerprint));
  }
  scenarioZoneEntries = candidate.generated.zones;
  if (pinnedZoneId && !zoneSessions.some(session => session.zoneId === pinnedZoneId)) pinnedZoneId = null;
  renderZoneSelector(scenarioZoneEntries);
  const selectedIndex = Math.max(0, zoneSessions.findIndex(session => session.zoneId === previousZoneId));
  const session = zoneSessions[selectedIndex];
  baseScene = session.baseScene; sceneEditor = session.sceneEditor; scene = sceneEditor.scene; simulation = session.simulation;
  if (metadataOnly) {
    cameraDirector.adoptRevision(scene, simulation);
  } else {
    player.reset(scene.spawn);
    cameraDirector.reset(scene, simulation, scene.spawn);
    document.exitPointerLock?.();
  }
  visualFingerprint = candidate.fingerprint;
  authoritativeSimulationReport = candidate.authoritativeReport;
  simulation.sceneModified = scenePatchHasChanges(sceneEditor.history.present);
  simulation.baseRevisionId = sceneEditor.history.present.base.revision_id || null;
  player.enabled = metadataOnly && !wasEditing && previousCameraState === 'MANUAL_FIRST_PERSON';
  player.editorEnabled = false;
  cameraState = player.enabled ? 'MANUAL_FIRST_PERSON' : 'AUTOPILOT';
  editorMode = false;
  document.body.classList.remove('editor-active');
  active = true;
  inspectedEntity = null;
  launcher.classList.add('hidden');
  document.body.classList.add('scenario-active');
  updateScenePatchUi();
  document.body.classList.toggle('manual-unavailable', !manualControlAllowed());
  hud.classList.remove('hidden');
  worldLabels.classList.remove('hidden');
  targetCard.classList.add('hidden');
  editorPanel.classList.add('hidden');
  document.querySelector('#editor-status').classList.add('hidden');
  if (metadataOnly && wasEditing) cameraDirector.resume(scene, simulation, player);
  activateZone(selectedIndex, 'INITIAL', false);
  return scene.scenario.revisionId;
}

function currentScenePatchState() {
  const patch = sceneEditor?.history.present;
  const modified = patch ? scenePatchHasChanges(patch) : false;
  return {
    baseRevisionId: patch?.base.revision_id,
    visualFingerprint: patch?.base.visual_fingerprint,
    zoneId: patch?.base.zone_id || scene?.scenario?.zoneId,
    status: modified ? 'MODIFIED' : 'CLEAN',
    summary: patch ? scenePatchSummary(patch) : { objects: 0, created: 0, deleted: 0, robots: 0 }
  };
}

function currentEditorState() {
  return { enabled: editorMode, sceneStatus: currentScenePatchState().status, simulationPaused: editorMode };
}

function updateScenePatchUi() {
  const modified = currentScenePatchState().status === 'MODIFIED';
  document.body.classList.toggle('scene-modified', modified);
  document.querySelector('#scene-modified-status').classList.toggle('hidden', !modified);
}

function announceEditorState() {
  embeddedBridge?.editorModeChanged(currentEditorState());
}

function announceScenePatch() {
  embeddedBridge?.scenePatchChanged(currentScenePatchState());
  embeddedBridge?.rendererReportChanged();
}

function showError(error) {
  errorBox.textContent = `Не удалось запустить РобКрафт: ${error.message}`;
  errorBox.classList.remove('hidden');
  console.error(error);
}

function populateForm(config) {
  Object.entries(config).forEach(([key, value]) => { if (fields[key]) fields[key].value = value; });
  document.querySelector('#occupancy-value').value = `${config.occupancy}%`;
  updateTemplateLabels();
}

function updateTemplateLabels() {
  const labels = {
    warehouse: ['Рядов стеллажей', 'Заполнение стеллажей'],
    airport: ['Выходов на посадку', 'Загрузка терминала'],
    hospital: ['Палат в крыле', 'Занятость палат']
  };
  const [units, occupancy] = labels[fields.template.value] || labels.warehouse;
  document.querySelector('#layout-units-label').textContent = units;
  document.querySelector('#occupancy-label').textContent = occupancy;
}

function readForm() {
  return normalizeConfig(Object.fromEntries(Object.entries(fields).map(([key, field]) => [key, field.value])));
}

function parseDescription() {
  descriptionSpec = parseWorldDescription(descriptionField.value, readForm());
  if (!descriptionSpec.source) {
    parseResult.textContent = 'Сначала опишите объект хотя бы одним предложением.';
    parseResult.classList.remove('hidden');
    return false;
  }
  populateForm(descriptionSpec.config);
  const confidence = Math.round(descriptionSpec.confidence * 100);
  const recognized = descriptionSpec.recognized.length ? descriptionSpec.recognized.join(' · ') : 'явные параметры не найдены';
  const assumptions = descriptionSpec.assumptions.length ? descriptionSpec.assumptions.join(' · ') : 'нет';
  parseResult.replaceChildren();
  const title = document.createElement('strong');
  title.textContent = 'Распознано';
  const score = document.createElement('span');
  score.className = 'confidence';
  score.textContent = `уверенность ${confidence}%`;
  const recognizedLine = document.createElement('div');
  recognizedLine.textContent = recognized;
  const assumptionLine = document.createElement('div');
  assumptionLine.className = 'assumption';
  assumptionLine.textContent = `Предположения: ${assumptions}`;
  parseResult.append(title, score, recognizedLine, assumptionLine);
  parseResult.classList.remove('hidden');
  return true;
}

function startWorld(config, capturePointer = true) {
  baseScene = generateWorld(config);
  sceneEditor = new SceneEditorModel(baseScene, createScenePatch(config));
  scene = sceneEditor.scene;
  simulation = createSimulation(scene);
  simulation.descriptionSpec = descriptionSpec;
  player.reset(scene.spawn);
  player.enabled = false;
  player.editorEnabled = false;
  cameraDirector.reset(scene, simulation, scene.spawn);
  cameraState = 'AUTOPILOT';
  editorMode = false;
  editorTool = 'select';
  buildKind = null;
  editorPanel.classList.add('hidden');
  document.querySelector('#editor-status').classList.add('hidden');
  document.querySelector('#editor-toggle').classList.remove('active');
  inspectedEntity = null;
  active = true;
  launcher.classList.add('hidden');
  hud.classList.remove('hidden');
  targetCard.classList.add('hidden');
  worldLabels.classList.remove('hidden');
  buildWorldLabels();
  analyticsEnabled = false;
  reportEnabled = false;
  lastEventId = 0;
  eventToastUntil = 0;
  renderer.setAnalytics(false);
  analyticsPanel.classList.add('hidden');
  reportPanel.classList.add('hidden');
  document.querySelector('#analytics-toggle').classList.remove('active');
  document.querySelector('#analytics-toggle').textContent = '◈ АНАЛИТИКА';
  document.querySelector('#report-toggle').classList.remove('active');
  history.replaceState(null, '', `${location.pathname}${configToQuery(config)}`);
  document.querySelector('#hud-seed').textContent = config.seed;
  document.querySelector('#hud-robots').textContent = config.robotCount;
  document.querySelector('#hud-mode').textContent = `${config.template.toUpperCase()} // LIVE`;
  cameraMode.textContent = '◉ РЕЖИМ: АВТОПОКАЗ';
  cameraMode.classList.add('flying');
  directorCaption.classList.remove('hidden');
  if (capturePointer) {
    audioEngine.start();
    audioEngine.setScene(config.template);
  }
}

async function enterManualCamera(reason = 'USER_REQUEST') {
  if (!active || editorMode || cameraState === 'MANUAL_FIRST_PERSON') return cameraSnapshot('NO_CHANGE');
  if (!manualControlAllowed()) return cameraSnapshot('MANUAL_CONTROL_DISABLED');
  try {
    await requestManualPointerLock();
  } catch {
    return announceCameraMode('POINTER_LOCK_UNAVAILABLE');
  }
  player.position = [...cameraDirector.position];
  player.yaw = cameraDirector.yaw;
  player.pitch = cameraDirector.pitch;
  player.flying = player.position[1] > 2.25;
  player.enabled = true;
  cameraDirector.suspend();
  cameraState = 'MANUAL_FIRST_PERSON';
  canvas.focus({ preventScroll: true });
  updateCameraUi();
  return announceCameraMode(reason);
}

function enterAutopilot(reason = 'USER_RETURN') {
  if (!active || editorMode || cameraState === 'AUTOPILOT') return cameraSnapshot('NO_CHANGE');
  cameraDirector.resume(scene, simulation, player);
  player.enabled = false;
  player.keys.clear();
  cameraState = 'AUTOPILOT';
  inspectedEntity = null;
  targetCard.classList.add('hidden');
  prompt.classList.add('hidden');
  updateCameraUi();
  if (embeddedMode && manualControlAllowed()) manualToggle.focus({ preventScroll: true });
  return announceCameraMode(reason);
}

function rebuildEditedScene(message = '') {
  scene = sceneEditor.scene;
  const previousDescription = simulation?.descriptionSpec;
  simulation = createSimulation(scene);
  simulation.descriptionSpec = previousDescription;
  simulation.sceneModified = scenePatchHasChanges(sceneEditor.history.present);
  simulation.baseRevisionId = sceneEditor.history.present.base.revision_id || null;
  if (embeddedMode && zoneSessions[activeZoneIndex]) {
    zoneSessions[activeZoneIndex].sceneEditor = sceneEditor;
    zoneSessions[activeZoneIndex].simulation = simulation;
  }
  buildWorldLabels();
  updateScenePatchUi();
  editorMessage.textContent = message || 'Изменение применено. Коллизии и маршруты проверяются заново.';
  updateEditorUi();
  announceScenePatch();
  announceEditorState();
}

function setEditorTool(tool, kind = null) {
  editorTool = tool;
  buildKind = kind;
  editorPreview = null;
  if (tool !== 'move') editorAxis = 'xz';
  document.querySelector('#editor-tool-label').textContent = tool === 'build' ? `СТРОИТЬ · ${BUILD_CATALOG.find(item => item.kind === kind)?.label || ''}` : tool === 'move' ? 'ПЕРЕМЕЩЕНИЕ' : 'ВЫБОР';
  document.querySelector('#editor-status-tool').textContent = document.querySelector('#editor-tool-label').textContent;
  document.querySelectorAll('#build-catalog button').forEach(button => button.classList.toggle('active', tool === 'build' && button.dataset.kind === kind));
}

function toggleEditor(force) {
  const enabled = force ?? !editorMode;
  if (enabled === editorMode || !active) return;
  if (enabled && !sceneEditor) throw new Error('Редактор не подготовлен для активной сцены');
  if (enabled && scene?.scenarioSpec?.presentation?.editor_available === false) throw new Error('Редактор недоступен для этого сценария');
  if (enabled && embeddedMode && cameraState !== 'MANUAL_FIRST_PERSON') throw new Error('Сначала перейдите в ручной режим осмотра');
  editorMode = enabled;
  player.editorEnabled = enabled;
  document.querySelector('#zone-select').disabled = enabled;
  document.body.classList.toggle('editor-active', enabled);
  document.querySelector('#editor-toggle').classList.toggle('active', enabled);
  editorPanel.classList.toggle('hidden', !enabled);
  document.querySelector('#editor-status').classList.toggle('hidden', !enabled);
  document.querySelector('#crosshair').classList.toggle('editor', enabled);
  document.querySelector('#hud-mode').textContent = `${scene.config.template.toUpperCase()} // ${enabled ? 'EDIT · PAUSED' : 'LIVE'}`;
  if (enabled) {
    editorPreviousCameraState = cameraState;
    if (cameraState === 'AUTOPILOT') {
      player.position = [...cameraDirector.position];
      player.yaw = cameraDirector.yaw;
      player.pitch = cameraDirector.pitch;
      cameraDirector.suspend();
      player.enabled = true;
    }
    editorPreviousFlight = player.flying;
    if (!player.flying) player.toggleFlight();
    document.exitPointerLock?.();
    reportPanel.classList.add('hidden'); reportEnabled = false;
    analyticsPanel.classList.add('hidden'); analyticsEnabled = false;
    renderer.setAnalytics(false);
    document.querySelector('#analytics-toggle').classList.remove('active');
    cameraMode.textContent = '▦ РЕЖИМ: РЕДАКТОР / СВОБОДНАЯ КАМЕРА';
    cameraMode.classList.add('flying');
    editorMessage.textContent = 'Симуляция на паузе. Кликните по объекту в центре экрана.';
    updateEditorUi();
  } else {
    if (!editorPreviousFlight && player.flying) player.toggleFlight();
    setEditorTool('select'); editorHovered = null;
    if (embeddedMode || editorPreviousCameraState === 'AUTOPILOT') {
      cameraState = 'MANUAL_FIRST_PERSON';
      enterAutopilot(embeddedMode ? 'EDITOR_CLOSED' : 'STATE_CHANGED');
    } else {
      cameraState = 'MANUAL_FIRST_PERSON';
      cameraMode.textContent = player.flying ? '◆ РЕЖИМ: СВОБОДНЫЙ ПОЛЁТ' : '● РЕЖИМ: ПЕШКОМ';
      cameraMode.classList.toggle('flying', player.flying);
    }
  }
  pauseNote.classList.toggle('hidden', !active || editorMode || cameraState === 'AUTOPILOT' || document.pointerLockElement === canvas);
  updateScenePatchUi();
  announceEditorState();
}

function updateEditorUi() {
  if (!sceneEditor) return;
  const entity = sceneEditor.entity();
  const robotId = sceneEditor.selectedId?.startsWith('robot:') ? Number(sceneEditor.selectedId.split(':')[1]) : null;
  const robot = robotId ? simulation.robots.find(item => item.id === robotId) : null;
  if (robot) {
    const options = compatibleRobotTypes(scene.config.template).map(type => `<option value="${type}" ${robot.robotType === type ? 'selected' : ''}>${type}</option>`).join('');
    editorSelection.innerHTML = `<strong>${robot.label} ${robot.id}</strong><small>Старт и зарядка редактируются в точке под прицелом.</small><select id="robot-model">${options}</select><div class="robot-edit"><button data-robot-point="start">Старт сюда</button><button data-robot-point="charge">Зарядка сюда</button><button data-robot-point="waypoint">Точка маршрута сюда</button></div>`;
  } else if (entity) editorSelection.innerHTML = `<strong>${entity.label}</strong><small>${entity.kind} · ${entity.position.map(value => value.toFixed(1)).join(' / ')} м<br>Размер ${entity.scale.map(value => value.toFixed(1)).join(' × ')} м · угол ${Math.round(entity.yaw * 180 / Math.PI)}°</small>`;
  else editorSelection.innerHTML = '<span>Наведите прицел и нажмите ЛКМ</span>';
  document.querySelector('#editor-status-grid').textContent = gridEnabled.checked ? `Сетка ${String(gridStep.value).replace('.', ',')} м` : 'Сетка выключена';
}

function updateEditorPreview() {
  if (!editorMode) return;
  editorHovered = pickEntity(player, sceneEditor.entities(), simulation.robots);
  if (editorTool !== 'build' && editorTool !== 'move') { editorPreview = null; return; }
  const point = rayGroundPoint(player);
  const step = Number(gridStep.value);
  const temporaryFree = player.keys.has('AltLeft') || player.keys.has('AltRight');
  if (gridEnabled.checked && !temporaryFree) { point[0] = Math.round(point[0] / step) * step; point[2] = Math.round(point[2] / step) * step; }
  if (editorTool === 'build') {
    const preset = BUILD_CATALOG.find(item => item.kind === buildKind);
    if (!preset) return;
    point[1] = preset.scale[1] / 2;
    const candidate = { position: point, scale: preset.scale, yaw: 0 };
    editorPreview = { ...candidate, valid: preset.solid === false || canPlaceSolid(candidate, scene.solids) };
  } else {
    const entity = sceneEditor.entity(); if (!entity || entity.kind === 'robot') { editorPreview = null; return; }
    point[1] = entity.position[1];
    const candidate = { position: point, scale: entity.scale, yaw: entity.yaw, editorId: entity.id };
    editorPreview = { ...candidate, valid: canPlaceSolid(candidate, scene.solids, entity.id) };
  }
}

function editorRenderState() {
  const selectedEntity = sceneEditor.entity();
  const selectedRobotId = sceneEditor.selectedId?.startsWith('robot:') ? Number(sceneEditor.selectedId.split(':')[1]) : null;
  const robot = selectedRobotId ? simulation.robots.find(item => item.id === selectedRobotId) : null;
  const selected = selectedEntity || (robot ? { id: `robot:${robot.id}`, kind: 'robot', position: robot.position, scale: [robot.radius * 2, 1.4, robot.radius * 2], robot } : null);
  return { hovered: editorHovered, selected, preview: editorPreview };
}

function showLauncher() {
  if (!active || embeddedMode) return;
  active = false;
  player.enabled = false;
  cameraDirector.suspend();
  document.exitPointerLock?.();
  launcher.classList.remove('hidden');
  hud.classList.add('hidden');
  worldLabels.classList.add('hidden');
}

function toggleAnalytics() {
  if (editorMode) return;
  analyticsEnabled = !analyticsEnabled;
  renderer.setAnalytics(analyticsEnabled);
  analyticsPanel.classList.toggle('hidden', !analyticsEnabled);
  const button = document.querySelector('#analytics-toggle');
  button.classList.toggle('active', analyticsEnabled);
  button.textContent = analyticsEnabled ? '◆ АНАЛИТИКА' : '◈ АНАЛИТИКА';
}

function reportInsight(report) {
  const geometry = report.geometry.status === 'MODIFIED' ? 'Геометрия изменена; расчётная ревизия и экономика не пересчитывались. ' : '';
  return `${geometry}Это локальная телеметрия визуального time-step loop. Capacity, productive utilization, SLA, очередь и экономика подтверждаются только связанным C23 SimulationReport.`;
}

function updateReport(report) {
  const percent = value => `${Math.max(0, Math.min(100, value)).toFixed(1)}%`;
  document.querySelector('#report-throughput').textContent = report.tasks.throughputPerHour.toFixed(1);
  document.querySelector('#report-cycle').textContent = Math.round(report.tasks.averageCycleSeconds);
  document.querySelector('#report-availability').textContent = percent(report.fleet.availabilityPercent);
  document.querySelector('#report-energy').textContent = report.energy.unitsPerCompletedTask.toFixed(1);
  document.querySelector('#report-utilization-label').textContent = percent(report.fleet.utilizationPercent);
  document.querySelector('#report-utilization-bar').style.width = percent(report.fleet.utilizationPercent);
  document.querySelector('#report-availability-label').textContent = percent(report.fleet.availabilityPercent);
  document.querySelector('#report-availability-bar').style.width = percent(report.fleet.availabilityPercent);
  document.querySelector('#report-completed').textContent = report.tasks.completed;
  document.querySelector('#report-queued').textContent = report.tasks.queued;
  document.querySelector('#report-downtime').textContent = `${Math.round(report.fleet.downtimeSeconds)} сек.`;
  document.querySelector('#report-insight').textContent = reportInsight(report);
}

function toggleReport() {
  if (editorMode) return;
  reportEnabled = !reportEnabled;
  reportPanel.classList.toggle('hidden', !reportEnabled);
  document.querySelector('#report-toggle').classList.toggle('active', reportEnabled);
  if (reportEnabled) {
    inspectedEntity = null;
    targetCard.classList.add('hidden');
    updateReport(getSimulationReport(simulation));
  }
}

function buildWorldLabels() {
  worldLabels.replaceChildren();
  labelElements = (scene.labels || []).map(label => {
    const element = document.createElement('div');
    element.className = `world-label ${label.kind || ''}`;
    element.textContent = label.text;
    worldLabels.appendChild(element);
    return { label, element };
  });
  rebuildInspectionTargets();
}

function updateWorldLabels(camera) {
  labelElements.forEach(({ label, element }) => {
    const dx = label.position[0] - camera.position[0];
    const dy = label.position[1] - camera.position[1];
    const dz = label.position[2] - camera.position[2];
    const distance = Math.hypot(dx, dy, dz);
    const projected = distance < 34 ? renderer.project(label.position) : null;
    element.style.display = projected ? 'block' : 'none';
    if (!projected) return;
    element.style.left = `${projected.x}px`;
    element.style.top = `${projected.y}px`;
    element.style.opacity = String(Math.max(.25, Math.min(1, 1.25 - distance / 38)));
    element.style.transform = `translate(-50%, -50%) scale(${Math.max(.72, Math.min(1, 12 / Math.max(distance, 1)))})`;
  });
}

function updateHud(delta) {
  hudTimer += delta;
  const targets = inspectionTargets();
  const target = cameraState === 'MANUAL_FIRST_PERSON' ? player.lookingAt(targets, 6) : null;
  const latestEvent = simulation.events.at(-1);
  if (latestEvent && latestEvent.id !== lastEventId) {
    lastEventId = latestEvent.id;
    eventToastUntil = performance.now() + 2800;
    document.querySelector('#event-toast').textContent = `СОБЫТИЕ · ${latestEvent.message}`;
  }
  document.querySelector('#event-toast').classList.toggle('hidden', performance.now() > eventToastUntil);
  directorCaption.textContent = cameraDirector.caption;
  directorCaption.classList.toggle('hidden', cameraState !== 'AUTOPILOT' || !cameraDirector.caption);
  prompt.classList.toggle('hidden', !target);
  if (inspectedEntity && player.lookingAt([inspectedEntity], 6.5) !== inspectedEntity) inspectedEntity = null;
  if (inspectedEntity && !reportEnabled) {
    targetCard.innerHTML = inspectionCard(inspectedEntity, latestEvent);
    targetCard.classList.remove('hidden');
  } else targetCard.classList.add('hidden');
  if (hudTimer < .2) return;
  hudTimer = 0;
  document.querySelector('#hud-trips').textContent = simulation.trips;
  document.querySelector('#hud-cargo').textContent = simulation.deliveredCargo.length;
  document.querySelector('#analytics-agents').textContent = `${simulation.robots.length} AMR · ${simulation.people.length} чел.`;
  const fleetMix = Object.entries(simulation.robots.reduce((mix, robot) => ({ ...mix, [robot.label]: (mix[robot.label] || 0) + 1 }), {}));
  document.querySelector('#analytics-fleet-mix').textContent = fleetMix.map(([label, count]) => `${label.replace('Автономный ', '').replace('Медицинский ', '')}: ${count}`).join(' · ');
  document.querySelector('#analytics-active-tasks').textContent = simulation.robots.filter(robot => robot.activeTask).length;
  document.querySelector('#analytics-traffic-limit').textContent = `${simulation.robots.filter(robot => robot.mode === 'working').length} / ${simulation.trafficCapacity}`;
  document.querySelector('#analytics-replans').textContent = simulation.dynamicReplans;
  document.querySelector('#analytics-task-queue').textContent = simulation.taskQueue.length;
  const averageWait = simulation.taskQueue.length
    ? simulation.taskQueue.reduce((sum, task) => sum + simulation.elapsed - task.createdAt, 0) / simulation.taskQueue.length
    : 0;
  document.querySelector('#analytics-task-wait').textContent = `${Math.round(averageWait)} сек.`;
  document.querySelector('#analytics-waiting').textContent = simulation.robots.filter(robot => robot.blockedByHuman || robot.blockedByRobot || robot.blockedBySolid || robot.reservationBlocked).length;
  document.querySelector('#analytics-physical-stops').textContent = simulation.physicalStops;
  document.querySelector('#analytics-reservations').textContent = simulation.activeReservations;
  document.querySelector('#analytics-traffic-conflicts').textContent = simulation.trafficConflicts;
  document.querySelector('#analytics-reservation-wait').textContent = `${Math.round(simulation.totalReservationWait)} сек.`;
  document.querySelector('#analytics-detours').textContent = simulation.detours;
  document.querySelector('#analytics-safety-stops').textContent = simulation.safetyStops;
  document.querySelector('#analytics-wait-loss').textContent = `${Math.round(simulation.totalWaitingTime)} сек.`;
  document.querySelector('#analytics-faults').textContent = `${simulation.faults} / ${simulation.faultsResolved}`;
  document.querySelector('#analytics-downtime').textContent = `${Math.round(simulation.totalDowntime)} сек.`;
  document.querySelector('#analytics-charging').textContent = simulation.robots.filter(robot => robot.mode === 'charging').length;
  document.querySelector('#analytics-delivered').textContent = simulation.deliveredCargo.length;
  const latestTask = simulation.completedTasks.at(-1);
  document.querySelector('#analytics-last-task').textContent = latestTask ? `${latestTask.id} · ${latestTask.title}` : 'пока нет';
  document.querySelector('#analytics-last-event').textContent = latestEvent ? latestEvent.message : 'событий нет';
  if (reportEnabled) updateReport(getSimulationReport(simulation));
  const minutes = simulation.facilityFrame
    ? Math.floor(((authoritativeSimulationReport.model_start?.seconds_from_midnight || 0) + simulation.elapsed) / 60) % (24 * 60)
    : (8 * 60 + Math.floor(simulation.elapsed * 2)) % (24 * 60);
  document.querySelector('#hud-time').textContent = `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

function robotCard(robot) {
  return `<h3>${robot.label} ${String(robot.id).padStart(2, '0')}</h3>
    <div class="status">● ${robot.state}</div><dl>
    <dt>Модель</dt><dd>${robot.modelCode}</dd><dt>Грузоподъёмность</dt><dd>до ${robot.maxLoadKg} кг</dd>
    <dt>Груз</dt><dd>${robot.carrying ? robot.cargoLabel : 'Нет'}</dd>
    <dt>Задание</dt><dd>${robot.activeTask ? `${robot.activeTask.id} · ${robot.activeTask.title}` : 'Ожидает назначения'}</dd>
    <dt>Скорость</dt><dd>${robot.currentSpeed.toFixed(1)} м/с</dd><dt>Батарея</dt><dd>${Math.round(robot.battery)}%${robot.mode === 'charging' ? ' · зарядка' : robot.needsCharge ? ' · требуется заряд' : ''}</dd>
    <dt>Рейсы</dt><dd>${robot.trips}</dd><dt>Процесс</dt><dd>${robot.process}</dd>
    <dt>Вклад в парк</dt><dd>1 из ${simulation.robots.length}</dd>
    <dt>Навигация</dt><dd>${robot.detourPath?.length ? `Лидарный объезд · ${robot.detourPath.length} точ.` : robot.avoidingHuman ? 'Локальный объезд' : robot.blockedByHuman ? 'Защитная остановка' : 'Динамический маршрут'}</dd>
    <dt>Перестроения</dt><dd>${robot.lidarReplans}</dd>
    <dt>Управление потоком</dt><dd>${robot.reservationBlocked ? 'Ожидает разрешение' : robot.reservedPosition ? 'Зона зарезервирована' : 'Свободный проезд'}</dd>
    <dt>Потери времени</dt><dd>${Math.round(robot.waitingTime)} сек.</dd>
    <dt>Простой</dt><dd>${Math.round(robot.downtime)} сек.</dd>
    <dt>Безопасность</dt><dd>${robot.blockedBySolid ? 'Стена или оборудование' : robot.blockedByHuman ? 'Человек на пути' : robot.blockedByRobot ? 'Робот на пути' : 'Маршрут свободен'}</dd></dl>`;
}

function personCard(person) {
  const status = person.pose === 'lying' ? 'ПАЦИЕНТ В ПАЛАТЕ' : person.pose === 'seated' ? 'РАБОТАЕТ ЗА ПУЛЬТОМ' : person.stationary ? 'НА БЕЗОПАСНОМ РАБОЧЕМ ПОСТУ' : person.blockedByRobot ? 'УСТУПАЕТ ДОРОГУ AMR' : person.blockedByPerson ? 'ПРОПУСКАЕТ ЧЕЛОВЕКА' : person.blockedByObstacle ? 'ПУТЬ ПЕРЕКРЫТ' : person.pause > 0 ? 'ВЫПОЛНЯЕТ ОПЕРАЦИЮ' : 'ДВИЖЕТСЯ ПО МАРШРУТУ';
  const behavior = person.pose === 'lying' ? 'Находится на кровати' : person.stationary ? 'Не входит в транспортные коридоры' : person.blockedByPerson ? 'Расходится во встречном потоке' : person.blockedByRobot ? 'Сохраняет дистанцию до AMR' : person.pause > 0 ? 'Операция в контрольной точке' : 'Следует по маршруту';
  return `<h3>${person.role} ${String(person.id).padStart(2, '0')}</h3>
    <div class="status">● ${status}</div><dl>
    <dt>Задача</dt><dd>${person.activity}</dd><dt>Скорость</dt><dd>${person.currentSpeed.toFixed(1)} м/с</dd>
    <dt>Поведение</dt><dd>${behavior}</dd>
    <dt>Размещение</dt><dd>${person.stationary ? 'Фиксированная безопасная зона' : `${person.waypoint + 1} / ${person.route.points.length - 1}`}</dd>
    <dt>Безопасность</dt><dd>AMR уступают дорогу</dd></dl>`;
}

function safeText(value) {
  return String(value ?? '—').replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[character]);
}

function rebuildInspectionTargets() {
  const stations = scene.staticObjects
    .filter(object => ['station', 'charger'].includes(object.type) && object.meta?.label)
    .map(object => ({
      entityType: 'station',
      position: object.position,
      label: object.meta.label,
      stationType: object.type
    }));
  const zone = scene.scenarioSpec?.zones?.find(item => (item.id || item.zone_id) === scene.scenario?.zoneId);
  const zoneTarget = zone ? [{
    entityType: 'zone',
    position: [0, 1.2, scene.layout?.crossAisleZ ?? 0],
    zone
  }] : [];
  inspectionEntities = [...stations, ...zoneTarget];
}

function inspectionTargets() {
  return [...simulation.robots, ...simulation.people, ...inspectionEntities];
}

function stationCard(station) {
  const role = station.stationType === 'charger'
    ? 'Стоянка и восстановление заряда AMR'
    : 'Приём груза, обмен и завершение транспортного рейса';
  return `<h3>${safeText(station.label)}</h3><div class="status">● СТАНЦИЯ</div><dl>
    <dt>Роль</dt><dd>${role}</dd>
    <dt>Маршруты</dt><dd>${scene.routes.length}</dd>
    <dt>Зона</dt><dd>${safeText(scene.scenario?.zoneName || 'Весь объект')}</dd></dl>`;
}

function zoneCard(target) {
  const zone = target.zone;
  const zoneId = zone.id || zone.zone_id;
  const fleet = scene.scenarioSpec.fleet.find(item => item.zone_id === zoneId);
  const task = scene.scenarioSpec.task_profiles?.find(item => item.zone_id === zoneId) || scene.scenarioSpec.tasks?.find(item => item.zone_id === zoneId);
  const demand = zone.demand_per_day ?? task?.demand?.value ?? '—';
  const batch = task?.units_per_trip ?? task?.batch?.units_per_cycle?.value ?? '—';
  const quantity = fleet?.quantity ?? fleet?.selected_fleet;
  const model = fleet?.equipment_model_id ?? fleet?.model_id;
  const finance = scene.scenarioSpec.schema_version === 'scenario-spec-v2'
    ? (scene.scenarioSpec.finance === null ? 'Не предоставлен (capacity-only)' : 'Immutable snapshot; см. расчёт')
    : `${scene.scenarioSpec.economics.fte_released} FTE`;
  return `<h3>${safeText(zone.name || zone.label)}</h3><div class="status">● КОНЦЕПТУАЛЬНАЯ ЗОНА</div><dl>
    <dt>Процесс</dt><dd>${safeText(zone.process_type || scene.scenario.processType)}</dd>
    <dt>Задание</dt><dd>${safeText(task?.task_id || task?.kind || 'не задано')}</dd>
    <dt>Точки</dt><dd>${safeText(scene.scenario.pickupId || 'не задана')} → ${safeText(scene.scenario.dropoffId || 'не задана')}</dd>
    <dt>Спрос</dt><dd>${demand} ${safeText(task?.demand?.unit || 'ед./день')}</dd>
    <dt>Рейс</dt><dd>${batch} ед.</dd>
    <dt>Парк</dt><dd>${fleet ? `${quantity} × ${safeText(model)}` : 'Не выбран'}</dd>
    <dt>Финансы</dt><dd>${finance}</dd>
    <dt>Смены / штат</dt><dd>см. расчёт</dd>
    <dt>Проход</dt><dd>${zone.aisle_width_m ?? '—'} м</dd>
    <dt>Ограничения</dt><dd>${safeText(scene.scenarioSpec.warnings[0] || scene.scenarioSpec.facility?.geometry_status || 'см. authoritative report')}</dd></dl>`;
}

function inspectionKey(entity) {
  if (!entity) return null;
  if (entity.entityType === 'zone') return `zone:${entity.zone.id || entity.zone.zone_id}`;
  if (entity.entityType === 'station') return `station:${entity.stationType}:${entity.label}`;
  return `${entity.entityType || 'robot'}:${entity.id}`;
}

function inspectionCard(entity, latestEvent) {
  if (entity.entityType === 'person') return personCard(entity);
  if (entity.entityType === 'station') return stationCard(entity);
  if (entity.entityType === 'zone') return zoneCard(entity);
  const eventLine = latestEvent ? `<dt>Событие</dt><dd>${safeText(latestEvent.message)}</dd>` : '';
  return robotCard(entity).replace('</dl>', `${eventLine}</dl>`);
}

function frame(now) {
  const delta = Math.min((now - lastFrame) / 1000, .05);
  lastFrame = now;
  if (scene && simulation) {
    if (active) {
      const facilityPlayback = scene.facilityPlan && authoritativeSimulationReport && embeddedPlayback && !simulation.sceneModified;
      if (cameraState === 'AUTOPILOT' && !editorMode && !facilityPlayback) cameraDirector.update(delta, scene, simulation);
      else player.update(delta, scene.solids, Boolean(scene.safePlaybackPlan));
      if (!editorMode) {
        if (facilityPlayback) {
          const visualFrame = applyFacilityPlayback(simulation, scene, authoritativeSimulationReport, embeddedPlayback.elapsed_seconds);
          if (cameraState === 'AUTOPILOT') updateFacilityCamera(cameraDirector, visualFrame, now / 1000);
        }
        else if (!embeddedMode || !embeddedPlayback) updateSimulation(simulation, delta, scene.solids);
        else if (scene.facilityPlan && simulation.sceneModified) {
          simulation.speedMultiplier = embeddedPlayback.speed;
          if (embeddedPlayback.status === 'RUNNING') updateSimulation(simulation, delta, scene.solids);
        }
        else {
          const target = embeddedPlayback.elapsed_seconds;
          if (simulation.elapsed > target + 1 || embeddedPlayback.reset) {
            const replacement = createSimulation(scene);
            replacement.baseRevisionId = simulation.baseRevisionId;
            replacement.sceneModified = simulation.sceneModified;
            zoneSessions[activeZoneIndex].simulation = replacement;
            simulation = replacement;
            embeddedPlayback.reset = false;
          }
          simulation.speedMultiplier = 1;
          // Unsupported legacy physical scenes have a bounded frame budget; the versioned saved playback seeks directly.
          for (let steps = 0; simulation.elapsed + .05 < target && steps < 8; steps += 1)
            updateSimulation(simulation, Math.min(.05, target - simulation.elapsed), scene.solids);
          simulation.speedMultiplier = embeddedPlayback.speed;
          if (embeddedPlayback.status === 'RUNNING') updateSimulation(simulation, delta, scene.solids);
        }
      }
      if (embeddedMode && cameraState === 'AUTOPILOT' && !editorMode && !pinnedZoneId && zoneSessions.length > 1) {
        zoneRotationElapsed += delta;
        if (zoneRotationElapsed >= 24) activateZone((activeZoneIndex + 1) % zoneSessions.length, 'AUTOPILOT_ROTATION');
      }
      const camera = cameraState === 'AUTOPILOT' && !editorMode ? cameraDirector : player;
      audioEngine.update(delta, camera, simulation, scene);
      updateHud(delta);
      updateEditorPreview();
    }
    const camera = active && cameraState === 'AUTOPILOT' && !editorMode ? cameraDirector : player;
    renderer.render(scene, simulation, camera, editorMode ? editorRenderState() : null);
    if (active) updateWorldLabels(camera);
  }
  requestAnimationFrame(frame);
}

try {
  renderer = new Renderer(canvas);
  player = new Player(canvas);
  cameraDirector = new CameraDirector();
  if (embeddedMode) {
    document.body.classList.add('embedded');
    launcher.classList.add('hidden');
    embeddedBridge = installParentBridge(window, {
      prepare: prepareEmbeddedScenario,
      apply: applyEmbeddedScenario,
      selectZone: zoneId => {
        const index = zoneSessions.findIndex(session => session.zoneId === zoneId);
          if (index < 0) return false;
          if (index === activeZoneIndex) { pinnedZoneId = zoneId; announceScenePatch(); return true; }
          return activateZone(index, 'PARENT_SELECTED');
      },
      setCameraMode: mode => mode === 'MANUAL_FIRST_PERSON'
        ? enterManualCamera('PARENT_REQUEST')
        : enterAutopilot('PARENT_REQUEST'),
      getCameraState: () => cameraSnapshot(),
      setEditorMode: enabled => {
        toggleEditor(enabled);
        return currentEditorState();
      },
      getEditorState: () => currentEditorState(),
      getScenePatchState: () => currentScenePatchState(),
      setPlayback: playback => {
        const reset = (embeddedPlayback !== null && embeddedPlayback.restart !== playback.restart)
          || (playback.status === 'STOPPED' && embeddedPlayback?.status !== 'STOPPED');
        embeddedPlayback = { ...playback, reset };
        document.body.classList.add('playback-synchronized');
        if (scene.safePlaybackPlan && authoritativeSimulationReport && !simulation.sceneModified) {
          applyFacilityPlayback(simulation, scene, authoritativeSimulationReport, playback.elapsed_seconds);
          embeddedBridge?.rendererReportChanged();
        }
      },
      getRendererReport: () => buildRendererReport(simulation, authoritativeSimulationReport)
    });
  } else {
    const initial = configFromUrl(location.search);
    populateForm(initial);
    scene = generateWorld(initial);
    simulation = createSimulation(scene);
    player.reset(scene.spawn);
    cameraDirector.reset(scene, simulation, scene.spawn);
    if (new URLSearchParams(location.search).get('autostart') === '1') startWorld(initial, false);
  }
  requestAnimationFrame(frame);
} catch (error) {
  showError(error);
  if (embeddedMode) {
    window.parent.postMessage(childMessage('ROBCRAFT_ERROR', null, null, {
      code: 'WEBGL_UNAVAILABLE', message: error.message
    }), location.origin);
  }
}

form.addEventListener('submit', event => {
  event.preventDefault();
  if (!renderer) return;
  const description = descriptionField.value.trim();
  if (description && descriptionSpec?.source !== description) parseDescription();
  startWorld(readForm());
});

fields.occupancy.addEventListener('input', () => { document.querySelector('#occupancy-value').value = `${fields.occupancy.value}%`; });
fields.template.addEventListener('change', updateTemplateLabels);
document.querySelector('#random-seed').addEventListener('click', () => {
  fields.seed.value = `WH-${Math.floor(100000 + Math.random() * 900000)}`;
});
document.querySelector('#parse-description').addEventListener('click', parseDescription);
descriptionField.addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.code === 'Enter') parseDescription();
});

document.addEventListener('pointerlockchange', () => {
  if (active && !editorMode && cameraState === 'MANUAL_FIRST_PERSON' && document.pointerLockElement !== canvas) enterAutopilot('POINTER_LOCK_RELEASED');
  pauseNote.classList.toggle('hidden', !active || editorMode || cameraState === 'AUTOPILOT' || document.pointerLockElement === canvas);
});

document.addEventListener('keydown', event => {
  if (active && !embeddedMode && event.code === 'KeyB' && !event.repeat) {
    toggleEditor();
    return;
  }
  if (active && !editorMode && event.code === 'KeyG') {
    showLauncher();
    return;
  }
  if (active && !editorMode && cameraState === 'MANUAL_FIRST_PERSON' && event.code === 'KeyF' && !event.repeat) {
    const groundBlocked = player.flying && scene.solids.some(solid =>
      circleIntersectsSolid(player.position[0], player.position[2], player.radius, solid)
    );
    if (groundBlocked) {
      cameraMode.textContent = '◆ СВОБОДНЫЙ ПОЛЁТ · НАЙДИТЕ СВОБОДНЫЙ ПОЛ';
      announceCameraMode('GROUND_POSITION_BLOCKED');
      return;
    }
    const flying = player.toggleFlight();
    cameraMode.textContent = flying ? '◆ РЕЖИМ: СВОБОДНЫЙ ПОЛЁТ' : '● РЕЖИМ: ПЕШКОМ';
    cameraMode.classList.toggle('flying', flying);
    announceCameraMode('FLIGHT_MODE_CHANGED');
    return;
  }
  if (active && event.code === 'Tab' && !event.repeat) {
    event.preventDefault();
    toggleAnalytics();
    return;
  }
  if (active && event.code === 'Space') event.preventDefault();
  if (active && editorMode) {
    if ((event.ctrlKey || event.metaKey) && event.code === 'KeyZ') { event.preventDefault(); sceneEditor.undo(); rebuildEditedScene('Последнее действие отменено.'); return; }
    if ((event.ctrlKey || event.metaKey) && (event.code === 'KeyY' || (event.shiftKey && event.code === 'KeyZ'))) { event.preventDefault(); sceneEditor.redo(); rebuildEditedScene('Отменённое действие возвращено.'); return; }
    if ((event.ctrlKey || event.metaKey) && event.code === 'KeyD') { event.preventDefault(); const id = sceneEditor.duplicate(); if (id) rebuildEditedScene('Создана копия объекта.'); else editorMessage.textContent = 'Для копии недостаточно свободного места.'; return; }
    if (event.code === 'Delete') { if (sceneEditor.delete()) rebuildEditedScene('Объект удалён.'); return; }
    if (event.code === 'KeyG') { if (sceneEditor.entity()) setEditorTool('move'); return; }
    if (editorTool === 'move' && ['KeyX', 'KeyY', 'KeyZ'].includes(event.code)) { editorAxis = event.code.at(-1).toLowerCase(); document.querySelector('#editor-status-tool').textContent = `ПЕРЕМЕЩЕНИЕ · ОСЬ ${editorAxis.toUpperCase()}`; return; }
    if (editorTool === 'move' && ['ArrowUp', 'ArrowDown'].includes(event.code)) {
      event.preventDefault(); const axis = editorAxis === 'y' ? 1 : editorAxis === 'z' ? 2 : 0; const delta = [0, 0, 0]; delta[axis] = (event.code === 'ArrowUp' ? 1 : -1) * Number(gridStep.value);
      if (sceneEditor.move(sceneEditor.selectedId, delta, { grid: gridEnabled.checked, gridStep: Number(gridStep.value) })) rebuildEditedScene(`Объект перемещён по оси ${editorAxis.toUpperCase()}.`); else editorMessage.textContent = 'Перемещение конфликтует с другим объектом.';
      return;
    }
    if (event.code === 'KeyR') { if (sceneEditor.rotate(sceneEditor.selectedId)) rebuildEditedScene('Объект повёрнут на 90°.'); return; }
    if (event.code === 'BracketLeft' || event.code === 'BracketRight') {
      const axis = event.shiftKey ? 2 : event.altKey ? 1 : 0;
      const amount = (event.code === 'BracketRight' ? 1 : -1) * Number(gridStep.value);
      if (sceneEditor.resize(sceneEditor.selectedId, amount, axis, { grid: gridEnabled.checked, gridStep: Number(gridStep.value) })) rebuildEditedScene('Размер объекта изменён.');
      return;
    }
    if (event.code === 'Escape') { setEditorTool('select'); editorMessage.textContent = 'Операция отменена.'; return; }
  }
  if (!active || editorMode || cameraState !== 'MANUAL_FIRST_PERSON' || event.code !== 'KeyE' || event.repeat) return;
  const target = player.lookingAt(inspectionTargets(), 6);
  inspectedEntity = inspectionKey(inspectedEntity) === inspectionKey(target) ? null : target;
});

manualToggle.addEventListener('click', () => enterManualCamera('USER_REQUEST'));

document.querySelector('#editor-toggle').addEventListener('click', () => toggleEditor());
document.querySelector('#zone-select').addEventListener('change', event => {
  const index = zoneSessions.findIndex(session => session.zoneId === event.target.value);
  if (index >= 0) activateZone(index, 'USER_SELECTED');
});

document.querySelector('#build-catalog').replaceChildren(...BUILD_CATALOG.map(item => {
  const button = document.createElement('button'); button.type = 'button'; button.dataset.kind = item.kind; button.textContent = item.label;
  button.addEventListener('click', () => setEditorTool('build', item.kind)); return button;
}));

canvas.addEventListener('click', () => {
  if (!editorMode) {
    if (!embeddedMode) enterManualCamera();
    return;
  }
  if (editorTool === 'build' && editorPreview) {
    if (!editorPreview.valid) { editorMessage.textContent = 'Красная область пересекает твёрдый объект.'; return; }
    const id = sceneEditor.create(buildKind, editorPreview.position, { yaw: editorPreview.yaw });
    if (id) { rebuildEditedScene('Новый объект размещён.'); setEditorTool('select'); }
  } else if (editorTool === 'move' && editorPreview) {
    if (!editorPreview.valid) { editorMessage.textContent = 'Нельзя подтвердить пересекающееся размещение.'; return; }
    if (sceneEditor.update(sceneEditor.selectedId, { position: editorPreview.position })) { rebuildEditedScene('Объект перемещён, коллизии обновлены.'); setEditorTool('select'); }
  } else if (editorHovered) {
    sceneEditor.select(editorHovered.id); updateEditorUi();
  } else { sceneEditor.select(null); updateEditorUi(); }
  canvas.requestPointerLock?.();
});

canvas.addEventListener('contextmenu', event => { if (!editorMode) return; event.preventDefault(); setEditorTool('select'); editorMessage.textContent = 'Операция отменена.'; });

editorPanel.addEventListener('click', event => {
  const action = event.target.closest('[data-editor-action]')?.dataset.editorAction;
  if (!action) return;
  if (action === 'close') toggleEditor(false);
  if (action === 'move' && sceneEditor.entity()) setEditorTool('move');
  if (action === 'rotate' && sceneEditor.rotate(sceneEditor.selectedId)) rebuildEditedScene('Объект повёрнут на 90°.');
  if (action === 'delete' && sceneEditor.delete()) rebuildEditedScene('Объект удалён.');
  if (action === 'duplicate') { const id = sceneEditor.duplicate(); if (id) rebuildEditedScene('Создана копия объекта.'); else editorMessage.textContent = 'Для копии недостаточно свободного места.'; }
  if (action === 'undo') { sceneEditor.undo(); rebuildEditedScene('Последнее действие отменено.'); }
  if (action === 'redo') { sceneEditor.redo(); rebuildEditedScene('Отменённое действие возвращено.'); }
  if (action === 'reset' && confirm('Сбросить все пользовательские изменения и вернуться к исходной сгенерированной сцене?')) { sceneEditor.reset(); rebuildEditedScene('Сцена сброшена к исходному seed.'); }
  if (action === 'export') {
    const blob = new Blob([exportSceneDocument(sceneEditor.history.present)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `robcraft-scene-${scene.config.seed}.json`; link.click(); URL.revokeObjectURL(url);
  }
  if (action === 'import') document.querySelector('#scene-import').click();
});

editorPanel.addEventListener('change', event => {
  if (event.target.id === 'robot-model') {
    const routeId = Number(sceneEditor.selectedId.split(':')[1]);
    if (sceneEditor.editRobot(routeId, { robotType: event.target.value })) rebuildEditedScene('Совместимая модель робота заменена.');
  }
  if (event.target === gridEnabled || event.target === gridStep) updateEditorUi();
});

editorPanel.addEventListener('click', event => {
  const pointType = event.target.dataset.robotPoint; if (!pointType) return;
  const routeId = Number(sceneEditor.selectedId.split(':')[1]); const route = scene.routes.find(item => item.id === routeId); const point = rayGroundPoint(player).filter((_, index) => index !== 1);
  if (pointType === 'start') sceneEditor.editRobot(routeId, { startPosition: point });
  if (pointType === 'charge') sceneEditor.editRobot(routeId, { chargePosition: point });
  if (pointType === 'waypoint') { const points = structuredClone(route.points); points.splice(Math.max(1, points.length - 1), 0, point); sceneEditor.editRobot(routeId, { points }); }
  rebuildEditedScene('Маршрут робота обновлён.');
});

document.querySelector('#scene-import').addEventListener('change', async event => {
  const file = event.target.files?.[0]; if (!file) return;
  try {
    const imported = importSceneDocument(await file.text());
    if (embeddedMode) {
      assertScenePatchCompatible(imported.patch, {
        revisionId: scene.scenarioSpec.revision_id,
        visualFingerprint,
        zoneId: scene.scenario.zoneId
      });
      sceneEditor = new SceneEditorModel(baseScene, imported.patch);
      zoneSessions[activeZoneIndex].sceneEditor = sceneEditor;
      sceneEditor.refresh();
      rebuildEditedScene('ScenePatch импортирован для активной расчётной ревизии.');
    } else {
      baseScene = generateWorld(imported.baseConfig);
      sceneEditor = new SceneEditorModel(baseScene, imported.patch);
      sceneEditor.refresh();
      rebuildEditedScene('ScenePatch импортирован; база восстановлена отдельно по seed.');
    }
  } catch (error) { editorMessage.textContent = `Импорт отклонён: ${error.message}`; }
  event.target.value = '';
});

document.querySelectorAll('[data-speed]').forEach(button => button.addEventListener('click', () => {
  simulation.speedMultiplier = Number(button.dataset.speed);
  document.querySelectorAll('[data-speed]').forEach(item => {
    const selected = item === button;
    item.classList.toggle('active', selected);
    item.setAttribute('aria-pressed', String(selected));
  });
}));

document.querySelector('#sound-toggle').addEventListener('click', event => {
  const enabled = audioEngine.toggle();
  event.currentTarget.textContent = enabled ? '🔊 ЗВУК' : '🔇 БЕЗ ЗВУКА';
  event.currentTarget.classList.toggle('muted', !enabled);
});

document.querySelector('#analytics-toggle').addEventListener('click', toggleAnalytics);
document.querySelector('#report-toggle').addEventListener('click', toggleReport);

document.querySelector('#report-export').addEventListener('click', () => {
  const payload = { engine: 'robcraft', version: 1, scenario: scene.config, descriptionSpec: simulation.descriptionSpec, report: getSimulationReport(simulation) };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `robcraft-${scene.config.template}-${scene.config.seed}.json`.replace(/[^a-zA-Z0-9а-яА-ЯёЁ._-]/g, '-');
  link.click();
  URL.revokeObjectURL(url);
});

document.querySelectorAll('[data-event]').forEach(button => button.addEventListener('click', () => {
  if (!active || !simulation || editorMode) return;
  const triggered = triggerSimulationEvent(simulation, button.dataset.event);
  if (triggered) audioEngine.scenarioEvent(button.dataset.event);
}));
