import { Renderer } from './core/renderer.js';
import { Player } from './player.js';
import { CameraDirector } from './camera-director.js';
import { generateWorld, generateWorldsFromScenarioSpec } from './world/generator.js';
import { configFromUrl, configToQuery, normalizeConfig } from './world/config.js';
import { buildRendererReport, createSimulation, getSimulationReport, preserveOperationalRobotPositions, triggerSimulationEvent, updateSimulation } from './simulation.js';
import { AudioEngine } from './audio.js';
import { BUILD_CATALOG, pickEntity, rayGroundPoint, SceneEditorModel } from './editor/editor.js?v=recovery-v2-r2-final';
import { EditorInventory } from './editor/inventory.js';
import { drawMap, mapEntityAt, mapPoint, mapScale, mapZoomAt, validZonePolygon } from './editor/map-view.js';
import { RobCraftProjectStore, SceneSaveConflict } from './editor/project-store.js';
import { canPlaceSolid, circleIntersectsSolid } from './editor/collisions.js';
import { ASSIGNABLE_ROBOTS, operationalAnchors, operationalRolesFor, planOperationalPath } from './editor/operational.js';
import { parseRobcraftDxf } from './editor/dxf-import.js';
import { ECONOMICS_FIELDS, calculateLiveEconomics } from './editor/live-economics.js';
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
const editorPanel = document.querySelector('#editor-panel');
const editorSelection = document.querySelector('#editor-selection');
const editorMessage = document.querySelector('#editor-message');
const gridEnabled = document.querySelector('#grid-enabled');
const gridStep = document.querySelector('#grid-step');
const craftMap = document.querySelector('#craft-map');
const touchControls = document.querySelector('#touch-controls');
const touchMode = window.matchMedia('(pointer: coarse)').matches || navigator.maxTouchPoints > 0;
document.body.classList.toggle('touch-mode', touchMode);
const mapControls = document.querySelector('#map-controls');
const hotbar = document.querySelector('#craft-hotbar');
const toolbar = document.querySelector('#craft-toolbar');
const viewToggle = document.querySelector('#view-toggle');
const inventoryToggle = document.querySelector('#inventory-toggle');
const emptyHand = document.querySelector('#empty-hand');
const fields = Object.fromEntries(['template', 'seed', 'width', 'depth', 'rackRows', 'robotCount', 'occupancy'].map(id => [id, document.querySelector(`#${id}`)]));
const embeddedMode = new URLSearchParams(location.search).get('embedded') === '1' && window.parent !== window;
const requestedProjectId = new URLSearchParams(location.search).get('project_id');
let projectId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(requestedProjectId || '') ? requestedProjectId : null;
const csrfToken = () => {
  const cookie = document.cookie.split('; ').find(item => item.startsWith('robodovod_csrf='));
  return cookie ? decodeURIComponent(cookie.slice('robodovod_csrf='.length)) : '';
};
let projectStore = projectId ? new RobCraftProjectStore(projectId, (...args) => fetch(...args), csrfToken) : null;
const projectControls = document.querySelector('#project-scene-controls');
const projectStatus = document.querySelector('#project-scene-status');
const projectSave = document.querySelector('#project-scene-save');
const projectSaveAs = document.querySelector('#project-scene-save-as');
const projectRename = document.querySelector('#project-scene-rename');
const projectNameForm = document.querySelector('#project-scene-name-form');
const projectNameInput = document.querySelector('#project-scene-name');
let projectNameAction = null;
const projectVersionList = document.querySelector('#project-scene-version-list');
let projectReady = false;
let projectDirty = false;

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
let startChoice = 'empty';
let inventory = new EditorInventory();
let editorView = '3d';
let buildYaw = 0;
let mapPreview = null;
let touchLookPointer = null;
let touchJoystickPointer = null;
let mapView = { zoom: 1, panX: 0, panZ: 0 };
let mapPan = null;
let mapDragEnded = false;
const mapTouches = new Map();
let mapGesture = null;
let mapSuppressClickUntil = 0;
let zoneDraft = null;
let wallDraft = null;
let roomDraft = null;
let operationalSelection = { chargeId: '', workId: '', dropoffId: '' };
let operationalPath = null;
let routePreviewRequested = false;
let operationalPlayback = false;
let operationalFollow = false;
let operationalSpeed = 1;
let lastOperationalStatusAt = 0;
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
    cameraDirector.facilityPinnedOrdinal = null;
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

function startWorld(config, capturePointer = true, imported = null, forceNew = false) {
  zoneDraft = null;
  wallDraft = null;
  roomDraft = null;
  operationalSelection = { chargeId: '', workId: '', dropoffId: '' };
  operationalPath = null;
  routePreviewRequested = false;
  mapPan = null;
  mapTouches.clear(); mapGesture = null;
  mapView = { zoom: 1, panX: 0, panZ: 0 };
  updateMapZoom();
  baseScene = createEditorBaseScene(config, document.querySelector('#scene-start').value);
  const stored = imported || (forceNew ? null : loadLocalScene(baseScene.config));
  sceneEditor = new SceneEditorModel(baseScene, stored?.patch || createScenePatch(baseScene.config));
  inventory = new EditorInventory(stored?.inventory?.slots, stored?.inventory?.active);
  editorView = stored?.view || document.querySelector('#initial-view').value;
  scene = sceneEditor.scene;
  simulation = createSimulation(scene);
  simulation.descriptionSpec = descriptionSpec;
  player.reset(scene.spawn);
  player.enabled = !embeddedMode;
  player.editorEnabled = false;
  cameraDirector.reset(scene, simulation, scene.spawn);
  cameraState = embeddedMode ? 'AUTOPILOT' : 'MANUAL_FIRST_PERSON';
  editorMode = false;
  editorTool = 'select';
  buildKind = null;
  renderHotbar();
  renderZoneList();
  renderRoomList();
  updateEditorView();
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
  history.replaceState(null, '', `${location.pathname}${configToQuery(config)}&editorStart=${baseScene.config.editorStart}${projectId ? `&project_id=${encodeURIComponent(projectId)}` : ''}`);
  document.querySelector('#hud-seed').textContent = config.seed;
  document.querySelector('#hud-robots').textContent = config.robotCount;
  document.querySelector('#hud-mode').textContent = `${config.template.toUpperCase()} // LIVE`;
  updateCameraUi();
  directorCaption.classList.toggle('hidden', !embeddedMode);
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
  operationalPlayback = false;
  const previousSimulation = simulation;
  scene = sceneEditor.scene;
  if (routePreviewRequested) operationalPath = planOperationalPath(scene, operationalSelection);
  const previousDescription = simulation?.descriptionSpec;
  simulation = createSimulation(scene);
  preserveOperationalRobotPositions(previousSimulation, simulation, scene);
  simulation.speedMultiplier = operationalSpeed;
  syncOperationalPlaybackUi();
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
  saveLocalScene();
}

