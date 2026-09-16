import { useEffect, useRef, useState } from 'react';
import OnboardingScreen from './OnboardingScreen';
import IntakeScreen from './components/IntakeScreen';
import ResultsPanel from './components/ResultsPanel';
import CatalogScreen from './components/CatalogScreen';
import { AppShell } from './components/AppShell';
import { AdminUsersScreen, AuthScreen, ProjectsScreen } from './components/PersistenceScreens';
import { readCsrfCookie } from './persistenceApi';

const STEPS = [
  { id: 'object', label: 'Объект' },
  { id: 'intake', label: 'Расчёт' },
  { id: 'results', label: 'Визуализация' },
];

const API = import.meta.env.VITE_API_URL || '';

export default function App() {
  const [phase, setPhase] = useState('onboarding');
  const [objectType, setObjectType] = useState(null);
  const [preset, setPreset] = useState(null);
  const [userInput, setUserInput] = useState(null);
  const [result, setResult] = useState(null);
  const [command, setCommand] = useState('');
  const [intakePrompt, setIntakePrompt] = useState('');
  const [user, setUser] = useState(null);
  const [activeProject, setActiveProject] = useState(null);
  const [saveState, setSaveState] = useState('');
  const calculationSequence = useRef(0);

  useEffect(() => {
    fetch(`${API}/api/auth/me`, { credentials: 'include' })
      .then((response) => response.ok ? response.json() : null)
      .then((payload) => payload && setUser(payload.user))
      .catch(() => {});
  }, []);

  const recalc = async (inp) => {
    calculationSequence.current += 1;
    const sequence = calculationSequence.current;
    const apiInput = Object.fromEntries(
      Object.entries(inp).filter(([key]) => !key.startsWith('_'))
    );
    try {
      const res = await fetch(`${API}/api/calculate`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(apiInput),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        if (sequence === calculationSequence.current) alert(e.detail || 'Ошибка расчёта');
        return;
      }
      const nextResult = await res.json();
      if (sequence !== calculationSequence.current) return;
      setUserInput(inp);
      setResult(nextResult);
    } catch {
      if (sequence === calculationSequence.current) {
        alert('Бэкенд недоступен. Запустите uvicorn main:app на порту 8000.');
      }
    }
  };

  const handleReady = (collected) => {
    const inp = { object_type: objectType, ...collected };
    setUserInput(inp);
    setPhase('results');
    recalc(inp);
  };

  const restart = () => {
    setPhase('onboarding');
    setObjectType(null);
    setPreset(null);
    setResult(null);
    setSaveState('');
  };

  const currentStep = phase === 'onboarding' ? 0 : phase === 'intake' ? 1 : 2;

  const navigate = ({ id, target }) => {
    if (id === 'home') {
      restart();
      return;
    }
    if (id === 'process') {
      setObjectType(objectType || 'other');
      setPhase('intake');
      return;
    }
    if (id === 'library') {
      setPhase('catalog');
      return;
    }
    if (id === 'projects') {
      setPhase(user ? 'projects' : 'account');
      return;
    }
    if (id === 'admin') {
      setPhase(user?.role === 'ADMIN' ? 'admin' : 'account');
      return;
    }
    if (id === 'account') {
      setPhase('account');
      return;
    }
    if (phase !== 'results') {
      setObjectType(objectType || 'other');
      setPhase('intake');
      return;
    }
    window.requestAnimationFrame(() => document.getElementById(target || id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };

  const submitCommand = (event) => {
    event.preventDefault();
    const prompt = command.trim();
    if (!prompt) return;
    setObjectType('other');
    setPreset(null);
    setIntakePrompt(prompt);
    setPhase('intake');
  };

  const saveAnalysis = async () => {
    if (!user || !activeProject || !userInput || !result) return;
    const scenario = activeProject.scenarios.find((item) => item.slot === 'BASE');
    if (!scenario) return;
    const apiInput = Object.fromEntries(
      Object.entries(userInput).filter(([key]) => !key.startsWith('_'))
    );
    setSaveState('saving');
    try {
      const response = await fetch(`${API}/api/projects/${activeProject.id}/analysis-runs`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': readCsrfCookie() },
        body: JSON.stringify({ scenario_id: scenario.id, input: apiInput }),
      });
      if (!response.ok) throw new Error('Не удалось сохранить расчёт');
      setSaveState('saved');
    } catch (error) {
      setSaveState(error.message);
    }
  };

  return (
    <AppShell phase={phase} user={user} activeProject={activeProject} onNavigate={navigate} command={command} setCommand={setCommand} onCommand={submitCommand}>
      {!['results', 'catalog', 'account', 'projects', 'admin'].includes(phase) && <Stepper current={currentStep} />}
      <div className="phase-content">
        {phase === 'onboarding' ? (
          <OnboardingScreen
            onChoose={(t) => {
              setObjectType(t);
              setPreset(null);
              setPhase('intake');
            }}
            onPreset={(t, d) => {
              setObjectType(t);
              setPreset(d);
              setPhase('intake');
            }}
          />
        ) : phase === 'intake' ? (
          <IntakeScreen
            objectType={objectType}
            initialCollected={preset}
            initialPrompt={intakePrompt}
            onReady={handleReady}
          />
        ) : phase === 'catalog' ? (
          <CatalogScreen objectType={objectType || 'other'} onContinue={() => setPhase(result ? 'results' : 'onboarding')} />
        ) : phase === 'account' ? (
          <AuthScreen
            user={user}
            onAuthenticated={(nextUser) => { setUser(nextUser); setPhase('account'); }}
            onLoggedOut={() => { setUser(null); setActiveProject(null); restart(); }}
            onNavigate={(target) => setPhase(target)}
          />
        ) : phase === 'projects' ? (
          <ProjectsScreen
            onOpenProject={(project) => { setActiveProject(project); setPhase('onboarding'); }}
            onOpenRun={(run, project) => {
              setActiveProject(project);
              setUserInput(run.input_snapshot);
              setResult(run.result_snapshot);
              setPhase('results');
              setSaveState('saved');
            }}
          />
        ) : phase === 'admin' && user?.role === 'ADMIN' ? (
          <AdminUsersScreen />
        ) : (
          <>
            {user && activeProject && result && (
              <div className="save-run-bar">
                <span>Проект: <strong>{activeProject.name}</strong> · базовый сценарий</span>
                <button className="primary-action" disabled={saveState === 'saving' || saveState === 'saved'} onClick={saveAnalysis}>
                  {saveState === 'saving' ? 'Сохраняем…' : saveState === 'saved' ? 'Расчёт сохранён' : 'Сохранить AnalysisRun'}
                </button>
                {saveState && !['saving', 'saved'].includes(saveState) && <small>{saveState}</small>}
              </div>
            )}
            <ResultsPanel
              result={result}
              userInput={userInput}
              onRecalc={(input) => { setSaveState(''); recalc(input); }}
              onRestart={restart}
            />
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
