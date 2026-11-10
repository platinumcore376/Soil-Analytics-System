'use client';

/* Screen 1 — Home. Pick a plot, or add one.
 *
 * The database models farm -> field, and it should: one farmer can work several plots, and
 * soil history must attach per plot. But that hierarchy is an implementation detail, and it
 * used to leak into the UI as two forms the farmer had to fill in order — five inputs before
 * they could photograph anything. Now one form creates both rows and the list is flat.
 *
 * The selected plot is kept in localStorage rather than a URL param: a farmer works one plot
 * at a time, and it survives the app being closed mid-flow.
 */

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';

import { createFarm, createField, listFarms, listFields } from '@/lib/api';
import { useLocale } from '@/lib/LocaleProvider';
import { FIELD_KEY } from '@/lib/useField';
import type { Farm, Field } from '@/lib/types';
import { Spinner } from '@/components/ui';

function CropIcon() {
  return (
    <svg aria-hidden width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-[#56823F]">
      <path
        d="M12 21V9M12 9c0-3.5-2-6-5-7 0 4 1.5 6.5 5 7ZM12 9c0-3.5 2-6 5-7 0 4-1.5 6.5-5 7Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M9 5l7 7-7 7"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function HomePage() {
  const { t, tError, locale, setLocale } = useLocale();
  const router = useRouter();

  const [farms, setFarms] = useState<Farm[]>([]);
  const [fields, setFields] = useState<Record<number, Field[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listFarms();
      setFarms(list);
      const entries = await Promise.all(
        list.map(async (farm) => [farm.id, await listFields(farm.id)] as const),
      );
      setFields(Object.fromEntries(entries));
    } catch (err) {
      setError(tError(err));
    } finally {
      setLoading(false);
    }
  }, [tError]);

  useEffect(() => {
    void load();
  }, [load]);

  const choose = (farm: Farm, field: Field) => {
    window.localStorage.setItem(
      FIELD_KEY,
      JSON.stringify({
        fieldId: field.id,
        fieldName: field.name,
        farmName: farm.name,
        areaHectares: field.area_hectares,
      }),
    );
    router.push('/capture');
  };

  if (loading) {
    return (
      <div className="fixed inset-0 w-screen h-screen flex items-center justify-center bg-[#2D231B] text-[#FFF9F0]">
        <Spinner label={t('loading')} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed inset-0 w-screen h-screen flex flex-col items-center justify-center bg-[#2D231B] p-6 text-center">
        <div className="max-w-md w-full bg-[#362B22] border border-[#6E5441] p-8 rounded-3xl shadow-2xl space-y-4">
          <p className="text-sm text-[#FFB4AB]">{error}</p>
          <button
            onClick={load}
            className="px-6 py-2.5 rounded-xl bg-[#56823F] text-white font-semibold hover:bg-[#466A32] transition-all"
          >
            {t('retry')}
          </button>
        </div>
      </div>
    );
  }

  const plots = farms.flatMap((farm) =>
    (fields[farm.id] ?? []).map((field) => ({ farm, field })),
  );
  const multipleFarms = farms.length > 1;

  return (
    <div className="fixed inset-0 w-screen h-screen bg-[#2D231B] text-[#F3EFEA] overflow-hidden flex flex-col">
      {/* Background Image */}
      <div 
        className="absolute inset-0 bg-cover bg-center pointer-events-none z-0 filter brightness-[0.7] contrast-[1.1]"
        style={{
          backgroundImage: `url('https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?q=80&w=2000&auto=format&fit=crop')`
        }}
      />
      <div className="absolute inset-0 bg-black/30 pointer-events-none z-0" />

      {/* Top Header Bar */}
      <header className="relative z-10 flex items-center justify-between px-6 py-6 max-w-7xl mx-auto w-full">
        <Link href="/welcome" className="flex items-center gap-3 group">
          <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-[#56823F] text-white text-sm shadow-md border border-[#74A859] group-hover:scale-105 transition-transform">🌱</span>
          <span className="font-bold tracking-wide text-xl text-[#FFF9F0] drop-shadow-md">Soil Health</span>
        </Link>
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
      <main className="relative z-10 flex-1 max-w-4xl mx-auto w-full px-6 py-8 overflow-y-auto space-y-6">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-[#FFF9F0]">
            {plots.length > 0 ? t('yourPlots') : t('addFirstPlot')}
          </h1>
          <p className="text-sm text-[#E2D4C7]">
            Select an active plot to begin soil diagnostics or add a new one.
          </p>
        </div>

        {plots.length === 0 && !adding && (
          <div 
            className="rounded-3xl backdrop-blur-xl border border-[#C5B4A4] p-8 shadow-2xl text-center space-y-4 text-[#3D2E23]"
            style={{ backgroundColor: 'rgba(226, 212, 199, 0.85)' }}
          >
            <p className="text-sm text-[#544031]">{t('noPlots')}</p>
            <button
              onClick={() => setAdding(true)}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#56823F] hover:bg-[#466A32] text-white py-3.5 font-semibold shadow-lg transition-all border border-[#74A859]"
            >
              <span>➕ {t('addFirstPlot')}</span>
            </button>
          </div>
        )}

        {plots.length > 0 && (
          <div className="space-y-3 sm:grid sm:grid-cols-2 sm:gap-4 sm:space-y-0">
            {plots.map(({ farm, field }) => (
              <button
                key={field.id}
                onClick={() => choose(farm, field)}
                className="flex w-full items-center gap-4 rounded-2xl border border-[#C5B4A4] backdrop-blur-md p-5 text-left hover:brightness-105 transition-all shadow-xl group"
                style={{ backgroundColor: '#E2D4C7' }}
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-[#56823F]/40 group-hover:scale-105 transition-transform bg-[#56823F]/15">
                  <CropIcon />
                </div>
                <div className="flex-1">
                  <span className="block font-semibold text-lg text-[#3D2E23]">{field.name}</span>
                  <span className="block text-xs text-[#786352] mt-0.5">
                    {Array.from(
                      new Set(
                        [
                          field.area_hectares !== null
                            ? `${field.area_hectares} ${t('unit_ha')}`
                            : null,
                          farm.location,
                          multipleFarms ? farm.name : null,
                        ].filter(Boolean) as string[],
                      ),
                    ).join(' · ')}
                  </span>
                </div>
                <span aria-hidden className="text-[#544031] group-hover:translate-x-1 transition-transform">
                  <ChevronRightIcon />
                </span>
              </button>
            ))}
          </div>
        )}

        {(adding || plots.length > 0) && (
          <AddPlotForm
            open={adding}
            existingFarm={farms[0] ?? null}
            onOpen={() => setAdding(true)}
            onCreated={async () => {
              setAdding(false);
              await load();
            }}
            labels={{
              add: plots.length === 0 ? t('addFirstPlot') : t('addPlot'),
              plotName: t('plotName'),
              plotNameHint: t('plotNameHint'),
              village: t('villageOptional'),
              area: t('areaOptional'),
              areaWhy: t('areaWhy'),
              save: t('save'),
              saving: t('savingPlot'),
              optional: t('optionalLabel'),
            }}
          />
        )}
      </main>
    </div>
  );
}

function AddPlotForm({
  open,
  existingFarm,
  onOpen,
  onCreated,
  labels,
}: {
  open: boolean;
  existingFarm: Farm | null;
  onOpen: () => void;
  onCreated: () => void;
  labels: Record<string, string>;
}) {
  const { tError } = useLocale();
  const [name, setName] = useState('');
  const [village, setVillage] = useState(existingFarm?.location ?? '');
  const [area, setArea] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <button
        onClick={onOpen}
        className="w-full flex items-center justify-center gap-2 rounded-2xl border border-dashed border-[#C5B4A4] backdrop-blur-md p-5 text-[#3D2E23] font-semibold transition-all shadow-md hover:bg-[rgba(226,212,199,0.85)]"
        style={{ backgroundColor: 'rgba(226, 212, 199, 0.65)' }}
      >
        <span>➕ {labels.add}</span>
      </button>
    );
  }

  const submit = async () => {
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const typed = village.trim();
      const sameVillage =
        !!existingFarm &&
        (typed === '' ||
          typed.toLowerCase() === (existingFarm.location ?? '').trim().toLowerCase());

      const farmId = sameVillage
        ? existingFarm.id
        : (
            await createFarm({
              name: typed || name.trim(),
              location: typed || undefined,
            })
          ).id;

      await createField({
        farm_id: farmId,
        name: name.trim(),
        area_hectares: area.trim() ? Number(area) : undefined,
      });
      onCreated();
    } catch (err) {
      setError(tError(err));
      setBusy(false);
    }
  };

  return (
    <div 
      className="rounded-3xl border border-[#C5B4A4] p-8 shadow-2xl space-y-4 text-[#3D2E23] backdrop-blur-xl"
      style={{ backgroundColor: 'rgba(226, 212, 199, 0.92)' }}
    >
      <div className="space-y-4">
        <TextField
          label={labels.plotName}
          hint={labels.plotNameHint}
          value={name}
          onChange={setName}
          required
        />
        <TextField
          label={labels.village}
          optionalLabel={labels.optional}
          value={village}
          onChange={setVillage}
        />
        <TextField
          label={labels.area}
          hint={labels.areaWhy}
          optionalLabel={labels.optional}
          value={area}
          onChange={setArea}
          numeric
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex gap-3 pt-2">
          <button
            onClick={submit}
            disabled={busy || !name.trim()}
            aria-label={busy ? labels.saving : labels.save}
            className="flex-1 rounded-xl bg-[#56823F] hover:bg-[#466A32] text-white py-3.5 font-semibold shadow-lg transition-all border border-[#74A859] disabled:opacity-50"
          >
            {busy ? labels.saving : labels.save}
          </button>
          <button
            onClick={() => onCreated()}
            className="rounded-xl bg-white/70 hover:bg-white text-[#3D2E23] px-6 py-3.5 font-medium border border-[#C5B4A4] transition-all"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  required,
  numeric,
  hint,
  optionalLabel,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  numeric?: boolean;
  hint?: string;
  optionalLabel?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-[#544031]">
          {label}
          {required && <span className="text-red-600"> *</span>}
        </span>
        {optionalLabel && !required && (
          <span className="text-[11px] text-[#786352]">{optionalLabel}</span>
        )}
      </span>
      <input
        type={numeric ? 'number' : 'text'}
        inputMode={numeric ? 'decimal' : 'text'}
        step={numeric ? '0.1' : undefined}
        min={numeric ? 0 : undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl bg-white border border-[#C5B4A4] px-4 py-3 text-sm text-[#3D2E23] placeholder-[#967F6C] focus:outline-none focus:border-[#56823F] transition-colors shadow-inner"
      />
      {hint && <span className="mt-1.5 block text-xs text-[#786352]">{hint}</span>}
    </label>
  );
}