function createEditorBaseScene(config, start = 'empty') {
  const base = generateWorld(config);
  base.config = { ...base.config, editorStart: start };
  if (start === 'empty' || start === 'cad') {
    base.staticObjects = base.staticObjects.filter(object => object.type === 'ground' || object.type === 'floor');
    base.solids = [];
    base.interactables = [];
    base.routes = [];
    base.people = [];
    base.labels = [];
    base.spawn = [0, 1.72, 0];
  }
  return base;
}
function localSceneKey(config = scene?.config) { return `robcraft:scene:v1:${config.template}:${config.seed}:${config.editorStart || 'ready'}`; }
function loadLocalScene(config) {
  if (embeddedMode) return null;
  try {
    const data = JSON.parse(localStorage.getItem(localSceneKey(config)) || 'null');
    if (!data) return null;
    const imported = importSceneDocument(data.document);
    if (JSON.stringify(imported.baseConfig) !== JSON.stringify(config)) return null;
    return { patch: imported.patch, inventory: imported.inventory, view: ['2d', '3d'].includes(data.view) ? data.view : null };
  } catch { return null; }
}
function latestLocalScene(template) {
  if (embeddedMode) return null;
  try {
    const prefix = `robcraft:scene:v1:${template}:`;
    const saved = [];
    for (let index = 0; index < localStorage.length; index += 1) {
      const key = localStorage.key(index);
      if (!key?.startsWith(prefix)) continue;
      const data = JSON.parse(localStorage.getItem(key) || 'null');
      const imported = importSceneDocument(data.document);
      saved.push({ ...imported, view: data.view, savedAt: Number(data.savedAt) || 0 });
    }
    return saved.sort((a, b) => b.savedAt - a.savedAt)[0] || null;
  } catch { return null; }
}
function saveLocalScene() {
  if (embeddedMode || !sceneEditor) return;
  try { localStorage.setItem(localSceneKey(), JSON.stringify({ document: JSON.parse(exportSceneDocument(sceneEditor.history.present, inventory.toJSON())), view: editorView, savedAt: Date.now() })); }
  catch { editorMessage.textContent = 'Не удалось сохранить сцену в браузере. Экспортируйте JSON.'; }
  if (projectStore && projectReady) {
    projectDirty = true;
    projectStatus.textContent = `Несохранённые изменения · версия проекта ${projectStore.revision}`;
  }
}
function renderHotbar() {
  hotbar.replaceChildren(...inventory.slots.map((kind, index) => {
    const button = document.createElement('button');
    button.type = 'button'; button.classList.toggle('active', inventory.active === index);
    button.setAttribute('aria-label', `Слот ${index + 1}: ${BUILD_CATALOG.find(item => item.kind === kind)?.label || 'пусто'}`);
    button.innerHTML = `<small>${index + 1}</small>${BUILD_CATALOG.find(item => item.kind === kind)?.label || '□'}`;
    button.addEventListener('click', () => { inventory.select(index); syncHeldItem(); });
    return button;
  }));
  emptyHand.classList.toggle('active', inventory.active === null);
}
function syncHeldItem() {
  if (inventory.held) setEditorTool('build', inventory.held);
  else setEditorTool('select');
  renderHotbar(); saveLocalScene();
}
function canPlaceEditorObject(candidate, preset) {
  const inside = Math.abs(candidate.position[0]) + preset.scale[0] / 2 <= scene.config.width / 2
    && Math.abs(candidate.position[2]) + preset.scale[2] / 2 <= scene.config.depth / 2;
  const robotCollision = simulation.robots.some(robot => circleIntersectsSolid(robot.position[0], robot.position[2], robot.radius, candidate));
  return inside && !robotCollision && (preset.solid === false || canPlaceSolid(candidate, scene.solids));
}
function updateEditorView() {
  craftMap.classList.toggle('hidden', !editorMode || editorView !== '2d');
  mapControls.classList.toggle('hidden', !editorMode || editorView !== '2d');
  touchControls.classList.toggle('hidden', !touchMode || !editorMode || editorView !== '3d');
  if (player) {
    player.touchEnabled = touchMode && editorMode && editorView === '3d';
    if (!player.touchEnabled) player.setTouchMove(0, 0);
  }
  if (!editorMode || editorView !== '3d') touchLookPointer = touchJoystickPointer = null;
  if (touchMode) {
    const panelOpen = editorMode && document.body.classList.contains('touch-panel-open');
    editorPanel.classList.toggle('hidden', !panelOpen);
    if (panelOpen) player?.setTouchMove(0, 0);
  }
  viewToggle.textContent = editorView === '2d' ? '3D · от первого лица' : '2D · вид сверху';
  if (editorView === '2d') document.exitPointerLock?.();
}

