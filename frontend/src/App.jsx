import { useCallback, useEffect, useRef, useState } from 'react';
import OnboardingScreen from './OnboardingScreen';
import IntakeScreen from './components/IntakeScreen';
import HistoricalRunViewer from './components/HistoricalRunViewer';
import CapacityResultsTrace from './components/CapacityResultsTrace';
import CommercialScenariosV2 from './components/CommercialScenariosV2';
import CatalogScreen from './components/CatalogScreen';
import { AppShell } from './components/AppShell';
import { AdminUsersScreen, AuthScreen, ProjectsScreen } from './components/PersistenceScreens';
import { isCapacityAnalysisResponse } from './capacityResultsModel';
import { isCommercialScenariosBundle } from './commercialScenariosModel';
import Simulation2DReport from './components/Simulation2DReport';
import EvidenceExportPanel from './components/EvidenceExportPanel';
import EconomicsInputsV2 from './components/EconomicsInputsV2';
import PartialEconomicsResult from './components/PartialEconomicsResult';
import SavedEconomicsEditor from './components/SavedEconomicsEditor';
import GuestWarehouseDemo from './components/GuestWarehouseDemo';
import ResultSimulation from './components/ResultSimulation';
import FacilityLayoutEvidence from './components/FacilityLayoutEvidence';
import CapacityScenarioDelta from './components/CapacityScenarioDelta';
import { loadLayoutEvidence, saveLayoutEvidence } from './facilityLayoutEvidence';
import { commercialSimulationSource, resultCapacityRunId } from './resultSimulationModel';
import CandidateComparisonPanel from './components/CandidateComparisonPanel';
import EconomicsGlossaryScreen from './components/EconomicsGlossaryScreen';
import EconomicsMethodologyScreen from './components/EconomicsMethodologyScreen';
import ReportsScreen from './components/ReportsScreen';
import ProjectTemplatesScreen from './components/ProjectTemplatesScreen';
import WarehouseRoleResult from './components/WarehouseRoleResult';
import { ObjectRoleResult } from './components/ObjectRoleWorkspace';
import AdminCatalogScreen from './components/AdminCatalogScreen';
import {
  forgetProjectId, readRememberedProjectId, rememberProjectId, selectRestorableProject,
} from './projectSelection';
import { phaseFromHash, phaseHash } from './appNavigation';
import { humanizePresentation } from './presentation';

const STEPS = [
  { id: 'object', label: 'Объект' },
  { id: 'intake', label: 'Работа' },
  { id: 'robots', label: 'Роботы' },
  { id: 'money', label: 'Деньги' },
  { id: 'results', label: 'Результат' },
];

const API = import.meta.env.VITE_API_URL || '';
const visiblePhase = (phase) => ['process', 'model', 'expert'].includes(phase) ? 'onboarding' : phase;
const sessionStore = () => {
  try { return window.sessionStorage; } catch { return null; }
};
const copyIntakeEntry = (setter, source, target) => {
  if (source === target) return;
  setter((current) => current[source] && !current[target]
    ? { ...current, [target]: current[source] } : current);
};

