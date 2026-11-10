'use client';

/* Screen 2 — Choose capture mode: photo or lab readings.
 *
 * The selected plot is read from localStorage (set on Screen 1). If missing (e.g. direct URL
 * navigation), it bounces back to the plot list.
 */

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';
import Link from 'next/link';

import { analyze, createSoilRecord } from '@/lib/api';
import { useLocale } from '@/lib/LocaleProvider';
import { NUTRIENT_LABEL, NUTRIENT_UNIT } from '@/lib/status';
import type { TKey } from '@/lib/tkey';
import { useField } from '@/lib/useField';
import { Spinner } from '@/components/ui';

interface ParamDef {
  key: string;
  apiKey?: string;
  min: number;
  max: number;
  step: number;
  lo: number;
  hi: number;
  help: TKey;
}

const PARAMETERS: ParamDef[] = [
  { key: 'nitrogen', min: 0, max: 140, step: 1, lo: 20, hi: 100, help: 'helpNitrogen' },
  { key: 'phosphorus', min: 0, max: 80, step: 1, lo: 10, hi: 60, help: 'helpPhosphorus' },
  { key: 'potassium', min: 0, max: 205, step: 1, lo: 10, hi: 80, help: 'helpPotassium' },
  { key: 'ph', min: 3, max: 10, step: 0.1, lo: 5, hi: 8.5, help: 'helpPh' },
  { key: 'organic_matter', min: 0, max: 100, step: 0.1, lo: 0.1, hi: 5, help: 'helpOrganic' },
  { key: 'moisture', min: 0, max: 100, step: 1, lo: 5, hi: 60, help: 'helpMoisture' },
];

const MICRO_PARAMETERS: ParamDef[] = [
  { key: 'EC', apiKey: 'ec', min: 0, max: 5, step: 0.01, lo: 0.1, hi: 1, help: 'helpEc' },
  { key: 'S', apiKey: 's', min: 0, max: 100, step: 0.1, lo: 5, hi: 30, help: 'helpSulfur' },
  { key: 'Cu', apiKey: 'cu', min: 0, max: 50, step: 0.1, lo: 0.2, hi: 5, help: 'helpCopper' },
  { key: 'Fe', apiKey: 'fe', min: 0, max: 200, step: 0.1, lo: 2, hi: 30, help: 'helpIron' },
  { key: 'Mn', apiKey: 'mn', min: 0, max: 200, step: 0.1, lo: 1, hi: 20, help: 'helpManganese' },
  { key: 'Zn', apiKey: 'zn', min: 0, max: 100, step: 0.1, lo: 0.5, hi: 5, help: 'helpZinc' },
  { key: 'B', apiKey: 'b', min: 0, max: 50, step: 0.01, lo: 0.2, hi: 2, help: 'helpBoron' },
];

export default function ManualPage() {
  return (
    <Suspense fallback={<div className="fixed inset-0 w-screen h-screen bg-[#2D231B] flex items-center justify-center"><Spinner label="Loading..." /></div>}>
      <ManualForm />
    </Suspense>
  );
}