function setEditorTool(tool, kind = null) {
  if (tool !== 'wall') {
    wallDraft = null;
    document.querySelector('#map-wall-cancel').classList.add('hidden');
  }
  if (tool !== 'room') {
    roomDraft = null;
    document.querySelector('#map-room-actions').classList.add('hidden');
  }
  document.querySelector('#map-room-door-cancel').classList.toggle('hidden', tool !== 'room-door');
  editorTool = tool;
  buildKind = kind;
  editorPreview = null;
  if (tool !== 'move') editorAxis = 'xz';
  document.querySelector('#editor-tool-label').textContent = tool === 'build' ? `СТРОИТЬ · ${BUILD_CATALOG.find(item => item.kind === kind)?.label || ''}` : tool === 'move' ? 'ПЕРЕМЕЩЕНИЕ' : tool === 'wall' ? (wallDraft?.door ? 'СТЕНА С ПРОЁМОМ' : 'СТЕНА ПО ТОЧКАМ') : tool === 'room' ? 'КОНТУР КОМНАТЫ' : tool === 'room-door' ? 'ПРОЁМ КОМНАТЫ' : zoneDraft ? 'КОНТУР ЗОНЫ' : 'ВЫБОР';
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
  operationalPlayback = false;
  if (enabled) operationalSpeed = simulation.speedMultiplier;
  syncOperationalPlaybackUi();
  player.editorEnabled = enabled;
  document.querySelector('#zone-select').disabled = enabled;
  document.body.classList.toggle('editor-active', enabled);
  document.querySelector('#editor-toggle').classList.toggle('active', enabled);
  editorPanel.classList.add('hidden');
  document.body.classList.remove('touch-panel-open');
  toolbar.classList.toggle('hidden', !enabled);
  document.querySelector('#craft-economics-summary').classList.toggle('hidden', !enabled);
  hotbar.classList.toggle('hidden', !enabled);
  updateEditorView();
  document.querySelector('#editor-status').classList.toggle('hidden', !enabled);
  document.querySelector('#crosshair').classList.toggle('editor', enabled);
  document.querySelector('#hud-mode').textContent = `${scene.config.template.toUpperCase()} // ${enabled ? 'EDIT · PAUSED' : 'LIVE'}`;
  if (enabled) {
    editorPreviousCameraState = cameraState;
    if (cameraState === 'AUTOPILOT') {
      player.position = scene.config.editorStart === 'empty' ? [...scene.spawn] : [...cameraDirector.position];
      player.yaw = scene.config.editorStart === 'empty' ? 0 : cameraDirector.yaw;
      player.pitch = scene.config.editorStart === 'empty' ? -.4 : cameraDirector.pitch;
      cameraDirector.suspend();
      player.enabled = true;
    }
    editorPreviousFlight = player.flying;
    if (!player.flying && scene.config.editorStart !== 'empty') player.toggleFlight();
    document.exitPointerLock?.();
    reportPanel.classList.add('hidden'); reportEnabled = false;
    analyticsPanel.classList.add('hidden'); analyticsEnabled = false;
    renderer.setAnalytics(false);
    document.querySelector('#analytics-toggle').classList.remove('active');
    cameraMode.textContent = '▦ РЕЖИМ: РЕДАКТОР / СВОБОДНАЯ КАМЕРА';
    cameraMode.classList.add('flying');
    editorMessage.textContent = 'Симуляция на паузе. Кликните по объекту в центре экрана.';
    syncHeldItem();
    updateEditorUi();
  } else {
    if (!editorPreviousFlight && player.flying) player.toggleFlight();
    setEditorTool('select'); editorHovered = null;
    if (embeddedMode) {
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
  renderZoneList();
  renderRoomList();
  const entity = sceneEditor.entity();
  const robotId = sceneEditor.selectedId?.startsWith('robot:') ? Number(sceneEditor.selectedId.split(':')[1]) : null;
  const robot = robotId ? simulation.robots.find(item => item.id === robotId) : null;
  if (robot) {
    const options = compatibleRobotTypes(scene.config.template).map(type => `<option value="${type}" ${robot.robotType === type ? 'selected' : ''}>${type}</option>`).join('');
    editorSelection.innerHTML = `<strong>${robot.label} ${robot.id}</strong><small>Старт и зарядка редактируются в точке под прицелом.</small><select id="robot-model">${options}</select><div class="robot-edit"><button data-robot-point="start">Старт сюда</button><button data-robot-point="charge">Зарядка сюда</button><button data-robot-point="waypoint">Точка маршрута сюда</button></div>`;
  } else if (entity) {
    editorSelection.innerHTML = `<strong>${entity.label}</strong><small>${entity.kind} · ${entity.position.map(value => value.toFixed(1)).join(' / ')} м<br>Размер ${entity.scale.map(value => value.toFixed(1)).join(' × ')} м · угол ${Math.round(entity.yaw * 180 / Math.PI)}°</small>`;
    const roles = operationalRolesFor(entity.parts[0]);
    if (entity.id.startsWith('user:') && roles.length) {
      const select = document.createElement('select'); select.id = 'entity-operational-role'; select.setAttribute('aria-label', 'Операционная роль объекта');
      for (const [value, label] of [['', 'Без операционной роли'], ...roles.map(role => [role, role])]) {
        const option = document.createElement('option'); option.value = value; option.textContent = label;
        select.append(option);
      }
      select.value = entity.parts[0].operational_role || '';
      editorSelection.append(select);
    }
  }
  else editorSelection.innerHTML = '<span>Наведите прицел и нажмите ЛКМ</span>';
  renderOperationalControls();
  renderLiveEconomics();
  document.querySelector('#editor-status-grid').textContent = gridEnabled.checked ? `Сетка ${String(gridStep.value).replace('.', ',')} м` : 'Сетка выключена';
}

function updateEditorPreview() {
  if (!editorMode) return;
  if (editorView === '2d') return;
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
    const candidate = { position: point, scale: preset.scale, yaw: buildYaw };
    editorPreview = { ...candidate, valid: canPlaceEditorObject(candidate, preset) };
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
      } else if (operationalPlayback && scene.editorAssignments?.some(item => item.ok)) {
        updateSimulation(simulation, delta, scene.solids);
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
    const followedRobot = editorMode && operationalFollow ? simulation.robots.find(robot => robot.route.assignmentRobotId === document.querySelector('#operational-robot').value)
      || simulation.robots.find(robot => robot.route.assignmentRobotId) : null;
    if (followedRobot && editorView === '2d') {
      mapView.panX = -followedRobot.position[0]; mapView.panZ = -followedRobot.position[2];
    }
    const followCamera = followedRobot && editorView === '3d' ? {
      position: [followedRobot.position[0] - Math.sin(followedRobot.yaw) * 5, 3.2, followedRobot.position[2] - Math.cos(followedRobot.yaw) * 5],
      yaw: followedRobot.yaw, pitch: -.32
    } : null;
    const camera = followCamera || (active && cameraState === 'AUTOPILOT' && !editorMode ? cameraDirector : player);
    renderer.render(scene, simulation, camera, editorMode ? editorRenderState() : null);
    if (editorMode && editorView === '2d') {
      const rect = craftMap.getBoundingClientRect();
      if (craftMap.width !== Math.round(rect.width) || craftMap.height !== Math.round(rect.height)) { craftMap.width = Math.round(rect.width); craftMap.height = Math.round(rect.height); }
      const assignedRoute = scene.routes.find(route => route.assignmentRobotId);
      drawMap(craftMap.getContext('2d'), scene, sceneEditor.entities(), mapPreview, mapView, zoneDraft || [], wallDraft, roomDraft || [], operationalAnchors(scene), operationalPath?.ok ? operationalPath.points : assignedRoute?.points || [], simulation.robots.filter(robot => robot.route.assignmentRobotId));
    }
    if (editorMode && now - lastOperationalStatusAt > 150) {
      lastOperationalStatusAt = now;
      const live = document.querySelector('#operational-live-status');
      const robot = followedRobot || simulation.robots.find(item => item.route.assignmentRobotId);
      live.textContent = `${operationalPlayback ? 'В движении' : 'Пауза'} · ${simulation.elapsed.toFixed(1).replace('.', ',')} с${robot ? ` · ${robot.position[0].toFixed(1).replace('.', ',')} / ${robot.position[2].toFixed(1).replace('.', ',')} м` : ''}`;
    }
    if (active) updateWorldLabels(camera);
  }
  requestAnimationFrame(frame);
}

try {
  renderer = new Renderer(canvas);
  canvas.addEventListener('webglcontextlost', event => {
    event.preventDefault();
    showError(new Error('Контекст WebGL потерян. Откройте 2D-представление.'));
    if (embeddedMode) window.parent.postMessage(childMessage('ROBCRAFT_ERROR', null, null, {
      code: 'WEBGL_UNAVAILABLE', message: 'Контекст WebGL потерян; переключаемся на 2D.'
    }), location.origin);
  });
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
      selectRobot: ordinal => {
        if (ordinal !== null && (!scene.safePlaybackPlan || ordinal >= scene.safePlaybackPlan.robots.length)) return false;
        cameraDirector.facilityPinnedOrdinal = ordinal;
        cameraDirector.facilityFollowUntil = -1;
        return true;
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
    const initialStart = new URLSearchParams(location.search).get('editorStart');
    document.querySelector('#scene-start').value = ['ready', 'cad'].includes(initialStart) ? initialStart : 'empty';
    startChoice = document.querySelector('#scene-start').value;
    syncStartChoices();
    document.querySelector('#cad-options').classList.toggle('hidden', initialStart !== 'cad');
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

function syncStartChoices() {
  const status = document.querySelector('#saved-scene-status');
  document.querySelector('#scene-start').value = startChoice === 'mine' ? 'empty' : startChoice;
  document.querySelector('#cad-options').classList.toggle('hidden', startChoice !== 'cad');
  document.querySelectorAll('[data-start]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.start === startChoice)));
  const saved = startChoice === 'mine' ? latestLocalScene(fields.template.value) : null;
  status.classList.toggle('hidden', startChoice !== 'mine');
  if (startChoice === 'mine') status.textContent = saved ? `Найдена сохранённая сцена: ${saved.baseConfig.seed}` : 'Сохранённой сцены для этого объекта пока нет.';
}
document.querySelectorAll('[data-start]').forEach(button => button.addEventListener('click', () => {
  startChoice = button.dataset.start;
  syncStartChoices();
}));
document.querySelector('#scene-start').addEventListener('change', event => {
  startChoice = event.target.value;
  syncStartChoices();
});
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!renderer) return;
  if (startChoice === 'mine') {
    const saved = latestLocalScene(fields.template.value);
    if (!saved) { syncStartChoices(); return; }
    populateForm(saved.baseConfig);
    document.querySelector('#scene-start').value = saved.baseConfig.editorStart || 'ready';
    startWorld(saved.baseConfig, true, saved);
    toggleEditor(true);
    return;
  }
  let cad = null;
  if (document.querySelector('#scene-start').value === 'cad') {
    const file = document.querySelector('#cad-file').files[0];
    const status = document.querySelector('#cad-status');
    if (!file) {
      const saved = loadLocalScene(createEditorBaseScene(readForm(), 'cad').config);
      if (saved) { startWorld(readForm()); toggleEditor(true); return; }
    }
    if (!file || !/\.dxf$/i.test(file.name) || file.size > 5_000_000) { status.textContent = 'Выберите текстовый DXF до 5 МБ. DWG экспортируйте в DXF.'; return; }
    try {
      cad = parseRobcraftDxf(await file.text(), {
        wallLayers: document.querySelector('#cad-wall-layers').value.split(',').map(item => item.trim()).filter(Boolean),
        obstacleLayers: document.querySelector('#cad-obstacle-layers').value.split(',').map(item => item.trim()).filter(Boolean),
        wallHeightM: Number(document.querySelector('#cad-wall-height').value),
        unitMeters: Number(document.querySelector('#cad-unit-meters').value) || null
      });
      fields.width.value = String(Math.ceil(cad.width)); fields.depth.value = String(Math.ceil(cad.depth));
      status.textContent = `${cad.objects.length} сегментов · пропущено сущностей: ${cad.unsupported + cad.malformed} · другие слои: ${cad.skippedLayers.join(', ') || 'нет'}`;
    } catch (error) { status.textContent = `DXF не импортирован: ${error.message}`; return; }
  }
  startWorld(readForm(), true, null, true);
  if (cad) {
    try { const count = sceneEditor.importDxfObjects(cad.objects, { file_name: document.querySelector('#cad-file').files[0].name,
      unit_meters: cad.unitMeters, wall_height_m: cad.wallHeightM, wall_layers: cad.wallLayers,
      obstacle_layers: cad.obstacleLayers, unsupported_entities: cad.unsupported, malformed_entities: cad.malformed });
      rebuildEditedScene(`DXF: ${count} редактируемых сегментов; нераспознанных сущностей ${cad.unsupported + cad.malformed}.`); }
    catch (error) { editorMessage.textContent = `DXF отклонён: ${error.message}`; }
  }
  toggleEditor(true);
});
document.querySelectorAll('[data-quality]').forEach(button => button.addEventListener('click', () => {
  renderer?.setQuality(button.dataset.quality);
  document.querySelectorAll('[data-quality]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
}));

fields.occupancy.addEventListener('input', () => { document.querySelector('#occupancy-value').value = `${fields.occupancy.value}%`; });
fields.template.addEventListener('change', () => { updateTemplateLabels(); syncStartChoices(); });
document.querySelector('#random-seed').addEventListener('click', () => {
  fields.seed.value = `WH-${Math.floor(100000 + Math.random() * 900000)}`;
});

document.addEventListener('pointerlockchange', () => {
  if (embeddedMode && active && !editorMode && cameraState === 'MANUAL_FIRST_PERSON' && document.pointerLockElement !== canvas) enterAutopilot('POINTER_LOCK_RELEASED');
  pauseNote.classList.toggle('hidden', !active || editorMode || cameraState === 'AUTOPILOT' || document.pointerLockElement === canvas);
});

document.addEventListener('keydown', event => {
  if (event.target.closest?.('input, textarea, select, [contenteditable]')) return;
  if (active && !embeddedMode && event.code === 'KeyB' && !event.repeat) {
    toggleEditor();
    return;
  }
  if (active && !embeddedMode && event.code === 'KeyI' && !event.repeat) {
    if (!editorMode) toggleEditor(true);
    editorPanel.classList.remove('hidden');
    if (touchMode) document.body.classList.add('touch-panel-open');
    document.querySelector('#catalog-section').scrollIntoView({ block: 'nearest' });
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
    if (event.code === 'KeyI' && !event.repeat) { event.preventDefault(); document.querySelector('.editor-section').classList.toggle('hidden'); return; }
    if (event.code === 'Digit0' || event.code === 'Numpad0') { event.preventDefault(); inventory.select(null); syncHeldItem(); return; }
    const digit = /^Digit([1-9])$/.exec(event.code) || /^Numpad([1-9])$/.exec(event.code);
    if (digit) { event.preventDefault(); inventory.select(Number(digit[1]) - 1); syncHeldItem(); return; }
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
    if (event.code === 'KeyR') { if (inventory.held) { buildYaw += Math.PI / 2; editorMessage.textContent = `Поворот предмета: ${Math.round(buildYaw * 180 / Math.PI) % 360}°`; } else if (sceneEditor.rotate(sceneEditor.selectedId)) rebuildEditedScene('Объект повёрнут на 90°.'); return; }
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

const catalogButtons = BUILD_CATALOG.map(item => {
  const button = document.createElement('button'); button.type = 'button'; button.dataset.kind = item.kind; button.textContent = `${item.label} · ∞`;
  button.addEventListener('click', () => {
    if (inventory.assign(item.kind)) { syncHeldItem(); editorMessage.textContent = `${item.label} добавлен в слот ${inventory.active + 1}. Количество ∞.`; }
    else editorMessage.textContent = 'Все слоты заняты. Выберите слот для замены и повторите действие.';
  }); return button;
});
const catalogItems = document.createElement('div'); catalogItems.className = 'catalog-items'; catalogItems.replaceChildren(...catalogButtons);
const catalogTabs = document.createElement('div'); catalogTabs.className = 'catalog-tabs';
const categories = ['Конструкции', 'Мебель/Оборудование', 'Роботы', 'Зоны/Маршруты', 'Декор'];
function showCatalogCategory(category) {
  catalogItems.querySelectorAll('[data-kind]').forEach(button => {
    button.classList.toggle('hidden', BUILD_CATALOG.find(item => item.kind === button.dataset.kind)?.category !== category);
  });
  catalogTabs.querySelectorAll('button').forEach(button => button.classList.toggle('active', button.textContent === category));
}
catalogTabs.replaceChildren(...categories.map(category => {
  const button = document.createElement('button'); button.type = 'button'; button.textContent = category;
  button.addEventListener('click', () => showCatalogCategory(category)); return button;
}));
document.querySelector('#build-catalog').replaceChildren(catalogTabs, catalogItems);
showCatalogCategory('Конструкции');

function apply3DEditAction({ breakOnly = false, selectOnly = false, shiftKey = false } = {}) {
  if (!editorMode || editorView !== '3d') return;
  updateEditorPreview();
  if (breakOnly) {
    if (editorHovered?.id.startsWith('user:') && sceneEditor.delete(editorHovered.id)) rebuildEditedScene('Объект удалён пустой рукой.');
    else editorMessage.textContent = 'Наведите прицел на установленный объект для удаления.';
    return;
  }
  if (selectOnly) { sceneEditor.select(editorHovered?.id || null); updateEditorUi(); return; }
  if (editorTool === 'build' && editorPreview) {
    if (!editorPreview.valid) { editorMessage.textContent = 'Красная область пересекает твёрдый объект.'; return; }
    const id = sceneEditor.create(buildKind, editorPreview.position, { yaw: editorPreview.yaw });
    if (id) rebuildEditedScene('Новый объект размещён. Предмет остаётся в руке: ∞.');
  } else if (editorTool === 'move' && editorPreview) {
    if (!editorPreview.valid) { editorMessage.textContent = 'Нельзя подтвердить пересекающееся размещение.'; return; }
    if (sceneEditor.update(sceneEditor.selectedId, { position: editorPreview.position })) { rebuildEditedScene('Объект перемещён, коллизии обновлены.'); setEditorTool('select'); }
  } else if (editorHovered) {
    if (inventory.active === null && !shiftKey && editorHovered.id.startsWith('user:')) {
      if (sceneEditor.delete(editorHovered.id)) rebuildEditedScene('Объект удалён пустой рукой.');
    } else { sceneEditor.select(editorHovered.id); updateEditorUi(); }
  } else { sceneEditor.select(null); updateEditorUi(); }
}

canvas.addEventListener('click', event => {
  if (!editorMode) {
    if (!embeddedMode && !touchMode) enterManualCamera();
    return;
  }
  if (touchMode) return;
  apply3DEditAction({ shiftKey: event.shiftKey });
  if (editorView === '3d' && !touchMode) canvas.requestPointerLock?.();
});

canvas.addEventListener('pointerdown', event => {
  if (!touchMode || !editorMode || editorView !== '3d' || event.pointerType !== 'touch') return;
  event.preventDefault();
  touchLookPointer = { id: event.pointerId, x: event.clientX, y: event.clientY };
  try { canvas.setPointerCapture?.(event.pointerId); } catch { /* Synthetic pointer events have no active capture. */ }
});
canvas.addEventListener('pointermove', event => {
  if (!touchLookPointer || touchLookPointer.id !== event.pointerId) return;
  player.lookTouch(event.clientX - touchLookPointer.x, event.clientY - touchLookPointer.y);
  touchLookPointer.x = event.clientX;
  touchLookPointer.y = event.clientY;
});
const endTouchLook = event => { if (touchLookPointer?.id === event.pointerId) touchLookPointer = null; };
canvas.addEventListener('pointerup', endTouchLook);
canvas.addEventListener('pointercancel', endTouchLook);

const joystick = document.querySelector('#touch-joystick');
const joystickKnob = document.querySelector('#touch-joystick-knob');
function updateJoystick(event) {
  const rect = joystick.getBoundingClientRect();
  const max = rect.width * .36;
  const x = Math.max(-1, Math.min(1, (event.clientX - rect.left - rect.width / 2) / max));
  const y = Math.max(-1, Math.min(1, (event.clientY - rect.top - rect.height / 2) / max));
  const length = Math.max(1, Math.hypot(x, y));
  const side = x / length, forward = -y / length;
  player.setTouchMove(forward, side);
  joystickKnob.style.left = `${50 + side * 30}%`;
  joystickKnob.style.top = `${50 - forward * 30}%`;
}
joystick.addEventListener('pointerdown', event => {
  if (!player.touchEnabled) return;
  event.preventDefault();
  touchJoystickPointer = event.pointerId;
  updateJoystick(event);
  try { joystick.setPointerCapture?.(event.pointerId); } catch { /* Synthetic pointer events have no active capture. */ }
});
joystick.addEventListener('pointermove', event => { if (touchJoystickPointer === event.pointerId) updateJoystick(event); });
const endJoystick = event => {
  if (touchJoystickPointer !== event.pointerId) return;
  touchJoystickPointer = null;
  player.setTouchMove(0, 0);
  joystickKnob.style.left = joystickKnob.style.top = '50%';
};
joystick.addEventListener('pointerup', endJoystick);
joystick.addEventListener('pointercancel', endJoystick);
document.querySelector('#touch-place').addEventListener('click', () => apply3DEditAction({ selectOnly: !inventory.held }));
document.querySelector('#touch-break').addEventListener('click', () => { inventory.select(null); syncHeldItem(); apply3DEditAction({ breakOnly: true }); });
document.querySelector('#touch-rotate').addEventListener('click', () => {
  if (inventory.held) { buildYaw += Math.PI / 2; editorMessage.textContent = `Поворот предмета: ${Math.round(buildYaw * 180 / Math.PI) % 360}°`; }
  else if (sceneEditor.rotate(sceneEditor.selectedId)) rebuildEditedScene('Объект повёрнут на 90°.');
});

canvas.addEventListener('contextmenu', event => { if (!editorMode) return; event.preventDefault(); setEditorTool('select'); editorMessage.textContent = 'Операция отменена.'; });

hotbar.addEventListener('wheel', event => { event.preventDefault(); inventory.cycle(Math.sign(event.deltaY)); syncHeldItem(); }, { passive: false });
inventoryToggle.addEventListener('click', () => {
  const open = editorPanel.classList.contains('hidden');
  editorPanel.classList.toggle('hidden', !open);
  if (touchMode) document.body.classList.toggle('touch-panel-open', open);
});
emptyHand.addEventListener('click', () => { inventory.select(null); syncHeldItem(); });
viewToggle.addEventListener('click', () => {
  editorView = editorView === '2d' ? '3d' : '2d';
  if (editorView === '3d' && (wallDraft || roomDraft || editorTool === 'room-door')) setEditorTool('select');
  if (touchMode) document.body.classList.toggle('touch-panel-open', editorView === '2d');
  mapPreview = null; updateEditorView(); saveLocalScene();
});

function renderZoneList() {
  const list = document.querySelector('#map-zone-list');
  if (!sceneEditor) { list.replaceChildren(); return; }
  list.replaceChildren(...(sceneEditor.scene.editorZones || []).map(zone => {
    const row = document.createElement('div');
    const label = document.createElement('span'); label.textContent = `${zone.name} · ${zone.points.length} точек`;
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Удалить';
    remove.setAttribute('aria-label', `Удалить зону ${zone.name}`);
    remove.addEventListener('click', () => { if (sceneEditor.deleteZone(zone.id)) rebuildEditedScene(`Зона «${zone.name}» удалена. Отмена доступна через Ctrl+Z.`); });
    const role = document.createElement('button'); role.type = 'button'; role.textContent = zone.operational_role === 'WORK' ? 'Снять WORK' : 'Назначить WORK';
    role.setAttribute('aria-label', `${zone.operational_role === 'WORK' ? 'Снять роль WORK с зоны' : 'Назначить роль WORK зоне'} ${zone.name}`);
    role.addEventListener('click', () => { if (sceneEditor.setZoneOperationalRole(zone.id, zone.operational_role === 'WORK' ? null : 'WORK')) rebuildEditedScene(`Операционная роль зоны «${zone.name}» изменена.`); });
    row.append(label, role, remove); return row;
  }));
}

function renderOperationalControls() {
  if (!scene) return;
  const anchors = operationalAnchors(scene);
  const robotSelect = document.querySelector('#operational-robot');
  const selectedRobot = robotSelect.value;
  robotSelect.replaceChildren(new Option('Выберите робота', ''), ...scene.staticObjects.filter(item => ASSIGNABLE_ROBOTS[item.kind]).map(item => new Option(item.meta?.label || item.kind, item.id)));
  robotSelect.value = selectedRobot;
  for (const [id, role, optional] of [['operational-charge', 'CHARGE', false], ['operational-work', 'WORK', false], ['operational-dropoff', 'DROPOFF', true]]) {
    const select = document.querySelector(`#${id}`);
    const current = operationalSelection[id === 'operational-charge' ? 'chargeId' : id === 'operational-work' ? 'workId' : 'dropoffId'];
    const options = [new Option(optional ? 'Без DROPOFF' : `Выберите ${role}`, ''),
      ...anchors.filter(anchor => anchor.role === role).map(anchor => new Option(`${role} · ${anchor.label}`, anchor.id))];
    select.replaceChildren(...options);
    select.value = current;
    if (select.selectedIndex < 0) select.value = '';
  }
  const status = document.querySelector('#operational-status');
  if (routePreviewRequested) status.textContent = operationalPath?.ok
    ? `Путь найден: ${operationalPath.distance.toFixed(1).replace('.', ',')} м.`
    : `Путь не построен: ${operationalPath?.reason || 'укажите CHARGE и WORK'}`;
  const list = document.querySelector('#operational-assignment-list');
  list.replaceChildren(...(scene.editorAssignments || []).map(assignment => {
    const row = document.createElement('div');
    const label = document.createElement('span');
    label.textContent = `${scene.staticObjects.find(item => item.id === assignment.robot_id)?.meta?.label || 'Робот'} · ${assignment.ok ? `маршрут ${assignment.distance.toFixed(1).replace('.', ',')} м` : `ОСТАНОВЛЕН: ${assignment.reason}`}`;
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Снять';
    remove.addEventListener('click', () => { if (sceneEditor.removeRobotAssignment(assignment.robot_id)) rebuildEditedScene('Назначение снято.'); });
    row.append(label, remove); return row;
  }));
}

const economicsLabels = {
  staff_count: 'Штат роли, чел.', monthly_employer_cost: 'Затраты работодателя, ₽/чел./мес.',
  workdays_year: 'Рабочих дней/год', hours_shift: 'Часов/смену', human_tasks_shift: 'Операций человека/смену',
  task_share: 'Доля времени на задачу, 0…1', workload_day: 'Спрос, операций/день',
  realization_share: 'Реализуемая доля часов, 0…1', robot_price: 'Цена робота, ₽/шт.',
  integration_cost: 'Интеграция, ₽', annual_service: 'Сервис, ₽/год', annual_energy: 'Энергия, ₽/год',
  discount_rate: 'Ставка дисконтирования, 0…1', operation_seconds: 'Операции на цикл, с'
};
function renderLiveEconomics() {
  if (!sceneEditor) return;
  const holder = document.querySelector('#economics-fields');
  if (!holder.children.length) holder.replaceChildren(...ECONOMICS_FIELDS.map(key => {
    const label = document.createElement('label'); label.textContent = economicsLabels[key];
    const input = document.createElement('input'); input.type = 'number'; input.step = 'any'; input.min = '0';
    input.dataset.economicsField = key; label.append(input); return label;
  }));
  const inputs = sceneEditor.history.present.economics || {};
  for (const input of holder.querySelectorAll('input')) if (document.activeElement !== input) input.value = inputs[input.dataset.economicsField] ?? '';
  const result = calculateLiveEconomics(scene, inputs);
  const format = value => value === null ? 'нужны вводные' : Math.round(value).toLocaleString('ru-RU');
  const money = value => value === null ? 'нужны вводные' : `${format(value)} ₽`;
  document.querySelector('#craft-economics-summary').textContent =
    `Роботы: ${result.active_robots}/${result.placed_robots} работают · CAPEX: ${money(result.capex)} · NPV 5 лет: ${money(result.npv_5)}`;
  document.querySelector('#economics-result').textContent = `Статус: ${result.status} · роботы ${result.placed_robots}, работают ${result.active_robots}, заблокированы ${result.blocked_robots}. ` +
    `Базовый ФОТ ${format(result.baseline_payroll_year)} ₽/год; CAPEX ${format(result.capex)} ₽; OPEX ${format(result.opex_year)} ₽/год. ` +
    `Потенциально ${format(result.potential_released_hours)} ч/год, реализуемо ${format(result.realized_released_hours)} ч/год, ${result.released_fte === null ? 'нужны вводные' : result.released_fte.toFixed(2)} FTE. ` +
    `Экономия ФОТ ${format(result.annual_labor_saving)} ₽/год; окупаемость ${result.payback_years === null ? 'не определена' : result.payback_years.toFixed(1) + ' г.'}; ` +
    `ROI 5/10 лет ${format(result.roi_5)}% / ${format(result.roi_10)}%; NPV 5/10 лет ${format(result.npv_5)} ₽ / ${format(result.npv_10)} ₽. ` +
    (result.missing.length ? `Не хватает: ${result.missing.map(key => economicsLabels[key] || key).join(', ')}.` : 'Расчёт сценарный, требуется подтверждение вводных.');
}
document.querySelector('#economics-apply').addEventListener('click', () => {
  const inputs = {};
  for (const input of document.querySelectorAll('[data-economics-field]')) {
    if (input.value.trim()) inputs[input.dataset.economicsField] = Number(input.value);
  }
  try {
    sceneEditor.setEconomicsInputs(inputs);
    scene = sceneEditor.scene;
    renderLiveEconomics(); updateScenePatchUi(); announceScenePatch(); saveLocalScene();
  } catch (error) { document.querySelector('#economics-result').textContent = `Вводные не сохранены: ${error.message}`; }
});

function syncOperationalPlaybackUi() {
  const toggle = document.querySelector('#operational-toggle');
  toggle.textContent = operationalPlayback ? 'Ⅱ Пауза' : '▶ Старт';
  toggle.setAttribute('aria-pressed', String(operationalPlayback));
  const quickPlay = document.querySelector('#craft-play');
  quickPlay.textContent = operationalPlayback ? 'Ⅱ Пауза' : '▶ Запустить робота';
  quickPlay.setAttribute('aria-pressed', String(operationalPlayback));
  document.querySelector('#operational-follow').setAttribute('aria-pressed', String(operationalFollow));
  document.querySelectorAll('[data-operational-speed]').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.operationalSpeed) === operationalSpeed)));
}

document.querySelector('#craft-play').addEventListener('click', () => {
  if (operationalPlayback) {
    operationalPlayback = false;
    syncOperationalPlaybackUi();
    return;
  }
  if (!scene.editorAssignments?.some(item => item.ok)) {
    const robot = scene.staticObjects.find(item => ASSIGNABLE_ROBOTS[item.kind]);
    const anchors = operationalAnchors(scene);
    const charge = anchors.find(item => item.role === 'CHARGE');
    const work = anchors.find(item => item.role === 'WORK');
    const dropoff = anchors.find(item => item.role === 'DROPOFF');
    if (!robot || !charge || !work) {
      editorPanel.classList.remove('hidden');
      editorMessage.textContent = 'Поставьте робота, зарядную станцию и рабочую точку. Затем нажмите «Запустить робота».';
      return;
    }
    operationalSelection = { chargeId: charge.id, workId: work.id, dropoffId: dropoff?.id || '' };
    routePreviewRequested = true;
    operationalPath = planOperationalPath(scene, operationalSelection);
    const result = sceneEditor.assignRobot(robot.id, operationalSelection,
      Number(document.querySelector('#operational-payload').value),
      Number(document.querySelector('#operational-speed').value));
    if (!result.ok) {
      editorPanel.classList.remove('hidden');
      editorMessage.textContent = `Маршрут не запущен: ${result.reason}`;
      return;
    }
    rebuildEditedScene('Робот назначен и готов к движению.');
  }
  operationalPlayback = true;
  syncOperationalPlaybackUi();
});

document.querySelector('#craft-economics-summary').addEventListener('click', () => {
  editorPanel.classList.remove('hidden');
  if (touchMode) document.body.classList.add('touch-panel-open');
  document.querySelector('#editor-project-tools').open = true;
  document.querySelector('#live-economics').open = true;
  document.querySelector('#live-economics').scrollIntoView({ block: 'nearest' });
});

for (const [id, key] of [['operational-charge', 'chargeId'], ['operational-work', 'workId'], ['operational-dropoff', 'dropoffId']]) {
  document.querySelector(`#${id}`).addEventListener('change', event => {
    operationalSelection[key] = event.target.value;
    if (routePreviewRequested) { operationalPath = planOperationalPath(scene, operationalSelection); renderOperationalControls(); }
  });
}
document.querySelector('#operational-plan').addEventListener('click', () => {
  routePreviewRequested = true;
  operationalPath = planOperationalPath(scene, operationalSelection);
  renderOperationalControls();
});
document.querySelector('#operational-assign').addEventListener('click', () => {
  const result = sceneEditor.assignRobot(document.querySelector('#operational-robot').value, operationalSelection,
    Number(document.querySelector('#operational-payload').value), Number(document.querySelector('#operational-speed').value));
  if (!result.ok) { document.querySelector('#operational-status').textContent = result.reason; return; }
  rebuildEditedScene('Робот назначен. Маршрут будет пересчитан при изменении сцены; движение запускается кнопкой Play.');
});
document.querySelector('#operational-toggle').addEventListener('click', () => {
  if (!operationalPlayback && !scene.editorAssignments?.some(item => item.ok)) {
    document.querySelector('#operational-status').textContent = 'Нет доступного маршрута для запуска.';
    return;
  }
  operationalPlayback = !operationalPlayback;
  syncOperationalPlaybackUi();
});
document.querySelector('#operational-follow').addEventListener('click', () => {
  operationalFollow = !operationalFollow;
  syncOperationalPlaybackUi();
});
document.querySelectorAll('[data-operational-speed]').forEach(button => button.addEventListener('click', () => {
  operationalSpeed = Number(button.dataset.operationalSpeed);
  if (simulation) simulation.speedMultiplier = operationalSpeed;
  syncOperationalPlaybackUi();
}));

function renderRoomList() {
  const list = document.querySelector('#map-room-list');
  if (!sceneEditor) { list.replaceChildren(); return; }
  list.replaceChildren(...(sceneEditor.scene.editorRooms || []).map(room => {
    const row = document.createElement('div');
    const label = document.createElement('span'); label.textContent = `${room.name} · ${room.points.length} стен`;
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Удалить';
    remove.setAttribute('aria-label', `Удалить комнату ${room.name}`);
    remove.addEventListener('click', () => { if (sceneEditor.deleteRoom(room.id)) rebuildEditedScene(`Комната «${room.name}» удалена. Отмена доступна через Ctrl+Z.`); });
    row.append(label, remove); return row;
  }));
}

function updateMapZoom() {
  document.querySelector('#map-zoom-label').textContent = `${Math.round(mapView.zoom * 100)}%`;
  document.querySelector('#map-pan-label').textContent = `${mapView.panX.toFixed(1).replace('.', ',')} / ${mapView.panZ.toFixed(1).replace('.', ',')} м`;
}
function zoomMap(factor, clientX, clientY) {
  if (!scene || editorView !== '2d') return;
  mapView = mapZoomAt(mapView, factor, clientX, clientY, craftMap.getBoundingClientRect(), scene.config.width, scene.config.depth);
  updateMapZoom();
}
document.querySelector('#map-zoom-in').addEventListener('click', () => { const r = craftMap.getBoundingClientRect(); zoomMap(1.25, r.left + r.width / 2, r.top + r.height / 2); });
document.querySelector('#map-zoom-out').addEventListener('click', () => { const r = craftMap.getBoundingClientRect(); zoomMap(.8, r.left + r.width / 2, r.top + r.height / 2); });
document.querySelector('#map-fit').addEventListener('click', () => { mapView = { zoom: 1, panX: 0, panZ: 0 }; updateMapZoom(); });
craftMap.addEventListener('wheel', event => {
  if (!editorMode || editorView !== '2d') return;
  event.preventDefault();
  zoomMap(event.deltaY < 0 ? 1.15 : 1 / 1.15, event.clientX, event.clientY);
}, { passive: false });
craftMap.addEventListener('pointerdown', event => {
  if (event.pointerType === 'touch') {
    mapTouches.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (mapTouches.size === 2) {
      const [a, b] = [...mapTouches.values()];
      mapGesture = { view: { ...mapView }, center: [(a.x + b.x) / 2, (a.y + b.y) / 2], distance: Math.hypot(a.x - b.x, a.y - b.y) };
      mapSuppressClickUntil = performance.now() + 500;
      mapPreview = null;
    }
    return;
  }
  if (!editorMode || editorView !== '2d' || !(event.button === 1 || (event.button === 0 && event.altKey))) return;
  event.preventDefault();
  mapPan = { pointerId: event.pointerId, button: event.button, x: event.clientX, y: event.clientY, panX: mapView.panX, panZ: mapView.panZ };
  try { craftMap.setPointerCapture?.(event.pointerId); } catch { /* Synthetic pointer events have no active capture. */ }
});
craftMap.addEventListener('pointerup', event => {
  if (event.pointerType === 'touch') {
    mapTouches.delete(event.pointerId);
    if (mapGesture) { mapGesture = null; mapSuppressClickUntil = performance.now() + 500; }
    return;
  }
  if (mapPan?.pointerId !== event.pointerId) return;
  if (mapPan.button === 1) mapDragEnded = false;
  mapPan = null;
  if (craftMap.hasPointerCapture?.(event.pointerId)) craftMap.releasePointerCapture(event.pointerId);
  setTimeout(() => { mapDragEnded = false; }, 0);
});
craftMap.addEventListener('pointercancel', event => { mapPan = null; mapTouches.delete(event.pointerId); mapGesture = null; });
craftMap.addEventListener('auxclick', event => { if (event.button === 1) event.preventDefault(); });

function beginWallTool(door) {
  if (!sceneEditor || !editorMode || editorView !== '2d') { editorMessage.textContent = 'Переключитесь в 2D, чтобы строить стены.'; return; }
  zoneDraft = null;
  document.querySelector('#map-zone-actions').classList.add('hidden');
  inventory.select(null); syncHeldItem();
  wallDraft = { start: null, end: null, door, valid: false };
  document.querySelector('#map-wall-cancel').classList.remove('hidden');
  setEditorTool('wall');
  editorMessage.textContent = door ? 'Укажите два конца стены. Посередине останется дверной проём 1,2 м.' : 'Укажите начало и конец стены. Следующий сегмент начнётся в последней точке.';
}
document.querySelector('#map-wall-start').addEventListener('click', () => beginWallTool(false));
document.querySelector('#map-door-start').addEventListener('click', () => beginWallTool(true));
document.querySelector('#map-wall-cancel').addEventListener('click', () => { setEditorTool('select'); editorMessage.textContent = 'Построение стен завершено.'; });

document.querySelector('#map-room-start').addEventListener('click', () => {
  if (!sceneEditor || !editorMode || editorView !== '2d') { editorMessage.textContent = 'Переключитесь в 2D, чтобы построить комнату.'; return; }
  zoneDraft = null;
  document.querySelector('#map-zone-actions').classList.add('hidden');
  inventory.select(null); syncHeldItem();
  roomDraft = [];
  document.querySelector('#map-room-name').value = `Комната ${(sceneEditor.scene.editorRooms || []).length + 1}`;
  document.querySelector('#map-room-actions').classList.remove('hidden');
  setEditorTool('room');
  editorMessage.textContent = 'Щёлкните минимум три угла комнаты и нажмите «Замкнуть комнату». Alt + перетаскивание двигает план.';
});
document.querySelector('#map-room-cancel').addEventListener('click', () => { setEditorTool('select'); editorMessage.textContent = 'Построение комнаты отменено.'; });
document.querySelector('#map-room-finish').addEventListener('click', () => {
  if (!roomDraft) return;
  const name = document.querySelector('#map-room-name').value.trim();
  const id = sceneEditor.addRoom(name, roomDraft);
  if (!id) { editorMessage.textContent = 'Не удалось создать комнату: проверьте контур, границы и пересечения с оборудованием.'; return; }
  setEditorTool('select');
  rebuildEditedScene(`Комната «${name}» создана: стены и пол доступны в 2D и 3D.`);
});
document.querySelector('#map-room-door-start').addEventListener('click', () => {
  if (!sceneEditor || !editorMode || editorView !== '2d') { editorMessage.textContent = 'Переключитесь в 2D, чтобы изменить проём комнаты.'; return; }
  zoneDraft = null;
  document.querySelector('#map-zone-actions').classList.add('hidden');
  inventory.select(null); syncHeldItem();
  setEditorTool('room-door');
  editorMessage.textContent = 'Щёлкните стену комнаты: проём 1,2 м появится посередине. Повторный клик закрывает его.';
});
document.querySelector('#map-room-door-cancel').addEventListener('click', () => { setEditorTool('select'); editorMessage.textContent = 'Изменение проёмов завершено.'; });

document.querySelector('#map-zone-start').addEventListener('click', () => {
  if (!sceneEditor || !editorMode || editorView !== '2d') { editorMessage.textContent = 'Переключитесь в 2D, чтобы нарисовать зону.'; return; }
  if (wallDraft || roomDraft || editorTool === 'room-door') setEditorTool('select');
  zoneDraft = [];
  inventory.select(null); syncHeldItem();
  document.querySelector('#map-zone-name').value = `Зона ${(sceneEditor.scene.editorZones || []).length + 1}`;
  document.querySelector('#map-zone-actions').classList.remove('hidden');
  document.querySelector('#editor-tool-label').textContent = 'КОНТУР ЗОНЫ';
  editorMessage.textContent = 'Щёлкните минимум три точки внутри площадки, затем завершите контур. Alt + перетаскивание двигает план.';
});
document.querySelector('#map-zone-cancel').addEventListener('click', () => {
  zoneDraft = null;
  document.querySelector('#map-zone-actions').classList.add('hidden');
  setEditorTool('select');
  editorMessage.textContent = 'Рисование зоны отменено.';
});
document.querySelector('#map-zone-finish').addEventListener('click', () => {
  if (!zoneDraft || !validZonePolygon(zoneDraft, scene.config.width, scene.config.depth)) { editorMessage.textContent = 'Контур должен иметь минимум три точки, площадь и не выходить за площадку.'; return; }
  const name = document.querySelector('#map-zone-name').value.trim();
  const id = sceneEditor.addZone(name, zoneDraft);
  if (!id) { editorMessage.textContent = 'Не удалось создать зону: проверьте название и контур.'; return; }
  zoneDraft = null;
  document.querySelector('#map-zone-actions').classList.add('hidden');
  setEditorTool('select');
  rebuildEditedScene(`Визуальная зона «${name}» сохранена. Маршруты и расчёты не меняются.`);
});

function mapPosition(event) {
  const [x, z] = mapPoint(event.clientX, event.clientY, craftMap.getBoundingClientRect(), scene.config.width, scene.config.depth, mapView);
  const step = gridEnabled.checked ? Number(gridStep.value) : 0;
  return [step ? Math.round(x / step) * step : x, 0, step ? Math.round(z / step) * step : z];
}
function updateMapPreviewAt(event) {
  if (editorTool === 'move' && sceneEditor.entity()) {
    const entity = sceneEditor.entity();
    const position = mapPosition(event); position[1] = entity.position[1];
    const candidate = { position, scale: entity.scale, yaw: entity.yaw, editorId: entity.id };
    mapPreview = { ...candidate, valid: canPlaceSolid(candidate, scene.solids, entity.id) };
    return;
  }
  if (!inventory.held) { mapPreview = null; return; }
  const preset = BUILD_CATALOG.find(item => item.kind === inventory.held);
  const position = mapPosition(event); position[1] = preset.scale[1] / 2;
  const candidate = { position, scale: preset.scale, yaw: buildYaw };
  mapPreview = { ...candidate, valid: canPlaceEditorObject(candidate, preset) };
}
craftMap.addEventListener('pointermove', event => {
  if (!editorMode || editorView !== '2d') return;
  if (event.pointerType === 'touch' && mapTouches.has(event.pointerId)) {
    mapTouches.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (mapGesture && mapTouches.size >= 2) {
      const [a, b] = [...mapTouches.values()];
      const center = [(a.x + b.x) / 2, (a.y + b.y) / 2];
      const distance = Math.hypot(a.x - b.x, a.y - b.y);
      const rect = craftMap.getBoundingClientRect();
      const anchor = mapPoint(...mapGesture.center, rect, scene.config.width, scene.config.depth, mapGesture.view);
      const zoom = Math.max(.5, Math.min(4, mapGesture.view.zoom * distance / Math.max(1, mapGesture.distance)));
      const scale = mapScale(rect.width, rect.height, scene.config.width, scene.config.depth, zoom);
      mapView = { zoom, panX: (center[0] - rect.left - rect.width / 2) / scale - anchor[0],
        panZ: (center[1] - rect.top - rect.height / 2) / scale - anchor[1] };
      updateMapZoom();
      mapSuppressClickUntil = performance.now() + 500;
      return;
    }
  }
  if (mapPan) {
    if (mapPan.pointerId !== event.pointerId) return;
    const scale = mapScale(craftMap.clientWidth, craftMap.clientHeight, scene.config.width, scene.config.depth, mapView.zoom);
    mapView.panX = mapPan.panX + (event.clientX - mapPan.x) / scale;
    mapView.panZ = mapPan.panZ + (event.clientY - mapPan.y) / scale;
    updateMapZoom();
    if (Math.hypot(event.clientX - mapPan.x, event.clientY - mapPan.y) > 3) mapDragEnded = true;
    return;
  }
  if (wallDraft) {
    if (wallDraft.start) {
      const point = mapPosition(event);
      wallDraft.end = [point[0], point[2]];
      wallDraft.valid = Boolean(sceneEditor.wallSegmentPlan(wallDraft.start, wallDraft.end, { door: wallDraft.door }));
    }
    mapPreview = null;
    return;
  }
  if (zoneDraft || roomDraft || editorTool === 'room-door') { mapPreview = null; return; }
  updateMapPreviewAt(event);
});
craftMap.addEventListener('pointerleave', () => { mapPreview = null; });
craftMap.addEventListener('click', event => {
  if (!editorMode || editorView !== '2d') return;
  if (performance.now() < mapSuppressClickUntil) return;
  if (mapDragEnded) { mapDragEnded = false; return; }
  if (wallDraft) {
    const position = mapPosition(event);
    const point = [position[0], position[2]];
    if (Math.abs(point[0]) > scene.config.width / 2 || Math.abs(point[1]) > scene.config.depth / 2) { editorMessage.textContent = 'Точка стены за пределами площадки.'; return; }
    if (!wallDraft.start) { wallDraft.start = point; wallDraft.end = point; editorMessage.textContent = 'Укажите конец сегмента стены.'; return; }
    const ids = sceneEditor.createWallSegment(wallDraft.start, point, { door: wallDraft.door });
    if (!ids) { editorMessage.textContent = 'Стена пересекает оборудование, слишком коротка или выходит за площадку.'; return; }
    wallDraft.start = wallDraft.door ? null : point;
    wallDraft.end = point;
    wallDraft.valid = false;
    rebuildEditedScene(wallDraft.door ? 'Стена с проходимым дверным проёмом создана.' : 'Сегмент стены создан. Щёлкните следующую точку или завершите построение.');
    return;
  }
  if (editorTool === 'room-door') {
    const position = mapPosition(event);
    const x = position[0], z = position[2];
    let nearest = null;
    for (const room of sceneEditor.scene.editorRooms || []) for (let edge = 0; edge < room.points.length; edge += 1) {
      const a = room.points[edge], b = room.points[(edge + 1) % room.points.length];
      const dx = b[0] - a[0], dz = b[1] - a[1];
      const t = Math.max(0, Math.min(1, ((x - a[0]) * dx + (z - a[1]) * dz) / (dx * dx + dz * dz)));
      const distance = Math.hypot(x - a[0] - t * dx, z - a[1] - t * dz);
      if (distance < .6 && (!nearest || distance < nearest.distance)) nearest = { room, edge, distance };
    }
    if (!nearest) { editorMessage.textContent = 'Щёлкните по стене комнаты.'; return; }
    const closing = nearest.room.doors?.some(door => door.edge === nearest.edge);
    if (!sceneEditor.toggleRoomDoor(nearest.room.id, nearest.edge)) { editorMessage.textContent = 'Проём нельзя изменить: стена коротка или место занято оборудованием.'; return; }
    rebuildEditedScene(closing ? `Проём комнаты «${nearest.room.name}» закрыт.` : `В стене комнаты «${nearest.room.name}» открыт проход 1,2 м.`);
    return;
  }
  if (roomDraft) {
    const point = mapPosition(event);
    if (Math.abs(point[0]) > scene.config.width / 2 || Math.abs(point[2]) > scene.config.depth / 2) { editorMessage.textContent = 'Точка комнаты за пределами площадки.'; return; }
    roomDraft.push([point[0], point[2]]);
    editorMessage.textContent = `Комната: ${roomDraft.length} углов. Замкните после трёх углов.`;
    return;
  }
  if (zoneDraft) {
    const point = mapPosition(event);
    if (Math.abs(point[0]) > scene.config.width / 2 || Math.abs(point[2]) > scene.config.depth / 2) { editorMessage.textContent = 'Точка зоны за пределами площадки.'; return; }
    zoneDraft.push([point[0], point[2]]);
    editorMessage.textContent = `Контур: ${zoneDraft.length} точек. Завершите после трёх точек.`;
    return;
  }
  if (editorTool === 'move') {
    updateMapPreviewAt(event);
    if (mapPreview?.valid && sceneEditor.update(sceneEditor.selectedId, { position: mapPreview.position })) {
      rebuildEditedScene('Объект перемещён в 2D.'); setEditorTool('select'); mapPreview = null;
    } else editorMessage.textContent = 'Перемещение пересекает другой объект.';
    return;
  }
  if (inventory.held) {
    updateMapPreviewAt(event);
    if (!mapPreview?.valid) { editorMessage.textContent = 'Красная область: место занято или за пределами площадки.'; return; }
    const id = sceneEditor.create(inventory.held, mapPreview.position, { yaw: buildYaw });
    if (id) rebuildEditedScene('Объект размещён в 2D. Предмет остаётся в руке: ∞.');
    return;
  }
  const point = mapPosition(event);
  const entity = mapEntityAt([point[0], point[2]], sceneEditor.entities());
  if (entity && !event.shiftKey && entity.id.startsWith('user:')) {
    sceneEditor.delete(entity.id); rebuildEditedScene('Объект удалён пустой рукой в 2D.');
  } else { sceneEditor.select(entity?.id || null); updateEditorUi(); }
});

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
    const blob = new Blob([exportSceneDocument(sceneEditor.history.present, inventory.toJSON())], { type: 'application/json' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `robcraft-scene-${scene.config.seed}.json`; link.click(); URL.revokeObjectURL(url);
  }
  if (action === 'import') document.querySelector('#scene-import').click();
});

