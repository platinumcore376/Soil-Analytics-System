'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { useLocale } from '@/lib/LocaleProvider';

export default function WelcomePage() {
  const { t, locale, setLocale } = useLocale();

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4, ease: 'easeInOut' }}
      className="relative min-h-screen overflow-hidden text-[#F3EFEA] bg-[#2D231B]"
    >
      {/* Background Image of Mountain Farming with a vibrant, bright filter */}
      <div 
        className="absolute inset-0 bg-cover bg-center pointer-events-none z-0 filter brightness-[0.7] contrast-[1.1]"
        style={{
          backgroundImage: `url('https://images.unsplash.com/photo-1500382017468-9049fed747ef?q=80&w=2000&auto=format&fit=crop')`
        }}
      />
      <div className="absolute inset-0 bg-black/30 pointer-events-none z-0" />

      {/* Navigation Header */}
      <header className="relative z-10 flex items-center justify-between px-6 py-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-2 font-bold tracking-wide text-lg text-[#F9F6F0]">
          <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-[#56823F] text-white text-sm shadow-md border border-[#74A859]">🌱</span>
          <span>Soil Health</span>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/signin"
            className="rounded-full bg-[#E2D4C7] border border-[#C5B4A4] px-5 py-2 text-sm font-medium text-[#3D2E23] hover:bg-[#F0E6DD] transition-all shadow-lg active:scale-95 leading-normal"
          >
            {t('signIn') || 'Sign In'}
          </Link>
          <Link
            href="/signin?mode=signup"
            className="rounded-full bg-[#56823F] border border-[#74A859] px-5 py-2 text-sm font-medium text-white hover:bg-[#466A32] transition-all shadow-lg active:scale-95 leading-normal"
          >
            Create Account
          </Link>
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as any)}
            aria-label={t('selectLanguage' as any)}
            className="rounded-full bg-[#E2D4C7] border border-[#C5B4A4] px-4 py-2 text-sm font-medium text-[#3D2E23] shadow-md outline-none cursor-pointer hover:bg-[#F0E6DD] leading-normal"
          >
            <option value="en" className="bg-[#E2D4C7] text-[#3D2E23]">English</option>
            <option value="hi" className="bg-[#E2D4C7] text-[#3D2E23]">हिन्दी</option>
            <option value="kn" className="bg-[#E2D4C7] text-[#3D2E23]">ಕನ್ನಡ</option>
            <option value="te" className="bg-[#E2D4C7] text-[#3D2E23]">తెలుగు</option>
          </select>
        </div>
      </header>

      {/* Hero Section */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 pt-12 pb-20 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="lg:col-span-7 space-y-8"
        >
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#3D2E23]/90 backdrop-blur-md border border-[#785F4A] text-xs font-semibold tracking-wider uppercase text-[#E5D4C0] shadow-sm">
            <span>🌿 Advanced Agronomy</span>
          </div>

          <h1 className="text-5xl lg:text-7xl font-bold tracking-tight leading-[1.08] text-[#FFF9F0]">
            Data-Driven <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#9BE27A] to-[#C3EDAE]">
              Soil Intelligence
            </span>
          </h1>

          <p className="text-lg text-[#E2D4C7] max-w-xl leading-relaxed font-light">
            We blend deep soil science with AI to deliver instant diagnostics, precise organic dosages, and localized crop recommendations right from your mobile device.
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <Link
              href="/signin?mode=signup"
              className="px-8 py-4 rounded-2xl bg-[#56823F] hover:bg-[#466A32] text-white font-semibold shadow-xl shadow-black/30 transition-all hover:scale-[1.02] active:scale-[0.98] border border-[#74A859]"
            >
              Get Started →
            </Link>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-3 gap-6 pt-8 border-t border-[#785F4A]/60 max-w-lg">
            <div>
              <p className="text-3xl font-bold text-[#FFF9F0]">11+</p>
              <p className="text-xs text-[#C5B4A4] uppercase tracking-wider mt-1">Nutrients Tracked</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-[#FFF9F0]">4</p>
              <p className="text-xs text-[#C5B4A4] uppercase tracking-wider mt-1">Local Languages</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-[#FFF9F0]">99%</p>
              <p className="text-xs text-[#C5B4A4] uppercase tracking-wider mt-1">Analysis Speed</p>
            </div>
          </div>
        </motion.div>

        {/* Right Feature Graphic Container */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, delay: 0.1, ease: 'easeOut' }}
          className="lg:col-span-5 flex justify-center"
        >
          <div className="relative w-full max-w-md aspect-square rounded-3xl bg-[#3D2E23]/95 backdrop-blur-xl border border-[#785F4A] p-8 shadow-2xl flex flex-col items-center justify-center text-center overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-b from-[#56823F]/25 via-transparent to-black/40 pointer-events-none" />
            <div className="absolute w-64 h-64 rounded-full border border-[#785F4A]/60 animate-[spin_60s_linear_infinite]" />
            <div className="absolute w-44 h-44 rounded-full border border-dashed border-[#967960]" />
            
            <div className="relative z-10 w-20 h-20 rounded-2xl bg-[#56823F]/60 border border-[#74A859] flex items-center justify-center shadow-inner mb-4">
              <span className="text-3xl">🍃</span>
            </div>
            <p className="relative z-10 text-sm font-semibold tracking-wide text-[#FFF9F0]">
              Biometric & Chemical Telemetry
            </p>
            <p className="relative z-10 text-xs text-[#E2D4C7] mt-1 max-w-[240px]">
              Real-time synchronization across edge sensors and cloud models.
            </p>
          </div>
        </motion.div>
      </main>

      {/* Feature Cards Grid */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 pb-24">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="rounded-3xl bg-[#3D2E23]/95 backdrop-blur-md border border-[#785F4A] p-8 shadow-xl hover:bg-[#544031] transition-all group">
            <div className="w-12 h-12 rounded-xl bg-[#56823F]/60 border border-[#74A859] flex items-center justify-center text-xl mb-5 group-hover:scale-110 transition-transform shadow-md">
              🧪
            </div>
            <h3 className="text-lg font-semibold text-[#FFF9F0] mb-2">Instant Analysis</h3>
            <p className="text-sm text-[#E2D4C7] leading-relaxed">
              Upload lab readings or scan your soil test card for immediate, actionable diagnostics.
            </p>
          </div>

          <div className="rounded-3xl bg-[#3D2E23]/95 backdrop-blur-md border border-[#785F4A] p-8 shadow-xl hover:bg-[#544031] transition-all group">
            <div className="w-12 h-12 rounded-xl bg-[#56823F]/60 border border-[#74A859] flex items-center justify-center text-xl mb-5 group-hover:scale-110 transition-transform shadow-md">
              🗣️
            </div>
            <h3 className="text-lg font-semibold text-[#FFF9F0] mb-2">Local Languages</h3>
            <p className="text-sm text-[#E2D4C7] leading-relaxed">
              Fully localized in Hindi, Kannada, Telugu, and English, featuring native voice read-aloud.
            </p>
          </div>

          <div className="rounded-3xl bg-[#3D2E23]/95 backdrop-blur-md border border-[#785F4A] p-8 shadow-xl hover:bg-[#544031] transition-all group">
            <div className="w-12 h-12 rounded-xl bg-[#56823F]/60 border border-[#74A859] flex items-center justify-center text-xl mb-5 group-hover:scale-110 transition-transform shadow-md">
              📊
            </div>
            <h3 className="text-lg font-semibold text-[#FFF9F0] mb-2">Actionable Advice</h3>
            <p className="text-sm text-[#E2D4C7] leading-relaxed">
              Receive precise fertilizer schedules and algorithmic crop suitability rankings.
            </p>
          </div>
        </div>
      </section>
    </motion.div>
  );
}