function ManualForm() {
  const { t, tError, locale, setLocale } = useLocale();
  const router = useRouter();
  const params = useSearchParams();
  const { field, ready } = useField();

  const imageId = params.get('image');

  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [showMicro, setShowMicro] = useState(false);

  const numeric = Object.fromEntries(
    Object.entries(values)
      .filter(([, v]) => v.trim() !== '')
      .map(([k, v]) => [k, Number(v)]),
  );
  const hasAny = Object.keys(numeric).length > 0;

  const ALL_PARAMS: ParamDef[] = [...PARAMETERS, ...MICRO_PARAMETERS];

  const problems: Record<string, { tone: 'error' | 'warn'; message: string }> = {};
  for (const p of ALL_PARAMS) {
    const raw = values[p.key];
    if (raw === undefined || raw.trim() === '') continue;

    const n = Number(raw);
    if (!Number.isFinite(n)) {
      problems[p.key] = { tone: 'error', message: t('outOfRange', { min: p.min, max: p.max }) };
    } else if (n < p.min || n > p.max) {
      problems[p.key] = { tone: 'error', message: t('outOfRange', { min: p.min, max: p.max }) };
    } else if (n < p.lo || n > p.hi) {
      problems[p.key] = { tone: 'warn', message: t('unusualValue') };
    }
  }
  const blocking = Object.values(problems).some((p) => p.tone === 'error');

  const submit = async () => {
    if (!field || !hasAny) return;
    setBusy(true);
    setError(null);

    try {
      const coreNumeric = Object.fromEntries(
        PARAMETERS.filter((p) => numeric[p.key] !== undefined).map((p) => [p.key, numeric[p.key]]),
      );

      const record = await createSoilRecord({
        field_id: field.fieldId,
        ...coreNumeric,
      });

      if (record?.id === undefined || record.id === null) {
        setSaved(true);
        setBusy(false);
        return;
      }

      const microInline = Object.fromEntries(
        MICRO_PARAMETERS.filter((p) => numeric[p.key] !== undefined).map((p) => [p.apiKey as string, numeric[p.key]]),
      );

      const result = await analyze({
        field_id: field.fieldId,
        soil_record_id: record.id,
        image_id: imageId ? Number(imageId) : undefined,
        explain: true,
        ...microInline,
      });

      if (result.analysis_id === null) {
        setError(t('somethingWrong'));
        setBusy(false);
        return;
      }
      router.push(`/results/${result.analysis_id}`);
    } catch (err) {
      setError(tError(err));
      setBusy(false);
    }
  };

  if (!ready || busy) {
    return (
      <div className="fixed inset-0 w-screen h-screen bg-[#2D231B] flex items-center justify-center text-[#FFF9F0]">
        <Spinner label={busy ? t('analysing') : t('loading')} />
      </div>
    );
  }

  if (!field) {
    router.replace('/');
    return null;
  }

  if (saved) {
    return (
      <div className="fixed inset-0 w-screen h-screen bg-[#2D231B] text-[#F3EFEA] flex flex-col items-center justify-center p-6">
        <div className="max-w-md w-full bg-[#362B22] border border-[#6E5441] p-8 rounded-3xl shadow-2xl space-y-6 text-center">
          <p aria-hidden className="text-5xl">✅</p>
          <div className="space-y-2">
            <p role="status" className="font-semibold text-lg text-[#8EC473]">{t('savedOffline')}</p>
            <p className="text-sm text-[#D1C2B4]">{t('analyseNeedsNet')}</p>
          </div>
          <Link
            href="/"
            className="flex items-center justify-center gap-2 w-full rounded-xl bg-[#4E3D2F] hover:bg-[#5C4837] text-[#FFF9F0] py-3.5 font-semibold border border-[#785F4A] transition-all"
          >
            <span>🌾 {t('chooseField')}</span>
          </Link>
        </div>
      </div>
    );
  }

  const renderField = (p: ParamDef) => {
    const { key, min, max, step, lo, hi, help } = p;
    const unitKey = NUTRIENT_UNIT[key];
    const problem = problems[key];
    return (
      <div key={key} className="space-y-1.5">
        <label className="block">
          <span className="mb-1.5 flex items-baseline justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#544031]">{t(NUTRIENT_LABEL[key])}</span>
            {unitKey && <span className="text-xs text-[#786352]">{t(unitKey)}</span>}
          </span>
          <input
            type="number"
            inputMode="decimal"
            min={min}
            max={max}
            step={step}
            value={values[key] ?? ''}
            onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
            aria-invalid={problem?.tone === 'error' || undefined}
            aria-describedby={`${key}-hint`}
            className={`w-full rounded-xl bg-white border-2 px-4 py-3 text-lg text-[#3D2E23] placeholder-[#967F6C] focus:outline-none transition-colors shadow-inner ${
              problem?.tone === 'error' 
                ? 'border-red-500 focus:border-red-500' 
                : 'border-[#C5B4A4] focus:border-[#56823F]'
            }`}
            placeholder="—"
          />
        </label>
        <p id={`${key}-hint`} className="text-xs text-[#786352]">
          {t('typicalRange', { min: lo, max: hi })}
        </p>
        {problem && (
          <p className={`text-xs font-medium ${problem.tone === 'error' ? 'text-red-600' : 'text-amber-700'}`}>
            {problem.message}
          </p>
        )}
        <details className="group text-xs">
          <summary className="cursor-pointer text-[#466A32] hover:underline font-medium list-none flex items-center gap-1">
            <span>{t('whatIsThis')}</span>
          </summary>
          <p className="mt-1 text-[#544031] leading-relaxed bg-white/60 p-2.5 rounded-lg border border-[#C5B4A4]">
            {t(help)}
          </p>
        </details>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 w-screen h-screen bg-[#2D231B] text-[#F3EFEA] overflow-y-auto flex flex-col">
      {/* Background Image matching Welcome and Signin */}
      <div 
        className="absolute inset-0 bg-cover bg-center pointer-events-none z-0 filter brightness-[0.7] contrast-[1.1] fixed"
        style={{
          backgroundImage: `url('https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?q=80&w=2000&auto=format&fit=crop')`
        }}
      />
      <div className="absolute inset-0 bg-black/30 pointer-events-none z-0 fixed" />

      {/* Top Header Bar */}
      <header className="relative z-10 flex items-center justify-between px-6 py-6 max-w-7xl mx-auto w-full">
        <div className="flex items-center gap-3">
          <Link href="/welcome" className="flex items-center gap-3 group">
            <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-[#56823F] text-white text-sm shadow-md border border-[#74A859] group-hover:scale-105 transition-transform">🌱</span>
            <span className="font-bold tracking-wide text-xl text-[#FFF9F0] drop-shadow-md">Soil Health</span>
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as any)}
            aria-label={t('selectLanguage' as any)}
            className="rounded-full bg-[#E2D4C7] border border-[#C5B4A4] px-4 py-2 text-sm font-medium text-[#3D2E23] shadow-md outline-none cursor-pointer hover:bg-[#F0E6DD]"
          >
            <option value="en" className="bg-[#E2D4C7] text-[#3D2E23]">English</option>
            <option value="hi" className="bg-[#E2D4C7] text-[#3D2E23]">हिन्दी</option>
            <option value="kn" className="bg-[#E2D4C7] text-[#3D2E23]">ಕನ್ನಡ</option>
            <option value="te" className="bg-[#E2D4C7] text-[#3D2E23]">తెలుగు</option>
          </select>
        </div>
      </header>

      {/* Main Container */}
      <main className="relative z-10 flex-1 max-w-4xl mx-auto w-full px-6 py-8 space-y-6">
        <Link
          href="/capture"
          className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-wider uppercase text-[#E2D4C7] hover:text-[#FFF9F0] transition-colors"
        >
          ← {t('back')}
        </Link>

        {/* Selected Field Badge (Kept in dark earth tone as requested) */}
        <div className="rounded-2xl bg-[#362B22]/90 backdrop-blur-md border border-[#6E5441] p-4 shadow-xl flex items-center gap-4">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#56823F]/30 border border-[#74A859]/50 text-base">
            🌾
          </span>
          <div className="flex-1">
            <span className="block text-xs font-semibold uppercase tracking-wider text-[#B8A494]">{field.farmName}</span>
            <span className="block font-bold text-lg text-[#FFF9F0]">{field.fieldName}</span>
            {imageId && (
              <span className="block text-xs text-[#9BE27A] mt-0.5">📷 {t('fromPhoto')} #{imageId}</span>
            )}
          </div>
        </div>

        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-[#FFF9F0]">{t('enterReadings')}</h1>
        </div>

        {/* Instructions Card (Kept in dark earth tone as requested) */}
        <div className="rounded-3xl bg-[#362B22]/90 backdrop-blur-xl border border-[#6E5441] p-6 shadow-2xl space-y-2">
          <p className="text-sm font-semibold text-[#FFF9F0]">📋 {t('whereToFind')}</p>
          <p className="text-sm font-medium text-[#E5C158]">
            ⚠ {t('indexNotKgHa')}
          </p>
        </div>

        {/* Core Parameters Card (Changed to #E2D4C7 cream) */}
        <div 
          className="rounded-3xl border border-[#C5B4A4] p-8 shadow-2xl text-[#3D2E23]"
          style={{ backgroundColor: '#E2D4C7' }}
        >
          <div className="space-y-6 sm:grid sm:grid-cols-2 sm:gap-x-8 sm:gap-y-6 sm:space-y-0">
            {PARAMETERS.map(renderField)}
          </div>
        </div>

        {/* Micro-Nutrients Accordion Card (Changed to #E2D4C7 cream) */}
        <div 
          className="rounded-3xl border border-[#C5B4A4] p-6 shadow-2xl text-[#3D2E23]"
          style={{ backgroundColor: '#E2D4C7' }}
        >
          <button
            type="button"
            onClick={() => setShowMicro((v) => !v)}
            className="flex w-full items-center justify-between text-left font-semibold text-[#3D2E23]"
          >
            <span>{t('nutrientLevels')}</span>
            <span className="text-xs text-[#544031]" aria-hidden>{showMicro ? '▲ Hide' : '▼ Show More'}</span>
          </button>
          {showMicro && (
            <div className="mt-6 pt-6 border-t border-[#C5B4A4] space-y-6 sm:grid sm:grid-cols-2 sm:gap-x-8 sm:gap-y-6 sm:space-y-0">
              {MICRO_PARAMETERS.map(renderField)}
            </div>
          )}
        </div>

        {/* Submission Warnings & Actions */}
        <div className="space-y-4 pt-4 pb-12">
          {!hasAny && <p className="text-center text-sm text-[#E2D4C7]">{t('atLeastOne')}</p>}
          {blocking && <p className="text-center text-sm text-[#FFB4AB]">{t('fixErrors')}</p>}
          {error && (
            <div className="rounded-2xl bg-[#5A2E2E]/80 border border-[#8C4E4E] p-4 text-[#FFB4AB] text-sm text-center">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={submit}
            disabled={!hasAny || blocking}
            className="w-full flex items-center justify-center gap-2 rounded-2xl bg-[#56823F] hover:bg-[#466A32] text-white py-4 font-semibold shadow-xl shadow-black/30 transition-all hover:scale-[1.01] active:scale-[0.98] border border-[#74A859] disabled:opacity-50"
          >
            <span>🔬 {t('analyse')}</span>
          </button>
        </div>
      </main>
    </div>
  );
}