/* Locale access for the whole app, backed by next-i18next.
 *
 * Spec requirement: "Implement next-i18next for static UI strings in Hindi and Kannada."
 * The catalogues live in `src/app/i18n/locales/<lng>/common.json`; `i18n.config.ts` wires
 * them up and `proxy.ts` resolves the active language.
 *
 * WHY THIS WRAPPER EXISTS RATHER THAN CALLING useT() DIRECTLY
 * i18next resolves keys at runtime and, on a miss, returns the key string itself. A typo or a
 * key missing from the Telugu catalogue would put the literal text `helpNitrogen` in front of
 * a farmer. `TKey` is derived from the English catalogue, so `t('helpNitrogn')` is a build
 * error — the guarantee the previous hand-rolled dictionary provided, kept.
 *
 * It also keeps `useLocale()` as the single call site used by ~9 components, so swapping the
 * implementation did not require touching each of them.
 */

import { useChangeLanguage, useT } from 'next-i18next/client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { LOCALES, errorKeyFor, type Locale } from './i18n';
import type { TKey } from './tkey';

const STORAGE_KEY = 'soil-health-locale';

interface LocaleContextValue {
  locale: Locale;
  setLocale: (next: Locale) => void;
  t: (key: TKey | 'selectLanguage', vars?: Record<string, string | number>) => string;
  /** Localised text for a caught error. See `errorKeyFor` in i18n.ts. */
  tError: (err: unknown) => string;
  /* False during the server render and the first client render, true afterwards. Controlled
   * form fields whose value depends on stored state must wait for this — a <select> is
   * restored by the browser before hydration, which otherwise mismatches. See AppChrome.
   */
  hydrated: boolean;
}

function isLocale(value: string | null | undefined): value is Locale {
  return !!value && (LOCALES as readonly string[]).includes(value);
}

/* No React context of its own: `I18nProvider` (mounted in the root layout) already provides
 * the i18next instance, and adding a second context would give two sources of truth for the
 * active language. This hook composes what the app needs on top of it.
 */
export function useLocale(): LocaleContextValue {
  const { t: rawT, i18n } = useT('common');
  const changeLanguage = useChangeLanguage();

  const [hydrated, setHydrated] = useState(false);

  const locale: Locale = isLocale(i18n.resolvedLanguage)
    ? (i18n.resolvedLanguage as Locale)
    : 'en';

  useEffect(() => {
    setHydrated(true);
  }, []);

  /* Keep <html lang> honest. The proxy sets it server-side from the cookie, but a language
   * switch is client-side only — without this a screen reader would keep announcing Telugu
   * text with English pronunciation. */
  useEffect(() => {
    if (document.documentElement.lang !== locale) {
      document.documentElement.lang = locale;
    }
  }, [locale]);

  const setLocale = useCallback(
    (next: Locale) => {
      /* localStorage as well as the cookie next-i18next sets. The service worker serves the
       * cached shell offline, where a cookie round-trip to the server cannot happen; this is
       * what a fully offline reload reads back. */
      try {
        window.localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* private-mode quota — the cookie still carries the choice */
      }
      document.documentElement.lang = next;
      changeLanguage(next);
    },
    [changeLanguage],
  );

  return useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale,
      // `rawT` is i18next's TFunction; the cast narrows the key type to our catalogue and
      // pins the return to string (i18next's overloads can widen it).
      t: (key, vars) => rawT(key as string, vars ?? {}) as unknown as string,
      tError: (err) => {
        const key = errorKeyFor(err);
        if (key) return rawT(key as string) as unknown as string;
        if (err instanceof Error && err.message) return err.message;
        return rawT('somethingWrong') as unknown as string;
      },
      hydrated,
    }),
    [locale, setLocale, rawT, hydrated],
  );
}

/* Applies the stored language preference once, at app startup.
 *
 * WHY THIS IS NEEDED AT ALL
 * next-i18next resolves the language server-side from a cookie. The service worker precached
 * `/` as HTML rendered in ONE language (English, whatever the first visit was), and offline it
 * serves that fixed shell for every navigation — the cookie never reaches a server. So an
 * offline reload boots in English even though the farmer chose Telugu. Server-rendered i18n
 * and an offline HTML cache pull against each other; this reconciles them on the client.
 *
 * Mounted exactly once, in AppChrome. It must NOT live inside `useLocale()` — that hook has
 * ~9 consumers, so the effect would fire once per consumer and several `changeLanguage` calls
 * would race.
 */
export function LocaleSync() {
  const changeLanguage = useChangeLanguage();
  const { i18n } = useT('common');
  const appliedRef = useRef(false);

  useEffect(() => {
    if (appliedRef.current) return;
    appliedRef.current = true;

    let stored: string | null = null;
    try {
      stored = window.localStorage.getItem(STORAGE_KEY);
    } catch {
      return; // private mode; the cookie remains the only source
    }
    if (isLocale(stored) && stored !== i18n.resolvedLanguage) {
      changeLanguage(stored);
      document.documentElement.lang = stored;
    }
  }, [changeLanguage, i18n]);

  return null;
}