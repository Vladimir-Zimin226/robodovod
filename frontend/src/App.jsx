import { useRef, useState } from 'react';
import OnboardingScreen from './OnboardingScreen';
import IntakeScreen from './components/IntakeScreen';
import ResultsPanel from './components/ResultsPanel';
import CatalogScreen from './components/CatalogScreen';
import { AppShell } from './components/AppShell';

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
  const calculationSequence = useRef(0);

  const recalc = async (inp) => {
    calculationSequence.current += 1;
    const sequence = calculationSequence.current;
    const apiInput = Object.fromEntries(
      Object.entries(inp).filter(([key]) => !key.startsWith('_'))
    );
    try {
      const res = await fetch(`${API}/api/calculate`, {
        method: 'POST',
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

  return (
    <AppShell phase={phase} onNavigate={navigate} command={command} setCommand={setCommand} onCommand={submitCommand}>
      {phase !== 'results' && phase !== 'catalog' && <Stepper current={currentStep} />}
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
        ) : (
          <ResultsPanel
            result={result}
            userInput={userInput}
            onRecalc={recalc}
            onRestart={restart}
          />
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
