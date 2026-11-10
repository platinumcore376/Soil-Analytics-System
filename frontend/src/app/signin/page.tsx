'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { login, apiErrorKey } from '@/lib/api';
import { useLocale } from '@/lib/LocaleProvider';
import { ErrorNote, Spinner } from '@/components/ui';

export default function SignInPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t, locale, setLocale, tError } = useLocale();

  // Mode state to toggle between signing in and creating an account
  const initialMode = searchParams.get('mode') === 'signup' ? 'signup' : 'signin';
  const [mode, setMode] = useState<'signin' | 'signup'>(initialMode);

  // Sign In fields
  const [identifier, setIdentifier] = useState('');

  // Create Account fields
  const [mobile, setMobile] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');

  // Common password & UI states
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync mode if query parameters change
  useEffect(() => {
    const m = searchParams.get('mode');
    if (m === 'signup' || m === 'signin') {
      setMode(m);
    }
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    try {
      if (mode === 'signin') {
        // Use your app's native login wrapper to correctly set all session context/cookies
        await login(identifier.trim(), password);
      } else {
        // 1. Create the account via direct fetch
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
        const response = await fetch(`${baseUrl}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: username.trim() || 'New Farmer',
            phone: mobile.trim() || undefined,
            email: email.trim() || undefined,
            password: password,
          }),
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          const detail = Array.isArray(errData.detail) 
            ? errData.detail[0].msg 
            : errData.detail;
          throw new Error(detail || 'Registration failed');
        }

        // 2. Immediately log the new user in using the native wrapper to establish the session
        const loginId = mobile.trim() || email.trim() || username.trim();
        await login(loginId, password);
      }
      
      // Full page reload ensures Next.js Server Components and Middleware see the newly established session
      window.location.href = '/';
      
    } catch (err) {
      const code = apiErrorKey(err);
      setError(code ? tError(code) : (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  // Multilingual labels for account creation across locales
  const signUpLabels: Record<string, string> = {
    en: 'Create Account',
    hi: 'खाता बनाएं',
    kn: 'ಖಾತೆ ರಚಿಸಿ',
    te: 'ఖాతాను సృష్టించండి',
  };
  const signUpText = signUpLabels[locale] || 'Create Account';

  return (
    <div className="fixed inset-0 w-screen h-screen grid grid-cols-1 lg:grid-cols-12 bg-[#2D231B] text-[#F3EFEA] overflow-hidden">
      {/* Left Visual Pane with Mountain Farming and Crops */}
      <div className="hidden lg:flex lg:col-span-7 relative overflow-hidden flex-col justify-between p-16">
        <div 
          className="absolute inset-0 bg-cover bg-center filter brightness-[0.75] contrast-[1.05]"
          style={{
            backgroundImage: `url('https://images.unsplash.com/photo-1542332213-9b5a5a3fad35?q=80&w=2000&auto=format&fit=crop')`
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent" />

        {/* Top Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <Link href="/welcome" className="flex items-center gap-3 group">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#56823F] text-white text-lg shadow-md border border-[#74A859] group-hover:scale-105 transition-transform">🌱</span>
            <span className="font-bold tracking-wide text-xl text-[#FFF9F0] drop-shadow-md">Soil Health</span>
          </Link>
        </div>

        {/* Center Quote / Context */}
        <div className="relative z-10 space-y-4 max-w-lg my-auto">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-black/40 backdrop-blur-md border border-white/20 text-xs font-semibold tracking-wider uppercase text-[#E5D4C0]">
            <span>🌾 Field Telemetry Portal</span>
          </div>
          <h1 className="text-5xl font-bold tracking-tight text-[#FFF9F0] leading-tight drop-shadow-md">
            Precision Agronomy at your fingertips.
          </h1>
          <p className="text-base text-[#E2D4C7] leading-relaxed font-light drop-shadow-md">
            Monitor nutritional metrics, forecast soil trends, and protect crop yields with real-time AI modeling across edge nodes and cloud analytics.
          </p>
        </div>

        {/* Footer info */}
        <div className="relative z-10 text-xs text-[#D1C2B4] drop-shadow-sm">
          © 2026 Soil Health Intelligence. All rights reserved.
        </div>
      </div>

      {/* Right Interactive Form Pane */}
      <div className="col-span-1 lg:col-span-5 flex flex-col justify-between p-8 sm:p-12 lg:p-16 bg-[#362B22] h-full overflow-y-auto">
        {/* Top Controls: Language Switcher + Toggle Buttons */}
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2 lg:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#56823F] text-white text-sm shadow-md">🌱</span>
            <span className="font-bold text-base text-[#FFF9F0]">Soil Health</span>
          </div>
          <div className="flex items-center gap-3 ml-auto">
            <button
              type="button"
              onClick={() => setMode('signin')}
              className={`rounded-full px-5 py-2 text-sm font-medium transition-all shadow-md ${
                mode === 'signin'
                  ? 'bg-[#56823F] text-white border border-[#74A859]'
                  : 'bg-[#E2D4C7] text-[#3D2E23] border border-[#C5B4A4] hover:bg-[#F0E6DD]'
              }`}
            >
              {t('signIn')}
            </button>
            <button
              type="button"
              onClick={() => setMode('signup')}
              className={`rounded-full px-5 py-2 text-sm font-medium transition-all shadow-md ${
                mode === 'signup'
                  ? 'bg-[#56823F] text-white border border-[#74A859]'
                  : 'bg-[#E2D4C7] text-[#3D2E23] border border-[#C5B4A4] hover:bg-[#F0E6DD]'
              }`}
            >
              {signUpText}
            </button>
            <select
              value={locale}
              onChange={(e) => setLocale(e.target.value as any)}
              aria-label={t('selectLanguage')}
              className="rounded-full bg-[#E2D4C7] border border-[#C5B4A4] px-4 py-2 text-sm font-medium text-[#3D2E23] shadow-md outline-none cursor-pointer hover:bg-[#F0E6DD]"
            >
              <option value="en" className="bg-[#E2D4C7] text-[#3D2E23]">English</option>
              <option value="hi" className="bg-[#E2D4C7] text-[#3D2E23]">हिन्दी</option>
              <option value="kn" className="bg-[#E2D4C7] text-[#3D2E23]">ಕನ್ನಡ</option>
              <option value="te" className="bg-[#E2D4C7] text-[#3D2E23]">తెలుగు</option>
            </select>
          </div>
        </div>

        {/* Form Container */}
        <div className="w-full max-w-md mx-auto my-auto space-y-6 py-6">
          <div className="space-y-2">
            <h2 className="text-3xl font-bold tracking-tight text-[#FFF9F0]">
              {mode === 'signin' ? t('signIn') : signUpText}
            </h2>
            <p className="text-sm text-[#E2D4C7]">
              {mode === 'signin'
                ? 'Sign in to access your farm diagnostics and active fields.'
                : 'Enter your credentials below to create your account.'}
            </p>
          </div>

          <div 
            className="rounded-3xl border border-[#C5B4A4] p-8 shadow-2xl space-y-6 text-[#3D2E23]"
            style={{ backgroundColor: '#E2D4C7' }}
          >
            {error && <ErrorNote message={error} />}

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === 'signin' ? (
                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[#544031]">
                      Mobile number or email
                    </label>
                    <span className="text-[11px] text-[#786352]">Either one works</span>
                  </div>
                  <input
                    type="text"
                    required
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    className="w-full rounded-xl bg-white border border-[#C5B4A4] px-4 py-3 text-sm text-[#3D2E23] placeholder-[#967F6C] focus:outline-none focus:border-[#56823F] transition-colors shadow-inner"
                    placeholder="Enter phone or email"
                  />
                </div>
              ) : (
                <>
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[#544031] mb-1.5">
                      Mobile Number *
                    </label>
                    <input
                      type="tel"
                      required
                      value={mobile}
                      onChange={(e) => setMobile(e.target.value)}
                      className="w-full rounded-xl bg-white border border-[#C5B4A4] px-4 py-3 text-sm text-[#3D2E23] placeholder-[#967F6C] focus:outline-none focus:border-[#56823F] transition-colors shadow-inner"
                      placeholder="Enter mobile number"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between items-center mb-1.5">
                      <label className="block text-xs font-semibold uppercase tracking-wider text-[#544031]">
                        Email Address
                      </label>
                      <span className="text-[11px] text-[#786352]">Optional</span>
                    </div>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full rounded-xl bg-white border border-[#C5B4A4] px-4 py-3 text-sm text-[#3D2E23] placeholder-[#967F6C] focus:outline-none focus:border-[#56823F] transition-colors shadow-inner"
                      placeholder="farmer@example.com (optional)"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[#544031] mb-1.5">
                      Username *
                    </label>
                    <input
                      type="text"
                      required
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="w-full rounded-xl bg-white border border-[#C5B4A4] px-4 py-3 text-sm text-[#3D2E23] placeholder-[#967F6C] focus:outline-none focus:border-[#56823F] transition-colors shadow-inner"
                      placeholder="Choose a username"
                    />
                  </div>
                </>
              )}

              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-[#544031]">
                    Password *
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="text-xs font-medium text-[#466A32] hover:underline"
                  >
                    {showPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-xl bg-white border border-[#C5B4A4] px-4 py-3 text-sm text-[#3D2E23] placeholder-[#967F6C] focus:outline-none focus:border-[#56823F] transition-colors shadow-inner"
                  placeholder="••••••••••••"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#56823F] hover:bg-[#466A32] text-white py-3.5 font-semibold shadow-lg shadow-black/20 transition-all hover:scale-[1.01] active:scale-[0.98] border border-[#74A859] disabled:opacity-50 mt-2"
              >
                {loading ? (
                  <Spinner label={t('loading')} />
                ) : (
                  <span>{mode === 'signin' ? `→ ${t('signIn')}` : `→ ${signUpText}`}</span>
                )}
              </button>
            </form>
          </div>

          <div className="text-center pt-2">
            <button
              type="button"
              onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}
              className="text-sm font-medium text-[#E2D4C7] hover:text-[#FFF9F0] hover:underline transition-colors"
            >
              {mode === 'signin'
                ? "New here? Create an account →"
                : "Already have an account? Sign in →"}
            </button>
          </div>
        </div>

        {/* Bottom copyright spacing */}
        <div className="text-center text-xs text-[#967F6C] lg:hidden">
          © 2026 Soil Health Intelligence
        </div>
      </div>
    </div>
  );
}