editorPanel.addEventListener('change', event => {
  if (event.target.id === 'entity-operational-role') {
    if (sceneEditor.setOperationalRole(sceneEditor.selectedId, event.target.value || null)) rebuildEditedScene('Операционная роль объекта сохранена. Проверка пути обновлена.');
  }
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
      baseScene = createEditorBaseScene(imported.baseConfig, imported.baseConfig.editorStart || 'ready');
      sceneEditor = new SceneEditorModel(baseScene, imported.patch);
      sceneEditor.refresh();
      inventory = new EditorInventory(imported.inventory?.slots, imported.inventory?.active);
      renderHotbar(); syncHeldItem();
      populateForm(imported.baseConfig);
      document.querySelector('#scene-start').value = imported.baseConfig.editorStart || 'ready';
      history.replaceState(null, '', `${location.pathname}${configToQuery(imported.baseConfig)}&editorStart=${imported.baseConfig.editorStart || 'ready'}`);
      rebuildEditedScene('ScenePatch импортирован; база восстановлена отдельно по seed.');
    }
  } catch (error) { editorMessage.textContent = `Импорт отклонён: ${error.message}`; }
  event.target.value = '';
});

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

function fillProjectVersions() {
  projectVersionList.replaceChildren(...projectStore.versions.map(item => {
    const option = document.createElement('option'); option.value = String(item.revision);
    option.textContent = `Версия ${item.revision} · ${item.name} · ${new Date(item.saved_at).toLocaleString('ru-RU')}`;
    return option;
  }));
  projectVersionList.value = String(projectStore.revision);
}

