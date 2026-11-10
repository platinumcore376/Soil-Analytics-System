'use client';                                                                                                                              
  
/* App shell: header with language switch, offline banner, service-worker registration.
 * Wraps every page so those three concerns live in one place.                
 */                                                                                        
  
import Link from 'next/link';                                                                                                             
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState, type ReactNode } from 'react';
import { motion } from 'framer-motion';

import { useAuth } from '@/lib/AuthProvider';
import { LOCALE_LABELS, LOCALES, type Locale } from '@/lib/i18n';
import { LocaleSync, useLocale } from '@/lib/LocaleProvider';

const PUBLIC_ROUTES = new Set(['/signin', '/welcome']);

export function AppChrome({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { locale, setLocale, t, hydrated } = useLocale();
  const { user, ready, signOut } = useAuth();
  const router = useRouter();
  const [online, setOnline] = useState(true);
  const [queueFlushed, setQueueFlushed] = useState(false);

  const isPublic = PUBLIC_ROUTES.has(pathname);

  // Route guard. Rendering the child first and redirecting after would flash a screen the
  // user is not entitled to see.
  useEffect(() => {
    if (ready && !user && !isPublic) router.replace('/welcome');
  }, [ready, user, isPublic, router]);

  // Register the service worker after mount. Without it there is no offline shell and no
  // write queue, so the app degrades to an ordinary website.
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/sw.js').catch(() => {
      /* Registration fails on insecure origins other than localhost. The app still works
         online; only offline support is lost. Not worth surfacing to a farmer. */
    });

    const onMessage = (event: MessageEvent) => {
      if (event.data?.type === 'queue-flushed') setQueueFlushed(true);
    };
    navigator.serviceWorker.addEventListener('message', onMessage);
    return () => navigator.serviceWorker.removeEventListener('message', onMessage);
  }, []);

  useEffect(() => {
    const update = () => {
      setOnline(navigator.onLine);
      if (navigator.onLine) {
        // Ask the worker to replay anything captured while offline.
        navigator.serviceWorker?.controller?.postMessage({ type: 'flush-queue' });
      }
    };
    update();
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
    };
  }, []);

  // Safe early return AFTER all hooks have executed
  if (pathname === '/welcome') {
    return <>{children}</>;
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="mx-auto flex min-h-dvh max-w-md flex-col sm:max-w-xl lg:max-w-3xl"
    >
      {/* Applies the stored language when the SW served an English cached shell. */}
      <LocaleSync />
      <header className="flex items-center justify-between gap-2 border-b border-black/10 bg-white px-4 py-3">
        {/* min-h-11: this is a real navigation target (goes home), but the globals.css rule
          * only covers a[role=button], so a plain <a> got no minimum height. */}
        <Link href="/" className="flex min-h-11 items-center gap-2 font-semibold">
          <img
            src="/icons/icon-192.png"
            alt="Soil Health Logo"
            className="h-7 w-7 rounded-lg object-contain shadow-xs"
          />
          <span>{t('appName')}</span>
        </Link>

        <div className="flex items-center gap-2">
          {user && (
            <button
              onClick={() => {
                // Confirm first: this is a single unlabelled glyph next to the language
                // switch, and signing out also clears the selected field.
                if (window.confirm(t('confirmSignOut'))) {
                  signOut();
                  router.replace('/welcome');
                }
              }}
              title={t('signOut')}
              aria-label={t('signOut')}
              data-compact
              className="rounded-xl border-2 border-black/15 px-3 text-lg"
            >
              <span aria-hidden>🚪</span>
            </button>
          )}
        {/* Rendered only after hydration. A <select> is restored by the browser on reload
          * before React attaches, so a server-rendered one carrying selected="" mismatches
          * as soon as the farmer has ever changed language. The placeholder keeps the
          * header from shifting when the real control replaces it. */}
        <label className="flex items-center gap-1 text-sm">
          <span className="sr-only">{t('languageLabel')}</span>
          {hydrated ? (
            <select
              value={locale}
              onChange={(e) => setLocale(e.target.value as Locale)}
              className="rounded-xl border-2 border-black/15 bg-white px-2 py-1 text-base"
            >
              {LOCALES.map((code) => (
                <option key={code} value={code}>
                  {LOCALE_LABELS[code]}
                </option>
              ))}
            </select>
          ) : (
            <span
              aria-hidden
              className="rounded-xl border-2 border-black/15 bg-white px-2 py-1 text-base opacity-0"
            >
              {LOCALE_LABELS.en}
            </span>
          )}
        </label>
        </div>
      </header>

      {!online && (
        <p
          role="status"
          className="bg-caution px-4 py-2 text-sm font-medium text-white"
        >
          {t('offline')}
        </p>
      )}

      {queueFlushed && online && (
        <p
          role="status"
          className="flex items-center justify-between gap-2 bg-ok px-4 py-2 text-sm font-medium text-white"
        >
          <span>✓ {t('queued')}</span>
          <button
            onClick={() => setQueueFlushed(false)}
            data-compact
            aria-label={t('cancel')}
            className="shrink-0 px-3 underline"
          >
            ✕
          </button>
        </p>
      )}

      <main className="flex-1 px-4 py-4 sm:px-6 sm:py-6">
        {/* Withhold protected content until the session is known. */}
        {!ready || (!user && !isPublic) ? null : children}
      </main>
    </motion.div>
  );
}