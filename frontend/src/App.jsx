import { useEffect, useRef, useState } from 'react';
import OnboardingScreen from './OnboardingScreen';
import IntakeScreen from './components/IntakeScreen';
import ProcessScreen from './components/ProcessScreen';
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
import TechnicalVisualization from './components/TechnicalVisualization';
import BrainModelScreen from './components/BrainModelScreen';
import CandidateComparisonPanel from './components/CandidateComparisonPanel';
import RoboExpertScreen from './components/RoboExpertScreen';
import EconomicsGlossaryScreen from './components/EconomicsGlossaryScreen';
import ReportsScreen from './components/ReportsScreen';
import ProjectTemplatesScreen from './components/ProjectTemplatesScreen';
import AdminCatalogScreen from './components/AdminCatalogScreen';
import {
  forgetProjectId, readRememberedProjectId, rememberProjectId, selectRestorableProject,
} from './projectSelection';
import { phaseFromHash, phaseHash } from './appNavigation';
import { humanizePresentation } from './presentation';

const STEPS = [
  { id: 'object', label: 'Объект' },
  { id: 'intake', label: 'Расчёт' },
  { id: 'results', label: 'Визуализация' },
];

const API = import.meta.env.VITE_API_URL || '';
const sessionStore = () => {
  try { return window.sessionStorage; } catch { return null; }
};