function currentProjectDocument() {
  return JSON.parse(exportSceneDocument(sceneEditor.history.present, inventory.toJSON()));
}

function reportProjectError(error) {
  projectStatus.textContent = error instanceof SceneSaveConflict
    ? `${error.message} Текущая версия: ${error.currentRevision}. Ваши изменения остались в редакторе; экспортируйте JSON при необходимости.`
    : error.message;
}

async function saveProjectScene(name) {
  if (!projectStore || !projectReady || !sceneEditor) return;
  projectSave.disabled = projectRename.disabled = projectSaveAs.disabled = true;
  projectStatus.textContent = 'Сохраняем сцену в проекте…';
  try {
    const sceneDocument = currentProjectDocument();
    await projectStore.save(sceneDocument, name);
    projectDirty = exportSceneDocument(sceneEditor.history.present, inventory.toJSON()) !== JSON.stringify(sceneDocument, null, 2);
    fillProjectVersions();
    projectStatus.textContent = projectDirty ? `Версия ${projectStore.revision} сохранена; появились новые несохранённые изменения.` : `Сохранено в проекте · версия ${projectStore.revision}`;
  } catch (error) { reportProjectError(error); }
  finally { projectSave.disabled = projectRename.disabled = projectSaveAs.disabled = false; }
}

