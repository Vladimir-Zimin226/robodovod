import { useEffect, useState } from 'react';
import AppIcon from './components/AppIcon';

const API = import.meta.env.VITE_API_URL || '';

const CARDS = [
  { type: 'retail', title: 'Торговля', sub: 'Склад', icon: 'cube', preset: true },
  { type: 'airport', title: 'Логистика', sub: 'Аэропорт', icon: 'process', preset: true },
  { type: 'clinic', title: 'Соц. сфера', sub: 'Медучреждение', icon: 'home', preset: true },
  { type: 'other', title: 'Другое', sub: 'Производственный объект', icon: 'chart', preset: false },
];

export default function OnboardingScreen({ onChoose, onPreset }) {
  const [busy, setBusy] = useState(false);
  const [profileCounts, setProfileCounts] = useState({});

  useEffect(() => {
    fetch(`${API}/api/object-profiles`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((payload) => setProfileCounts(Object.fromEntries(
        payload.items.map((item) => [item.code, item.parameter_count]),
      )))
      .catch(() => {});
  }, []);

  const applyPreset = async (type) => {
    setBusy(true);
    try {
      const res = await fetch(`${API}/api/object-profiles/${type}/preset`);
      if (!res.ok) {
        alert('Не удалось загрузить пример. Проверьте, что бэкенд запущен.');
        return;
      }
      const preset = await res.json();
      onPreset(type, preset.normalized_input);
    } catch {
      alert('Бэкенд недоступен. Запустите uvicorn main:app на порту 8000.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="onboarding-screen min-h-full flex flex-col items-center justify-center p-8">
      <h1 className="text-3xl font-bold">РОБОДОВОД</h1>
      <p className="text-slate-500 mb-8 text-center">
        Предварительное ТЭО роботизации до внедрения
      </p>
      <div className="grid grid-cols-4 gap-4 max-w-5xl">
        {CARDS.map((c) => (
          <div
            key={c.type}
            className="bg-white rounded-2xl border p-6 text-center hover:shadow-lg transition"
          >
            <div className="onboarding-icon"><AppIcon name={c.icon} size={30} /></div>
            <div className="font-semibold">{c.title}</div>
            <div className="text-sm text-slate-500 mb-4">{c.sub}</div>
            <button
              onClick={() => onChoose(c.type)}
              className="w-full bg-blue-600 text-white rounded-xl py-2 text-sm mb-2"
            >
              Выбрать
            </button>
            {c.preset && (
              <>
                <button
                  disabled={busy}
                  onClick={() => applyPreset(c.type)}
                  className="w-full text-xs text-slate-500 underline disabled:opacity-50"
                >
                  {busy ? 'Загрузка…' : 'Заполнить официальным профилем'}
                </button>
                {profileCounts[c.type === 'retail' ? 'warehouse' : c.type === 'clinic' ? 'medical_facility' : c.type] && (
                  <div className="text-[10px] text-slate-400 mt-1">
                    {profileCounts[c.type === 'retail' ? 'warehouse' : c.type === 'clinic' ? 'medical_facility' : c.type]} параметров · с источниками
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
