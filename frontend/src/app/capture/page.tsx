'use client';

/* Screen 2 — Choose capture mode: photo or lab readings.
 *
 * The selected plot is read from localStorage (set on Screen 1). If missing (e.g. direct URL
 * navigation), it bounces back to the plot list.
 */

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { useLocale } from '@/lib/LocaleProvider';
import { FIELD_KEY } from '@/lib/useField';
import { Spinner } from '@/components/ui';

interface SelectedField {
  fieldId: number;
  fieldName: string;
  farmName: string;
  areaHectares: number | null;
}

function CameraIcon() {
  return (
    <svg aria-hidden width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-white">
      <path
        d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2v11z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="13" r="4" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function LabIcon() {
  return (
    <svg aria-hidden width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-white">
      <path
        d="M9 3h6M10 9l-5 8a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-8V3M10 13h4"
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

export default function CaptureChoicePage() {
  const router = useRouter();
  const { t, locale, setLocale } = useLocale();
  const [field, setField] = useState<SelectedField | null>(null);

  useEffect(() => {
    const raw = window.localStorage.getItem(FIELD_KEY);
    if (!raw) {
      router.replace('/');
      return;
    }
    try {
      setField(JSON.parse(raw) as SelectedField);
    } catch {
      router.replace('/');
    }
  }, [router]);

  if (!field) {
    return (
      <div className="fixed inset-0 w-screen h-screen bg-[#2D231B] flex items-center justify-center text-[#FFF9F0]">
        <Spinner label={t('loading')} />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 w-screen h-screen bg-[#2D231B] text-[#F3EFEA] overflow-y-auto flex flex-col">
      {/* Background Image matching welcome, signin, and home */}
      <div 
        className="absolute inset-0 bg-cover bg-center pointer-events-none z-0 filter brightness-[0.7] contrast-[1.1] fixed"
        style={{
          backgroundImage: `url('https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?q=80&w=2000&auto=format&fit=crop')`
        }}
      />
      <div className="absolute inset-0 bg-black/30 pointer-events-none z-0 fixed" />

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
      <main className="relative z-10 flex-1 max-w-4xl mx-auto w-full px-6 py-8 space-y-6">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-wider uppercase text-[#E2D4C7] hover:text-[#FFF9F0] transition-colors"
        >
          ← Back to plots
        </Link>

        {/* Selected Plot Badge Card (Kept in dark earth tone as requested) */}
        <div className="rounded-2xl bg-[#362B22]/90 backdrop-blur-md border border-[#6E5441] p-4 shadow-xl flex items-center gap-4 max-w-md">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#56823F]/30 border border-[#74A859]/50 text-base">
            🌾
          </span>
          <div>
            <span className="block text-xs font-semibold uppercase tracking-wider text-[#B8A494]">{field.farmName}</span>
            <span className="block font-bold text-lg text-[#FFF9F0]">{field.fieldName}</span>
          </div>
        </div>

        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-[#FFF9F0]">
            How do you want to check?
          </h1>
          <p className="text-sm text-[#E2D4C7]">
            Choose whether to take a live photo of your soil sample or enter physical lab report numbers.
          </p>
        </div>

        {/* Choice Cards in #E2D4C7 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 pb-12">
          <Link
            href="/capture/camera"
            className="flex items-center gap-4 rounded-3xl border border-[#C5B4A4] bg-[#E2D4C7] backdrop-blur-xl p-6 hover:bg-[#F0E6DD] transition-all shadow-xl group text-[#3D2E23]"
          >
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#56823F] text-white shadow-md border border-[#74A859] group-hover:scale-105 transition-transform">
              <CameraIcon />
            </div>
            <div className="flex-1">
              <span className="block font-bold text-lg text-[#3D2E23]">Take a soil photo</span>
              <span className="block text-xs text-[#786352] mt-0.5">Use your camera</span>
            </div>
            <span aria-hidden className="text-[#544031] group-hover:translate-x-1 transition-transform">
              <ChevronRightIcon />
            </span>
          </Link>

          <Link
            href="/capture/manual"
            className="flex items-center gap-4 rounded-3xl border border-[#C5B4A4] bg-[#E2D4C7] backdrop-blur-xl p-6 hover:bg-[#F0E6DD] transition-all shadow-xl group text-[#3D2E23]"
          >
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#56823F] text-white shadow-md border border-[#74A859] group-hover:scale-105 transition-transform">
              <LabIcon />
            </div>
            <div className="flex-1">
              <span className="block font-bold text-lg text-[#3D2E23]">Enter lab readings</span>
              <span className="block text-xs text-[#786352] mt-0.5">From your soil test card</span>
            </div>
            <span aria-hidden className="text-[#544031] group-hover:translate-x-1 transition-transform">
              <ChevronRightIcon />
            </span>
          </Link>
        </div>
      </main>
    </div>
  );
}