function openProjectDocument(sceneDocument) {
  const imported = importSceneDocument(sceneDocument);
  populateForm(imported.baseConfig);
  document.querySelector('#scene-start').value = imported.baseConfig.editorStart || 'ready';
  startWorld(imported.baseConfig, false, imported);
  toggleEditor(true);
  projectDirty = false;
  projectStatus.textContent = `Сохранено в проекте · версия ${projectStore.revision}`;
}

async function loadProjectScene() {
  if (!projectStore) return;
  projectControls.classList.remove('hidden');
  projectSave.disabled = true;
  projectSaveAs.disabled = projectRename.disabled = true;
  const launchStatus = document.querySelector('#project-launch-status');
  launchStatus.classList.remove('hidden');
  launchStatus.textContent = 'Открываем сцену проекта…';
  try {
    const document = await projectStore.load();
    projectReady = true;
    projectSave.disabled = false;
    projectSaveAs.disabled = projectRename.disabled = false;
    fillProjectVersions();
    if (document) openProjectDocument(document);
    else launchStatus.textContent = 'В проекте пока нет сцены RobCraft. Создайте её и нажмите «Сохранить».';
  } catch (error) {
    launchStatus.textContent = error.message;
    projectStatus.textContent = error.message;
  }
}

projectSave.addEventListener('click', () => saveProjectScene(projectStore.name || `Сцена ${scene.config.seed}`));