export default function App() {
  const [phase, setPhase] = useState(() => phaseFromHash(window.location.hash));
  const [objectType, setObjectType] = useState(() => window.location.hash === '#calculation' ? 'retail' : null);
  const [preset, setPreset] = useState(null);
  const [userInput, setUserInput] = useState(null);
  const [result, setResult] = useState(null);
  const [command, setCommand] = useState('');
  const [intakePrompt, setIntakePrompt] = useState('');
  const [intakeInitialSources, setIntakeInitialSources] = useState(null);
  const [catalogFocusId, setCatalogFocusId] = useState(null);
  const [catalogContext, setCatalogContext] = useState(null);
  const [assistantSession, setAssistantSession] = useState(null);
  const [assistantImport, setAssistantImport] = useState(null);
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
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

  const showPhase = (nextPhase) => {
    if (phase !== nextPhase) {
      const url = new URL(window.location.href);
      url.hash = phaseHash(nextPhase);
      window.history.pushState({ robodovodPhase: nextPhase }, '', url);
    }
    setPhase(nextPhase);
  };

  useEffect(() => {
    if (window.location.hash !== '#process') return;
    const url = new URL(window.location.href);
    url.hash = '#assistant';
    window.history.replaceState({ robodovodPhase: 'process' }, '', url);
  }, []);

  useEffect(() => {
    const restore = () => {
      if (window.location.hash === '#process') {
        const url = new URL(window.location.href);
        url.hash = '#assistant';
        window.history.replaceState({ robodovodPhase: 'process' }, '', url);
      }
      const nextPhase = phaseFromHash(window.location.hash, Boolean(result));
      if (nextPhase === 'onboarding' && window.location.hash === '#results') {
        const url = new URL(window.location.href);
        url.hash = '';
        window.history.replaceState({ robodovodPhase: 'onboarding' }, '', url);
      }
      setPhase(nextPhase);
    };
    window.addEventListener('popstate', restore);
    return () => window.removeEventListener('popstate', restore);
  }, [result]);

  useEffect(() => {
    if (phase !== 'results') return undefined;
    const target = pendingResultTarget.current;
    const frame = window.requestAnimationFrame(() => {
      // Clear only after execution: StrictMode may cancel the first frame.
      pendingResultTarget.current = null;
      if (target) document.getElementById(target)?.scrollIntoView({ behavior: 'instant', block: 'start' });
      else window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
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

  const selectActiveProject = (project) => {
    setCatalogContext(null);
    setActiveProject(project);
    setActiveRun(null);
    setResult(null);
    setUserInput(null);
    rememberProjectId(sessionStore(), user?.id, project.id);
  };

  const restart = () => {
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

  const currentStep = phase === 'onboarding' ? 0 : phase === 'intake' ? 1 : 2;
  const assistantSessionKey = `${user?.id || 'guest'}:${activeProject?.id || 'none'}`;

  const openCalculation = () => {
    setEditorRequestedRunId(null);
    setAssistantImport(null);
    setIntakeInitialSources(null);
    const savedInput = activeProject?.scenarios?.find((item) => item.slot === 'BASE')?.inputs;
    const nextType = savedInput?.object_type || objectType || 'retail';
    setObjectType(nextType);
    setPreset(savedInput || (preset?.object_type === nextType ? preset : null));
    showPhase('intake');
  };

  const openSavedRun = (run, project, options = {}) => {
    selectActiveProject(project);
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
    if (id === 'process') {
      showPhase('process');
      return;
    }
    if (id === 'model') {
      showPhase('model');
      return;
    }
    if (id === 'expert' || id === 'variants') {
      showPhase('expert');
      return;
    }
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
    if (id === 'admin') {
      showPhase(user?.role === 'ADMIN' ? 'admin' : 'account');
      return;
    }
    if (id === 'adminCatalog') {
      showPhase(user?.role === 'ADMIN' ? 'adminCatalog' : 'account');
      return;
    }
    if (id === 'account') {
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
    <AppShell phase={phase} user={user} activeProject={activeProject} onNavigate={navigate} command={command} setCommand={setCommand} onCommand={submitCommand}>
      {['onboarding', 'intake'].includes(phase) && <Stepper current={currentStep} />}
      <div className="phase-content">
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
            onGuestDemo={() => showPhase('guestDemo')}
            onOwnProcess={openCalculation}
            onOpenCatalog={() => { setCatalogFocusId(null); catalogReturnPhase.current = 'onboarding'; showPhase('catalog'); }}
            onChoose={(t) => {
              setIntakeInitialSources(null);
              setIntakePrompt('');
              setObjectType(t);
              setAssistantImport(null);
              const savedInput = activeProject?.scenarios?.find((item) => item.slot === 'BASE')?.inputs;
              setPreset(savedInput?.object_type === t ? savedInput : null);
              showPhase('intake');
            }}
          />
        ) : phase === 'economics' ? (
          <EconomicsGlossaryScreen onOpenCalculation={openCalculation} onOpenDemo={() => showPhase('guestDemo')} />
        ) : phase === 'reports' ? (
          <ReportsScreen user={user} onOpenAccount={() => showPhase('account')} onOpenRun={openSavedRun} />
        ) : phase === 'process' ? (
          <ProcessScreen key={assistantSessionKey} activeProject={activeProject} user={user} hasResult={Boolean(result)}
            sessionKey={assistantSessionKey}
            session={assistantSession?.key === assistantSessionKey ? assistantSession.value : null}
            onSessionChange={setAssistantSession}
            onStartCalculation={openCalculation}
            onOpenCatalog={(positionId = null) => { setCatalogFocusId(positionId); catalogReturnPhase.current = 'process'; showPhase('catalog'); }}
            onOpenDemo={() => showPhase('guestDemo')}
            onOpenProjects={() => showPhase(user ? 'projects' : 'account')}
            onReturnToResult={() => showPhase('results')} />
        ) : phase === 'model' ? (
          <BrainModelScreen key={activeProject?.id || 'no-project'} project={activeProject} user={user}
            onOpenProjects={() => showPhase('projects')} onOpenAccount={() => showPhase('account')}
            onViewRun={(run, request) => {
              setActiveRun(run); setResult(run.result_snapshot); setUserInput(request); showPhase('results');
            }} />
        ) : phase === 'expert' ? (
          <RoboExpertScreen user={user} project={activeProject}
            capacityRunId={activeRun?.run_kind === 'CAPACITY_ANALYSIS' ? activeRun.id : null}
            onOpenAccount={() => showPhase('account')} />
        ) : phase === 'intake' ? (
          <IntakeScreen
            key={`${activeProject?.id || 'guest'}:${objectType}`}
            objectType={objectType}
            initialCollected={preset}
            initialSources={intakeInitialSources}
            initialPrompt={intakePrompt}
            importedAssistant={assistantImport}
            activeProject={activeProject}
            initialFacilityContext={userInput?.facility_context || activeRun?.input_snapshot?.facility_context}
            user={user}
            authChecked={authChecked}
            projectChoices={projectChoices}
            projectStatus={projectStatus}
            onChooseProject={selectActiveProject}
            onOpenProjects={() => showPhase('projects')}
            onOpenAccount={() => showPhase('account')}
            onFileApplied={(normalized, imported) => {
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
            onIntakeV2Normalized={(snapshot) => { intakeV2Snapshot.current = snapshot; const p = snapshot.response?.normalized_processes?.find((p) => p.active); setCatalogContext(p ? { process_code: p.process_code, constraints: p.item_mass?.status === 'KNOWN' ? { max_payload_kg: p.item_mass.normalized_value } : {} } : null); }}
            onCapacityResult={(response, request) => {
              setResult(response);
              setUserInput(request);
              setActiveRun({ id: response.run_id, run_kind: 'CAPACITY_ANALYSIS' });
              setSaveState('saved');
              showPhase('results');
            }}
          />
        ) : phase === 'catalog' ? (
          <CatalogScreen key={`${activeProject?.id || 'guest'}-${objectType}`} projectContext={catalogContext} objectType={objectType || 'other'} focusPositionId={catalogFocusId} onContinue={openCalculation}
            onBack={() => showPhase(catalogReturnPhase.current)} />
        ) : phase === 'account' ? (
          <AuthScreen
            user={user}
            onAuthenticated={(nextUser) => {
              setActiveProject(null);
              setProjectChoices([]);
              setProjectStatus('loading');
              setUser(nextUser);
              setAuthChecked(true);
              showPhase('account');
            }}
            onLoggedOut={() => {
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
            onOpenProject={(project) => { selectActiveProject(project); showPhase('onboarding'); }}
            onOpenRun={openSavedRun}
          />
        ) : phase === 'admin' ? (
          user?.role === 'ADMIN' ? <><div className="persistence-screen"><button className="secondary-action" onClick={() => showPhase('adminCatalog')}>Каталог и источники</button></div><AdminUsersScreen /></>
            : <div className="persistence-screen"><p>{authChecked ? 'Требуется учётная запись администратора.' : 'Проверяем учётную запись…'}</p><button className="secondary-action" onClick={() => showPhase('account')}>Учётная запись</button></div>
        ) : phase === 'adminCatalog' ? (
          user?.role === 'ADMIN' ? <AdminCatalogScreen user={user} />
            : <div className="persistence-screen"><p>{authChecked ? 'Требуется учётная запись администратора.' : 'Проверяем учётную запись…'}</p><button className="secondary-action" onClick={() => showPhase('account')}>Учётная запись</button></div>
        ) : (
          <>
            {result?.schema_version === 'simulation-2d-bundle-v1' ? (
              <Simulation2DReport key={result.request?.request_id || result.run_id} request={result.request} initialReport={result.report} scenarios={result.scenarios} />
            ) : isCapacityAnalysisResponse(result) ? (
              <>
                <TechnicalVisualization autoStart onReady={setTechnicalExportRun} key={activeRun?.id || result.run_id} run={activeRun} capacityRequest={userInput} capacityRunId={activeRun?.id || result.run_id} project={activeProject} />
                <CapacityResultsTrace response={result} zoneContext={userInput?.zone_context} onRestart={restart} />
                <EconomicsInputsV2
                  key={activeRun?.id || result.run_id}
                  capacityRequest={userInput}
                  capacityResult={result}
                  capacityRunId={activeRun?.id || result.run_id}
                  project={activeProject}
                  onComplete={(run) => {
                    setActiveRun(run);
                    setResult(run.result_snapshot);
                    setSaveState('saved');
                  }}
                />
              </>
            ) : result?.schema_version === 'economics-partial-result-v1' ? (
              <PartialEconomicsResult result={result} run={activeRun} project={activeProject} autoOpenEditor={editorRequestedRunId === activeRun?.id} onComplete={(run) => {
                setActiveRun(run);
                setResult(run.result_snapshot);
                setSaveState('saved');
              }} />
            ) : isCommercialScenariosBundle(result) ? (
              <>
                <p className="mx-auto max-w-6xl">Глубина расчёта: {({ BASIC: 'Базовый', ADVANCED: 'Углублённый', FULL: 'Полный' })[activeRun?.input_snapshot?.economics?.calculation_depth] || 'Не указана в историческом расчёте'}</p>
                <CommercialScenariosV2 key={`commercial:${result.run_id}`} bundle={result} scenarioSpec={activeRun?.scenario_spec_snapshot} projectName={activeProject?.name} project={activeProject} run={activeRun} onComplete={(run) => { setActiveRun(run); setResult(run.result_snapshot); setSaveState('saved'); }} capacityRunId={activeRun?.input_snapshot?.capacity_run_id} onRestart={restart} onRecalculate={() => {
                  if (activeRun?.id) { setEditorRequestedRunId(activeRun.id); requestAnimationFrame(() => document.getElementById('edit-economics-run')?.scrollIntoView({ behavior: 'smooth', block: 'start' })); }
                  else openCalculation();
                }} />
                <SavedEconomicsEditor key={`editor:${activeRun?.id || result.run_id}`} project={activeProject} run={activeRun} autoOpen={editorRequestedRunId === activeRun?.id} onComplete={(run) => {
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

function Stepper({ current }) {
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
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                    isDone
                      ? 'bg-green-500 text-white'
                      : isActive
                        ? 'bg-blue-600 text-white ring-4 ring-blue-100'
                        : 'bg-slate-200 text-slate-400'
                  }`}
                >
                  {isDone ? '✓' : '•'}
                </div>
                <span
                  className={`text-sm font-medium ${
                    isDone ? 'text-green-600' : isActive ? 'text-blue-600' : 'text-slate-400'
                  }`}
                >
                  {step.label}
                </span>
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