export default function App() {
  const [phase, setPhase] = useState(() => visiblePhase(phaseFromHash(window.location.hash)));
  const [journeyMode, setJourneyMode] = useState(() => sessionStore()?.getItem('robodovod-journey-mode') || 'ADVANCED');
  const [objectType, setObjectType] = useState(() => window.location.hash === '#calculation' ? 'retail' : null);
  const [preset, setPreset] = useState(null);
  const [intakeDrafts, setIntakeDrafts] = useState({});
  const [intakeSnapshots, setIntakeSnapshots] = useState({});
  const [intakeFocus, setIntakeFocus] = useState(null);
  const [userInput, setUserInput] = useState(null);
  const [result, setResult] = useState(null);
  const [layoutEvidence, setLayoutEvidence] = useState(null);
  const [capacityComparison, setCapacityComparison] = useState(null);
  const lastCapacity = useRef(null);
  const [editableCapacityRunId, setEditableCapacityRunId] = useState(null);
  const [command, setCommand] = useState('');
  const [intakePrompt, setIntakePrompt] = useState('');
  const [intakeInitialSources, setIntakeInitialSources] = useState(null);
  const [catalogFocusId, setCatalogFocusId] = useState(null);
  const [catalogContext, setCatalogContext] = useState(null);
  const [assistantImport, setAssistantImport] = useState(null);
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [resumeIntake, setResumeIntake] = useState(false);
  const [activeProject, setActiveProject] = useState(null);
  const [projectChoices, setProjectChoices] = useState([]);
  const [projectStatus, setProjectStatus] = useState('loading');
  const [activeRun, setActiveRun] = useState(null);
  const [technicalExportRun, setTechnicalExportRun] = useState(null);
  const [editorRequestedRunId, setEditorRequestedRunId] = useState(null);
  const [, setSaveState] = useState('');
  const intakeV2Snapshot = useRef(null);
  const catalogReturnPhase = useRef('onboarding');
  const pendingResultTarget = useRef(null);
  const previousPhase = useRef(phase);
  const pendingIntakeReturn = useRef(false);

  const showPhase = (nextPhase) => {
    if (phase !== nextPhase) {
      const url = new URL(window.location.href);
      url.hash = phaseHash(nextPhase);
      window.history.pushState({ robodovodPhase: nextPhase }, '', url);
    }
    setPhase(visiblePhase(nextPhase));
  };

  useEffect(() => {
    const legacyPhase = phaseFromHash(window.location.hash);
    if (!['process', 'model', 'expert'].includes(legacyPhase)) return;
    // Legacy entry points remain parseable for old bookmarks, but no longer start AI selection.
    const url = new URL(window.location.href);
    url.hash = '';
    window.history.replaceState({ robodovodPhase: 'onboarding' }, '', url);
    if (legacyPhase === 'process') window.dispatchEvent(new Event('robodovod:open-help'));
  }, []);

  useEffect(() => {
    const restore = () => {
      const nextPhase = phaseFromHash(window.location.hash, Boolean(result));
      if (nextPhase === 'onboarding' && window.location.hash === '#results') {
        const url = new URL(window.location.href);
        url.hash = '';
        window.history.replaceState({ robodovodPhase: 'onboarding' }, '', url);
      }
      setPhase(visiblePhase(nextPhase));
    };
    window.addEventListener('popstate', restore);
    return () => window.removeEventListener('popstate', restore);
  }, [result]);

  useEffect(() => {
    const enteredResults = previousPhase.current !== 'results' && phase === 'results';
    const changedPage = previousPhase.current !== phase;
    previousPhase.current = phase;
    if (phase !== 'results') {
      if (changedPage) window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
      return undefined;
    }
    if (enteredResults && !pendingResultTarget.current) {
      window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
      return undefined;
    }
    if (!enteredResults && !pendingResultTarget.current) return undefined;
    const target = pendingResultTarget.current;
    const frame = window.requestAnimationFrame(() => {
      // Clear only after execution: StrictMode may cancel the first frame.
      pendingResultTarget.current = null;
      if (target) document.getElementById(target)?.scrollIntoView({ behavior: 'instant', block: 'start' });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [phase, result]);

  useEffect(() => {
    fetch(`${API}/api/auth/me`, { credentials: 'include' })
      .then((response) => response.ok ? response.json() : null)
      .then((payload) => payload && setUser(payload.user))
      .catch(() => {})
      .finally(() => setAuthChecked(true));
  }, []);

  useEffect(() => {
    if (!user?.id) return undefined;
    const controller = new AbortController();
    fetch(`${API}/api/projects`, { credentials: 'include', signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (controller.signal.aborted) return;
        const items = Array.isArray(payload.items) ? payload.items : [];
        const remembered = readRememberedProjectId(sessionStore(), user.id);
        const selected = selectRestorableProject(items, remembered);
        setProjectChoices(items);
        setActiveProject((current) => current || selected);
        setProjectStatus('ready');
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setProjectStatus('error');
      });
    return () => controller.abort();
  }, [user?.id]);

  useEffect(() => {
    if (!pendingIntakeReturn.current || !user?.id || !activeProject?.id || !objectType) return;
    const source = `${user.id}:none:${objectType}`;
    const target = `${user.id}:${activeProject.id}:${objectType}`;
    copyIntakeEntry(setIntakeDrafts, source, target);
    copyIntakeEntry(setIntakeSnapshots, source, target);
    pendingIntakeReturn.current = false;
    setResumeIntake(false);
  }, [user?.id, activeProject?.id, objectType]);

  const selectActiveProject = (project) => {
    if (phase === 'intake' || pendingIntakeReturn.current) {
      const source = `${user?.id || 'guest'}:${activeProject?.id || 'none'}:${objectType || 'none'}`;
      const target = `${user?.id || 'guest'}:${project.id}:${objectType || 'none'}`;
      copyIntakeEntry(setIntakeDrafts, source, target);
      copyIntakeEntry(setIntakeSnapshots, source, target);
      pendingIntakeReturn.current = false;
      setResumeIntake(false);
    }
    setCatalogContext(null);
    setEditableCapacityRunId(null);
    setActiveProject(project);
    setActiveRun(null);
    setResult(null);
    setUserInput(null);
    rememberProjectId(sessionStore(), user?.id, project.id);
  };

  const restart = () => {
    pendingIntakeReturn.current = false;
    setResumeIntake(false);
    setIntakeDrafts({});
    setIntakeSnapshots({});
    setIntakeFocus(null);
    setEditableCapacityRunId(null);
    setCatalogContext(null);
    showPhase('onboarding');
    setObjectType(null);
    setPreset(null);
    setAssistantImport(null);
    setIntakeInitialSources(null);
    setResult(null);
    setActiveRun(null);
    setSaveState('');
    intakeV2Snapshot.current = null;
  };

  const currentStep = ({ onboarding: 0, intake: 1, robots: 2, money: 3, results: 4 })[phase] ?? 0;
  const intakeDraftKey = `${user?.id || 'guest'}:${activeProject?.id || 'none'}:${objectType || 'none'}`;
  const currentDraft = intakeDrafts[intakeDraftKey];
  const hasEditableDraft = Boolean(currentDraft?.objectKind);
  const resultRevision = userInput?.input_revision;
  const canEditResultDraft = Boolean(result && hasEditableDraft && resultRevision
    && currentDraft.objectKind === userInput?.process?.object_kind
    && editableCapacityRunId === resultCapacityRunId(result, activeRun));
  const resultNeedsRecalculation = Boolean(canEditResultDraft
    && currentDraft.inputRevision !== resultRevision);
  const evidenceRunId = resultCapacityRunId(result, activeRun);
  useEffect(() => {
    if (!activeProject?.id || !evidenceRunId) return undefined;
    const controller = new AbortController();
    loadLayoutEvidence(activeProject.id, evidenceRunId, controller.signal)
      .then((snapshot) => {
        if (snapshot) setLayoutEvidence({ capacityRunId: evidenceRunId, projectId: activeProject.id,
          facilityPlan: snapshot.layout, processId: snapshot.process_id,
          appliedDistanceM: Number(snapshot.applied_distance_m), saveStatus: 'saved',
          layoutDigest: snapshot.layout_digest });
      }).catch(() => {});
    return () => controller.abort();
  }, [activeProject?.id, evidenceRunId]);
  const persistLayoutEvidence = (projectId, runId, evidence) => {
    saveLayoutEvidence(projectId, runId, evidence)
      .then((snapshot) => setLayoutEvidence((current) => current?.capacityRunId === runId
        ? { ...current, facilityPlan: snapshot.layout, saveStatus: 'saved',
          layoutDigest: snapshot.layout_digest } : current))
      .catch((failure) => setLayoutEvidence((current) => current?.capacityRunId === runId
        ? { ...current, saveStatus: 'error', saveError: failure.message } : current));
  };
  const rememberIntakeDraft = useCallback((draft) => setIntakeDrafts((current) =>
    current[intakeDraftKey] === draft ? current : { ...current, [intakeDraftKey]: draft }), [intakeDraftKey]);

  const openCalculation = (focusSalary = false) => {
    setEditorRequestedRunId(null);
    setAssistantImport(null);
    setIntakeInitialSources(null);
    const savedInput = activeProject?.scenarios?.find((item) => item.slot === 'BASE')?.inputs;
    const nextType = hasEditableDraft ? objectType : savedInput?.object_type || objectType || 'retail';
    setObjectType(nextType);
    setPreset(savedInput || (preset?.object_type === nextType ? preset : null));
    setIntakeFocus(focusSalary === true ? { kind: 'salary', processId: userInput?.process?.process_id, nonce: Date.now() } : null);
    showPhase('intake');
  };

  const editCalculatedInputs = () => {
    if (canEditResultDraft) { openCalculation(true); return; }
    if (activeRun?.input_snapshot?.economics) {
      setEditorRequestedRunId(activeRun.id);
      requestAnimationFrame(() => document.getElementById('edit-economics-run')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
      return;
    }
    openCalculation();
  };

  const openSavedRun = (run, project, options = {}) => {
    selectActiveProject(project);
    const savedType = project?.scenarios?.find((item) => item.slot === 'BASE')?.inputs?.object_type;
    if (savedType) setObjectType(savedType);
    setActiveRun(run);
    setUserInput(run.input_snapshot);
    setResult(run.result_snapshot);
    setEditorRequestedRunId(options.edit ? run.id : null);
    pendingResultTarget.current = options.edit ? 'edit-economics-run' : null;
    showPhase('results');
    setSaveState('saved');
  };

  const navigate = ({ id, target }) => {
    if (id === 'templates') { showPhase('templates'); return; }
    if (id === 'home') {
      restart();
      return;
    }
    if (id === 'demo') { showPhase('guestDemo'); return; }
    if (id === 'results') { showPhase(result ? 'results' : 'guestDemo'); return; }
    if (id === 'robots') { showPhase(result ? 'robots' : 'intake'); return; }
    if (id === 'money') { showPhase(result ? 'money' : 'intake'); return; }
    if (id === 'process') { window.dispatchEvent(new Event('robodovod:open-help')); return; }
    if (id === 'model' || id === 'expert' || id === 'variants') { showPhase(result ? 'robots' : 'intake'); return; }
    if (id === 'economics') {
      showPhase('economics');
      return;
    }
    if (id === 'report') {
      showPhase('reports');
      return;
    }
    if (id === 'calculation') {
      openCalculation();
      return;
    }
    if (id === 'library') {
      setCatalogFocusId(null);
      if (phase !== 'catalog') catalogReturnPhase.current = phase;
      showPhase('catalog');
      return;
    }
    if (id === 'projects') {
      showPhase(user ? 'projects' : 'account');
      return;
    }
    if (id === 'register') {
      pendingIntakeReturn.current = phase === 'intake';
      setResumeIntake(phase === 'intake');
      setAuthMode('register');
      showPhase('account');
      return;
    }
    if (id === 'admin') {
      showPhase(user?.role === 'ADMIN' ? 'admin' : 'account');
      return;
    }
    if (id === 'adminCatalog') {
      showPhase(user?.role === 'ADMIN' ? 'adminCatalog' : 'account');
      return;
    }
    if (id === 'account') {
      pendingIntakeReturn.current = phase === 'intake' && !user;
      setResumeIntake(phase === 'intake' && !user);
      setAuthMode('login');
      showPhase('account');
      return;
    }
    if (!result) {
      openCalculation();
      return;
    }
    pendingResultTarget.current = target || id;
    if (phase === 'results') {
      window.requestAnimationFrame(() => {
        const section = pendingResultTarget.current;
        pendingResultTarget.current = null;
        document.getElementById(section)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    } else showPhase('results');
  };

  const submitCommand = (event) => {
    event.preventDefault();
    const prompt = command.trim();
    if (!prompt) return;
    setObjectType(objectType && objectType !== 'other' ? objectType : 'retail');
    setPreset(null);
    setAssistantImport(null);
    setIntakeInitialSources(null);
    setIntakePrompt(prompt);
    showPhase('intake');
  };

  return (
    <AppShell phase={phase} user={user} activeProject={activeProject} objectType={objectType} journeyMode={journeyMode} result={result}
      onNavigate={navigate} command={command} setCommand={setCommand} onCommand={submitCommand}>
      {['onboarding', 'intake', 'robots', 'money', 'results'].includes(phase) && <Stepper current={currentStep}
        canOpenIntake={Boolean(objectType || activeProject)} canOpenResults={Boolean(result)}
        onSelect={(id) => {
          if (id === 'object') showPhase('onboarding');
          else if (id === 'intake') {
            if (phase === 'results' && !canEditResultDraft && activeRun?.input_snapshot?.economics) editCalculatedInputs();
            else openCalculation(phase === 'results' && canEditResultDraft);
          }
          else if (id === 'robots' && result) showPhase('robots');
          else if (id === 'money' && result) showPhase('money');
          else if (id === 'results' && result) showPhase('results');
        }} />}
      <div className={`phase-content${phase === 'results' ? ' phase-content-visualization' : ''}`}>
        {phase === 'templates' ? (
          <ProjectTemplatesScreen user={user} project={activeProject} projects={projectChoices} onChooseProject={selectActiveProject}
            onNavigate={(next, type) => { if (type) setObjectType(type); if (next === 'intake') setAssistantImport(null); showPhase(next); }}
            onApplied={async () => {
              const response = await fetch(`${API}/api/projects/${activeProject.id}`, { credentials: 'include' });
              if (response.ok) setActiveProject(await response.json());
            }} />
        ) : phase === 'guestDemo' ? (
          <GuestWarehouseDemo onContinue={() => { setIntakePrompt(''); setObjectType('retail'); showPhase('intake'); }} onBack={restart} />
        ) : phase === 'onboarding' ? (
          <OnboardingScreen
            mode={journeyMode}
            onModeChange={(value) => { setJourneyMode(value); sessionStore()?.setItem('robodovod-journey-mode', value); }}
            onGuestDemo={() => showPhase('guestDemo')}
            onOwnProcess={openCalculation}
            onOpenCatalog={() => { setCatalogFocusId(null); catalogReturnPhase.current = 'onboarding'; showPhase('catalog'); }}
            onChoose={(t) => {
              setIntakeInitialSources(null);
              setIntakePrompt('');
              setObjectType(t);
              setResult(null);
              setActiveRun(null);
              setAssistantImport(null);
              const savedInput = activeProject?.scenarios?.find((item) => item.slot === 'BASE')?.inputs;
              setPreset(savedInput?.object_type === t ? savedInput : null);
              showPhase('intake');
            }}
          />
        ) : phase === 'economics' ? (
          <EconomicsGlossaryScreen onOpenCalculation={openCalculation} onOpenDemo={() => showPhase('guestDemo')}
            onOpenMethodology={() => showPhase('economicsMethodology')} />
        ) : phase === 'economicsMethodology' ? (
          <EconomicsMethodologyScreen onBack={() => showPhase('economics')} onOpenCalculation={openCalculation} />
        ) : phase === 'reports' ? (
          <ReportsScreen user={user} onOpenAccount={() => showPhase('account')} onOpenRun={openSavedRun} />
        ) : phase === 'intake' ? (
          <IntakeScreen
            key={`${activeProject?.id || 'guest'}:${objectType}`}
            objectType={objectType}
            journeyMode={journeyMode}
            initialCollected={preset}
            initialSources={intakeInitialSources}
            initialPrompt={intakePrompt}
            importedAssistant={assistantImport}
            activeProject={activeProject}
            initialFacilityContext={userInput?.facility_context || activeRun?.input_snapshot?.facility_context}
            initialDraft={intakeDrafts[intakeDraftKey] || (resumeIntake && intakeDrafts[`${user?.id || 'guest'}:none:${objectType || 'none'}`])}
            initialNormalized={intakeSnapshots[intakeDraftKey] || (resumeIntake && intakeSnapshots[`${user?.id || 'guest'}:none:${objectType || 'none'}`])}
            initialCapacityRequest={userInput}
            focusTarget={intakeFocus}
            onDraftChange={rememberIntakeDraft}
            user={user}
            authChecked={authChecked}
            projectChoices={projectChoices}
            projectStatus={projectStatus}
            onChooseProject={selectActiveProject}
            onOpenProjects={() => { pendingIntakeReturn.current = true; setResumeIntake(true); showPhase('projects'); }}
            onOpenAccount={() => { pendingIntakeReturn.current = true; setResumeIntake(true); setAuthMode('register'); showPhase('account'); }}
            onFileApplied={(normalized, imported) => {
              setIntakeDrafts((current) => {
                const next = { ...current }; delete next[intakeDraftKey]; return next;
              });
              setIntakeSnapshots((current) => {
                const next = { ...current }; delete next[intakeDraftKey]; return next;
              });
              setPreset(normalized);
              setActiveProject((project) => project ? ({
                ...project,
                profile: { ...project.profile, project_file_import_id: imported?.id,
                  ...(normalized.schema_version === 'project-workbook-v1' ? { file_intake_v2: normalized } : {}) },
                scenarios: project.scenarios.map((scenario) => (
                  scenario.slot === 'BASE' ? { ...scenario, inputs: normalized } : scenario
                )),
              }) : project);
            }}
            onOpenObjects={() => showPhase('onboarding')}
            roleReport={['warehouse-role-analysis-v1', 'warehouse-role-analysis-v2', 'object-role-analysis-v2', 'object-role-analysis-v3'].includes(result?.schema_version) ? result : null}
            onRolePreview={(response) => { setResult(response); setActiveRun(null); setUserInput(null); setSaveState('preview'); }}
            onRoleInvalidated={() => { if (['warehouse-role-analysis-v1', 'warehouse-role-analysis-v2', 'object-role-analysis-v2', 'object-role-analysis-v3'].includes(result?.schema_version)) setResult(null); }}
            onRoleContinue={() => showPhase('robots')}
            onIntakeV2Normalized={(snapshot) => { intakeV2Snapshot.current = snapshot; setIntakeSnapshots((current) => ({ ...current, [intakeDraftKey]: snapshot })); const p = snapshot.response?.normalized_processes?.find((p) => p.active); setCatalogContext(p ? { process_code: p.process_code, constraints: p.item_mass?.status === 'KNOWN' ? { max_payload_kg: p.item_mass.normalized_value } : {} } : null); }}
            onCapacityResult={(response, request, evidence) => {
              const previous = lastCapacity.current;
              const next = { response, request, projectId: activeProject?.id };
              setCapacityComparison(previous && previous.projectId === next.projectId
                && previous.request?.process?.process_id === request?.process?.process_id
                && previous.response.run_id !== response.run_id ? { before: previous, after: next } : null);
              lastCapacity.current = next;
              setEditableCapacityRunId(response.run_id);
              setResult(response);
              setUserInput(request);
              setLayoutEvidence(evidence ? { ...evidence, capacityRunId: response.run_id,
                projectId: activeProject?.id, saveStatus: 'saving' } : null);
              if (evidence && activeProject?.id) persistLayoutEvidence(activeProject.id, response.run_id, evidence);
              setActiveRun({ id: response.run_id, run_kind: 'CAPACITY_ANALYSIS' });
              setSaveState('saved');
              showPhase('robots');
            }}
            onWarehouseRoleSaved={(response) => {
              setResult(response);
              setActiveRun(null);
              setUserInput(null);
              setSaveState('saved');
            }}
          />
        ) : phase === 'robots' ? (
          ['object-role-analysis-v2', 'object-role-analysis-v3'].includes(result?.schema_version) ? <><ObjectRoleResult report={result} focus="robots" onEdit={() => openCalculation()} />
            <div className="journey-actions mx-auto max-w-6xl pb-6"><button type="button" className="primary-action" onClick={() => showPhase('money')}>К экономике объекта</button></div></>
          : ['warehouse-role-analysis-v1', 'warehouse-role-analysis-v2'].includes(result?.schema_version) ? <><WarehouseRoleResult report={result} focus="robots" onEdit={() => openCalculation()} />
            <div className="journey-actions mx-auto max-w-6xl pb-6"><button type="button" className="primary-action" onClick={() => showPhase('money')}>К экономике склада</button></div></>
          : <main className="journey-panel" aria-label="Какие роботы могут подойти?">
            <p className="eyebrow">Шаг 3 из 5</p><h1>Какие роботы могут подойти?</h1>
            <p>Сначала посмотрите расчёт парка и ограничения выбранной модели. Сравнение использует тот же сохранённый расчёт и каталог.</p>
            {isCapacityAnalysisResponse(result) ? <CapacityResultsTrace response={result} zoneContext={userInput?.zone_context} compact />
              : <p>{result ? 'Открыт сохранённый денежный результат. Его модель и ограничения указаны в итоговом отчёте.' : 'Сначала опишите работу и сохраните расчёт потребного парка.'}</p>}
            {activeProject && evidenceRunId && <details className="simple-robot-comparison"><summary>Сравнить модели и посмотреть источники</summary><CandidateComparisonPanel project={activeProject} capacityRunId={activeRun?.input_snapshot?.capacity_run_id || evidenceRunId} /></details>}
            <div className="journey-actions"><button type="button" className="secondary-action" onClick={() => openCalculation()}>Назад к работе</button>
              <button type="button" className="primary-action" onClick={() => showPhase('money')}>Продолжить к стоимости</button></div>
          </main>
        ) : phase === 'money' ? (
          ['object-role-analysis-v2', 'object-role-analysis-v3'].includes(result?.schema_version) ? <><ObjectRoleResult report={result} focus="money" onEdit={() => openCalculation()} />
            <div className="journey-actions mx-auto max-w-6xl pb-6"><button type="button" className="primary-action" onClick={() => showPhase('results')}>К общему результату</button></div></>
          : ['warehouse-role-analysis-v1', 'warehouse-role-analysis-v2'].includes(result?.schema_version) ? <><WarehouseRoleResult report={result} focus="money" onEdit={() => openCalculation()} />
            <div className="journey-actions mx-auto max-w-6xl pb-6"><button type="button" className="primary-action" onClick={() => showPhase('results')}>К общему результату</button></div></>
          : <main className="journey-panel" aria-label="Сколько это будет стоить?">
            <p className="eyebrow">Шаг 4 из 5</p><h1>Сколько это будет стоить?</h1>
            <p>Оборудование, внедрение и эксплуатация считаются отдельно. Неизвестные условия останутся видимыми в результате.</p>
            {isCapacityAnalysisResponse(result) ? <EconomicsInputsV2
              key={activeRun?.id || result.run_id} initialDepth={journeyMode === 'FAMILIAR' ? 'BASIC' : journeyMode === 'FULL' ? 'FULL' : 'ADVANCED'}
              capacityRequest={userInput} capacityResult={result} capacityRunId={activeRun?.id || result.run_id} project={activeProject}
              onComplete={(run) => { setActiveRun(run); setResult(run.result_snapshot); setSaveState('saved'); showPhase('results'); }} />
              : result?.schema_version === 'economics-partial-result-v1' ? <PartialEconomicsResult result={result} run={activeRun} project={activeProject} onComplete={(run) => { setActiveRun(run); setResult(run.result_snapshot); showPhase('results'); }} />
                : isCommercialScenariosBundle(result) ? <SavedEconomicsEditor project={activeProject} run={activeRun} autoOpen onComplete={(run) => { setActiveRun(run); setResult(run.result_snapshot); showPhase('results'); }} />
                : <p>{result ? 'Смета сохранена в этом расчёте. На следующем шаге показаны сравнение и источники.' : 'Сначала опишите работу и сохраните расчёт потребного парка.'}</p>}
            <div className="journey-actions"><button type="button" className="secondary-action" onClick={() => showPhase('robots')}>Назад к роботам</button>
              <button type="button" className="secondary-action" onClick={() => showPhase('results')}>Посмотреть доступный результат</button></div>
          </main>
        ) : phase === 'catalog' ? (
          <CatalogScreen key={`${activeProject?.id || 'guest'}-${objectType}`} projectContext={catalogContext} objectType={objectType || 'other'} focusPositionId={catalogFocusId} onContinue={openCalculation}
            onBack={() => showPhase(catalogReturnPhase.current)} />
        ) : phase === 'account' ? (
          <AuthScreen
            key={authMode}
            user={user}
            initialMode={authMode}
            onAuthenticated={(nextUser) => {
              const returnToIntake = pendingIntakeReturn.current;
              if (returnToIntake) {
                const source = `guest:none:${objectType || 'none'}`;
                const target = `${nextUser.id}:none:${objectType || 'none'}`;
                copyIntakeEntry(setIntakeDrafts, source, target);
                copyIntakeEntry(setIntakeSnapshots, source, target);
              }
              setActiveProject(null);
              setProjectChoices([]);
              setProjectStatus('loading');
              setUser(nextUser);
              setAuthChecked(true);
              showPhase(returnToIntake ? 'intake' : 'account');
            }}
            onLoggedOut={() => {
              setIntakeDrafts({});
              setIntakeSnapshots({});
              forgetProjectId(sessionStore(), user?.id);
              setUser(null);
              setActiveProject(null);
              setProjectChoices([]);
              setProjectStatus('idle');
              restart();
            }}
            onNavigate={showPhase}
          />
        ) : phase === 'projects' ? (
          <ProjectsScreen
            onOpenProject={(project) => { const returnToIntake = pendingIntakeReturn.current; selectActiveProject(project); showPhase(returnToIntake ? 'intake' : 'onboarding'); }}
            onOpenRun={openSavedRun}
          />
        ) : phase === 'admin' ? (
          user?.role === 'ADMIN' ? <><div className="persistence-screen"><button className="secondary-action" onClick={() => showPhase('adminCatalog')}>Каталог и источники</button></div><AdminUsersScreen /></>
            : <div className="persistence-screen"><p>{authChecked ? 'Требуется учётная запись администратора.' : 'Проверяем учётную запись…'}</p><button className="secondary-action" onClick={() => showPhase('account')}>Учётная запись</button></div>
        ) : phase === 'adminCatalog' ? (
          user?.role === 'ADMIN' ? <AdminCatalogScreen user={user} />
            : <div className="persistence-screen"><p>{authChecked ? 'Требуется учётная запись администратора.' : 'Проверяем учётную запись…'}</p><button className="secondary-action" onClick={() => showPhase('account')}>Учётная запись</button></div>
        ) : ['object-role-analysis-v2', 'object-role-analysis-v3'].includes(result?.schema_version) ? (
          <ObjectRoleResult report={result} onEdit={() => openCalculation()} />
        ) : ['warehouse-role-analysis-v1', 'warehouse-role-analysis-v2'].includes(result?.schema_version) ? (
          <WarehouseRoleResult report={result} onEdit={() => openCalculation()} />
        ) : (
          <>
            {resultNeedsRecalculation && <div className="mx-auto max-w-6xl px-4 pt-4" role="status"><div className="rounded-xl border border-amber-400 bg-amber-50 p-4 text-sm text-amber-950">Ввод изменён после этого расчёта. Показан сохранённый результат прежней версии. <button type="button" className="underline font-semibold" onClick={() => openCalculation(true)}>Вернуться к изменённым полям и пересчитать</button></div></div>}
            {result && <div className="mx-auto max-w-6xl px-4 pt-4 flex flex-wrap items-center gap-3" aria-label="Действия с расчётом">
              <button type="button" className="primary-action" onClick={editCalculatedInputs}>{canEditResultDraft ? 'Изменить зарплату или другие данные' : activeRun?.input_snapshot?.economics ? 'Изменить сохранённую экономику' : 'Новый расчёт по проекту'}</button>
              {canEditResultDraft && <span className="text-sm text-slate-500">Заполненные поля сохранены в этой вкладке; после правки создайте новую версию расчёта.</span>}
              {!canEditResultDraft && !activeRun?.input_snapshot?.economics && <span className="text-sm text-slate-500">Для архивного расчёта черновик формы не сохранён; откроются данные проекта.</span>}
            </div>}
            <ResultSimulation key={resultCapacityRunId(result, activeRun) || activeRun?.id || 'none'} result={result}
              run={activeRun} technicalRun={technicalExportRun} capacityRequest={userInput}
              project={activeProject} onReady={setTechnicalExportRun} />
            {layoutEvidence?.capacityRunId === resultCapacityRunId(result, activeRun)
              && layoutEvidence.projectId === activeProject?.id && <FacilityLayoutEvidence evidence={layoutEvidence}
                onRetrySave={layoutEvidence.saveStatus === 'error' ? () => {
                  setLayoutEvidence((current) => ({ ...current, saveStatus: 'saving' }));
                  persistLayoutEvidence(activeProject.id, layoutEvidence.capacityRunId, layoutEvidence);
                } : null} />}
            {capacityComparison?.after.response.run_id === resultCapacityRunId(result, activeRun)
              && capacityComparison.after.projectId === activeProject?.id && <CapacityScenarioDelta comparison={capacityComparison} />}
            {result?.schema_version === 'simulation-2d-bundle-v1' ? (
              <Simulation2DReport key={result.request?.request_id || result.run_id} request={result.request} initialReport={result.report} scenarios={result.scenarios} />
            ) : isCapacityAnalysisResponse(result) ? (
              <>
                <CapacityResultsTrace response={result} zoneContext={userInput?.zone_context} onRestart={restart} />
                <div className="mx-auto max-w-6xl px-4 pb-4"><button type="button" className="secondary-action" onClick={() => openCalculation()}>Вернуться к заполненным зонам и операциям</button></div>
                <EconomicsInputsV2
                  key={activeRun?.id || result.run_id}
                  capacityRequest={userInput}
                  capacityResult={result}
                  capacityRunId={activeRun?.id || result.run_id}
                  project={activeProject}
                  onComplete={(run) => {
                    pendingResultTarget.current = 'economics-result';
                    setActiveRun(run);
                    setResult(run.result_snapshot);
                    setSaveState('saved');
                  }}
                />
              </>
            ) : result?.schema_version === 'economics-partial-result-v1' ? (
              <PartialEconomicsResult result={result} run={activeRun} project={activeProject} autoOpenEditor={editorRequestedRunId === activeRun?.id} onComplete={(run) => {
                pendingResultTarget.current = 'economics-result';
                setActiveRun(run);
                setResult(run.result_snapshot);
                setSaveState('saved');
              }} />
            ) : isCommercialScenariosBundle(result) ? (
              <>
                <p className="mx-auto max-w-6xl">Глубина расчёта: {({ BASIC: 'Базовый', ADVANCED: 'Углублённый', FULL: 'Полный' })[activeRun?.input_snapshot?.economics?.calculation_depth] || 'Не указана в историческом расчёте'}</p>
                <CommercialScenariosV2 key={`commercial:${result.run_id}`} bundle={result} projectName={activeProject?.name} project={activeProject} run={activeRun} hasVisualization={Boolean(commercialSimulationSource(result, activeRun, technicalExportRun, activeProject?.id))} onComplete={(run) => { pendingResultTarget.current = 'economics-result'; setActiveRun(run); setResult(run.result_snapshot); setSaveState('saved'); }} capacityRunId={activeRun?.input_snapshot?.capacity_run_id} onRestart={restart} onRecalculate={() => {
                  if (activeRun?.id) { setEditorRequestedRunId(activeRun.id); requestAnimationFrame(() => document.getElementById('edit-economics-run')?.scrollIntoView({ behavior: 'smooth', block: 'start' })); }
                  else openCalculation();
                }} />
                <SavedEconomicsEditor key={`editor:${activeRun?.id || result.run_id}`} project={activeProject} run={activeRun} autoOpen={editorRequestedRunId === activeRun?.id} onComplete={(run) => {
                  pendingResultTarget.current = 'economics-result';
                  setActiveRun(run); setResult(run.result_snapshot); setSaveState('saved');
                }} />
              </>
            ) : (
              <HistoricalRunViewer run={activeRun} result={result} userInput={userInput} onNewCalculation={openCalculation} />
            )}
            {activeRun && activeProject && (
              <>
                {activeRun.economics_runtime?.migration_notice && (
                  <div className="save-run-bar" role="status">{humanizePresentation(activeRun.economics_runtime.migration_notice)}</div>
                )}
                <details className="comparison-disclosure mx-auto my-6 max-w-6xl rounded-xl border p-4">
                  <summary className="cursor-pointer font-semibold">Сравнить модели роботов</summary>
                  <p className="text-sm my-2">Сравнение технических характеристик на одинаковых входах. Денежное сравнение требует отдельных сохранённых расчётов моделей.</p>
                  <CandidateComparisonPanel key={activeRun.id} project={activeProject} capacityRunId={activeRun.input_snapshot?.capacity_run_id || activeRun.id} />
                </details>
                <EvidenceExportPanel key={isCapacityAnalysisResponse(result) && technicalExportRun?.input_snapshot?.capacity_run_id === activeRun.id ? technicalExportRun.id : activeRun.id} projectId={activeProject.id} runId={isCapacityAnalysisResponse(result) && technicalExportRun?.input_snapshot?.capacity_run_id === activeRun.id ? technicalExportRun.id : activeRun.id} />
              </>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}

function Stepper({ current, canOpenIntake, canOpenResults, onSelect }) {
  return (
    <div className="stepper-shell">
      <div className="max-w-4xl mx-auto flex items-center justify-between">
        {STEPS.map((step, i) => {
          const isActive = i === current;
          const isDone = i < current || (i === current && i === STEPS.length - 1);
          const isLast = i === STEPS.length - 1;
          return (
            <div key={step.id} className="flex items-center flex-1">
              <div className="flex items-center gap-2">
                <button type="button" disabled={step.id === 'intake' ? !canOpenIntake : ['robots', 'money', 'results'].includes(step.id) ? !canOpenResults : false}
                  aria-current={isActive ? 'step' : undefined} onClick={() => onSelect(step.id)}
                  className={`stepper-link flex items-center gap-2 text-sm font-medium ${isDone ? 'text-green-600' : isActive ? 'text-blue-600' : 'text-slate-400'}`}>
                  <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                    isDone ? 'bg-green-500 text-white' : isActive ? 'bg-blue-600 text-white ring-4 ring-blue-100' : 'bg-slate-200 text-slate-400'
                  }`}>{isDone ? '✓' : i + 1}</span>{step.label}
                </button>
              </div>
              {!isLast && (
                <div
                  className={`flex-1 h-0.5 mx-4 ${
                    i < current ? 'bg-green-400' : 'bg-slate-200'
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