projectRename.addEventListener('click', () => {
  if (!projectStore || !projectReady || !sceneEditor) { projectStatus.textContent = 'Откройте сцену проекта перед переименованием.'; return; }
  projectNameAction = 'rename';
  projectNameInput.value = projectStore.name || `Сцена ${scene.config.seed}`;
  projectNameForm.classList.remove('hidden');
  projectNameInput.focus();
  projectNameInput.select();
});

projectSaveAs.addEventListener('click', () => {
  if (!projectStore || !projectReady || !sceneEditor) return;
  projectNameAction = 'save-as';
  projectNameInput.value = `${projectStore.name || 'Сцена'} — копия`;
  projectNameForm.classList.remove('hidden');
  projectNameInput.focus();
  projectNameInput.select();
});

document.querySelector('#project-scene-name-cancel').addEventListener('click', () => {
  projectNameForm.classList.add('hidden');
  projectNameAction = null;
});

projectNameForm.addEventListener('submit', async event => {
  event.preventDefault();
  const name = projectNameInput.value.trim();
  if (!name || name.length > 200) { projectStatus.textContent = 'Название должно содержать от 1 до 200 символов.'; return; }
  if (projectNameAction === 'rename') {
    projectNameForm.classList.add('hidden');
    projectNameAction = null;
    await saveProjectScene(name);
    return;
  }
  if (projectNameAction !== 'save-as' || !projectStore || !projectReady || !sceneEditor) return;
  projectSave.disabled = projectRename.disabled = projectSaveAs.disabled = true;
  projectStatus.textContent = 'Создаём новый проект со сценой…';
  try {
    const sceneDocument = currentProjectDocument();
    const saved = await projectStore.saveAs(sceneDocument, name);
    projectId = saved.project_id;
    projectStore = new RobCraftProjectStore(projectId, (...args) => fetch(...args), csrfToken);
    projectStore.revision = saved.revision;
    projectStore.name = saved.name;
    projectStore.versions = [saved];
    const url = new URL(location.href);
    url.searchParams.set('project_id', projectId);
    history.replaceState(null, '', url);
    projectDirty = exportSceneDocument(sceneEditor.history.present, inventory.toJSON()) !== JSON.stringify(sceneDocument, null, 2);
    fillProjectVersions();
    projectStatus.textContent = `Новый проект «${saved.name}» создан · версия ${saved.revision}`;
    projectNameForm.classList.add('hidden');
    projectNameAction = null;
    if (window.parent !== window) window.parent.postMessage({ type: 'ROBCRAFT_PROJECT_CREATED', project_id: projectId }, location.origin);
  } catch (error) { reportProjectError(error); }
  finally { projectSave.disabled = projectRename.disabled = projectSaveAs.disabled = false; }
});

document.querySelector('#project-scene-versions').addEventListener('click', () => {
  if (!projectStore) return;
  fillProjectVersions();
  projectVersionList.classList.toggle('hidden', !projectVersionList.classList.contains('hidden'));
});

projectVersionList.addEventListener('change', async () => {
  if (projectDirty && !confirm('Открыть сохранённую версию? Несохранённые изменения можно вернуть через локальный черновик или заранее экспортировать JSON.')) return;
  try {
    const version = await projectStore.readVersion(Number(projectVersionList.value));
    openProjectDocument(version.document);
    projectDirty = version.revision !== projectStore.revision;
    projectStatus.textContent = `Открыта версия ${version.revision}. Сохранение создаст новую версию проекта.`;
  } catch (error) { projectStatus.textContent = error.message; }
});

if (projectStore) loadProjectScene();
